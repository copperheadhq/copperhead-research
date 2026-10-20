"""Stage II: a two-conductor transmission-line (MTL) model of every variant.

The coupled telegrapher equations for the pair, with per-unit-length
impedance and admittance matrices Z = R + jwL and Y = G + jwC (2 x 2), are

    dV/dx = -Z I,    dI/dx = -Y V,

and for a symmetric pair Z and Y are diagonalised by the even and odd modes.
The modal parameters are calibrated from the full-wave straight fixture A:
the odd mode from its Sdd (100 ohm) and the even mode from its Scc (25 ohm),
each by the Eisenstadt-Eo extraction of a uniform line's impedance and
propagation constant. So the MTL's coupled pair is the EM pair, launch
included; nothing about it is assumed.

A section where P leaves N (a tuning excursion, the outer trace's excess in
a bend) is modelled as uncoupled single lines with Hammerstad-Jensen
parameters. That is the model's stated blind spot: it has no coupling
between the folds of a meander, no coupling across the U, and no corner or
bend discontinuity. Comparing it with full wave isolates exactly those
effects.

Run: python scripts/mtl.py [level] -> build/sparams/mtl/<variant>.s4p
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import skrf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis  # noqa: E402
import analytic  # noqa: E402
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
C0 = 299792458.0
Z0 = 50.0


def extract_line(s11, s21, zref):
    """Characteristic impedance and gamma*l of a uniform line from its 2-port."""
    k = np.sqrt(((s11 ** 2 - s21 ** 2 + 1) ** 2 - (2 * s11) ** 2) / (2 * s21) ** 2)
    e1 = 1 / ((1 - s11 ** 2 + s21 ** 2) / (2 * s21) + k)
    e2 = 1 / ((1 - s11 ** 2 + s21 ** 2) / (2 * s21) - k)
    e = np.where(np.abs(e1) <= 1, e1, e2)          # the decaying root
    alpha_l = -np.log(np.abs(e))
    beta_l = -np.unwrap(np.angle(e))
    gl = alpha_l + 1j * beta_l
    zc = zref * np.sqrt(((1 + s11) ** 2 - s21 ** 2) / ((1 - s11) ** 2 - s21 ** 2))
    zc = np.where(zc.real < 0, -zc, zc)
    return zc, gl


def calibrate(level="medium"):
    a = analysis.load(level, "A")
    mm = analysis.mixed(a)
    f = mm.f
    L = geometry.build("A")["tuning"]["length"] * 1e-3
    zd, gld = extract_line(mm.s[:, 0, 0], mm.s[:, 1, 0], 100.0)
    zc, glc = extract_line(mm.s[:, 2, 2], mm.s[:, 3, 2], 25.0)
    # per line: odd-mode Z = Zdiff / 2, even-mode Z = 2 Zcomm
    return {"f": f, "z_odd": zd / 2, "g_odd": gld / L, "z_even": 2 * zc, "g_even": glc / L}


def single_line(f):
    p = geometry.params()
    eeff, z0 = analytic.hammerstad(p["pair"]["width"], p["stackup"]["dielectric_height"],
                                   p["stackup"]["epsilon_r"])
    tand = p["stackup"]["loss_tangent"] * p["stackup"]["loss_tangent_at"] / np.maximum(f, 1.0)
    er = p["stackup"]["epsilon_r"]
    # dielectric loss of a quasi-TEM line (filling factor form)
    q = (eeff - 1) / (er - 1)
    alpha_d = math.pi * f / C0 * er * q / math.sqrt(eeff) * tand
    beta = 2 * math.pi * f * math.sqrt(eeff) / C0
    return z0 + 0j, alpha_d + 1j * beta


T = np.array([[1, 1], [1, -1]]) / math.sqrt(2)   # even, odd -> P, N (orthonormal)


def chain_coupled(cal, length):
    """4x4 chain matrices [V(l); I(l)] = Phi [V(0); I(0)] of a coupled section."""
    n = cal["f"].size
    phi = np.zeros((n, 4, 4), complex)
    for k, (zm, gm) in enumerate(((cal["z_even"], cal["g_even"]), (cal["z_odd"], cal["g_odd"]))):
        ch, sh = np.cosh(gm * length), np.sinh(gm * length)
        m = np.zeros((n, 4, 4), complex)
        m[:, k, k] = ch
        m[:, k, 2 + k] = -zm * sh
        m[:, 2 + k, k] = -sh / zm
        m[:, 2 + k, 2 + k] = ch
        phi += m
    big = np.zeros((4, 4))
    big[:2, :2] = T
    big[2:, 2:] = T
    return big @ phi @ big.T


def chain_single(f, len_p, len_n):
    """Both conductors as uncoupled single lines of their own lengths."""
    z, g = single_line(f)
    n = f.size
    phi = np.zeros((n, 4, 4), complex)
    for k, ln in ((0, len_p), (1, len_n)):
        ch, sh = np.cosh(g * ln), np.sinh(g * ln)
        phi[:, k, k] = ch
        phi[:, k, 2 + k] = -z * sh
        phi[:, 2 + k, k] = -sh / z
        phi[:, 2 + k, 2 + k] = ch
    return phi


def to_s(phi):
    a, b, c, d = phi[:, :2, :2], phi[:, :2, 2:], phi[:, 2:, :2], phi[:, 2:, 2:]
    ci = np.linalg.inv(c)
    z = np.zeros_like(phi)
    z[:, :2, :2] = -ci @ d
    z[:, :2, 2:] = -ci
    z[:, 2:, :2] = b - a @ ci @ d
    z[:, 2:, 2:] = -a @ ci
    eye = np.eye(4) * Z0
    return (z - eye) @ np.linalg.inv(z + eye)


def topology(name: str):
    """The variant as a list of sections along the route: ("c", length) for
    coupled, ("u", len_P, len_N) for uncoupled, in metres."""
    p = geometry.params()
    g = geometry.build(name, p)
    L = p["fixture"]["leg_length"]
    R, s = p["fixture"]["bend_radius"], p["pair"]["pitch"]
    mm = 1e-3
    slices = 18

    def bend(radius):
        out = []
        for _ in range(slices):
            out.append(("c", math.pi * radius / slices * mm))
            out.append(("u", 0.0, math.pi * s / slices * mm))   # N's excess, spread along the bend
        return out

    if name in ("A", "S_ref"):
        return [("c", g["tuning"]["length"] * mm)]
    if name.startswith("B_R"):
        return [("c", L * mm)] + bend(g["tuning"]["bend_radius"]) + [("c", L * mm)]
    if name in ("B", "E"):
        lower = [("c", L * mm)]
        if name == "E":   # the excursion adds equal length to both traces; model it as coupled
            lower = [("c", (L + (g["length"]["P"] - geometry.build("B")["length"]["P"])) * mm)]
        return lower + bend(R) + [("c", L * mm)]
    t = g["tuning"]
    n, a, top, bottom, c = t["excursions"], t["amplitude"], t["top"], t["bottom"], t["chamfer"]
    bump_p = 2 * a + top - 6 * c + 4 * math.sqrt(2) * c
    bump_n = top + 2 * c
    sec = []
    for k in range(n):
        sec.append(("u", bump_p * mm, bump_n * mm))
        if k < n - 1:
            sec.append(("c", (bottom - 2 * c) * mm))
    x0, x1 = t["section_start"], t["section_end"]
    if name.startswith("S_"):
        total = g["tuning"]["length"]
        return [("c", x0 * mm)] + sec + [("c", (total - x1) * mm)]
    return [("c", x0 * mm)] + sec + [("c", (L - x1) * mm)] + bend(R) + [("c", L * mm)]


def model(name: str, cal) -> skrf.Network:
    f = cal["f"]
    phi = np.broadcast_to(np.eye(4, dtype=complex), (f.size, 4, 4)).copy()
    for sec in topology(name):
        step = chain_coupled(cal, sec[1]) if sec[0] == "c" else chain_single(f, sec[1], sec[2])
        phi = step @ phi
    s = np.zeros_like(phi)
    ok = f > 0
    s[ok] = to_s(phi[ok])
    s[~ok] = s[ok][0]
    ntw = skrf.Network(frequency=skrf.Frequency.from_f(f, unit="Hz"), s=s, z0=Z0, name=name)
    return ntw


def main(level="medium", names=None):
    cal = calibrate(level)
    out = ROOT / "build" / "sparams" / "mtl"
    out.mkdir(parents=True, exist_ok=True)
    names = names or ["A", "B", "C", "C_far", "D", "E", "F", "C_cal", "D_cal", "F_cal", "S_ref", "S_loose",
                      "S_tight", "B_R075", "B_R3"]
    sel = (cal["f"] > 0.5e9) & (cal["f"] < 10e9)
    info = {"eps_odd": float(np.mean((cal["g_odd"].imag[sel] * C0 / (2 * np.pi * cal["f"][sel])) ** 2)),
            "eps_even": float(np.mean((cal["g_even"].imag[sel] * C0 / (2 * np.pi * cal["f"][sel])) ** 2)),
            "z_odd": float(np.mean(cal["z_odd"].real[sel])), "z_even": float(np.mean(cal["z_even"].real[sel]))}
    (out / "calibration.json").write_text(json.dumps(info, indent=1))
    print("calibration", info)
    for nm in names:
        ntw = model(nm, cal)
        ntw.comments = f"MTL model of {nm}, calibrated on full-wave A ({level})"
        ntw.write_touchstone(str(out / nm), form="ri", skrf_comment=False)


if __name__ == "__main__":
    main(*(sys.argv[1:2] or []))

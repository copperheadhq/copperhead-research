"""Mixed-mode and time-domain analysis of the extracted four-ports.

Mixed mode: scikit-rf's se2gmm(p=2) on single-ended ports ordered
P_near, N_near, P_far, N_far gives d_near, d_far, c_near, c_far, so
Sdd11 = S[0,0], Sdd21 = S[1,0], Scd21 = S[3,0], Scc21 = S[3,2]; the
reference impedances are its defaults, 100 ohm differential and 25 ohm common.

Time domain: a differential step of 1 V open-circuit (+1 V on port 1 and
-1 V on port 2, each behind 50 ohm, so 1 V differential into a matched pair)
with a Gaussian edge of 10-90 % rise time t_r; the far end is two 50-ohm
loads to the return plane (100 ohm differential, 25 ohm common). Every
waveform is the superposition the four-port gives, computed in the frequency
domain and taken to time by an inverse FFT; nothing is fitted.

Skew is t50(N falling) - t50(P rising) at the far end: positive means P,
the inner trace, arrives first.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import skrf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
C0 = 299792458.0
Z0 = 50.0
DT = 0.25e-12          # time step of the reconstructed waveforms


def load(level: str, variant: str) -> skrf.Network:
    return skrf.Network(str(ROOT / "build" / "sparams" / level / f"{variant}.s4p"))


def mixed(ntw: skrf.Network) -> skrf.Network:
    mm = ntw.copy()
    mm.se2gmm(p=2)
    return mm


# ------------------------------------------------------------- time domain

def _edge(f, rise, delay):
    sigma = rise / (2 * 1.2815515655446004)
    return np.exp(-0.5 * (2 * np.pi * f * sigma) ** 2) * np.exp(-2j * np.pi * f * delay)


def step(f, transfer, rise, delay):
    """The response of `transfer` to a unit step with a Gaussian edge."""
    df = f[1] - f[0]
    n = int(round(1 / (df * DT)))
    spec = np.zeros(n // 2 + 1, complex)
    spec[: f.size] = transfer * _edge(f, rise, delay)
    impulse = np.fft.irfft(spec, n=n) * n * df
    t = np.arange(n) * DT
    return t, np.cumsum(impulse) * DT


def waveforms(ntw: skrf.Network, rise: float, window=3e-9):
    """Far- and near-end voltages for the differential step."""
    f, s = ntw.f, ntw.s
    delay = 6 * rise / 2.563 + 20e-12
    # incident waves of the two sources: a = +-V/(2 sqrt Z0) with V = 1 V
    out = {}
    for name, k in (("p_far", 2), ("n_far", 3), ("p_near", 0), ("n_near", 1)):
        h = 0.5 * (s[:, k, 0] - s[:, k, 1])
        if name == "p_near":
            h = h + 0.5
        elif name == "n_near":
            h = h - 0.5
        t, v = step(f, h, rise, delay)
        out[name] = v
    keep = t < window + delay
    out = {k: v[keep] for k, v in out.items()}
    out["t"] = t[keep] - delay
    out["vd_far"] = out["p_far"] - out["n_far"]
    out["vc_far"] = 0.5 * (out["p_far"] + out["n_far"])
    out["vd_near"] = out["p_near"] - out["n_near"]
    return out


def crossing(t, v, level, rising=True):
    """First time v crosses `level`, by linear interpolation."""
    x = v if rising else -v
    lv = level if rising else -level
    idx = np.nonzero((x[:-1] < lv) & (x[1:] >= lv))[0]
    if idx.size == 0:
        return math.nan
    i = idx[0]
    return t[i] + (lv - x[i]) * (t[i + 1] - t[i]) / (x[i + 1] - x[i])


def timing(w):
    t = w["t"]
    end = slice(int(0.9 * t.size), None)
    p_final = w["p_far"][end].mean()
    n_final = w["n_far"][end].mean()
    d_final = w["vd_far"][end].mean()
    tp = crossing(t, w["p_far"], 0.5 * p_final, rising=True)
    tn = crossing(t, w["n_far"], 0.5 * n_final, rising=False)
    td = crossing(t, w["vd_far"], 0.5 * d_final, rising=True)
    vc = w["vc_far"]
    return {"t50_P": tp, "t50_N": tn, "skew": tn - tp, "t50_d": td,
            "vc_pp": float(vc.max() - vc.min()), "vc_pp_rel": float((vc.max() - vc.min()) / d_final),
            "vd_final": float(d_final)}


def tdr(mm: skrf.Network, rise: float, mode="dd", window=1.5e-9):
    """Step TDR from Sdd11 (or Scc11): the reflected step rho(t), and the
    impedance 100 (or 25) * (1 + rho) / (1 - rho) it implies. Times are
    round-trip from the launch reference plane."""
    k, zref = (0, 100.0) if mode == "dd" else (2, 25.0)
    delay = 6 * rise / 2.563 + 20e-12
    t, rho = step(mm.f, mm.s[:, k, k], rise, delay)
    keep = t < window + delay
    t, rho = t[keep] - delay, rho[keep]
    return t, rho, zref * (1 + rho) / (1 - rho)


# ------------------------------------------------------------- frequency domain

def band_metrics(mm: skrf.Network, bands):
    f = mm.f
    out = {}
    for lo, hi in bands:
        sel = (f >= lo) & (f <= hi)
        key = f"{lo / 1e9:g}-{hi / 1e9:g}GHz"
        db = lambda x: 20 * np.log10(np.abs(x[sel]))  # noqa: E731
        out[key] = {
            "Sdd11_max_dB": float(db(mm.s[:, 0, 0]).max()),
            "Sdd21_min_dB": float(db(mm.s[:, 1, 0]).min()),
            "Scd21_max_dB": float(db(mm.s[:, 3, 0]).max()),
            "Scd21_mean_dB": float(20 * np.log10(np.sqrt(np.mean(np.abs(mm.s[sel, 3, 0]) ** 2)))),
            "Scd11_max_dB": float(db(mm.s[:, 2, 0]).max()),
        }
    return out


def group_delay(f, s21, lo, hi):
    """Least-squares slope of the unwrapped phase over [lo, hi]."""
    sel = (f >= lo) & (f <= hi)
    ph = np.unwrap(np.angle(s21))[sel]
    slope = np.polyfit(2 * np.pi * f[sel], ph, 1)[0]
    return -slope


def modal(level="medium", lo=0.5e9, hi=10e9):
    """Odd- and even-mode velocities from the straight reference A."""
    a = load(level, "A")
    mm = mixed(a)
    L = geometry.build("A")["tuning"]["length"] * 1e-3
    tdd = group_delay(mm.f, mm.s[:, 1, 0], lo, hi)
    tcc = group_delay(mm.f, mm.s[:, 3, 2], lo, hi)
    return {"length_m": L, "tau_dd": tdd, "tau_cc": tcc,
            "eps_odd": (C0 * tdd / L) ** 2, "eps_even": (C0 * tcc / L) ** 2,
            "v_odd": L / tdd, "v_even": L / tcc}


def summarize(level: str, variants, rises, bands):
    rows = {}
    for v in variants:
        ntw = load(level, v)
        mm = mixed(ntw)
        g = geometry.build(v)
        row = {"geometry": {"P_len": g["length"]["P"], "N_len": g["length"]["N"],
                            "N_minus_P": g["length"]["N_minus_P"], "bbox_mm2": g["area_bbox"],
                            "tuning": g["tuning"]},
               "bands": band_metrics(mm, bands), "timing": {}}
        for r in rises:
            row["timing"][f"{r * 1e12:g}ps"] = timing(waveforms(ntw, r))
        f = ntw.f
        row["phase_delay_ps"] = {
            "S31_P": group_delay(f, ntw.s[:, 2, 0], 0.5e9, 10e9) * 1e12,
            "S42_N": group_delay(f, ntw.s[:, 3, 1], 0.5e9, 10e9) * 1e12,
            "Sdd21": group_delay(f, mm.s[:, 1, 0], 0.5e9, 10e9) * 1e12,
        }
        rows[v] = row
    return rows


if __name__ == "__main__":
    level = sys.argv[1] if len(sys.argv) > 1 else "medium"
    variants = sys.argv[2:] or [v for v in geometry.VARIANTS]
    p = geometry.params()
    out = summarize(level, variants, p["analysis"]["rise_times"], p["analysis"]["bands"])
    dest = ROOT / "build" / "results"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"summary_{level}.json").write_text(json.dumps(out, indent=1, default=float))
    for v, row in out.items():
        t = row["timing"]["50ps"]
        print(f"{v:6s} skew50={t['skew'] * 1e12:+7.2f} ps  vc_pp={t['vc_pp_rel'] * 100:5.2f}%  "
              f"Scd21max(0.1-20)={row['bands']['0.1-20GHz']['Scd21_max_dB']:6.1f} dB  "
              f"Sdd11max={row['bands']['0.1-20GHz']['Sdd11_max_dB']:6.1f} dB")


# ------------------------------------------------------------- eye, area, Pareto

def prbs7(n_bits=254):
    """PRBS7 (x^7 + x^6 + 1), starting from all ones."""
    state, out = 0x7F, []
    for _ in range(n_bits):
        bit = ((state >> 6) ^ (state >> 5)) & 1
        state = ((state << 1) | bit) & 0x7F
        out.append(bit)
    return out


def eye(ntw: skrf.Network, bit_rate: float, rise: float, n_bits=254, skip=16):
    """A PRBS7 NRZ stream (0/1 V open-circuit differential, Gaussian edges)
    built from the step response by superposition. Returns the differential
    eye height (best sampling phase), eye width (phases where the eye is open
    by more than 10 % of the swing) and the far-end common-mode peak-to-peak."""
    w = waveforms(ntw, rise, window=(n_bits + 8) / bit_rate)
    t, vd, vc = w["t"], w["vd_far"], w["vc_far"]
    dt = t[1] - t[0]
    ui = 1 / bit_rate
    bits = prbs7(n_bits)
    shift = lambda v, k: np.concatenate([np.zeros(k), v[: v.size - k]]) if k > 0 else v  # noqa: E731
    d = np.zeros_like(vd)
    c = np.zeros_like(vc)
    prev = 0
    for k, b in enumerate(bits):
        if b != prev:
            n = int(round(k * ui / dt))
            sign = 1 if b > prev else -1
            d += sign * shift(vd, n)
            c += sign * shift(vc, n)
            prev = b
    per = int(round(ui / dt))
    # bit k reaches the far end over [k UI + td, (k+1) UI + td), td the
    # step's own 50 % delay
    td = timing(w)["t50_d"]
    swing = vd[int(0.9 * vd.size):].mean()
    heights = []
    for ph in range(per):
        ones, zeros = [], []
        for k in range(skip, len(bits) - 2):
            i = int(round((k * ui + td + ph * dt - t[0]) / dt))
            if 0 <= i < d.size:
                (ones if bits[k] else zeros).append(d[i])
        heights.append(min(ones) - max(zeros))
    heights = np.array(heights)
    open_ = heights > 0.1 * swing
    start = int(round((skip * ui + td - t[0]) / dt))
    return {"bit_rate": bit_rate, "rise": rise, "eye_height": float(np.nanmax(heights)),
            "eye_height_rel": float(np.nanmax(heights) / swing),
            "eye_width": float(open_.sum() * dt), "eye_width_ui": float(open_.sum() * dt / ui),
            "vc_pp": float(c[start:].max() - c[start:].min()), "vc_pp_rel": float((c[start:].max() - c[start:].min()) / swing),
            "t": t, "vd": d, "vc": c, "ui": ui, "start": start * dt}


def area_mm2(g: dict) -> float:
    """Board area the tuning occupies beyond the untuned route: the section's
    length times its excursion (centreline amplitude)."""
    tun = g["tuning"]
    if "section_start" not in tun or g["name"].startswith("S_"):
        return 0.0
    return (tun["section_end"] - tun["section_start"]) * tun["amplitude"]


def pareto(points: dict, keys) -> list:
    """Names whose objective vectors no other point dominates (all minimised)."""
    names = list(points)
    keep = []
    for a in names:
        dominated = any(all(points[b][k] <= points[a][k] for k in keys) and
                        any(points[b][k] < points[a][k] for k in keys) for b in names if b != a)
        if not dominated:
            keep.append(a)
    return keep

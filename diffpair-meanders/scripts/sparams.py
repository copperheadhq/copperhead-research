"""Four-port S-parameters from the four runs of one variant.

Each run excites one port; the other three are passive 50-ohm loads. For
port k the probes give voltage u_k(t) (signal copper minus return plane) and
current i_k(t) (flowing from the port into the structure). Their transforms
give the power waves a_k = (u_k + Z i_k) / (2 sqrt Z) and
b_k = (u_k - Z i_k) / (2 sqrt Z), and S[i, j] = b_i / a_j for the run that
excites j. Each probe is transformed on its own time axis (openEMS samples
current half a timestep after voltage).

Run: python scripts/sparams.py <level> <variant> [...]
     -> build/sparams/<level>/<variant>.s4p and <variant>.checks.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import skrf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DF = 10e6
F_MAX = 30e9
FREQ = np.arange(0.0, F_MAX + DF / 2, DF)
Z0 = 50.0


def read_probe(path: Path):
    data = np.loadtxt(path, comments="%")
    return data[:, 0], data[:, 1]


def transform(t, v, f=FREQ):
    """dt * sum v(t) exp(-j 2 pi f t), on the probe's own time axis."""
    dt = t[1] - t[0]
    out = np.empty(f.size, complex)
    for lo in range(0, f.size, 500):
        fs = f[lo:lo + 500, None]
        out[lo:lo + 500] = dt * (np.exp(-2j * np.pi * fs * t[None, :]) @ v)
    return out


def run_dir(level, variant, k):
    return ROOT / "runs" / level / variant / f"p{k}"


def extract(level: str, variant: str):
    s = np.zeros((FREQ.size, 4, 4), complex)
    checks = {"variant": variant, "level": level, "truncation_dB": {}, "timesteps": {}, "final_energy_dB": {}}
    for j in range(1, 5):
        d = run_dir(level, variant, j)
        prov = json.loads((d / "provenance.json").read_text())
        checks["timesteps"][j] = prov.get("timesteps")
        checks["final_energy_dB"][j] = prov.get("final_energy_dB")
        u, i, peak, tail = {}, {}, 0.0, 0.0
        for k in range(1, 5):
            tu, vu = read_probe(d / f"port_ut_{k}")
            ti, vi = read_probe(d / f"port_it_{k}")
            u[k], i[k] = transform(tu, vu), transform(ti, vi)
            n = max(1, len(vu) // 20)
            peak = max(peak, np.abs(vu).max())
            tail = max(tail, np.abs(vu[-n:]).max())
        # how far every port voltage had fallen over the record's last 5 %
        checks["truncation_dB"][j] = float(20 * np.log10(max(tail, 1e-300) / peak))
        a = {k: (u[k] + Z0 * i[k]) / (2 * np.sqrt(Z0)) for k in u}
        b = {k: (u[k] - Z0 * i[k]) / (2 * np.sqrt(Z0)) for k in u}
        for k in range(1, 5):
            s[:, k - 1, j - 1] = b[k] / a[j]
    ntw = skrf.Network(frequency=skrf.Frequency.from_f(FREQ, unit="Hz"), s=s, z0=Z0, name=variant)
    ntw.port_names = ["P_near", "N_near", "P_far", "N_far"]
    band = (FREQ > 0) & (FREQ <= F_MAX)
    recip = np.abs(s - np.transpose(s, (0, 2, 1)))[band].max()
    sv = np.linalg.svd(s[band], compute_uv=False).max(axis=1)
    checks.update({
        "reciprocity_max_abs_diff": float(recip),
        "passivity_max_singular_value": float(sv.max()),
        "passivity_worst_frequency_Hz": float(FREQ[band][sv.argmax()]),
        "power_balance_min": float((1 - (np.abs(s[band]) ** 2).sum(axis=1)).min()),
    })
    return ntw, checks


def main(argv):
    level, variants = argv[0], argv[1:]
    out = ROOT / "build" / "sparams" / level
    out.mkdir(parents=True, exist_ok=True)
    for v in variants:
        ntw, checks = extract(level, v)
        ntw.comments = (f"diffpair-meanders {v} ({geometry.VARIANTS[v]}), mesh {level}\n"
                        "ports 1 P_near 2 N_near 3 P_far 4 N_far; openEMS FDTD, lumped 50 ohm ports")
        ntw.write_touchstone(str(out / v), form="ri", skrf_comment=False)
        (out / f"{v}.checks.json").write_text(json.dumps(checks, indent=1))
        print(v, json.dumps({k: checks[k] for k in ("reciprocity_max_abs_diff", "passivity_max_singular_value",
                                                    "power_balance_min", "truncation_dB")}))


if __name__ == "__main__":
    main(sys.argv[1:])

"""Mesh convergence of the skew: Richardson extrapolation and Roache's grid
convergence index (GCI) over the coarse, medium and fine meshes.

For a quantity f on meshes of finest cell h1 < h2 < h3 (ratio r ~ 1.5):
  observed order  p = ln(|f3 - f2| / |f2 - f1|) / ln r
  extrapolated    f* = f1 + (f1 - f2) / (r^p - 1)
  GCI (fine)      = Fs |f1 - f2| / (r^q - 1),  Fs = 1.25, q = min(p, 2)
When the three do not converge monotonically, p is not defined; the bound is
then Fs = 3 times the largest difference between any two meshes.

Run: python scripts/convergence.py -> build/results/convergence.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis  # noqa: E402
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEVELS = ("fine", "medium", "coarse")
FORMAL_ORDER = 2.0


def gci(f1, f2, f3, r):
    e21, e32 = f2 - f1, f3 - f2
    if e21 == 0:
        return {"monotonic": True, "order": math.inf, "extrapolated": f1, "gci": 0.0}
    ratio = e32 / e21
    if ratio > 0 and abs(ratio) != 1:
        p = math.log(abs(ratio)) / math.log(r)
        if p > 0:
            # an observed order above the scheme's formal order (2 for Yee
            # FDTD) is not trusted: the bound uses the smaller of the two
            q = min(p, FORMAL_ORDER)
            ext = f1 + (f1 - f2) / (r ** q - 1)
            return {"monotonic": True, "order": p, "extrapolated": ext, "gci": 1.25 * abs(e21) / (r ** q - 1)}
    spread = max(f1, f2, f3) - min(f1, f2, f3)
    return {"monotonic": False, "order": None, "extrapolated": None, "gci": 3.0 * spread}


def main(variants=("B", "C")):
    p = geometry.params()
    cells = p["simulation"]["levels"]
    h = [cells[l] for l in LEVELS]
    r = (h[1] / h[0] * h[2] / h[1]) ** 0.5
    rises = p["analysis"]["rise_times"]
    out = {"cells_mm": dict(zip(LEVELS, h)), "ratio": r, "variants": {}}
    for v in variants:
        rows = {}
        for lvl in LEVELS:
            ntw = analysis.load(lvl, v)
            mm = analysis.mixed(ntw)
            t = {f"{x * 1e12:g}ps": analysis.timing(analysis.waveforms(ntw, x)) for x in rises}
            band = analysis.band_metrics(mm, p["analysis"]["bands"])
            rows[lvl] = {"skew_ps": {k: val["skew"] * 1e12 for k, val in t.items()},
                         "t50_d_ps": {k: val["t50_d"] * 1e12 for k, val in t.items()},
                         "vc_pp_pct": {k: val["vc_pp_rel"] * 100 for k, val in t.items()},
                         "Scd21_max_dB": band["0.1-20GHz"]["Scd21_max_dB"],
                         "Sdd11_max_dB": band["0.1-20GHz"]["Sdd11_max_dB"]}
        res = {"by_level": rows, "gci": {}}
        for key in ("skew_ps", "t50_d_ps", "vc_pp_pct"):
            res["gci"][key] = {}
            for rk in rows["fine"][key]:
                f1, f2, f3 = (rows[l][key][rk] for l in LEVELS)
                res["gci"][key][rk] = gci(f1, f2, f3, r)
        for key in ("Scd21_max_dB", "Sdd11_max_dB"):
            f1, f2, f3 = (rows[l][key] for l in LEVELS)
            res["gci"][key] = gci(f1, f2, f3, r)
        out["variants"][v] = res
    # the difference B - C: what the tuning changes, which is what the study compares
    if {"B", "C"} <= set(variants):
        diff = {}
        for rk in out["variants"]["B"]["by_level"]["fine"]["skew_ps"]:
            f = [out["variants"]["B"]["by_level"][l]["skew_ps"][rk] - out["variants"]["C"]["by_level"][l]["skew_ps"][rk]
                 for l in LEVELS]
            diff[rk] = {"values": dict(zip(LEVELS, f)), **gci(*f, r)}
        out["skew_change_B_minus_C"] = diff
    dest = ROOT / "build" / "results"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "convergence.json").write_text(json.dumps(out, indent=1))
    for v, res in out["variants"].items():
        s = res["by_level"]
        print(v, {l: round(s[l]["skew_ps"]["50ps"], 3) for l in LEVELS}, "GCI",
              round(res["gci"]["skew_ps"]["50ps"]["gci"], 3))


if __name__ == "__main__":
    main(tuple(sys.argv[1:]) or ("B", "C"))

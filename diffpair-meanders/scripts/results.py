"""Gather every number the report and the post quote into build/results/results.json.

Nothing in the write-ups is typed by hand: figures, the LaTeX macros and
tables (scripts/tex_numbers.py) and the post all read this file.

Delay efficiency, as the study defines it:
    eta = (skew_ref - skew_X) / (dL_add * sqrt(eps_single) / c)
where skew_ref is the untuned fixture's (B, or S_ref for the serpentines),
dL_add is the centreline length the tuning adds to P, and eps_single is the
Hammerstad-Jensen single-line value (the "nominal" velocity a designer's
length-to-delay conversion would use).

Run: python scripts/results.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import skrf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis as an  # noqa: E402
import analytic  # noqa: E402
import convergence  # noqa: E402
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
C0 = 299792458.0
LEVEL = "medium"
U_VARIANTS = ["B", "C", "C_far", "D", "E", "F", "C_cal", "D_cal", "F_cal"]
SL_VARIANTS = ["B_sl", "C_sl", "D_sl", "F_sl", "S_ref_sl", "S_loose_sl", "S_tight_sl"]
ALL = ["A"] + U_VARIANTS + ["S_ref", "S_loose", "S_tight", "B_R075", "B_R3"] + SL_VARIANTS


def reference(v):
    """The untuned fixture a variant's delay efficiency is measured against."""
    if v.endswith("_sl"):
        base = v[:-3]
        if base.startswith("S_"):
            return "S_ref_sl" if base != "S_ref" else None
        return "B_sl" if base != "B" else None
    if v.startswith("S_"):
        return "S_ref" if v != "S_ref" else None
    return "B" if v in U_VARIANTS and v != "B" else None


def have(level, v):
    return (ROOT / "build" / "sparams" / level / f"{v}.s4p").exists()


def main():
    p = geometry.params()
    rises = p["analysis"]["rise_times"]
    bands = p["analysis"]["bands"]
    eeff, z0 = analytic.hammerstad(p["pair"]["width"], p["stackup"]["dielectric_height"], p["stackup"]["epsilon_r"])
    ps_per_mm = math.sqrt(eeff) / C0 * 1e-3 * 1e12
    # stripline is homogeneous: its nominal velocity is c / sqrt(eps_r)
    ps_per_mm_sl = math.sqrt(p["stackup"]["epsilon_r"]) / C0 * 1e-3 * 1e12
    out = {"analytic": json.loads((ROOT / "build" / "results" / "analytic.json").read_text()),
           "mtl_calibration": json.loads((ROOT / "build" / "sparams" / "mtl" / "calibration.json").read_text()),
           "ps_per_mm_single": ps_per_mm, "ps_per_mm_stripline": ps_per_mm_sl, "variants": {}}
    for v in ALL:
        if not have(LEVEL, v):
            continue
        ntw = an.load(LEVEL, v)
        mm = an.mixed(ntw)
        g = geometry.build(v, p)
        row = {"description": geometry.VARIANTS[v],
               "P_len": g["length"]["P"], "N_len": g["length"]["N"], "N_minus_P": g["length"]["N_minus_P"],
               "tuning": g["tuning"], "area_mm2": an.area_mm2(g),
               "checks": json.loads((ROOT / "build" / "sparams" / LEVEL / f"{v}.checks.json").read_text()),
               "bands": an.band_metrics(mm, bands), "timing": {}, "eye": {}}
        for r in rises:
            t = an.timing(an.waveforms(ntw, r))
            row["timing"][f"{r * 1e12:g}"] = {k: (val * 1e12 if k in ("t50_P", "t50_N", "skew", "t50_d") else val)
                                             for k, val in t.items()}
        for br, rt in ((10e9, 50e-12), (16e9, 35e-12)):
            e = an.eye(ntw, br, rt)
            row["eye"][f"{br / 1e9:g}"] = {k: e[k] for k in ("eye_height_rel", "eye_width_ui", "vc_pp_rel")}
        tt, rho, z = an.tdr(mm, 35e-12)
        sel = (tt > 20e-12) & (tt < 0.9 * 2 * row["timing"]["50"]["t50_d"] * 1e-12)
        row["tdr_35ps"] = {"zdiff_max": float(z[sel].max()), "zdiff_min": float(z[sel].min())}
        f = mm.f
        r_ = np.abs(mm.s[:, 3, 0]) / np.abs(mm.s[:, 1, 0])
        tau = 2 * np.arctan(r_) / (2 * np.pi * np.maximum(f, 1)) * 1e12
        row["skew_fd_ps"] = {f"{fx / 1e9:g}": float(tau[np.searchsorted(f, fx)]) for fx in (2e9, 5e9, 10e9, 15e9, 20e9, 25e9)}
        mtl_file = ROOT / "build" / "sparams" / "mtl" / f"{v}.s4p"
        if mtl_file.exists():
            mt = skrf.Network(str(mtl_file))
            row["mtl_skew_50"] = an.timing(an.waveforms(mt, 50e-12))["skew"] * 1e12
        out["variants"][v] = row

    V = out["variants"]
    p_len_b = V["B"]["P_len"]
    for v, row in V.items():
        ref = reference(v)
        if ref and ref in V:
            ref_len = V[ref]["P_len"]
            added = row["P_len"] - ref_len
            only_p = abs(row["N_len"] - V[ref]["N_len"]) < 1e-6
            if abs(added) > 1e-6 and only_p:
                rate = ps_per_mm_sl if v.endswith("_sl") else ps_per_mm
                for r in row["timing"]:
                    dt = V[ref]["timing"][r]["skew"] - row["timing"][r]["skew"]
                    row["timing"][r]["eta"] = dt / (added * rate)
                row["added_mm"] = added
    out["bend_eta"] = V["B"]["timing"]["50"]["skew"] / (math.pi * p["pair"]["pitch"] * ps_per_mm)
    if "B_sl" in V:
        out["bend_eta_sl"] = V["B_sl"]["timing"]["50"]["skew"] / (math.pi * p["pair"]["pitch"] * ps_per_mm_sl)
        out["skew_geometric_sl"] = math.pi * p["pair"]["pitch"] * ps_per_mm_sl

    # convergence on the three finest meshes each variant has
    conv = {}
    cells = p["simulation"]["levels"]
    for v in ("B", "C", "D", "S_ref", "S_loose", "S_tight"):
        levels = sorted((l for l in cells if have(l, v)), key=lambda l: cells[l])
        if len(levels) < 3:
            continue
        skews = {l: an.timing(an.waveforms(an.load(l, v), 50e-12))["skew"] * 1e12 for l in levels}
        f3l = levels[:3]
        r = (cells[f3l[2]] / cells[f3l[0]]) ** 0.5
        g = convergence.gci(*(skews[l] for l in f3l), r)
        # the comparison tables quote the medium mesh, so its value gets its
        # own bound: 1.25 x its distance from the extrapolated value, or three
        # times the spread over the meshes used where they oscillate
        if g["monotonic"] and g["extrapolated"] is not None:
            bound = 1.25 * abs(skews["medium"] - g["extrapolated"])
        else:
            used = [skews[l] for l in set(f3l) | {"medium"}]
            bound = 3.0 * (max(used) - min(used))
        conv[v] = {"skew_50": skews, "levels_used": f3l, "ratio": r, "bound_medium": bound, **g}
    out["convergence"] = conv
    # delay efficiency on each mesh, against the reference on the same mesh
    # (B has no 18 um solution; D there is taken against B's finest)
    eta_lv = {}
    for v, ref, added in (("C", "B", None), ("D", "B", None), ("S_loose", "S_ref", None), ("S_tight", "S_ref", None)):
        if v not in conv or ref not in conv:
            continue
        add = V[v]["P_len"] - V[ref]["P_len"]
        row = {}
        for l, sk in conv[v]["skew_50"].items():
            ref_l = l if l in conv[ref]["skew_50"] else min(conv[ref]["skew_50"], key=lambda q: cells[q])
            row[l] = (conv[ref]["skew_50"][ref_l] - sk) / (add * ps_per_mm)
        eta_lv[v] = row
    out["eta_by_level"] = eta_lv
    # each variant's bound: its own where it was solved on three meshes, else
    # that of the converged variant whose smallest features it shares
    proxy = {"A": "B", "B": "B", "E": "B", "B_R075": "B", "B_R3": "B", "C": "C", "C_far": "C", "F": "C",
             "C_cal": "C", "F_cal": "C", "D": "D", "D_cal": "D", "S_ref": "S_ref", "S_loose": "S_loose",
             "S_tight": "S_tight"}
    for v, row in V.items():
        base = v[:-3] if v.endswith("_sl") else v
        src = proxy.get(base)
        row["uncertainty_ps"] = conv[src]["bound_medium"] if src in conv else None
        row["uncertainty_from"] = src
    out["uncertainty_ps"] = {"untuned": conv.get("B", {}).get("bound_medium"),
                             "tuned_C": conv.get("C", {}).get("bound_medium"),
                             "tuned_D": conv.get("D", {}).get("bound_medium")}
    if all(v in conv for v in ("S_ref", "S_loose", "S_tight")):
        out["uncertainty_ps"]["serpentine"] = max(conv[v]["bound_medium"] for v in ("S_ref", "S_loose", "S_tight"))

    # Pareto over the bent candidates: |skew| (50 ps edge), RMS Scd21 and
    # worst Sdd11 over 0.1-20 GHz, and the area the tuning occupies
    cand = {v: {"skew": abs(V[v]["timing"]["50"]["skew"]),
                "scd21_rms_db": V[v]["bands"]["0.1-20GHz"]["Scd21_mean_dB"],
                "sdd11_max_db": V[v]["bands"]["0.1-20GHz"]["Sdd11_max_dB"],
                "area": V[v]["area_mm2"]} for v in U_VARIANTS if v in V}
    out["pareto"] = {"objectives": cand,
                     "front_all": an.pareto(cand, ("skew", "scd21_rms_db", "sdd11_max_db", "area")),
                     "front_skew_area": an.pareto(cand, ("skew", "area")),
                     "front_skew_sdd11": an.pareto(cand, ("skew", "sdd11_max_db"))}
    dest = ROOT / "build" / "results" / "results.json"
    dest.write_text(json.dumps(out, indent=1, default=float))
    for v, row in V.items():
        t = row["timing"]["50"]
        print(f"{v:8s} skew {t['skew']:+7.2f}  eta {t.get('eta', float('nan')):5.3f}  vc {t['vc_pp_rel'] * 100:5.2f}%  "
              f"Sdd11 {row['bands']['0.1-20GHz']['Sdd11_max_dB']:6.1f}  Scd21rms {row['bands']['0.1-20GHz']['Scd21_mean_dB']:6.1f}"
              f"  Zmax {row['tdr_35ps']['zdiff_max']:6.1f}  area {row['area_mm2']:5.2f}")
    print("pareto", out["pareto"]["front_all"], "uncertainty", out["uncertainty_ps"], "bend eta", out["bend_eta"])


if __name__ == "__main__":
    main()

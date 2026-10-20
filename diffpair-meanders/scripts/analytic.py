"""Analytical estimates: bend mismatch, nominal skew, tuning length, and a
closed-form single-line microstrip estimate. None of this is an EM result.

Hammerstad and Jensen's closed form (zero-thickness strip) gives the
single-line effective permittivity and impedance; it says nothing about the
odd and even modes of the coupled pair, which come from the EM runs.

Run: python scripts/analytic.py  -> build/results/analytic.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402

C0 = 299792458.0
ETA0 = 376.730313668


def hammerstad(w, h, er):
    u = w / h
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
    fu = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
    z01 = ETA0 / (2 * math.pi) * math.log(fu / u + math.sqrt(1 + (2 / u) ** 2))
    return eeff, z01 / math.sqrt(eeff)


def skew_ps(dl_mm, eeff):
    return dl_mm * 1e-3 * math.sqrt(eeff) / C0 * 1e12


def main():
    p = geometry.params()
    s, w, h, er = p["pair"]["pitch"], p["pair"]["width"], p["stackup"]["dielectric_height"], p["stackup"]["epsilon_r"]
    dl = math.pi * s
    eeff, z0 = hammerstad(w, h, er)
    c = p["tuning"]["chamfer"]
    out = {
        "bend_mismatch_mm": dl, "bend_mismatch_mil": dl / 0.0254,
        "skew_ps_at_eps_3.8": skew_ps(dl, 3.8),
        "eps_for_9.5ps": (9.5e-12 * C0 / (dl * 1e-3)) ** 2,
        "two_turns_same_direction_mm": 2 * dl, "two_turns_opposite_mm": 0.0,
        "single_line": {"eps_eff": eeff, "z0_ohm": z0, "skew_ps": skew_ps(dl, eeff),
                        "note": "Hammerstad-Jensen, zero thickness, uncoupled line"},
        "bounds_ps": {"air (eps 1)": skew_ps(dl, 1.0), f"bulk (eps {er})": skew_ps(dl, er)},
        "tuning": {},
    }
    for fam, f in p["tuning"]["families"].items():
        n = f["excursions"]
        a_rule = dl / (2 * n)
        a_cut = (dl / n + geometry.CHAMFER_SAVING * c) / 2
        out["tuning"][fam] = {"N": n, "A_2NA_rule": a_rule, "A_with_chamfers": a_cut,
                              "shortfall_if_2NA_used_mm": n * geometry.CHAMFER_SAVING * c,
                              "shortfall_ps_single_line": skew_ps(n * geometry.CHAMFER_SAVING * c, eeff)}
    dest = Path(__file__).resolve().parent.parent / "build" / "results"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "analytic.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()

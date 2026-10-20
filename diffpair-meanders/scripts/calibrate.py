"""The EM-informed added lengths for C_cal, D_cal and F_cal.

added = pi*s + residual * (pi*s / skew_B): the length-matched version's
residual skew, converted to length at the rate the untuned bend shows.
Prints the values parameters.yaml records under calibrated_added_length.

Run: python scripts/calibrate.py  (needs build/results/summary_medium.json)
"""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

d = json.loads((ROOT / "build" / "results" / "summary_medium.json").read_text())
sb = d["B"]["timing"]["50ps"]["skew"]
dl = math.pi * 0.508
for v in ("C", "D", "F"):
    r = d[v]["timing"]["50ps"]["skew"]
    print(f"{v}: {dl + r * dl / sb:.4f}")

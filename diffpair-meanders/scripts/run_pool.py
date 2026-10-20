"""Run the whole simulation plan on a pool of single-thread openEMS workers.

On this host one openEMS process scales poorly with threads (memory
bandwidth is not the limit; three processes side by side each ran at about
the speed one ran alone), so independent runs go in parallel instead.
A run already recorded for the same model hash is skipped, so the pool can be
stopped and started again.

Run: python scripts/run_pool.py [workers]
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

run.THREADS = 1

PLAN2 = (
    [("coarse", "D"), ("fine", "D")]
    + [(lvl, v) for lvl in ("coarse", "fine") for v in ("S_ref", "S_loose", "S_tight")]
)

PLAN3 = [("medium", v) for v in ("C_cal", "D_cal", "F_cal")]

PLAN4 = [("medium", v) for v in ("B_sl", "C_sl", "D_sl", "F_sl", "S_ref_sl", "S_loose_sl", "S_tight_sl")]

PLAN5 = [("xfine", "D")]

PLAN = (
    [("medium", v) for v in ("B", "C", "A", "D", "F", "E", "C_far")]
    + [("medium", v) for v in ("S_ref", "S_loose", "S_tight", "B_R075", "B_R3")]
    + [("coarse", v) for v in ("B", "C")]
    + [("fine", v) for v in ("B", "C")]
)


def main(workers: int, plan=None):
    jobs = [(lvl, v, k) for lvl, v in (plan or PLAN) for k in (1, 2, 3, 4)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run.run_one, *job): job for job in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                info = fut.result()
                if info.get("returncode") != 0:
                    print(f"FAILED {job}: rc={info.get('returncode')}", flush=True)
            except Exception as exc:  # report and carry on with the rest
                print(f"ERROR {job}: {exc!r}", flush=True)
    print("pool finished", flush=True)


if __name__ == "__main__":
    plans = {"--plan2": PLAN2, "--plan3": PLAN3, "--plan4": PLAN4, "--plan5": PLAN5}
    chosen = next((plans[a] for a in sys.argv if a in plans), None)
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5, chosen)

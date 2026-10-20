"""Run openEMS once per excited port for each variant at one mesh level.

Each run lives in runs/<level>/<variant>/p<k>/ with the model, the solver's
log, its probe files and a provenance record (provenance.json): the
solver's version line, the command, the model's SHA-256, wall time and the
timesteps taken. A run whose provenance names the same model hash is skipped.

Run: python scripts/run.py <level> <variant> [<variant> ...] [--ports 1,2,3,4]
"""

from __future__ import annotations

import hashlib
import math
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOLVER = shutil.which("openEMS")
THREADS = 6


def version() -> str:
    out = subprocess.run([SOLVER, "--help"], capture_output=True, text=True).stdout
    m = re.search(r"openEMS 64bit -- version (\S+)", out)
    return m.group(1) if m else "unknown"


def run_one(level: str, variant: str, port: int) -> dict:
    where = ROOT / "runs" / level / variant / f"p{port}"
    where.mkdir(parents=True, exist_ok=True)
    p = model.geometry.params()
    record_time = p["simulation"]["record_time"]
    dry = where / "dry"
    dry.mkdir(parents=True, exist_ok=True)
    (dry / "model.xml").write_text(model.model_xml(variant, level, port, max_timesteps=10))
    out = subprocess.run([SOLVER, "model.xml", "--no-simulation"], cwd=dry, capture_output=True, text=True).stdout
    dt = float(re.search(r"FDTD timestep is: (\S+) s", out).group(1))
    shutil.rmtree(dry)
    steps = math.ceil(record_time / dt)
    xml = model.model_xml(variant, level, port, max_timesteps=steps, end_criteria=1e-12)
    digest = hashlib.sha256(xml.encode()).hexdigest()
    record = where / "provenance.json"
    if record.exists():
        old = json.loads(record.read_text())
        if old.get("model_sha256") == digest and old.get("returncode") == 0:
            print(f"skip {level}/{variant}/p{port} (done)", flush=True)
            return old
    for f in where.iterdir():
        if f.is_file():
            f.unlink()
    (where / "model.xml").write_text(xml)
    cmd = [SOLVER, "model.xml", "--engine=multithreaded", f"--numThreads={THREADS}"]
    start = time.time()
    began = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"run  {level}/{variant}/p{port} ...", flush=True)
    for attempt in range(3):
        with open(where / "openems.log", "w") as log:
            rc = subprocess.run(cmd, cwd=where, stdout=log, stderr=subprocess.STDOUT).returncode
        if rc == 0:
            break
        print(f"     rc={rc}, retrying", flush=True)
    wall = time.time() - start
    text = (where / "openems.log").read_text(errors="replace")
    steps = re.findall(r"Time for (\d+) iterations with ([\d.e+]+) cells", text)
    energy = re.findall(r"energy: ~?([\d.e+-]+) \(-\s*([\d.]+)dB\)", text)
    info = {
        "variant": variant, "level": level, "excited_port": port,
        "solver": "openEMS", "solver_version": version(), "command": cmd,
        "model_sha256": digest, "started_utc": began, "wall_seconds": round(wall, 1),
        "returncode": rc, "timestep_s": dt, "record_time_s": record_time,
        "timesteps": int(steps[-1][0]) if steps else None,
        "cells": float(steps[-1][1]) if steps else None,
        "final_energy_dB": -float(energy[-1][1]) if energy else None,
    }
    record.write_text(json.dumps(info, indent=1))
    print(f"done {level}/{variant}/p{port}: rc={rc} {wall:.0f}s steps={info['timesteps']} "
          f"energy={info['final_energy_dB']} dB", flush=True)
    return info


def main(argv):
    ports = [1, 2, 3, 4]
    if "--ports" in argv:
        i = argv.index("--ports")
        ports = [int(v) for v in argv[i + 1].split(",")]
        argv = argv[:i] + argv[i + 2:]
    level, variants = argv[0], argv[1:]
    for v in variants:
        for k in ports:
            run_one(level, v, k)


if __name__ == "__main__":
    main(sys.argv[1:])

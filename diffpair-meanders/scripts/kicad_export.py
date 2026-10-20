"""Export each variant as a KiCad board and run KiCad's DRC on it.

Assumptions, stated because they are choices:
- Tracks are the same centreline polylines the EM model buffers, on F.Cu at
  the pair width; arcs go out as their 1-degree chords, not as KiCad arcs
  (fang's own board reader drops arc tracks, so chords keep the export
  readable by it too).
- KiCad's y axis points down, so y is negated.
- B.Cu carries a filled GND zone over the board outline (the return plane).
- The ports are not footprints, so KiCad reports the track ends as dangling;
  those reports are expected and listed separately from clearance results.
- Clearance comes from a .kicad_dru beside the board: 0.15 mm between nets.
  KiCad does not check spacing within one net, so the fold spacing of a
  meander is reported by geometry.py from its parameters, not by DRC.

Run: python scripts/kicad_export.py  -> build/kicad/<variant>/
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "kicad"


def board(g: dict, p: dict) -> str:
    w = p["pair"]["width"]
    xs = [pt[0] for net in ("P", "N") for pt in g["copper"][net]]
    ys = [-pt[1] for net in ("P", "N") for pt in g["copper"][net]]
    m = 1.0
    x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
    lines = ['(kicad_pcb (version 20221018) (generator "diffpair_meanders")',
             '  (general (thickness 1.6))', '  (paper "A3")',
             '  (layers (0 "F.Cu" signal) (31 "B.Cu" signal) (44 "Edge.Cuts" user))',
             '  (setup (pad_to_mask_clearance 0))',
             '  (net 0 "") (net 1 "P") (net 2 "N") (net 3 "GND")',
             f'  (gr_rect (start {x0:.6f} {y0:.6f}) (end {x1:.6f} {y1:.6f}) (stroke (width 0.05) (type default)) '
             '(fill none) (layer "Edge.Cuts"))']
    for netno, net in ((1, "P"), (2, "N")):
        pts = g["centreline"][net]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            lines.append(f'  (segment (start {ax:.6f} {-ay:.6f}) (end {bx:.6f} {-by:.6f}) (width {w}) '
                         f'(layer "F.Cu") (net {netno}))')
    lines.append(f'  (zone (net 3) (net_name "GND") (layer "B.Cu") (hatch edge 0.5) (connect_pads (clearance 0)) '
                 f'(min_thickness 0.2) (fill yes (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
                 f'(polygon (pts (xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1}))))')
    lines.append(")")
    return "\n".join(lines) + "\n"


RULES = """(version 1)
(rule "pair clearance"
  (condition "A.Net != B.Net")
  (constraint clearance (min {clear}mm)))
"""


def main():
    p = geometry.params()
    cli = shutil.which("kicad-cli")
    summary = {}
    for name in geometry.VARIANTS:
        g = geometry.build(name, p)
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        pcb = d / f"{name}.kicad_pcb"
        pcb.write_text(board(g, p))
        (d / f"{name}.kicad_dru").write_text(RULES.format(clear=p["pair"]["min_clearance"]))
        report = d / "drc.json"
        run = subprocess.run([cli, "pcb", "drc", "--format", "json", "--refill-zones", "--output", str(report),
                              str(pcb)], capture_output=True, text=True)
        data = json.loads(report.read_text()) if report.exists() else {}
        kinds = {}
        for v in data.get("violations", []) + data.get("unconnected_items", []):
            kinds[v.get("type", "?")] = kinds.get(v.get("type", "?"), 0) + 1
        clearance = sum(n for k, n in kinds.items() if "clearance" in k or "short" in k)
        summary[name] = {"returncode": run.returncode, "violations_by_type": kinds,
                         "clearance_or_short_violations": clearance,
                         "kicad_version": data.get("kicad_version")}
        print(name, summary[name])
    (OUT / "drc_summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

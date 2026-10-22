"""The report's first-page figure: a render of board D beside what the solver
finds at its receiver.

(a) is KiCad 10's raytraced render of the board file the study exports for its
DRC (build/kicad/D, written by kicad_export.py from geometry.py's polygons),
copied with the study's own stackup (0.2 mm dielectric, 35 um copper, no
solder mask) in place of KiCad's default 1.6 mm board, and with its key facts
set in silkscreen: the trace names, the number of excursions and the length
report. (b) is the far-end P and -N of board D for a 50 ps edge, with the
untuned bend B in grey, each skew dimensioned with its bound from the mesh
study, to the two decimals the report's text quotes. Every number on it comes
from geometry.py and results.json.

Run: python scripts/fig_teaser.py   (needs kicad-cli on the path)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis as an  # noqa: E402
import geometry  # noqa: E402
import style as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "build" / "results" / "results.json").read_text())
V = R["variants"]
WORK = ROOT / "build" / "renders" / "teaser"
BOARD = "D"

#: The camera: KiCad's rotation (degrees about x, y, z), zoom and pan, chosen so the
#: whole board, its bend and its four excursions are in view.
CAMERA = {"rotate": "-50,0,-15", "zoom": "1.45", "pan": "-1.2,0,0"}
#: The dielectric's colour in the render (a dark laminate green); copper is bare.
LAMINATE = "#1E3A2B"


def render_board() -> Path:
    """Write the render's board file and raytrace it; returns the PNG, cut to
    the board and its shadow."""
    p = geometry.params()
    g = geometry.build(BOARD, p)
    st = p["stackup"]
    h, tc = st["dielectric_height"], st["copper_thickness"]
    src = (ROOT / "build" / "kicad" / BOARD / f"{BOARD}.kicad_pcb").read_text()
    t = src.replace("(general (thickness 1.6))", f"(general (thickness {h + 2 * tc:g}))")
    t = re.sub(r'\(layers \(0 "F\.Cu" signal\) \(31 "B\.Cu" signal\) \(44 "Edge\.Cuts" user\)\)',
               '(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (37 "F.SilkS" user) (38 "B.Mask" user) '
               '(39 "F.Mask" user) (44 "Edge.Cuts" user))', t)
    clear = "#00000000"
    stack = ('(setup (stackup'
             ' (layer "F.SilkS" (type "Top Silk Screen") (color "White"))'
             f' (layer "F.Mask" (type "Top Solder Mask") (color "{clear}") (thickness 0.01))'
             f' (layer "F.Cu" (type "copper") (thickness {tc:g}))'
             f' (layer "dielectric 1" (type "core") (color "{LAMINATE}") (thickness {h:g}) (material "FR4")'
             f' (epsilon_r {st["epsilon_r"]:g}) (loss_tangent {st["loss_tangent"]:g}))'
             f' (layer "B.Cu" (type "copper") (thickness {tc:g}))'
             f' (layer "B.Mask" (type "Bottom Solder Mask") (color "{clear}") (thickness 0.01))'
             ' (copper_finish "None") (dielectric_constraints no)) (pad_to_mask_clearance 0))')
    assert "(setup (pad_to_mask_clearance 0))" in t
    t = t.replace("(setup (pad_to_mask_clearance 0))", stack)
    # silkscreen, in KiCad's coordinates (y down, so the geometry's y negated)
    R_ = p["fixture"]["bend_radius"]
    s = p["pair"]["pitch"]
    n_exc = g["tuning"]["excursions"]
    lp, ln = g["length"]["P"], g["length"]["N"]
    size, thick = 0.3, 0.05

    def silk(text, x, y, justify="left", sz=size):
        return (f'  (gr_text "{text}" (at {x:g} {y:g} 0) (layer "F.SilkS") '
                f'(effects (font (size {sz:g} {sz:g}) (thickness {thick:g})) (justify {justify})))\n')

    # inside the U, clear of the copper: the excursions reach no closer to the
    # middle than y = R - A, and the bend's inner edge is past x = L + R/2
    same = abs(lp - ln) < 5e-4
    report = (f"LENGTH REPORT: P = N = {lp:.3f} mm" if same
              else f"LENGTH REPORT: P = {lp:.3f}, N = {ln:.3f} mm")
    silks = (silk("P", 0.35, R_ - 0.4) + silk("N", 0.35, R_ + s + 0.45)
             + silk(f"BOARD {BOARD}: {n_exc} EXCURSIONS ON P", 1.4, -0.32)
             + silk(report, 1.4, 0.3))
    t = t.rstrip().rstrip(")") + "\n" + silks + ")\n"
    WORK.mkdir(parents=True, exist_ok=True)
    board = WORK / f"{BOARD}-render.kicad_pcb"
    board.write_text(t)
    raw = WORK / f"{BOARD}-render-raw.png"
    cmd = ["kicad-cli", "pcb", "render", str(board), "-o", str(raw), "-w", "3600", "-h", "1800",
           "--quality", "high", "--perspective", "--rotate", CAMERA["rotate"], "--zoom", CAMERA["zoom"],
           "--pan", CAMERA["pan"], "--floor", "--background", "transparent", "--use-board-stackup-colors",
           "--light-side-elevation", "50"]
    if not shutil.which("kicad-cli"):
        raise SystemExit("kicad-cli is not on the path")
    subprocess.run(cmd, check=True, capture_output=True)
    im = Image.open(raw).convert("RGBA")
    box = im.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
    out = WORK / f"{BOARD}-render.png"
    im.crop(box).save(out)
    return out


def fig_teaser(render: Path):
    t = S.use("report")
    plt.rcParams["figure.constrained_layout.use"] = False
    b = t["base"]
    img = Image.open(render).convert("RGBA")
    # composite on white so the PDF carries no transparency
    bg = Image.new("RGBA", img.size, "white")
    bg.alpha_composite(img)
    img = np.asarray(bg.convert("RGB"))
    W = t["double"]
    wa = W * 0.6
    ha = wa * img.shape[0] / img.shape[1]
    H = ha + 0.32
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 0.3 / H, wa / W, ha / H])
    ax.imshow(img, interpolation="lanczos")
    ax.set_axis_off()
    fig.text(wa / 2 / W, 0.02, "(a)", ha="center", va="bottom", fontsize=b)

    # (b) the receiver
    x0 = wa + 0.42
    ax2 = fig.add_axes([x0 / W, 0.62 / H, (W - x0 - 0.04) / W, (H - 0.62 - 0.22) / H])
    tm = {v: V[v]["timing"]["50"] for v in ("B", BOARD)}
    mid = tm[BOARD]["t50_d"]
    lo, hi = mid - 32, mid + 32
    level = {}
    for v, cp, cn, lw in (("B", "#B9B9C0", "#B9B9C0", 1.0), (BOARD, S.COPPER, S.TEAL, 1.4)):
        w = an.waveforms(an.load("medium", v), 50e-12)
        tt = w["t"] * 1e12
        sel = (tt > lo) & (tt < hi)
        ax2.plot(tt[sel], w["p_far"][sel], color=cp, lw=lw, zorder=3 if v != "B" else 2)
        ax2.plot(tt[sel], -w["n_far"][sel], color=cn, lw=lw, zorder=3 if v != "B" else 2)
        level[v] = (np.mean(w["p_far"][-20:]) - np.mean(w["n_far"][-20:])) / 4
    ax2.set_xlim(lo, hi)
    ax2.set_ylim(-0.02, 0.52)
    ax2.set_xlabel("Time (ps)", labelpad=1)
    ax2.set_ylabel("Far-end voltage (V)", labelpad=2)
    ax2.tick_params(labelsize=b - 1)
    ax2.grid(True, color="#E4E4E4", lw=0.4)

    def gap(v, colour, dy, text, at, ha):
        """The skew between the 50 % crossings, dimensioned `dy` above or below
        them, and its readout at `at` (data coordinates) with a leader."""
        tp, tn = tm[v]["t50_P"], tm[v]["t50_N"]
        y = level[v]
        ax2.plot([tp], [y], "o", ms=2.6, color=colour if v == "B" else S.COPPER, zorder=5)
        ax2.plot([tn], [y], "o", ms=2.6, color=colour if v == "B" else S.TEAL, zorder=5)
        ya = y + dy
        for x in (tp, tn):
            ax2.plot([x, x], [y, ya], color=colour, lw=0.4, zorder=4)
        ax2.add_patch(FancyArrowPatch((tp, ya), (tn, ya), arrowstyle="<|-|>", mutation_scale=5, lw=0.6,
                                      color=colour, shrinkA=0, shrinkB=0, zorder=6))
        # the readout sits inside the plot at `at` (its left end for "left", its right end
        # for "right"); the leader runs from the dimension to the readout's near end
        label = ax2.text(*at, text, ha=ha, va="center", fontsize=b - 0.5, color=colour if v == "B" else S.INK,
                         zorder=7)
        fig.canvas.draw()
        ext = label.get_window_extent().transformed(ax2.transData.inverted())
        near = (ext.x1 + 0.5, at[1]) if ha == "left" else (ext.x0 - 0.5, at[1])
        end = tp if near[0] < tp else tn
        ax2.plot([end, near[0]], [ya, near[1]], color=colour, lw=0.4, zorder=4)

    ub, ud = V["B"]["uncertainty_ps"], V[BOARD]["uncertainty_ps"]
    gap(BOARD, S.INK, 0.07, rf"board {BOARD}: ${tm[BOARD]['skew']:.2f} \pm {ud:.2f}$ ps", (lo + 1.2, 0.335),
        "left")
    gap("B", "#8A8A92", -0.07, rf"untuned: ${tm['B']['skew']:.2f} \pm {ub:.2f}$ ps", (hi - 1.0, 0.075),
        "right")
    ax2.text(0.03, 0.97, "P", transform=ax2.transAxes, ha="left", va="top", fontsize=b, color=S.COPPER)
    ax2.text(0.075, 0.97, "and", transform=ax2.transAxes, ha="left", va="top", fontsize=b, color=S.INK)
    ax2.text(0.165, 0.97, "$-$N", transform=ax2.transAxes, ha="left", va="top", fontsize=b, color=S.TEAL)
    ax2.text(0.03, 0.87, "grey: untuned bend B", transform=ax2.transAxes, ha="left", va="top",
             fontsize=b - 1, color="#8A8A92")
    fig.text((x0 + W) / 2 / W, 0.02, "(b)", ha="center", va="bottom", fontsize=b)
    S.save(fig, "fig_teaser", "report")


if __name__ == "__main__":
    fig_teaser(render_board())
    print("ok")

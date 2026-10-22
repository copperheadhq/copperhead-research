"""The report's first-page figure: board D as the solver meshes it, beside what
the solver finds at its receiver.

(a) is the top view of board D in the solver's colours (the report's figure
of the computational domain), cut to the board's outline: the substrate
green, the copper gold, the four lumped ports red, and the medium mesh the
runs used drawn over it, so its grading from the finest cells over the copper
to the coarsest away from it shows. The cells whose centre lies in the copper are filled, which is the
staircase the solver sees; an inset enlarges D's excursions so the staircase
can be read. (b) is the far-end P and -N of board D for a 50 ps edge, with
the untuned bend B in grey, each skew dimensioned with its bound from the
mesh study, to the two decimals the report's text quotes.

Every polygon and mesh line comes from geometry.py and model.py, the sources
the runs used, and every number from results.json. The mesh sizes the caption
quotes are written to report/generated/teaser.tex.

Run: python scripts/fig_teaser.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle
from matplotlib.path import Path as MPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis as an  # noqa: E402
import fig_diagrams as D  # noqa: E402
import geometry  # noqa: E402
import model  # noqa: E402
import style as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "build" / "results" / "results.json").read_text())
V = R["variants"]
BOARD = "D"
LEVEL = "medium"
#: The part of board D the inset enlarges (mm): its first two excursions on P.
ZOOM = (8.12, 10.06, -1.71, -1.02)
#: Where the inset sits, in the panel's own millimetres: inside the U, clear of copper.
INSET = (0.55, 7.55, -1.22, 1.24)
#: The board outline's margin round the copper, as kicad_export.py sets it (mm).
BOARD_MARGIN = 1.0
#: Raster resolution for the meshed panel (the mesh is too fine to keep as vectors).
DPI = 600


def cells_in_copper(X, Y, polys):
    """A (len(Y)-1, len(X)-1) mask: True where a cell's centre lies in the copper."""
    cx = (np.asarray(X[:-1]) + np.asarray(X[1:])) / 2
    cy = (np.asarray(Y[:-1]) + np.asarray(Y[1:])) / 2
    gx, gy = np.meshgrid(cx, cy)
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    inside = np.zeros(len(pts), bool)
    for poly in polys:
        inside |= MPath(poly).contains_points(pts)
    return inside.reshape(gy.shape)


def draw_mesh(ax, X, Y, g, window, line_lw, edge_lw, alpha):
    """The substrate, the cells in the copper filled, the mesh lines and the
    copper's true outline, over `window` (x0, x1, y0, y1)."""
    x0, x1, y0, y1 = window
    xs = [x for x in X if x0 - 0.2 <= x <= x1 + 0.2]
    ys = [y for y in Y if y0 - 0.2 <= y <= y1 + 0.2]
    mask = cells_in_copper(xs, ys, [g["copper"][n] for n in ("P", "N")])
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=D.SUBSTRATE, ec="none", zorder=1))
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([D.SUBSTRATE, D.METAL])
    ax.pcolormesh(xs, ys, mask.astype(float), cmap=cmap, vmin=0, vmax=1, shading="flat", zorder=2,
                  rasterized=True)
    segs = [[(x, y0), (x, y1)] for x in xs if x0 <= x <= x1] + [[(x0, y), (x1, y)] for y in ys if y0 <= y <= y1]
    ax.add_collection(LineCollection(segs, colors="white", linewidths=line_lw, alpha=alpha, zorder=3,
                                     rasterized=True))
    for n in ("P", "N"):
        ax.add_patch(Polygon(g["copper"][n], closed=True, fc="none", ec=D.METAL_EDGE, lw=edge_lw, zorder=4))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)


def fig_teaser():
    t = D.use()
    b = t["base"]
    p = geometry.params()
    w = p["pair"]["width"]
    grid = model.mesh("U", LEVEL, p)
    X, Y = grid["x"], grid["y"]
    g = geometry.build(BOARD, p)
    # the view is the board's own outline, as kicad_export.py draws it (the copper's
    # extent and 1 mm round it); the solver's domain runs a further 1 mm past it
    xs = [q[0] for n in ("P", "N") for q in g["copper"][n]]
    ys = [q[1] for n in ("P", "N") for q in g["copper"][n]]
    dom = (min(xs) - BOARD_MARGIN, max(xs) + BOARD_MARGIN, min(ys) - BOARD_MARGIN, max(ys) + BOARD_MARGIN)

    W = t["double"]
    wa = 3.75                                    # panel (a)'s plot width (in)
    ha = wa * (dom[3] - dom[2]) / (dom[1] - dom[0])
    left, bottom = 0.34, 0.52
    H = bottom + ha + 0.1
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([left / W, bottom / H, wa / W, ha / H])

    # (a) board D as the solver meshes it
    draw_mesh(ax, X, Y, g, dom, line_lw=0.14, edge_lw=0.25, alpha=0.5)
    for q in g["ports"]:
        ax.plot([q["x"], q["x"]], [q["y"] - w / 2, q["y"] + w / 2], color=D.PORT, lw=1.6, solid_capstyle="butt",
                zorder=5)
    for net, q in (("P", g["ports"][0]), ("N", g["ports"][1])):
        ax.text(-0.35, q["y"] + (0.06 if net == "P" else -0.06), net, color="white", fontsize=b - 1, ha="right",
                va="bottom" if net == "P" else "top", style="italic", zorder=6)
    zx0, zx1, zy0, zy1 = ZOOM
    ax.add_patch(Rectangle((zx0, zy0), zx1 - zx0, zy1 - zy0, fc="none", ec="white", lw=0.7, zorder=7))
    # the inset, inside the U
    ix0, ix1, iy0, iy1 = INSET
    to_fig = lambda x, y: fig.transFigure.inverted().transform(ax.transData.transform((x, y)))  # noqa: E731
    (fx0, fy0), (fx1, fy1) = to_fig(ix0, iy0), to_fig(ix1, iy1)
    ins = fig.add_axes([fx0, fy0, fx1 - fx0, fy1 - fy0])
    draw_mesh(ins, X, Y, g, ZOOM, line_lw=0.25, edge_lw=0.6, alpha=0.55)
    ins.set_xticks([])
    ins.set_yticks([])
    for sp in ins.spines.values():
        sp.set_visible(True)                 # the report style hides the top and right spines
        sp.set_edgecolor("white")
        sp.set_linewidth(0.9)
    cell = p["simulation"]["levels"][LEVEL] * 1000
    # the cell size, above the window, on the substrate inside the U (clear of copper)
    ax.text(zx0 + 0.25, zy1 + 0.12, rf"{cell:g} $\mu$m cells", ha="left", va="bottom", fontsize=b - 1.5,
            color="white", zorder=8)
    # leaders from the window's corners to the inset's
    for (wx, wy), (jx, jy) in (((zx0, zy1), (ix1, iy1)), ((zx0, zy0), (ix1, iy0))):
        ax.plot([wx, jx], [wy, jy], color="white", lw=0.5, alpha=0.9, zorder=7)
    ax.set_aspect("equal")
    ax.grid(False)
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.5)
    ax.tick_params(direction="out", length=2.5, width=0.5, pad=1.5, labelsize=b - 1)
    ax.xaxis.set_major_locator(plt.MultipleLocator(2))
    ax.yaxis.set_major_locator(plt.MultipleLocator(2))
    ax.set_xlabel(r"$x$ (mm)", labelpad=1)
    ax.set_ylabel(r"$y$ (mm)", labelpad=1)
    fig.text((left + wa / 2) / W, 0.02, "(a)", ha="center", va="bottom", fontsize=b)

    # (b) the receiver
    x0 = left + wa + 0.5
    ax2 = fig.add_axes([x0 / W, bottom / H, (W - x0 - 0.04) / W, (ha - 0.02) / H])
    tm = {v: V[v]["timing"]["50"] for v in ("B", BOARD)}
    mid = tm[BOARD]["t50_d"]
    lo, hi = mid - 32, mid + 32
    level = {}
    for v, cp, cn, lw in (("B", "#B9B9C0", "#B9B9C0", 1.0), (BOARD, S.COPPER, S.TEAL, 1.4)):
        wv = an.waveforms(an.load(LEVEL, v), 50e-12)
        tt = wv["t"] * 1e12
        sel = (tt > lo) & (tt < hi)
        ax2.plot(tt[sel], wv["p_far"][sel], color=cp, lw=lw, zorder=3 if v != "B" else 2)
        ax2.plot(tt[sel], -wv["n_far"][sel], color=cn, lw=lw, zorder=3 if v != "B" else 2)
        level[v] = (np.mean(wv["p_far"][-20:]) - np.mean(wv["n_far"][-20:])) / 4
    ax2.set_xlim(lo, hi)
    ax2.set_ylim(-0.02, 0.52)
    ax2.set_xlabel("Time (ps)", labelpad=1)
    ax2.set_ylabel("Far-end voltage (V)", labelpad=2)
    ax2.tick_params(labelsize=b - 1)
    ax2.xaxis.set_major_locator(plt.MultipleLocator(20))
    ax2.grid(True, color="#E4E4E4", lw=0.4)

    def gap(v, colour, dy, text, at, ha_):
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
        label = ax2.text(*at, text, ha=ha_, va="center", fontsize=b - 0.5, color=colour if v == "B" else S.INK,
                         zorder=7, bbox=dict(fc="white", ec="none", pad=0.6))
        fig.canvas.draw()
        ext = label.get_window_extent().transformed(ax2.transData.inverted())
        # the leader runs from the dimension's nearer end to the label's facing edge,
        # stopping a little short of the label's white ground
        end = tn if abs(tn - (ext.x0 + ext.x1) / 2) < abs(tp - (ext.x0 + ext.x1) / 2) else tp
        lx = min(max(end, ext.x0 + 1.0), ext.x1 - 1.0)
        ly = ext.y0 - 0.012 if ya < ext.y0 else ext.y1 + 0.012
        ax2.plot([end, lx], [ya, ly], color=colour, lw=0.4, zorder=4)

    ub, ud = V["B"]["uncertainty_ps"], V[BOARD]["uncertainty_ps"]
    gap(BOARD, S.INK, 0.07, rf"board {BOARD}: ${tm[BOARD]['skew']:.2f} \pm {ud:.2f}$ ps", (lo + 1.6, 0.4),
        "left")
    gap("B", "#8A8A92", -0.07, rf"untuned: ${tm['B']['skew']:.2f} \pm {ub:.2f}$ ps", (hi - 1.0, 0.075),
        "right")
    ax2.text(0.03, 0.97, "P", transform=ax2.transAxes, ha="left", va="top", fontsize=b, color=S.COPPER)
    ax2.text(0.085, 0.97, "and", transform=ax2.transAxes, ha="left", va="top", fontsize=b, color=S.INK)
    ax2.text(0.19, 0.97, "$-$N", transform=ax2.transAxes, ha="left", va="top", fontsize=b, color=S.TEAL)
    pos = ax2.get_position()
    fig.text(pos.x0 + pos.width / 2, 0.02, "(b)", ha="center", va="bottom", fontsize=b)

    out = ROOT / "figures" / "report"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "fig_teaser.pdf", dpi=DPI, metadata={"CreationDate": None})
    plt.close(fig)
    gen = ROOT / "report" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "teaser.tex").write_text(
        "% generated by scripts/fig_teaser.py; do not edit\n"
        f"\\newcommand{{\\TeaserFineUm}}{{{cell:g}}}\n"
        f"\\newcommand{{\\TeaserCoarseUm}}{{{p['simulation']['coarse_cell'] * 1000:g}}}\n"
        f"\\newcommand{{\\TeaserLinesX}}{{{len(X)}}}\n"
        f"\\newcommand{{\\TeaserLinesY}}{{{len(Y)}}}\n")


if __name__ == "__main__":
    fig_teaser()
    print("ok")

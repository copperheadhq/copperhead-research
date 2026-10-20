"""The report's diagrams, drawn as a paper draws them.

Two kinds. The model views show what openEMS was given, the way a field
solver's layout view shows it: the computational domain as a green
substrate, the copper polygons in gold, the lumped ports in red, and the
mesh. The drawings are dimensioned line drawings: the cross-sections, the
bend, the geometry of one tuning section, and the pipeline. Every polygon,
port, mesh line and dimension comes from geometry.py, model.py and
parameters.yaml, the same sources the runs used; nothing is typed in.

Each figure is laid out at the width it is printed (a column, 3.45 in, or
the page, 7.0 in), so its type prints at the size it is set.

The blog keeps its own figures (fig_geometry.py); these are the report's.

Run: python scripts/fig_diagrams.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle
from matplotlib.path import Path as MPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402
import model  # noqa: E402
import style as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGET = "report"

# model views
SUBSTRATE = "#2D6A49"
SUBSTRATE_EDGE = "#173B28"
METAL = "#E9B949"
METAL_EDGE = "#6E5210"
PORT = "#D7362B"
ON_SUBSTRATE = "#FFFFFF"
# drawings
INK = "#000000"
DIELECTRIC = "#E4E4E4"
P_LIGHT = "#E7C9A6"
N_LIGHT = "#A9D6DD"
LW_THIN = 0.35
DASHDOT = (6, 1.6, 1.2, 1.6)
# drawing constants the captions quote, written to report/generated/diagrams.tex
MACROS: dict[str, str] = {}


# ------------------------------------------------------------------ helpers

def use():
    """The report style, laid out by hand: every axes here is placed in
    inches, so constrained layout is off."""
    t = S.use(TARGET)
    plt.rcParams["figure.constrained_layout.use"] = False
    return t


def bare(ax):
    ax.set_aspect("equal")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def mm_axes(ax, step):
    """Axes in millimetres around a model view, ticks outward."""
    ax.set_aspect("equal")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(True)
        s.set_linewidth(0.5)
    ax.tick_params(direction="out", length=2.5, width=0.5, pad=1.5)
    ax.xaxis.set_major_locator(plt.MultipleLocator(step))
    ax.yaxis.set_major_locator(plt.MultipleLocator(step))


def drawing(width, xlim, ylim, pad=(0.0, 0.0, 0.0, 0.0)):
    """A figure `width` inches wide holding one equal-aspect axes over xlim and
    ylim, with `pad` (left, right, bottom, top, in inches) around it."""
    l, r, b_, t = pad
    scale = (width - l - r) / (xlim[1] - xlim[0])          # inches per mm
    height = (ylim[1] - ylim[0]) * scale + b_ + t
    fig = plt.figure(figsize=(width, height))
    ax = fig.add_axes([l / width, b_ / height, (width - l - r) / width, (height - b_ - t) / height])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    bare(ax)
    return fig, ax, scale


def save_cropped(fig, name, pad=0.03):
    """Save cut to what is drawn: a 3D axes reaches past what it draws, so a
    tight box (which counts the axes) is no use."""
    import numpy as np
    from matplotlib.transforms import Bbox
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())
    ys, xs = np.nonzero((img[..., :3] < 250).any(axis=2))
    dpi, h = fig.dpi, img.shape[0]
    box = Bbox.from_extents(xs.min() / dpi - pad, (h - ys.max() - 1) / dpi - pad, (xs.max() + 1) / dpi + pad,
                            (h - ys.min()) / dpi + pad)
    out = ROOT / "figures" / TARGET
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.pdf", bbox_inches=box, metadata={"CreationDate": None})
    plt.close(fig)


def arrow(ax, p, q, both=True, lw=0.45, size=4.5, colour=INK, z=8):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="<|-|>" if both else "-|>", mutation_scale=size, lw=lw,
                                 color=colour, shrinkA=0, shrinkB=0, zorder=z, joinstyle="miter",
                                 capstyle="butt"))


def ext(ax, x0, y0, x1, y1, colour=INK):
    """An extension or leader line."""
    ax.plot([x0, x1], [y0, y1], color=colour, lw=LW_THIN, solid_capstyle="butt", zorder=7)


def centreline(ax, pts, lw=0.4, colour=INK, z=6):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=colour, lw=lw, dashes=DASHDOT, zorder=z)


def metal(ax, g, lw=0.35):
    for net in ("P", "N"):
        ax.add_patch(Polygon(g["copper"][net], closed=True, fc=METAL, ec=METAL_EDGE, lw=lw, joinstyle="miter",
                             zorder=3))


def ports(ax, g, w, fs=None, lw=2.2, label_dx=-0.42):
    for q in g["ports"]:
        x, y = q["x"], q["y"]
        ax.plot([x, x], [y - w / 2, y + w / 2], color=PORT, lw=lw, solid_capstyle="butt", zorder=5)
        if fs:
            ax.text(x + label_dx, y, str(q["number"]), ha="center", va="center", fontsize=fs,
                    color=ON_SUBSTRATE, fontweight="bold", zorder=6)


# ------------------------------------------------------------------ the model

def fig_model():
    """(a) Fixture B in its computational domain at the medium level; (b) the
    medium mesh over D's first excursions, with the cells whose centre lies
    in the copper filled."""
    t = use()
    b = t["base"]
    p = geometry.params()
    w = p["pair"]["width"]
    grid = model.mesh("U", "medium", p)
    X, Y = grid["x"], grid["y"]
    g = geometry.build("B", p)
    win = (8.15, 9.35, -2.25, -1.05)
    W, Hh = t["double"], 2.75
    fig = plt.figure(figsize=(W, Hh))
    # both panels the same height on the page
    ph = 2.05
    xa = (X[0] - 0.3, X[-1] + 0.3)
    ya = (Y[0] - 0.3, Y[-1] + 0.3)
    wa = ph * (xa[1] - xa[0]) / (ya[1] - ya[0])
    wb_ = ph * (win[1] - win[0]) / (win[3] - win[2])
    left, bottom = 0.42, 0.52
    ax = fig.add_axes([left / W, bottom / Hh, wa / W, ph / Hh])
    ax2 = fig.add_axes([(W - wb_ - 0.08) / W, bottom / Hh, wb_ / W, ph / Hh])

    # (a) the domain and fixture B
    ax.add_patch(Rectangle((X[0], Y[0]), X[-1] - X[0], Y[-1] - Y[0], fc=SUBSTRATE, ec=SUBSTRATE_EDGE, lw=0.6,
                           zorder=1))
    metal(ax, g)
    ports(ax, g, w, b - 1.5)
    ax.plot([0, 0], [Y[0], Y[-1]], color=ON_SUBSTRATE, lw=0.4, dashes=(3, 2), zorder=2, alpha=0.8)
    ax.text(0.15, Y[0] + 0.25, "launch plane", color=ON_SUBSTRATE, fontsize=b - 1.5, ha="left", va="bottom",
            zorder=6)
    for net, q in (("P", g["ports"][0]), ("N", g["ports"][1])):
        ax.text(1.0, q["y"] + (0.32 if net == "P" else -0.34), net, color=ON_SUBSTRATE, fontsize=b - 1,
                ha="center", va="center", zorder=6, style="italic")
    ax.add_patch(Rectangle((win[0], win[2]), win[1] - win[0], win[3] - win[2], fc="none", ec=ON_SUBSTRATE, lw=0.6,
                           zorder=7))
    ax.text(win[0] - 0.1, win[3] + 0.08, "(b)", color=ON_SUBSTRATE, fontsize=b - 1.5, ha="right", va="bottom",
            zorder=7)
    mm_axes(ax, 2)
    ax.set_xlim(*xa)
    ax.set_ylim(*ya)
    ax.set_xlabel(r"$x$ (mm)", labelpad=1)
    ax.set_ylabel(r"$y$ (mm)", labelpad=1)
    ax.tick_params(labelsize=b - 1)

    # (b) the mesh over D's first excursions
    d = geometry.build("D", p)
    ax2.add_patch(Rectangle((win[0], win[2]), win[1] - win[0], win[3] - win[2], fc=SUBSTRATE, ec="none", zorder=1))
    xs = [x for x in X if win[0] - 0.1 <= x <= win[1] + 0.1]
    ys = [y for y in Y if win[2] - 0.1 <= y <= win[3] + 0.1]
    paths = [MPath(d["copper"][net]) for net in ("P", "N")]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(pa.contains_point((cx, cy)) for pa in paths):
                ax2.add_patch(Rectangle((xs[i], ys[j]), xs[i + 1] - xs[i], ys[j + 1] - ys[j], fc=METAL, ec="none",
                                        alpha=0.6, zorder=2))
    for net in ("P", "N"):
        ax2.add_patch(Polygon(d["copper"][net], closed=True, fc="none", ec=METAL_EDGE, lw=0.8, zorder=4))
    for x in xs:
        ax2.plot([x, x], [win[2], win[3]], color=ON_SUBSTRATE, lw=0.25, alpha=0.5, zorder=3)
    for y in ys:
        ax2.plot([win[0], win[1]], [y, y], color=ON_SUBSTRATE, lw=0.25, alpha=0.5, zorder=3)
    MACROS["MediumCellUm"] = f"{p['simulation']['levels']['medium'] * 1000:g}"
    mm_axes(ax2, 0.4)
    ax2.set_xlim(*win[:2])
    ax2.set_ylim(*win[2:])
    ax2.set_xlabel(r"$x$ (mm)", labelpad=1)
    ax2.tick_params(labelsize=b - 1)
    for a_, lab in ((ax, "(a)"), (ax2, "(b)")):
        pos = a_.get_position()
        fig.text(pos.x0 + pos.width / 2, 0.03, lab, ha="center", va="bottom", fontsize=b)
    S.save(fig, "fig_model", TARGET)


def fig_model3d():
    """Fixture B's model in three dimensions, its height drawn `ZE` times its
    true scale so that the slab and the ports can be seen."""
    from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
    t = use()
    b = t["base"]
    p = geometry.params()
    w, h = p["pair"]["width"], p["stackup"]["dielectric_height"]
    air = p["simulation"]["air_above"]
    grid = model.mesh("U", "medium", p)
    X, Y = grid["x"], grid["y"]
    g = geometry.build("B", p)
    ZE = 4.0
    MACROS["ModelZE"] = f"{ZE:g}"
    H, TOP = h * ZE, (h + air) * ZE
    fig = plt.figure(figsize=(3.75, 3.3), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1], projection="3d", computed_zorder=False)
    x0, x1, y0, y1 = X[0], X[-1], Y[0], Y[-1]
    c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    ax.add_collection3d(Poly3DCollection([[(x, y, 0) for x, y in c]], fc="#B9BCC2", ec="#6B6E75", lw=0.4,
                                         zorder=1))
    faces = ([[(x, y, H) for x, y in c]]
             + [[(*c[k], 0), (*c[(k + 1) % 4], 0), (*c[(k + 1) % 4], H), (*c[k], H)] for k in range(4)])
    ax.add_collection3d(Poly3DCollection(faces, fc=SUBSTRATE, ec=SUBSTRATE_EDGE, lw=0.4, alpha=0.85, zorder=2))
    for net in ("P", "N"):
        ax.add_collection3d(Poly3DCollection([[(x, y, H) for x, y in g["copper"][net]]], fc=METAL, ec=METAL_EDGE,
                                             lw=0.3, zorder=4))
    for q in g["ports"]:
        y = q["y"]
        sheet = [(0, y - w / 2, 0), (0, y + w / 2, 0), (0, y + w / 2, H), (0, y - w / 2, H)]
        ax.add_collection3d(Poly3DCollection([sheet], fc=PORT, ec=PORT, lw=0.6, zorder=5))
    edges = []
    for k in range(4):
        edges.append([(*c[k], TOP), (*c[(k + 1) % 4], TOP)])
        edges.append([(*c[k], H), (*c[k], TOP)])
    ax.add_collection3d(Line3DCollection(edges, colors="#7C7F86", lw=0.45, linestyles=(0, (3, 2)), zorder=6))
    # a triad at the front corner, each arm 2.5 drawn units
    for (dx, dy, dz), lab in (((2.5, 0, 0), "x"), ((0, 2.5, 0), "y"), ((0, 0, 2.5), "z")):
        ax.quiver(x0, y0, 0, dx, dy, dz, color=INK, lw=0.6, arrow_length_ratio=0.3, zorder=9)
        ax.text(x0 + dx * 1.25, y0 + dy * 1.25, dz * 1.25, f"${lab}$", fontsize=b - 1, ha="center", va="center",
                zorder=10)
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, TOP, "Mur boundaries", fontsize=b - 1.5, ha="center", va="center",
            zorder=10)
    ax.text(x1, y0, -0.15 * TOP, "PEC floor", fontsize=b - 1.5, ha="left", va="top", zorder=10)
    # the port label sits in the empty air in front, with a leader to the near ports
    lx, lz = 6.5, H + 0.5 * TOP
    ax.plot([lx - 0.15, 0.0], [y0, -1.75], [lz - 0.02 * TOP, H * 1.1], color=PORT, lw=0.5, zorder=9)
    ax.text(lx, y0, lz, "lumped ports", fontsize=b - 1.5, ha="left", va="center", color=PORT, zorder=10)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_zlim(0, TOP)
    ax.set_box_aspect((x1 - x0, y1 - y0, TOP), zoom=1.0)
    ax.view_init(elev=24, azim=-58)
    ax.set_axis_off()
    save_cropped(fig, "fig_model3d")


# ------------------------------------------------------------------ the drawings

def _plane(ax, x0, x1, y, thick, below):
    """A return plane: a heavy line, hatched on the side away from the dielectric."""
    ax.add_patch(Rectangle((x0, y - thick if below else y), x1 - x0, thick, fc="white", ec="none",
                           hatch="//////", lw=0, zorder=2))
    ax.plot([x0, x1], [y, y], color=INK, lw=0.8, zorder=3)


def fig_xsec():
    """(a) The microstrip and (b) the stripline cross-section, both at true
    scale and at the same scale."""
    t = use()
    b = t["base"]
    plt.rcParams["hatch.linewidth"] = 0.35
    p = geometry.params()
    st = p["stackup"]
    h, w, s = st["dielectric_height"], p["pair"]["width"], p["pair"]["pitch"]
    tc = st["copper_thickness"]
    bs = p["stripline"]["plane_spacing"]
    xl, xr = -0.95, 0.95
    ya = (-0.07, h + 0.42)
    yb = (-0.07, bs + 0.07)
    W = t["single"]
    scale = W / (xr - xl)
    cap = 0.24                                       # inches for each panel's label
    ha_, hb_ = (ya[1] - ya[0]) * scale, (yb[1] - yb[0]) * scale
    Hh = ha_ + hb_ + 2 * cap + 0.08
    fig = plt.figure(figsize=(W, Hh))
    a1 = fig.add_axes([0, (hb_ + 2 * cap + 0.08) / Hh, 1, ha_ / Hh])
    a2 = fig.add_axes([0, cap / Hh, 1, hb_ / Hh])
    hat = 0.045

    def traces(ax, y0):
        for x, fc, lab in ((-s / 2, S.COPPER, "P"), (s / 2, S.TEAL, "N")):
            ax.add_patch(Rectangle((x - w / 2, y0), w, tc, fc=fc, ec=INK, lw=0.4, zorder=5))
            ax.plot([x, x], [y0 + tc + 0.015, y0 + tc + 0.06], color=INK, lw=0.3, zorder=6)
            ax.text(x, y0 - 0.025, lab, ha="center", va="top", fontsize=b - 0.5, style="italic", zorder=6)

    # (a) microstrip
    a1.add_patch(Rectangle((xl, 0), xr - xl, h, fc=DIELECTRIC, ec="none", zorder=1))
    _plane(a1, xl, xr, 0.0, hat, below=True)
    a1.plot([xl, xr], [h, h], color=INK, lw=0.4, zorder=3)
    traces(a1, h)
    top = h + tc
    ys_ = top + 0.27
    for x in (-s / 2, s / 2):
        ext(a1, x, top + 0.075, x, ys_ + 0.04)
    arrow(a1, (-s / 2, ys_), (s / 2, ys_))
    a1.text(0, ys_ + 0.025, rf"$s = {s:g}$", ha="center", va="bottom", fontsize=b - 1)
    yw = top + 0.09
    for x in (-s / 2 - w / 2, -s / 2 + w / 2):
        ext(a1, x, top + 0.015, x, yw + 0.035)
    arrow(a1, (-s / 2 - w / 2, yw), (-s / 2 + w / 2, yw))
    a1.text(-s / 2 - w / 2 - 0.03, yw, rf"$w = {w:g}$", ha="right", va="center", fontsize=b - 1)
    xh = xl + 0.1
    arrow(a1, (xh, 0.0), (xh, h))
    a1.text(xh + 0.04, h / 2, rf"$h = {h:g}$", ha="left", va="center", fontsize=b - 1)
    a1.annotate(rf"$t = {tc * 1000:g}\ \mu$m", (s / 2 + w / 2, h + tc * 0.6), (s / 2 + w / 2 + 0.1, h + 0.17),
                fontsize=b - 1, ha="left", va="center",
                arrowprops=dict(arrowstyle="-|>", lw=0.4, color=INK, mutation_scale=4, shrinkA=1, shrinkB=0))
    a1.text(xr - 0.04, h / 2, rf"$\varepsilon_r = {st['epsilon_r']:g}$, $\tan\delta = {st['loss_tangent']:g}$",
            ha="right", va="center", fontsize=b - 1)
    a1.text(xr - 0.04, h + 0.36, "air", ha="right", va="center", fontsize=b - 1, style="italic")
    a1.set_xlim(xl, xr)
    a1.set_ylim(*ya)
    bare(a1)

    # (b) stripline
    a2.add_patch(Rectangle((xl, 0), xr - xl, bs, fc=DIELECTRIC, ec="none", zorder=1))
    _plane(a2, xl, xr, 0.0, hat, below=True)
    _plane(a2, xl, xr, bs, hat, below=False)
    y0 = bs / 2 - tc / 2
    traces(a2, y0)
    arrow(a2, (xh, 0.0), (xh, bs))
    a2.text(xh + 0.04, bs * 0.78, rf"$b = {bs:g}$", ha="left", va="center", fontsize=b - 1)
    xb = xl + 0.42
    ext(a2, xb - 0.04, bs / 2, -s / 2 - w / 2 - 0.03, bs / 2)
    arrow(a2, (xb, 0.0), (xb, bs / 2))
    a2.text(xb + 0.04, bs / 4, r"$b/2$", ha="left", va="center", fontsize=b - 1)
    a2.text(xr - 0.04, bs * 0.22, rf"$\varepsilon_r = {st['epsilon_r']:g}$, $\tan\delta = {st['loss_tangent']:g}$",
            ha="right", va="center", fontsize=b - 1)
    a2.text(xr - 0.04, bs * 0.8, r"$w$, $s$, $t$ as in (a)", ha="right", va="center", fontsize=b - 1)
    a2.set_xlim(xl, xr)
    a2.set_ylim(*yb)
    bare(a2)
    fig.text(0.5, (hb_ + cap + 0.08 + 0.04) / Hh, "(a) Microstrip", ha="center", va="bottom", fontsize=b)
    fig.text(0.5, 0.04 / Hh, "(b) Stripline", ha="center", va="bottom", fontsize=b)
    S.save(fig, "fig_xsec", TARGET)


def fig_bend():
    """The U-bend of fixture B: centrelines, radii and pitch."""
    t = use()
    b = t["base"]
    p = geometry.params()
    R, s, L = p["fixture"]["bend_radius"], p["pair"]["pitch"], p["fixture"]["leg_length"]
    g = geometry.build("B", p)
    fig, ax, _ = drawing(t["single"], (L - 3.0, L + R + s + 1.9), (-(R + s) - 0.45, R + s + 0.45))
    for net, fc in (("P", P_LIGHT), ("N", N_LIGHT)):
        ax.add_patch(Polygon(g["copper"][net], closed=True, fc=fc, ec=INK, lw=0.45, zorder=2))
        centreline(ax, g["centreline"][net])
    cx = L
    # the centre, marked with a cross on its centre lines
    ax.plot([cx - 0.3, cx + 0.3], [0, 0], color=INK, lw=0.4, zorder=6)
    ax.plot([cx, cx], [-0.3, 0.3], color=INK, lw=0.4, zorder=6)
    ax.plot([cx - 2.9, cx - 0.45], [0, 0], color=INK, lw=0.3, dashes=DASHDOT, zorder=6)
    ax.plot([cx, cx], [-(R + s) - 0.35, -0.45], color=INK, lw=0.3, dashes=DASHDOT, zorder=6)
    ax.plot([cx, cx], [0.45, R + s + 0.35], color=INK, lw=0.3, dashes=DASHDOT, zorder=6)
    # R: arrow to P's centreline, label inside the bend
    a = math.radians(60)
    arrow(ax, (cx, 0), (cx + R * math.cos(a), R * math.sin(a)), both=False)
    ax.text(cx + 0.55 * R * math.cos(a) - 0.1, 0.55 * R * math.sin(a) + 0.05, rf"$R = {R:g}$", fontsize=b - 1,
            ha="right", va="center", zorder=9)
    # R + s: arrow to N's centreline, then a leader out past the copper to its label
    a = math.radians(-28)
    tip = (cx + (R + s) * math.cos(a), (R + s) * math.sin(a))
    arrow(ax, (cx, 0), tip, both=False)
    out_ = (cx + (R + s + 0.45) * math.cos(a), (R + s + 0.45) * math.sin(a))
    ext(ax, *tip, *out_)
    ext(ax, *out_, out_[0] + 0.25, out_[1])
    ax.text(out_[0] + 0.3, out_[1], rf"$R + s = {R + s:.3f}$", fontsize=b - 1, ha="left", va="center", zorder=9)
    # pitch, on the lower legs
    xd = L - 1.4
    arrow(ax, (xd, -R), (xd, -(R + s)))
    ax.text(xd - 0.1, -(R + s / 2), rf"$s = {s:g}$", fontsize=b - 1, ha="right", va="center")
    # arc lengths, at the arcs
    a = math.radians(-62)
    ax.text(cx + (R - 0.45) * math.cos(a), (R - 0.45) * math.sin(a), r"$\pi R$", fontsize=b - 1, ha="center",
            va="center", zorder=9)
    a = math.radians(40)
    ax.text(cx + (R + s + 0.3) * math.cos(a), (R + s + 0.3) * math.sin(a), r"$\pi (R + s)$", fontsize=b - 1,
            ha="left", va="bottom", zorder=9)
    ax.text(L - 2.95, R + s + 0.2, "N", fontsize=b - 0.5, style="italic", ha="left", va="bottom")
    ax.text(L - 2.95, R - 0.2, "P", fontsize=b - 0.5, style="italic", ha="left", va="top")
    S.save(fig, "fig_bend", TARGET)


def fig_excursion():
    """One tuning section (C, two excursions) with the symbols the text and the
    families table use. Detail X, in its own band below, shows a 45-degree
    corner chamfer at a larger scale."""
    t = use()
    b = t["base"]
    p = geometry.params()
    R, s, w, L = p["fixture"]["bend_radius"], p["pair"]["pitch"], p["pair"]["width"], p["fixture"]["leg_length"]
    c = p["tuning"]["chamfer"]
    g = geometry.build("C", p)
    tu = g["tuning"]
    A, top, bottom = tu["amplitude"], tu["top"], tu["bottom"]
    x_start, x_end = tu["section_start"], tu["section_end"]
    yP, yN = -R, -(R + s)
    x1 = x_start + c                     # the first rising leg's centreline
    x2 = x1 + top                        # its falling leg
    x3 = x2 + bottom                     # the second excursion's rising leg
    x4 = x3 + top
    ytop = yP + A
    yd = ytop + w / 2 + 0.3              # the chain dimension
    yrow = yN - w / 2 - 0.3              # tuning section and D
    band = 1.05                          # mm of height for detail X
    xlim = (x_start - 1.45, L + 0.55)
    ylim = (yrow - 0.3 - band, yd + 0.24)
    fig, ax, scale = drawing(t["single"], xlim, ylim)
    for net, fc in (("P", P_LIGHT), ("N", N_LIGHT)):
        ax.add_patch(Polygon(g["copper"][net], closed=True, fc=fc, ec=INK, lw=0.45, zorder=2))
        centreline(ax, g["centreline"][net], lw=0.35)
    for xa, xb, lab in ((x1, x2, r"$a$"), (x2, x3, r"$b$"), (x3, x4, r"$a$")):
        ext(ax, xa, ytop + w / 2 + 0.04, xa, yd + 0.05)
        ext(ax, xb, ytop + w / 2 + 0.04, xb, yd + 0.05)
        arrow(ax, (xa, yd), (xb, yd))
        ax.text((xa + xb) / 2, yd + 0.04, lab, ha="center", va="bottom", fontsize=b)
    # amplitude, between centrelines, left of the first excursion
    xa = x_start - 0.42
    ext(ax, xa - 0.08, ytop, x1 - 0.06, ytop)
    arrow(ax, (xa, yP), (xa, ytop))
    ax.text(xa - 0.06, (yP + ytop) / 2, r"$A$", ha="right", va="center", fontsize=b)
    # fold edge spacing, inside the first excursion
    yg = yP + A * 0.3
    arrow(ax, (x1 + w / 2, yg), (x2 - w / 2, yg))
    ax.text((x1 + x2) / 2, yg + 0.05, r"$g$", ha="center", va="bottom", fontsize=b)
    # pitch, between the excursions
    xs_ = (x2 + x3) / 2
    arrow(ax, (xs_, yN), (xs_, yP))
    ax.text(xs_ + 0.07, (yP + yN) / 2, r"$s$", ha="left", va="center", fontsize=b)
    # the tuning section and its distance to the bend, as a chain
    ext(ax, x_start, yP - w / 2 - 0.04, x_start, yrow - 0.05)
    ext(ax, x_end, yP - w / 2 - 0.04, x_end, yrow - 0.05)
    ext(ax, L, yN - w / 2 - 0.04, L, yrow - 0.05)
    arrow(ax, (x_start, yrow), (x_end, yrow))
    arrow(ax, (x_end, yrow), (L, yrow))
    ax.text((x_start + x_end) / 2, yrow - 0.05, "tuning section", ha="center", va="top", fontsize=b - 1.5,
            style="italic")
    ax.text((x_end + L) / 2, yrow - 0.05, r"$D$", ha="center", va="top", fontsize=b)
    ax.text(L + 0.06, yN + 0.17, "bend", ha="left", va="bottom", fontsize=b - 1.5, style="italic")
    ax.text(xlim[0] + 0.05, yP + w / 2 + 0.04, "P", ha="left", va="bottom", fontsize=b - 0.5, style="italic")
    ax.text(xlim[0] + 0.05, yN - w / 2 - 0.04, "N", ha="left", va="top", fontsize=b - 0.5, style="italic")
    # detail X: the first excursion's upper-left corner, in the band below
    cxy = (x1, ytop)
    ax.add_patch(Circle(cxy, 0.17, fc="none", ec=INK, lw=0.4, zorder=8))
    ax.text(cxy[0] - 0.14, cxy[1] + 0.14, "X", fontsize=b - 1, ha="right", va="bottom", style="italic")
    bx0, bx1 = x_start - 0.3, x_start + 1.0
    by0, by1 = ylim[0] + 0.06, ylim[0] + band - 0.05
    fw, fh = fig.get_size_inches()
    (px0, py0), (px1, py1) = ax.transData.transform((bx0, by0)), ax.transData.transform((bx1, by1))
    dpi = fig.dpi
    ins = fig.add_axes([px0 / dpi / fw, py0 / dpi / fh, (px1 - px0) / dpi / fw, (py1 - py0) / dpi / fh])
    half_w = 0.13
    mag = (bx1 - bx0) / (2 * half_w)
    MACROS["DetailScale"] = f"{mag:.0f}"
    half_h = (by1 - by0) / mag / 2
    ins.add_patch(Polygon(g["copper"]["P"], closed=True, fc=P_LIGHT, ec=INK, lw=0.6, zorder=2))
    centreline(ins, g["centreline"]["P"], lw=0.45)
    cx0, cy0 = cxy[0] + 0.0, cxy[1] - 0.03
    ins.set_xlim(cx0 - half_w, cx0 + half_w)
    ins.set_ylim(cy0 - half_h, cy0 + half_h)
    ins.set_xticks([])
    ins.set_yticks([])
    for sp in ins.spines.values():
        sp.set_linewidth(0.4)
    # the chamfer's two legs on the centreline, each c long, arrows from outside
    tail = 0.03
    yh = cxy[1] + 0.022
    ext(ins, x1, cxy[1] - c + 0.004, x1, yh + 0.008)
    ext(ins, x1 + c, cxy[1] + 0.004, x1 + c, yh + 0.008)
    arrow(ins, (x1 - tail, yh), (x1, yh), both=False, size=3.5)
    arrow(ins, (x1 + c + tail, yh), (x1 + c, yh), both=False, size=3.5)
    ins.text(x1 + c / 2, yh + 0.004, r"$c$", ha="center", va="bottom", fontsize=b - 1)
    xv = x1 - 0.035
    ext(ins, x1 - 0.004, cxy[1] - c, xv - 0.008, cxy[1] - c)
    ext(ins, x1 - 0.004, cxy[1], xv - 0.008, cxy[1])
    arrow(ins, (xv, cxy[1] - c - tail), (xv, cxy[1] - c), both=False, size=3.5)
    arrow(ins, (xv, cxy[1] + tail), (xv, cxy[1]), both=False, size=3.5)
    ins.text(xv - 0.008, cxy[1] - c / 2, r"$c$", ha="right", va="center", fontsize=b - 1)
    ax.text(bx1 + 0.12, (by0 + by1) / 2,
            f"Detail X ({mag:.0f}:1): the 45-degree\nchamfer cut at every corner.\nLengths are measured on\nthe centrelines.",
            fontsize=b - 1.5, ha="left", va="center", linespacing=1.2)
    S.save(fig, "fig_excursion", TARGET)


def fig_variants():
    """Every variant's model view at one scale: copper and ports on its share
    of the substrate, three to a row; A, twice as long as a bent fixture,
    takes the last row."""
    t = use()
    b = t["base"]
    p = geometry.params()
    w = p["pair"]["width"]
    rows = [[("B", "untuned U-bend"), ("C", "sparse excursions"), ("D", "dense accordion")],
            [("F", "broad trombone"), ("C_far", "C at the launch"), ("E", "pair-level control")],
            [("A", "straight reference, the U-bend's mean length")]]
    builds = {n: geometry.build(n, p) for row in rows for n, _ in row}
    pad = 0.5
    bent = [g for n, g in builds.items() if n != "A"]
    ux1 = max(x for g in bent for net in "PN" for x, _ in g["copper"][net]) + pad
    uy0 = min(y for g in bent for net in "PN" for _, y in g["copper"][net]) - pad
    uy1 = max(y for g in bent for net in "PN" for _, y in g["copper"][net]) + pad
    W = t["double"]
    gapx, lab, gapy = 0.12, 0.34, 0.06
    tile_w = (W - 2 * gapx) / 3
    scale = tile_w / (ux1 + pad)
    a = builds["A"]
    ax1 = max(x for net in "PN" for x, _ in a["copper"][net]) + pad
    ay0 = min(y for net in "PN" for _, y in a["copper"][net]) - pad
    ay1 = max(y for net in "PN" for _, y in a["copper"][net]) + pad
    h_a = (ay1 - ay0) * scale
    h_u = (uy1 - uy0) * scale
    lab_a = 0.2
    Hh = 2 * (h_u + lab + gapy) + h_a + lab_a
    fig = plt.figure(figsize=(W, Hh))
    letters = iter("abcdefg")
    y_cursor = Hh
    for row in rows:
        is_a = row[0][0] == "A"
        hrow = h_a if is_a else h_u
        y_cursor -= hrow
        for k, (name, desc) in enumerate(row):
            g = builds[name]
            if is_a:
                x0, x1, y0, y1 = -pad, ax1, ay0, ay1
                left = (W - (x1 - x0) * scale) / 2
            else:
                x0, x1, y0, y1 = -pad, ux1, uy0, uy1
                left = k * (tile_w + gapx)
            ax = fig.add_axes([left / W, y_cursor / Hh, (x1 - x0) * scale / W, hrow / Hh])
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=SUBSTRATE, ec=SUBSTRATE_EDGE, lw=0.5, zorder=1))
            metal(ax, g, lw=0.2)
            ports(ax, g, w, lw=1.3)
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            bare(ax)
            tun = g["tuning"]
            line1 = f"({next(letters)}) {name.replace('_', ' ')}: {desc}"
            dl = g["length"]["N_minus_P"]
            if "amplitude_nominal" in tun:
                line2 = rf"$N = {tun['excursions']}$, $A = {tun['amplitude']:.3f}$ mm"
            elif abs(dl) > 1e-6:
                line2 = rf"$L_N - L_P = {dl:.3f}$ mm"
            else:
                line2 = ""
            text = line1 if is_a else line1 + ("\n" + line2 if line2 else "")
            ax.text(0.5, -0.04 if not is_a else -0.12, text, transform=ax.transAxes, ha="center", va="top",
                    fontsize=b - 0.5, linespacing=1.25)
            if name == "B":
                for q in g["ports"][:2]:
                    ax.text(0.45, q["y"] + (0.4 if q["net"] == "P" else -0.42), q["net"], color=ON_SUBSTRATE,
                            fontsize=b - 2, style="italic", ha="left", va="center", zorder=6)
        y_cursor -= (lab_a if is_a else lab) + gapy
    S.save(fig, "fig_variants", TARGET)


def fig_flow():
    """The pipeline. The main chain runs left to right; the line model (Stage
    II) is a branch, calibrated on fixture A's mixed-mode parameters and
    read beside the full-wave results."""
    t = use()
    b = t["base"]
    runs = len(list((ROOT / "runs").glob("*/*/p*/provenance.json")))
    mono = S.MONO
    groups = [
        ("Geometry", [("Generator", "geometry.py", "solved lengths"),
                      ("DRC", "kicad-cli", "P–N clearance")]),
        ("Stage III: full wave", [("Model", "model.py", "graded mesh"),
                                  ("FDTD", "openEMS", f"{runs} runs"),
                                  ("S-parameters", "sparams.py", "4-port, checks")]),
        ("Post-processing", [("Mixed mode", "scikit-rf", "se2gmm"),
                             ("Metrics", "analysis.py", "skew, TDR, eye"),
                             ("Convergence", "convergence.py", "error bounds")]),
    ]
    W = t["double"]
    wb, hb, gap, ggap, gpad = 0.7, 0.5, 0.13, 0.26, 0.07
    n = sum(len(items) for _, items in groups)
    used = n * wb + (n - len(groups)) * gap + (len(groups) - 1) * ggap + 2 * gpad
    x = (W - used) / 2 + gpad
    y_top, head = 0.78, 0.2
    Hh = y_top + hb + head + 0.08
    fig = plt.figure(figsize=(W, Hh))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, Hh)
    bare(ax)
    boxes = {}

    def box(x, y, title, file, note):
        ax.add_patch(Rectangle((x, y), wb, hb, fc="white", ec=INK, lw=0.55, zorder=3))
        ax.text(x + wb / 2, y + hb * 0.76, title, ha="center", va="center", fontsize=b - 1, zorder=4)
        ax.text(x + wb / 2, y + hb * 0.47, file, ha="center", va="center", fontsize=b - 2, family=mono, zorder=4)
        ax.text(x + wb / 2, y + hb * 0.2, note, ha="center", va="center", fontsize=b - 2, color="#444444",
                zorder=4)
        boxes[file] = (x, y)

    def group(x0, x1, y0, y1, title, at="top"):
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#F4F4F4", ec="#8A8A8A", lw=0.45, ls=(0, (3, 2)),
                               zorder=1))
        if at == "top":
            ax.text(x0 + 0.05, y1 - 0.04, title, ha="left", va="top", fontsize=b - 1.5, style="italic", zorder=4)
        else:
            ax.text(x0 - 0.06, (y0 + y1) / 2, title, ha="right", va="center", fontsize=b - 1.5, style="italic",
                    zorder=4)

    chain = []
    for title, items in groups:
        gx0 = x - gpad
        for name, file, note in items:
            box(x, y_top, name, file, note)
            chain.append(file)
            x += wb + gap
        group(gx0, x - gap + gpad, y_top - gpad, y_top + hb + head, title)
        x += ggap - gap
    for a_, b_ in zip(chain, chain[1:]):
        (xa, ya), (xb, yb) = boxes[a_], boxes[b_]
        arrow(ax, (xa + wb, ya + hb / 2), (xb, yb + hb / 2), both=False, lw=0.5, size=5)
    # the line model, under the post-processing that it feeds
    xs, _ = boxes["scikit-rf"]
    xm = xs + (wb + gap) / 2
    box(xm, 0.1, "Line model", "mtl.py", "modes from A")
    group(xm - gpad, xm + wb + gpad, 0.1 - gpad, 0.1 + hb + gpad, "Stage II", at="left")
    xa_, ya_ = boxes["scikit-rf"]
    arrow(ax, (xa_ + wb * 0.3, ya_ - gpad), (xm + wb * 0.1, 0.1 + hb + gpad), both=False, lw=0.5, size=5)
    xb_, yb_ = boxes["analysis.py"]
    arrow(ax, (xm + wb * 0.9, 0.1 + hb + gpad), (xb_ + wb * 0.7, yb_ - gpad), both=False, lw=0.5, size=5)
    S.save(fig, "fig_flow", TARGET)


def main():
    fig_model()
    fig_model3d()
    fig_xsec()
    fig_bend()
    fig_excursion()
    fig_variants()
    fig_flow()
    gen = ROOT / "report" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    (gen / "diagrams.tex").write_text("% generated by scripts/fig_diagrams.py; do not edit\n"
                                      + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(MACROS.items())))
    print("ok")


if __name__ == "__main__":
    main()

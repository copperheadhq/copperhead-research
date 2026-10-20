"""Geometry figures, drawn from the copper polygons the EM model uses.

Run: python scripts/fig_geometry.py [report|blog]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402
import style as S  # noqa: E402

P_FILL, N_FILL = S.COPPER, S.TEAL


def copper(ax, g, alpha=0.9, lw=0):
    for net, colour in (("P", P_FILL), ("N", N_FILL)):
        ax.add_patch(Polygon(g["copper"][net], closed=True, facecolor=colour, edgecolor="none",
                             alpha=alpha, lw=lw, zorder=3))


def ports(ax, g, size, side_note=True):
    for q in g["ports"]:
        x, y = q["x"], q["y"]
        ax.plot([x], [y], marker="s", ms=size * 0.45, color=S.INK, zorder=5)
        dx = -0.35 if q["inward"] == 1 else 0.35
        ax.text(x + dx, y, str(q["number"]), ha="right" if dx < 0 else "left", va="center",
                fontsize=size, color=S.INK, fontweight="bold", zorder=6)


def scalebar(ax, x, y, length, size, label=None):
    ax.plot([x, x + length], [y, y], color=S.SOFT, lw=1.2, solid_capstyle="butt")
    for xx in (x, x + length):
        ax.plot([xx, xx], [y - 0.12, y + 0.12], color=S.SOFT, lw=1.0)
    ax.text(x + length / 2, y - 0.25, label or f"{length:g} mm", ha="center", va="top", fontsize=size,
            color=S.SOFT)


def bare(ax):
    ax.set_aspect("equal")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


# ------------------------------------------------------------------ figure 1

def fig_bend(target):
    t = S.use(target)
    p = geometry.params()
    R, s, w, L = p["fixture"]["bend_radius"], p["pair"]["pitch"], p["pair"]["width"], p["fixture"]["leg_length"]
    g = geometry.build("B", p)
    fig, ax = plt.subplots(figsize=(t["single"], t["single"] * 0.78))
    copper(ax, g, alpha=0.28)
    for net, colour in (("P", P_FILL), ("N", N_FILL)):
        xs, ys = zip(*g["centreline"][net])
        ax.plot(xs, ys, color=colour, lw=1.3, zorder=4)
    b = t["base"]
    # radii from the bend centre
    cx = L
    ax.plot([cx], [0], marker="+", color=S.INK, ms=6, zorder=6)
    for r, ang, colour in ((R, math.radians(35), P_FILL), (R + s, math.radians(-35), N_FILL)):
        ax.add_patch(FancyArrowPatch((cx, 0), (cx + r * math.cos(ang), r * math.sin(ang)), arrowstyle="-|>",
                                     mutation_scale=7, color=colour, lw=0.9, zorder=6))
    # radius labels to the left of the centre, clear of the copper
    ax.text(cx - 0.25, 0.32, f"R = {R:g} mm", fontsize=b - 1, color=S.INK, ha="right", va="center", zorder=7)
    ax.text(cx - 0.25, -0.32, f"R + s = {R + s:.3f} mm", fontsize=b - 1, color=S.INK, ha="right", va="center",
            zorder=7)
    # pitch dimension on the lower leg
    xd = L - 3.2
    ax.annotate("", (xd, -R), (xd, -(R + s)), arrowprops=dict(arrowstyle="<->", color=S.INK, lw=0.8,
                                                              shrinkA=0, shrinkB=0), zorder=6)
    ax.text(xd, -(R + s) - 0.3, "s = 0.508 mm (20 mil)", ha="center", va="top", fontsize=b - 1,
            color=S.INK)
    ax.text(L - 1.6, R + s + 0.55, "N, outer:  arc = π(R + s)", color=S.INK, fontsize=b - 1, ha="center")
    ax.text(L - 1.6, R - 0.55, "P, inner:  arc = πR", color=S.INK, fontsize=b - 1, ha="center")
    ax.text(L - 6.6, 0.0, "ΔL = π(R + s) − πR = πs\n= 1.596 mm = 62.8 mil\n(independent of R)",
            fontsize=b, color=S.INK, ha="left", va="center", fontweight="medium")
    ax.text(L - 6.6, -1.05, "analytical", fontsize=b - 1.5, color=S.NOTE, style="italic", ha="left")
    ax.set_xlim(L - 6.8, L + R + s + 0.6)
    ax.set_ylim(-(R + s) - 0.75, R + s + 0.95)
    bare(ax)
    S.save(fig, "fig_bend", target)


# ------------------------------------------------------------------ figure 2

TITLES = {
    "A": "A  straight reference",
    "B": "B  untuned U-bend",
    "C": "C  sparse, 2 excursions",
    "C_far": "C far  sparse, at the launch",
    "D": "D  dense accordion, 4 excursions",
    "E": "E  pair-level excursion (control)",
    "F": "F  one broad trombone",
}


def _placed(ax, g, dx, dy, alpha=0.95):
    for net, colour in (("P", P_FILL), ("N", N_FILL)):
        pts = [(x + dx, y + dy) for x, y in g["copper"][net]]
        ax.add_patch(Polygon(pts, closed=True, facecolor=colour, edgecolor="none", alpha=alpha, zorder=3))
    for q in g["ports"]:
        ax.plot([q["x"] + dx], [q["y"] + dy], marker="s", ms=2.6, color=S.INK, zorder=5)


def fig_families(target):
    """Every variant at one scale, in one set of axes."""
    t = S.use(target)
    b = t["base"]
    col = 18.5            # mm between the two columns
    row = 7.4             # mm between rows
    place = {"A": (0, 0), "B": (0, 1), "C": (1, 1), "D": (0, 2), "F": (1, 2), "C_far": (0, 3), "E": (1, 3)}
    fig, ax = plt.subplots(figsize=(t["double"], t["double"] * 0.78))
    for name, (c, r) in place.items():
        g = geometry.build(name)
        dx, dy = c * col, -r * row - (0.0 if name != "A" else -1.6)
        _placed(ax, g, dx, dy)
        ymax = max(y for net in ("P", "N") for _, y in g["copper"][net]) + dy
        ax.text(dx - 0.6, ymax + 1.15, TITLES[name], fontsize=b, fontweight="bold", color=S.INK, va="bottom")
        dl = g["length"]["N_minus_P"]
        note = "N − P = 0 mm" if abs(dl) < 1e-6 else f"N − P = {dl:+.3f} mm"
        tun = g["tuning"]
        if "amplitude_nominal" in tun:
            note += f",  A = {tun['amplitude']:.3f} mm"
        ax.text(dx - 0.6, ymax + 0.35, note, fontsize=b - 1.5, color=S.NOTE, va="bottom", family="IBM Plex Mono")
    # key and scale
    kx, ky = 0.0 * col, -3.0 * row - 5.6
    scalebar(ax, kx, ky + 0.6, 5.0, b - 1)
    ax.add_patch(Rectangle((kx + 7.5, ky + 0.35), 1.2, 0.5, color=P_FILL))
    ax.text(kx + 9.0, ky + 0.6, "P, the inner trace of the bend", va="center", fontsize=b - 1, color=S.SOFT)
    ax.add_patch(Rectangle((kx + 22.0, ky + 0.35), 1.2, 0.5, color=N_FILL))
    ax.text(kx + 23.5, ky + 0.6, "N, the outer trace", va="center", fontsize=b - 1, color=S.SOFT)
    ax.plot([kx + 7.5 + 0.6], [ky - 0.6], marker="s", ms=2.6, color=S.INK)
    ax.text(kx + 9.0, ky - 0.6, "50 Ω lumped port (numbering in the port figure)", va="center",
            fontsize=b - 1, color=S.SOFT)
    ax.set_xlim(-1.5, col + 16.0)
    ax.set_ylim(ky - 1.6, 1.6 + 2.6)
    bare(ax)
    S.save(fig, "fig_families", target)


def fig_tuning_zoom(target):
    t = S.use(target)
    b = t["base"]
    fig, axes = plt.subplots(2, 3, figsize=(t["double"], t["double"] * 0.36),
                             gridspec_kw={"hspace": 0.35, "wspace": 0.05})
    for ax, name in zip(axes.ravel(), ["B", "C", "D", "F", "E", "C_far"]):
        g = geometry.build(name)
        copper(ax, g)
        bare(ax)
        if name == "C_far":
            x0 = 0.4
        else:
            x0 = 7.1
        ax.set_xlim(x0, x0 + 5.2)
        ax.set_ylim(-3.3, -0.25)
        ax.set_title(TITLES[name], fontsize=b - 0.5, pad=2)
        if name == "B":
            scalebar(ax, x0 + 0.3, -0.75, 1.0, b - 1.5)
    S.save(fig, "fig_tuning_zoom", target)


# ------------------------------------------------------------------ figure 3

def fig_ports(target):
    t = S.use(target)
    b = t["base"]
    p = geometry.params()
    h, w, s = p["stackup"]["dielectric_height"], p["pair"]["width"], p["pair"]["pitch"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(t["double"], t["double"] * 0.30),
                                   gridspec_kw={"width_ratios": [1.0, 1.35], "wspace": 0.08})
    # cross-section, in units of mm, drawn at its true aspect
    xs = 0.95
    ax1.add_patch(Rectangle((-xs, -0.035), 2 * xs, 0.035, color=S.PLANE, zorder=2))
    ax1.add_patch(Rectangle((-xs, 0.0), 2 * xs, h, color=S.DIELECTRIC, ec=S.AXES, lw=0.5, zorder=1))
    tc = 0.035
    for x, colour, lab in ((-s / 2, P_FILL, "P"), (s / 2, N_FILL, "N")):
        ax1.add_patch(Rectangle((x - w / 2, h), w, tc, color=colour, zorder=3))
        ax1.text(x, h + tc + 0.03, lab, ha="center", va="bottom", fontsize=b, fontweight="bold", color=S.INK)
    ax1.annotate("", (-s / 2, h + 0.27), (s / 2, h + 0.27),
                 arrowprops=dict(arrowstyle="<->", lw=0.7, color=S.INK, shrinkA=0, shrinkB=0))
    ax1.text(0, h + 0.29, "s 0.508", ha="center", va="bottom", fontsize=b - 1.5, color=S.INK)
    ax1.annotate("", (s / 2 - w / 2, h - 0.07), (s / 2 + w / 2, h - 0.07),
                 arrowprops=dict(arrowstyle="<->", lw=0.6, color=S.INK, shrinkA=0, shrinkB=0))
    ax1.text(s / 2 + w / 2 + 0.03, h - 0.07, "w 0.25", ha="left", va="center", fontsize=b - 1.5, color=S.INK)
    ax1.annotate("", (-0.82, 0), (-0.82, h), arrowprops=dict(arrowstyle="<->", lw=0.6, color=S.INK,
                                                           shrinkA=0, shrinkB=0))
    ax1.text(-0.78, h / 2, "h 0.2", ha="left", va="center", fontsize=b - 1.5, color=S.INK)
    notes = ["air above, 2.5 mm to the boundary", "copper 35 µm, σ 58 MS/m",
             "dielectric εr 4.3, tan δ 0.02 at 5 GHz", "return plane: the PEC floor"]
    for k, line in enumerate(notes):
        ax1.text(-xs, -0.1 - 0.085 * k, line, ha="left", va="top", fontsize=b - 2, color=S.SOFT)
    ax1.set_xlim(-xs, xs)
    ax1.set_ylim(-0.48, h + 0.45)
    bare(ax1)
    ax1.set_title("Cross-section (mm), true scale", fontsize=b, pad=2)
    # plan view of fixture B with the four ports
    g = geometry.build("B", p)
    ax2.add_patch(Rectangle((-0.8, -3.0), 16.0, 6.0, color=S.PLANE, alpha=0.35, zorder=1))
    copper(ax2, g)
    ports(ax2, g, b - 1)
    labels = {1: "P near", 2: "N near", 3: "P far", 4: "N far"}
    for q in g["ports"]:
        ax2.text(-1.45, q["y"], labels[q["number"]], ha="right", va="center", fontsize=b - 2, color=S.SOFT)
    ax2.text(5.6, 0.0, "in: ports 1, 2   out: ports 3, 4\nse2gmm(p=2): d1 d2 c1 c2",
             ha="center", va="center", fontsize=b - 2.2, color=S.SOFT, family="IBM Plex Mono", linespacing=1.4)
    ax2.text(14.9, -2.85, "return plane under the whole fixture", ha="right", va="bottom", fontsize=b - 2,
             color=S.SOFT)
    ax2.set_xlim(-4.6, 15.4)
    ax2.set_ylim(-3.1, 3.1)
    bare(ax2)
    ax2.set_title("Plan view of B, launch plane at x = 0", fontsize=b, pad=2)
    S.save(fig, "fig_ports", target)


# ------------------------------------------------------------------ figure 4

def fig_pipeline(target):
    t = S.use(target)
    b = t["base"]
    steps = [
        ("geometry.py", "centrelines, solved\nlengths, polygons"),
        ("KiCad 10 DRC", "clearance check\n(kicad-cli)"),
        ("model.py", "openEMS XML,\nshared mesh"),
        ("openEMS", "4 runs per variant,\n1 port excited"),
        ("sparams.py", "power waves to\n4-port .s4p"),
        ("scikit-rf", "se2gmm(p=2)\nmixed mode"),
        ("analysis.py", "skew, TDR, Vc,\neye, η"),
        ("convergence", "3 meshes,\nerror bound"),
    ]
    fig, ax = plt.subplots(figsize=(t["double"], t["double"] * 0.17))
    n = len(steps)
    wbox, gap = 1.12, 0.2
    for i, (head, body) in enumerate(steps):
        x = i * (wbox + gap)
        ax.add_patch(FancyBboxPatch((x, 0), wbox, 1.0, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="white", ec=S.AXES, lw=0.8))
        ax.add_patch(Rectangle((x, 0.93), wbox, 0.07, color=S.COPPER, lw=0))
        ax.text(x + wbox / 2, 0.70, head, ha="center", va="center", fontsize=b - (2.2 if target == "report" else 1),
                color=S.INK, family="IBM Plex Mono", fontweight="medium")
        ax.text(x + wbox / 2, 0.33, body, ha="center", va="center", fontsize=b - (2.6 if target == "report" else 2.2),
                color=S.SOFT, linespacing=1.15)
        if i < n - 1:
            ax.annotate("", (x + wbox + gap - 0.03, 0.5), (x + wbox + 0.03, 0.5),
                        arrowprops=dict(arrowstyle="-|>", color=S.SOFT, lw=0.8, mutation_scale=7))
    ax.set_xlim(-0.05, n * (wbox + gap) - gap + 0.05)
    ax.set_ylim(-0.05, 1.05)
    bare(ax)
    ax.set_aspect("auto")
    S.save(fig, "fig_pipeline", target)


if __name__ == "__main__":
    targets = sys.argv[1:] or ["report", "blog"]
    for tg in targets:
        fig_bend(tg)
        fig_families(tg)
        fig_tuning_zoom(tg)
        fig_ports(tg)
        fig_pipeline(tg)
    print("ok")

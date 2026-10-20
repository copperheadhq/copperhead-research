"""The explainer video for the meander study, in the three shapes fang's
site/social/make.py draws its videos in, from the scene script in
/home/animesh/fang/renders/diffpair-meanders/video/script.md (revision 2).

    python scripts/video.py [--make PATH] [--stills DIR] [--only SHAPE] [--shots 3,8]

It draws with make.py's pieces (the page, the head, the title and closing
cards, the colours and type, the encoder), loaded from --make, as
site/social/decoupling.py does. Every number on it comes from this study's
runs: build/results/results.json, the four-ports in build/sparams/ (waveforms,
eyes, TDR and the skew against frequency are computed from them as the frames
are drawn), the copper from geometry.py and the solver's grid from model.py.
Nothing is typed in by hand.

Revision 2 draws the figures as scientific figures (the explainer-video
skill's section 3): titled axes with numbered ticks, every result with its
numerical bound, equations set as mathematics with matplotlib's mathtext,
dimensioned engineering drawings drawn with matplotlib from the solver's
polygons, the solver's own model view (substrate, metal, ports, mesh, a 3D
view), a source line on every result, leader labels in clear space and
labels that fade in. Scenes 2 and 3 are illustrations, not runs, and say so.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import io
import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
from matplotlib.patches import Polygon as MPolygon  # noqa: E402
from matplotlib.patches import Rectangle as MRect  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FANG = Path("/home/animesh/fang")
OUT = FANG / "renders" / "diffpair-meanders" / "video"
sys.path.insert(0, str(HERE))
import analysis as an  # noqa: E402
import geometry  # noqa: E402
import model  # noqa: E402

for _f in sorted((ROOT / "fonts").glob("*.ttf")) + sorted((ROOT / "fonts").glob("*.otf")):
    font_manager.fontManager.addfont(str(_f))
#: Words in the drawings are Inter, as on the cards; mathematics is Computer Modern.
MPL = {"font.family": "Inter", "mathtext.fontset": "cm", "lines.scale_dashes": False,
       "hatch.linewidth": 0.5, "axes.unicode_minus": True}
plt.rcParams.update(MPL)

MU, NB, MINUS, PM = "µ", "\u00a0", "−", "±"

#: The video's title, in the form of the user's other videos (the user asked
#: for the fang prefix on 2026-10-19).
TITLE = ("Fang", "Simulating Serpentine Length Matching")

#: A sweep plays for this long behind its cursor.
SWEEP = 2.6

#: Grey for a reading that a later one replaces, and the tints behind a part
#: a scene is about (copper's, and teal's for N).
OLD, GLOW, TINT, TEAL_GLOW = "#a9a9b2", "#ecd3b8", "#e9c9a6", "#bfe3e8"

#: The solver's view: the domain, the metal, the lumped ports.
SUBSTRATE, SUBSTRATE_EDGE, METAL, METAL_EDGE, PORT_RED = "#2D6A49", "#173B28", "#E9B949", "#6E5210", "#D7362B"
DIELECTRIC = "#EEF0E2"

#: The edge every time-domain scene uses (10 to 90 %), and the one window all
#: three scopes share, in ps.
EDGE, SCOPE = 50e-12, (125.0, 225.0)

#: The height the air box above the board is drawn, in the 3D view's z units
#: (the slab is 0.8 there, 4 times its 0.2 mm): shorter than its 2.5 mm at
#: that scale, and broken on its edges to say so.
AIR_DRAWN = 2.6

#: Frames over which a scene's end labels fade in.
FADE_IN = 9

#: Dash-dot for centrelines, in points.
DASHDOT = (5.0, 1.6, 1.2, 1.6)


def nb(text: str) -> str:
    """A number and its unit stay on one line."""
    import re
    return re.sub(r"(\d) (?=[A-Za-zµ%±])", "\\1" + NB, text)


def grouped(digits: str) -> str:
    """29000000000 as 29 000 000 000."""
    out = ""
    for i, ch in enumerate(reversed(digits)):
        if i and i % 3 == 0:
            out = NB + out
        out = ch + out
    return out


def ease(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 2


def clamp(u: float) -> float:
    return min(max(u, 0.0), 1.0)


def ps(v: float, unc: float | None = None) -> str:
    """A skew as the video writes it, with its bound when there is one."""
    s = f"{v:.2f}" if abs(v) < 1 else f"{v:.1f}"
    if unc is not None:
        s += f" {PM} {unc:.2f}" if unc < 0.1 else f" {PM} {unc:.1f}"
    return s


# --------------------------------------------------------------------------
# The runs
# --------------------------------------------------------------------------


class Runs:
    """What the video reads from the study."""

    def __init__(self):
        self.r = json.loads((ROOT / "build" / "results" / "results.json").read_text())
        self.V = self.r["variants"]
        self.p = geometry.params()
        prov = json.loads((ROOT / "runs" / "medium" / "B" / "p1" / "provenance.json").read_text())
        self.version = ".".join(prov["solver_version"].lstrip("v").split(".")[:2])
        self.cells = prov["cells"]
        self.runs = len(list((ROOT / "runs").glob("*/*/p*/provenance.json")))
        self.geo = {v: geometry.build(v, self.p) for v in ("A", "B", "C", "C_far", "D", "F", "S_loose",
                                                             "S_tight")}
        self.wave = {v: self._waves(v) for v in ("A", "B", "D", "F", "F_cal")}
        self.eyes = {v: self._eye(v) for v in ("A", "B")}
        self.fd = {v: self._fd(v) for v in ("C", "C_far")}
        self.tdr = {v: self._tdr(v) for v in ("B", "F")}
        self.mesh = model.mesh("U", "medium", self.p)

    def _waves(self, v):
        w = an.waveforms(an.load("medium", v), EDGE)
        t = w["t"] * 1e12
        keep = (t > -50) & (t < 400)
        return {k: (w[k][keep]).tolist() for k in ("p_far", "n_far", "vc_far", "vd_far")} | {
            "t": t[keep].tolist()}

    def _eye(self, v):
        e = an.eye(an.load("medium", v), 16e9, 35e-12)
        t, d, c, ui = e["t"], e["vd"], e["vc"], e["ui"]
        dt = t[1] - t[0]
        td = self.V[v]["timing"]["35"]["t50_d"] * 1e-12
        per = int(round(ui / dt))
        n0 = int(round((16 * ui + td - ui / 2 - t[0]) / dt))
        traces = []
        for j in range(16, 230):
            s0 = n0 + (j - 16) * per
            seg = d[s0: s0 + 2 * per]
            if seg.size == 2 * per:
                traces.append(seg[::5].tolist())
        x = (np.arange(0, 2 * per, 5) * dt / ui).tolist()          # in UI
        vc_t = ((t[n0: n0 + 40 * per] - t[n0]) * 1e9)[::4].tolist()  # in ns
        vc = (c[n0: n0 + 40 * per] * 1000)[::4].tolist()
        return {"x": x, "traces": traces, "ui_ps": ui * 1e12, "vc_t": vc_t, "vc": vc,
                "height": e["eye_height_rel"] * 100, "vc_pp": e["vc_pp_rel"] * 100}

    def _fd(self, v):
        m = an.mixed(an.load("medium", v))
        f = m.f
        r = np.abs(m.s[:, 3, 0]) / np.abs(m.s[:, 1, 0])
        tau = 2 * np.arctan(r) / (2 * np.pi * np.maximum(f, 1)) * 1e12
        keep = (f >= 1e9) & (f <= 30e9)
        return (f[keep] / 1e9).tolist(), tau[keep].tolist()

    def _tdr(self, v):
        t, rho, z = an.tdr(an.mixed(an.load("medium", v)), 35e-12)
        keep = (t > -10e-12) & (t < 400e-12)
        return (t[keep] * 1e12).tolist(), z[keep].tolist()

    # -- numbers ---------------------------------------------------------------

    def skew(self, v, rise="50"):
        return self.V[v]["timing"][rise]["skew"]

    def unc(self, v):
        return self.V[v].get("uncertainty_ps")

    def t50(self, v, which):
        return self.V[v]["timing"]["50"][which]

    def removed(self, v, ref="B"):
        return (1 - self.skew(v) / self.skew(ref)) * 100

    def vc_peak(self, v):
        return max(self.wave[v]["vc_far"]) * 1000

    def eta(self, v):
        return self.V[v]["timing"]["50"]["eta"]


# --------------------------------------------------------------------------
# Drawing pieces: the page's own (PIL) and matplotlib's
# --------------------------------------------------------------------------


class Board:
    """The study's copper, in millimetres, fitted into a box at one scale and
    drawn on a layer of its own, so a close-up cannot spill out of its box."""

    def __init__(self, M, p, box, xr, yr, k=None, bg=None):
        self.M, self.p = M, p
        x0, y0, x1, y1 = box
        fit = min((x1 - x0) / (xr[1] - xr[0]), (y1 - y0) / (yr[1] - yr[0]))
        self.k = fit if k is None else min(k, fit)
        w, h = (xr[1] - xr[0]) * self.k, (yr[1] - yr[0]) * self.k
        self.x0, self.y0 = x0 + ((x1 - x0) - w) / 2, y0 + ((y1 - y0) - h) / 2
        self.x1, self.y1 = self.x0 + w, self.y0 + h
        self.xr, self.yr = xr, yr
        self.layer = Image.new("RGB", (max(1, round(w * p.ss)), max(1, round(h * p.ss))), bg or M.CARD)
        self.draw = ImageDraw.Draw(self.layer)

    def P(self, x, y):
        return self.x0 + (x - self.xr[0]) * self.k, self.y0 + (self.yr[1] - y) * self.k

    def L(self, x, y):
        px, py = self.P(x, y)
        return (px - self.x0) * self.p.ss, (py - self.y0) * self.p.ss

    def poly(self, pts, fill):
        self.draw.polygon([self.L(*q) for q in pts], fill=fill)

    def line(self, pts, fill, width):
        if len(pts) > 1:
            self.M.brand.stroke(self.draw, [self.L(*q) for q in pts], width * self.p.ss, fill)

    def dashed(self, pts, fill, width, dash=6.0, gap=5.0):
        """A dashed polyline, `dash` and `gap` in page pixels."""
        segs = []
        for a, b in zip(pts, pts[1:]):
            segs.append((a, b, math.dist(self.P(*a), self.P(*b))))
        on, left, cur = True, dash, []
        for a, b, d in segs:
            pos = 0.0
            while pos < d - 1e-9:
                step = min(left, d - pos)
                u0, u1 = pos / d, (pos + step) / d
                pa = (a[0] + (b[0] - a[0]) * u0, a[1] + (b[1] - a[1]) * u0)
                pb = (a[0] + (b[0] - a[0]) * u1, a[1] + (b[1] - a[1]) * u1)
                if on:
                    if not cur:
                        cur = [pa]
                    cur.append(pb)
                pos += step
                left -= step
                if left <= 1e-9:
                    if on and cur:
                        self.line(cur, fill, width)
                        cur = []
                    on = not on
                    left = dash if on else gap
        if on and cur:
            self.line(cur, fill, width)

    def box(self, a, b, fill, radius=0.0):
        (ax, ay), (bx, by) = self.L(*a), self.L(*b)
        self.draw.rounded_rectangle((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)),
                                    radius=radius * self.p.ss, fill=fill)

    def glow(self, x0, y0, x1, y1, pad=0.22):
        self.box((x0 - pad, y0 - pad), (x1 + pad, y1 + pad), GLOW, radius=6)

    def copper(self, g, pc=None, nc=None):
        self.poly(g["copper"]["N"], nc or self.M.TEAL)
        self.poly(g["copper"]["P"], pc or self.M.COPPER)

    def paste(self):
        if self.p.drawing:
            self.p.image.paste(self.layer, (round(self.x0 * self.p.ss), round(self.y0 * self.p.ss)))


def partial(pts, u):
    """The first fraction u of a polyline, by length."""
    if u >= 1:
        return pts
    lengths = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    total, goal, out = sum(lengths), sum(lengths) * max(u, 0.0), [pts[0]]
    for (a, b), d in zip(zip(pts, pts[1:]), lengths):
        if goal <= d:
            if d > 0:
                out.append((a[0] + (b[0] - a[0]) * goal / d, a[1] + (b[1] - a[1]) * goal / d))
            return out
        out.append(b)
        goal -= d
    return out


def arrowhead(p, tip, tail, colour, size):
    """A filled arrowhead at `tip`, pointing away from `tail`, `size` long."""
    if not p.drawing:
        return
    (tx, ty), (sx, sy) = tip, tail
    ang = math.atan2(ty - sy, tx - sx)
    pts = [tip]
    for da in (math.pi - 0.38, math.pi + 0.38):
        pts.append((tx + size * math.cos(ang + da), ty + size * math.sin(ang + da)))
    p.draw.polygon([(x * p.ss, y * p.ss) for x, y in pts], fill=colour)


def arrow(p, a, b, colour, width=1.8, size=9.0, both=True):
    """A dimension or pointer arrow in page pixels; `both` puts a head at each end."""
    d = math.dist(a, b)
    if d < 1e-6:
        return
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    s0 = size * 0.7 if both else 0.0
    p.line([(a[0] + ux * s0, a[1] + uy * s0), (b[0] - ux * size * 0.7, b[1] - uy * size * 0.7)], colour, width)
    arrowhead(p, b, a, colour, size)
    if both:
        arrowhead(p, a, b, colour, size)


_MATH: dict = {}


def math_image(tex: str, px: float, ss: float, colour: str) -> Image.Image:
    """`tex` set by matplotlib's mathtext, an em `px` page pixels tall, on a
    transparent ground cut to the ink."""
    key = (tex, round(px, 3), ss, colour)
    if key not in _MATH:
        with plt.rc_context(MPL):
            fig = plt.figure(figsize=(4, 1), dpi=100)
            fig.patch.set_alpha(0)
            fig.text(0.0, 0.5, tex, fontsize=px * ss * 0.72, color=colour, va="center")
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100, transparent=True, bbox_inches="tight", pad_inches=0.06)
            plt.close(fig)
        img = Image.open(io.BytesIO(buf.getvalue())).convert("RGBA")
        _MATH[key] = img.crop(img.getchannel("A").getbbox())
    return _MATH[key]


def put_math(p, x, y, tex, px, colour, anchor="lm", rotate=False):
    """Paste a formula at (x, y) by `anchor` (l/m/r then t/m/b); returns its
    width and height in page pixels."""
    img = math_image(tex, px, p.ss, colour)
    if rotate:
        img = img.rotate(90, expand=True)
    w, h = img.width / p.ss, img.height / p.ss
    ax = {"l": 0.0, "m": 0.5, "r": 1.0}[anchor[0]]
    ay = {"t": 0.0, "m": 0.5, "b": 1.0}[anchor[1]]
    if p.drawing:
        p.image.paste(img, (round((x - w * ax) * p.ss), round((y - h * ay) * p.ss)), img)
    return w, h


class Drawing:
    """A matplotlib drawing in millimetres, fitted into a box on the page at
    one scale and rendered on a transparent ground at the page's
    supersampling, so a glow drawn first on the card shows round the copper.
    Sizes are page pixels: a font of `px` page pixels is `px * 0.72` points at
    the dpi used here."""

    def __init__(self, p, box, xr, yr, k=None, halign="c", valign="c"):
        x0, y0, x1, y1 = box
        fit = min((x1 - x0) / (xr[1] - xr[0]), (y1 - y0) / (yr[1] - yr[0]))
        self.k = fit if k is None else min(k, fit)
        self.w, self.h = (xr[1] - xr[0]) * self.k, (yr[1] - yr[0]) * self.k
        self.x0 = {"c": x0 + ((x1 - x0) - self.w) / 2, "l": x0, "r": x1 - self.w}[halign]
        self.y0 = {"c": y0 + ((y1 - y0) - self.h) / 2, "t": y0, "b": y1 - self.h}[valign]
        self.p, self.xr, self.yr = p, xr, yr
        self.fig = plt.figure(figsize=(self.w / 100, self.h / 100), dpi=100 * p.ss)
        self.fig.patch.set_alpha(0)
        ax = self.fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(*xr)
        ax.set_ylim(*yr)
        ax.set_axis_off()
        ax.patch.set_alpha(0)
        self.ax = ax

    def P(self, x, y):
        return self.x0 + (x - self.xr[0]) * self.k, self.y0 + (self.yr[1] - y) * self.k

    def mm(self, px):
        return px / self.k

    def poly(self, pts, fc, ec=None, lw=1.2, z=2, alpha=1.0):
        self.ax.add_patch(MPolygon(pts, closed=True, fc=fc, ec=ec or "none", lw=lw * 0.72, joinstyle="miter",
                                   zorder=z, alpha=alpha))

    def rect(self, x, y, w, h, fc, ec=None, lw=0.0, z=1, hatch=None):
        self.ax.add_patch(MRect((x, y), w, h, fc=fc, ec=ec or "none", lw=lw * 0.72, hatch=hatch, zorder=z))

    def line(self, pts, colour, lw=1.2, dashes=None, z=5):
        xs, ys = zip(*pts)
        kw = {"dashes": dashes} if dashes else {}
        self.ax.plot(xs, ys, color=colour, lw=lw * 0.72, solid_capstyle="butt", zorder=z, **kw)

    def centre(self, pts, colour="#0a0a0a", lw=1.0, z=6):
        self.line(pts, colour, lw, DASHDOT, z)

    def arrow(self, a, b, both=True, lw=1.4, head=9.0, colour="#0a0a0a", z=8):
        style = "<|-|>" if both else "-|>"
        self.ax.add_patch(FancyArrowPatch(a, b, arrowstyle=f"{style},head_length=0.5,head_width=0.2",
                                          mutation_scale=head * 0.72 / 0.5, lw=lw * 0.72, color=colour,
                                          shrinkA=0, shrinkB=0, zorder=z, joinstyle="miter", capstyle="butt"))

    def text(self, x, y, s, px, ha="center", va="center", weight=560, colour="#0a0a0a", z=9, bg=None,
             style="normal"):
        self.ax.text(x, y, s, fontsize=px * 0.72, ha=ha, va=va, fontweight=weight, color=colour, zorder=z,
                     fontstyle=style, bbox=dict(fc=bg, ec="none", pad=1.5) if bg else None)

    def dim(self, a, b, label, px, off, *, tside=1, tgap=0.5, ext_from=None, colour="#0a0a0a", ha=None,
            rotate=False):
        """A dimension between feature points a and b: extension lines from the
        features, an arrowed line `off` mm along the left normal of a to b, and
        its label `tgap` font heights beyond it (`tside` -1 puts it inside)."""
        (x1, y1), (x2, y2) = a, b
        d = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / d, (y2 - y1) / d
        nx, ny = -uy, ux
        pa, pb = (x1 + nx * off, y1 + ny * off), (x2 + nx * off, y2 + ny * off)
        gap, over = self.mm(3), self.mm(4)
        sg = 1 if off >= 0 else -1
        if off:
            for (fx, fy), (qx, qy) in zip(ext_from or (a, b), (pa, pb)):
                self.line([(fx + nx * gap * sg, fy + ny * gap * sg), (qx + nx * over * sg, qy + ny * over * sg)],
                          colour, 0.9, z=7)
        self.arrow(pa, pb, colour=colour)
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        t = self.mm(px * tgap) + self.mm(px * 0.5)
        s = sg * tside
        tx, ty = mx + nx * t * s, my + ny * t * s
        self.text(tx, ty, label, px, ha=ha or "center", va="center", colour=colour)

    def render(self) -> Image.Image:
        self.fig.canvas.draw()
        img = Image.fromarray(np.asarray(self.fig.canvas.buffer_rgba()).copy(), "RGBA")
        plt.close(self.fig)
        return img

    def paste(self, img=None):
        img = img or self.render()
        if self.p.drawing:
            self.p.image.paste(img, (round(self.x0 * self.p.ss), round(self.y0 * self.p.ss)), img)
        return img


class Plot:
    """A chart: both axes with numbered ticks and a title with its unit, drawn
    once; series drawn up to a cursor on each frame (a min and max per
    column, as decoupling's Plot does). Tick lists are (value, text)."""

    def __init__(self, M, p, box, x0, x1, y0, y1, xticks, yticks, xtitle=None, ytitle=None, *,
                 ytitle_math=False, xtitle_math=False, grid=True, xlabels=True, spines=True):
        self.M, self.p = M, p
        t = p.type
        n = t.note
        bx0, by0, bx1, by1 = box
        wl = max((p.width_of(nb(lab), "sans", n) for _, lab in yticks), default=0)
        ytw = n * 1.55 if ytitle else 0
        self.left, self.right = bx0 + ytw + wl + 10, bx1 - 6
        self.top = by0 + n * 0.55
        self.bottom = by1 - (n * 1.45 if xticks and xlabels else 2) - (n * 1.55 if xtitle else 0)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        for v, lab in yticks:
            y = self.Y(v)
            if grid:
                p.rect((self.left, y - 0.5, self.right, y + 0.5), fill=M.GRID)
            p.rect((self.left - 5, y - 0.75, self.left, y + 0.75), fill=M.AXIS)
            p.text(self.left - 9, y + n * 0.36, nb(lab.replace("-", MINUS)), "sans", n, M.NOTE, anchor="rs")
        for v, lab in xticks:
            x = self.X(v)
            p.rect((x - 0.75, self.bottom, x + 0.75, self.bottom + 5), fill=M.AXIS)
            if xlabels:
                w = p.width_of(nb(lab), "sans", n)
                cx = min(max(x, bx0 + w / 2), bx1 - w / 2)
                p.text(cx, self.bottom + n * 1.25, nb(lab.replace("-", MINUS)), "sans", n, M.NOTE, anchor="ms")
        if spines:
            p.rect((self.left - 0.75, self.top, self.left + 0.75, self.bottom), fill=M.AXIS)
            p.rect((self.left, self.bottom - 0.75, self.right, self.bottom + 0.75), fill=M.AXIS)
        mid = (self.left + self.right) / 2
        if xtitle:
            if xtitle_math:
                put_math(p, mid, by1 - n * 0.55, xtitle, n, M.SOFT, anchor="mm")
            else:
                p.text(mid, by1 - n * 0.2, nb(xtitle), "medium", n, M.SOFT, anchor="ms")
        if ytitle:
            if ytitle_math:
                put_math(p, bx0 + n * 0.62, (self.top + self.bottom) / 2, ytitle, n, M.SOFT, anchor="mm",
                         rotate=True)
            else:
                p.vertical(bx0 + n * 0.62, (self.top + self.bottom) / 2, ytitle, "medium", n, M.SOFT)

    def X(self, v):
        return self.left + (v - self.x0) / (self.x1 - self.x0) * (self.right - self.left)

    def Y(self, v):
        v = min(max(v, min(self.y0, self.y1)), max(self.y0, self.y1))
        return self.bottom - (v - self.y0) / (self.y1 - self.y0) * (self.bottom - self.top)

    def series(self, xs, ys, upto, colour, width=3.0, columns=700, start=None):
        pts, bucket, edge = [], [], None
        span = (self.right - self.left) / columns
        lo_x = self.x0 if start is None else start
        for x, v in zip(xs, ys):
            if x < lo_x:
                continue
            if x > upto or x > self.x1:
                break
            px = self.X(x)
            if edge is None:
                edge = px + span
            if px > edge and bucket:
                lo, hi = min(bucket), max(bucket)
                mid = edge - span / 2
                pts += [(mid, self.Y(lo)), (mid, self.Y(hi))] if hi > lo else [(mid, self.Y(lo))]
                bucket = []
                while px > edge:
                    edge += span
            bucket.append(v)
        if bucket:
            pts.append((self.X(min(upto, xs[-1], self.x1)), self.Y(bucket[-1])))
        if len(pts) > 1:
            self.p.line(pts, colour, width)

    def cursor(self, at):
        if self.x0 < at < self.x1:
            x = self.X(at)
            self.p.rect((x - 1.25, self.top, x + 1.25, self.bottom), fill=self.M.COPPER)

    def hdash(self, v, colour, x_from=None, x_to=None):
        """A dashed level line across the plot."""
        y = self.Y(v)
        x = self.X(x_from) if x_from is not None else self.left
        end = self.X(x_to) if x_to is not None else self.right
        while x < end:
            self.p.rect((x, y - 0.8, min(x + 8, end), y + 0.8), fill=colour)
            x += 14

    def leader(self, x, v, text, colour, dx, dy, dot=True, size=None, face="bold", lw=1.6):
        """A value label `dx`, `dy` page pixels from its point, in clear space,
        with a thin leader back to the point."""
        p, M = self.p, self.M
        size = size or p.type.note
        px, py = self.X(x), self.Y(v)
        lx, ly = px + dx, py + dy
        text = nb(text)
        wide = p.width_of(text, face, size)
        left = lx if dx >= 0 else lx - wide
        end = (left - 5, ly) if dx >= 0 else (left + wide + 5, ly)
        p.line([(px, py), end], colour, lw)
        if dot:
            p.disc(px, py, 4.5, colour)
        p.rect((left - 4, ly - size * 0.78, left + wide + 4, ly + size * 0.42), fill=M.CARD, radius=3)
        p.text(left, ly + size * 0.36, text, face, size, colour)

    def errbar(self, x_px, lo, hi, colour, cap=7.0, width=2.0):
        y0, y1 = self.Y(lo), self.Y(hi)
        self.p.line([(x_px, y0), (x_px, y1)], colour, width)
        for y in (y0, y1):
            self.p.line([(x_px - cap, y), (x_px + cap, y)], colour, width)


class LanePlot:
    """Revision 1's chart, kept for the eye scene, which the user preferred as
    revision 1 drew it (2026-10-20): ticks on the y axis with the unit on the
    last, and no axis titles, so the eyes keep their height."""

    def __init__(self, M, p, box, x0, x1, y0, y1, yticks, xticks, yunit, left_pad=3.3):
        self.M, self.p = M, p
        t = p.type
        bx0, top, bx1, bottom = box
        self.left, self.right = bx0 + t.note * left_pad, bx1 - 8
        self.top, self.bottom = top + 6, bottom - (t.note * 1.5 if xticks else 4)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        for i, v in enumerate(yticks):
            p.rect((self.left, self.Y(v) - 0.5, self.right, self.Y(v) + 0.5), fill=M.GRID)
            label = f"{v:g} {yunit}".strip() if i == len(yticks) - 1 else f"{v:g}"
            p.text(self.left - 8, self.Y(v) + t.note * 0.35, nb(label.replace("-", MINUS)), "sans",
                   t.note, M.NOTE, anchor="rs")
        p.rect((self.left, self.bottom, self.right, self.bottom + 1.5), fill=M.AXIS)
        for i, (x, text) in enumerate(xticks):
            last, first = i == len(xticks) - 1, i == 0
            p.text(self.right if last else (self.X(x) if not first else self.X(x)),
                   self.bottom + t.note * 1.25, nb(text), "sans", t.note, M.NOTE,
                   anchor="rs" if last else ("ls" if first and self.X(x) - self.left < 20 else "ms"))

    def X(self, v):
        return self.left + (v - self.x0) / (self.x1 - self.x0) * (self.right - self.left)

    def Y(self, v):
        v = min(max(v, self.y0), self.y1)
        return self.bottom - (v - self.y0) / (self.y1 - self.y0) * (self.bottom - self.top)

    def series(self, xs, ys, upto, colour, width=3.0, columns=700):
        pts, bucket, edge = [], [], None
        span = (self.right - self.left) / columns
        for x, v in zip(xs, ys):
            if x < self.x0:
                continue
            if x > upto or x > self.x1:
                break
            px = self.X(x)
            if edge is None:
                edge = px + span
            if px > edge and bucket:
                lo, hi = min(bucket), max(bucket)
                mid = edge - span / 2
                pts += [(mid, self.Y(lo)), (mid, self.Y(hi))] if hi > lo else [(mid, self.Y(lo))]
                bucket = []
                while px > edge:
                    edge += span
            bucket.append(v)
        if bucket:
            pts.append((self.X(min(upto, xs[-1], self.x1)), self.Y(bucket[-1])))
        if len(pts) > 1:
            self.p.line(pts, colour, width)

    def cursor(self, at):
        if self.x0 < at < self.x1:
            x = self.X(at)
            self.p.rect((x - 1.25, self.top - 4, x + 1.25, self.bottom), fill=self.M.COPPER)

    def vdash(self, x, colour):
        px, y = self.X(x), self.top
        while y < self.bottom:
            self.p.rect((px - 1, y, px + 1, min(y + 7, self.bottom)), fill=colour)
            y += 12

    def label(self, x, v, text, colour, above=True, at=None, dot=True, side=None):
        p, size = self.p, self.p.type.note
        px, py = self.X(x), self.Y(v)
        if dot:
            p.disc(px, py, 5, colour)
        base = py - size * 0.6 if above else py + size * 1.5
        if at is not None:
            base = self.Y(at)
        wide = p.width_of(text, "bold", size * 1.1)
        right = side == "right" or (side is None and px + 12 + wide < self.right)
        left = px + 12 if right else px - 12 - wide
        p.rect((left - 5, base - size * 1.05, left + wide + 5, base + size * 0.35), fill=self.M.CARD,
               radius=4)
        p.text(left, base, nb(text), "bold", size * 1.1, colour)


# --------------------------------------------------------------------------
# The video
# --------------------------------------------------------------------------


class Video:
    def __init__(self, M, R: Runs):
        self.M, self.R = M, R
        running = f"Field simulation  ·  openEMS {R.version}"
        self.shapes = {
            "diffpair-wide": M.Shape("diffpair-wide", (1200, 675), 1.6, type=M.VIDEOS[1].type,
                                     running=running),
            "diffpair": M.Shape("diffpair", (1080, 1350), 1, type=M.VIDEOS[0].type, running=running),
            "diffpair-story": M.Shape("diffpair-story", (1080, 1920), 1, 214, 1920 - 250,
                                      M.STORY_VIDEO_TYPE, running=running),
        }
        p = R.p
        self.L, self.Rb, self.s, self.w = (p["fixture"]["leg_length"], p["fixture"]["bend_radius"],
                                           p["pair"]["pitch"], p["pair"]["width"])
        self.h = p["stackup"]["dielectric_height"]
        self.cell_um = p["simulation"]["levels"]["medium"] * 1000

    # -- the scene frame --------------------------------------------------------

    def scene(self, shape, kicker, headline, text, source=None, tag=None):
        """The heading, a white card under it, the scene's sentences at the top
        of the card, a source line at its foot and, for an illustration, a tag
        at its top right. Returns the page and the room left in the card."""
        M = self.M
        p = shape.new()
        t = p.type
        y = M._heading(p, p.top, kicker, nb(headline))
        ix0, iy0, ix1, iy1 = p.card((M.MARGIN, y + t.body * 0.4, p.right, shape.bottom(p)))
        size = t.note * 1.08
        width = ix1 - ix0
        if tag:
            tw = p.width_of(tag, "bold", t.note * 0.85)
            p.rect((ix1 - tw - 16, iy0 - t.note * 0.2, ix1, iy0 + t.note * 1.05), fill=M.PAGE, radius=6)
            p.text(ix1 - tw - 8, iy0 + t.note * 0.66, tag, "bold", t.note * 0.85, M.NOTE)
            width -= tw + 28
        yy = p.paragraph(ix0, iy0 + size, width, [(nb(text), "medium", M.SOFT)], size, size * 1.35)
        if source:
            p.text(ix0, iy1 - t.note * 0.1, nb(source), "medium", t.note * 0.86, M.NOTE)
            iy1 -= t.note * 1.5
        return p, (ix0, yy + size * 1.0, ix1, iy1)

    def key(self, p, x0, x1, y, entries, size=None):
        """A key centred over x0..x1 from y; returns its foot."""
        M, t = self.M, p.type
        size = size or t.note
        rows = M._key_rows(p, entries, size, x1 - x0)
        M._legend(p, (x0 + x1) / 2, y + size, rows, size)
        return y + size + (len(rows) - 1) * size * 1.75 + size * 0.7

    def slower(self, p, x, y, span_ps, size=None):
        factor = self.M._times_slower(span_ps * 1e-12, SWEEP)
        size = size or p.type.note * 0.9
        p.text(x, y, nb(f"Shown {grouped(factor)} times slower"), "medium", size, self.M.NOTE, anchor="rs")

    @staticmethod
    def split(box, wide, share=0.5, gap=24):
        x0, y0, x1, y1 = box
        if wide:
            m = x0 + (x1 - x0) * share
            return (x0, y0, m - gap / 2, y1), (m + gap / 2, y0, x1, y1)
        m = y0 + (y1 - y0) * share
        return (x0, y0, x1, m - gap / 2), (x0, m + gap / 2, x1, y1)

    # -- drawings ---------------------------------------------------------------

    def xsection(self, p, box, strip=False, signs=False, dims=True):
        """The pair in cross-section at true scale, as the report's figure 4:
        hatched return planes, the dielectric, the two traces, and with `dims`
        the dimensions and the material. The pitch is dimensioned edge to edge
        (P's left edge to N's), so its extension lines never cross w's."""
        M, t = self.M, p.type
        st = self.R.p["stackup"]
        h, w, s, tc = st["dielectric_height"], self.w, self.s, st["copper_thickness"]
        slab = self.R.p["stripline"]["plane_spacing"] if strip else h
        hat = 0.05
        n = t.note
        xr = (-1.0, 1.0)
        top_room = 0.12 if strip else (0.66 if dims else 0.32)
        yr = (-hat - 0.02, slab + (hat + 0.02 if strip else top_room))
        d = Drawing(p, box, xr, yr)
        d.rect(xr[0], 0, xr[1] - xr[0], slab, DIELECTRIC, z=1)
        d.rect(xr[0], -hat, xr[1] - xr[0], hat, "white", hatch="//////", z=2)
        d.line([(xr[0], 0), (xr[1], 0)], M.INK, 1.6, z=3)
        if strip:
            d.rect(xr[0], slab, xr[1] - xr[0], hat, "white", hatch="//////", z=2)
            d.line([(xr[0], slab), (xr[1], slab)], M.INK, 1.6, z=3)
        else:
            d.line([(xr[0], slab), (xr[1], slab)], M.INK, 0.8, z=3)
        y0 = slab / 2 - tc / 2 if strip else slab
        for x, fc in ((-s / 2, M.COPPER), (s / 2, M.TEAL)):
            d.rect(x - w / 2, y0, w, tc, fc, ec=M.INK, lw=0.8, z=5)
        if signs:
            for x, mark, fc in ((-s / 2, "+", M.COPPER), (s / 2, MINUS, M.TEAL)):
                d.text(x, y0 + tc + d.mm(n * 0.9), mark, n * 1.5, weight=700, colour=fc)
        else:
            for x, name in ((-s / 2, "P"), (s / 2, "N")):
                d.text(x, y0 - d.mm(n * 0.75), name, n, weight=700)
        if dims:
            top = y0 + tc
            ea, eb = -s / 2 - w / 2, s / 2 - w / 2          # the two left edges: the pitch
            if strip:
                ys = top + d.mm(n * 0.75)
                for x in (ea, eb):
                    d.line([(x, top + d.mm(3)), (x, ys + d.mm(4))], M.INK, 0.9, z=7)
                d.arrow((ea, ys), (eb, ys))
                d.text((ea + eb) / 2, ys + d.mm(n * 0.62), f"$s = {s:g}$", n)
            else:
                yw = top + d.mm(n * 0.8)
                ys = top + d.mm(n * 2.3)
                for x in (eb, s / 2 + w / 2):
                    d.line([(x, top + d.mm(3)), (x, yw + d.mm(4))], M.INK, 0.9, z=7)
                d.arrow((eb, yw), (s / 2 + w / 2, yw))
                d.text(s / 2 + w / 2 + d.mm(7), yw, f"$w = {w:g}$", n, ha="left")
                for x in (ea, eb):
                    d.line([(x, top + d.mm(3)), (x, ys + d.mm(4))], M.INK, 0.9, z=7)
                d.arrow((ea, ys), (eb, ys))
                d.text((ea + eb) / 2, ys + d.mm(n * 0.62), f"$s = {s:g}$", n)
                d.text(xr[0] + 0.04, ys, "air", n * 0.9, ha="left", colour=M.SOFT)
            xh = xr[0] + 0.07
            d.arrow((xh, 0), (xh, slab))
            d.text(xh + d.mm(9), slab * (0.78 if strip else 0.5), f"$b = {slab:g}$" if strip else f"$h = {h:g}$",
                   n, ha="left")
            d.text(xr[1] - 0.04, slab * (0.22 if strip else 0.5), rf"$\varepsilon_r = {st['epsilon_r']:g}$", n,
                   ha="right")
        d.paste()
        return d

    def plan(self, p, box, g, xr=None, yr=None, dims=False, ports=True, k=None, lit=(), lit_colour=None,
             centres=False):
        """A board in plan as an engineering drawing: P and N in their colours
        with a thin outline, the four lumped ports as ink squares, and with
        `dims` the leg length and the bend radius (the pitch is on the
        cross-section). Returns the Drawing, so callers can place tags by its
        mapping."""
        M = self.M
        xr = xr or (-0.6, self.L + self.Rb + self.s + 0.5)
        yr = yr or (-(self.Rb + self.s) - 0.6, self.Rb + self.s + 0.6)
        n = p.type.note
        d = Drawing(p, box, xr, yr, k)
        for x0, y0, x1, y1 in lit:
            pad = d.mm(10)
            d.rect(x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, lit_colour or GLOW, z=1)
        d.poly(g["copper"]["N"], M.TEAL, "#00505c", 0.8, z=3)
        d.poly(g["copper"]["P"], M.COPPER, "#5e3408", 0.8, z=3)
        if centres:
            for net in ("P", "N"):
                d.centre(g["centreline"][net], "#ffffff", 0.9, z=4)
        if ports:
            side = d.mm(max(5.0, 0.24 * d.k))
            for q in g["ports"]:
                d.rect(q["x"] - side / 2, q["y"] - side / 2, side, side, M.INK, z=4)
        if dims:
            L, R, s = self.L, self.Rb, self.s
            yt = R + s + self.w / 2
            d.dim((0, yt), (L, yt), rf"$L = {L:g}\ \mathrm{{mm}}$", n, d.mm(n * 1.1), tgap=0.35)
            a = math.radians(55)
            d.arrow((L, 0), (L + R * math.cos(a), R * math.sin(a)), both=False)
            d.text(L - d.mm(8), d.mm(n * 0.7), rf"$R = {R:g}\ \mathrm{{mm}}$", n, ha="right")
            d.ax.plot([L - 0.25, L + 0.25], [0, 0], color=M.INK, lw=0.7)
            d.ax.plot([L, L], [-0.25, 0.25], color=M.INK, lw=0.7)
        d.paste()
        return d

    def section(self, g, pad_y=0.15):
        tun = g["tuning"]
        a = tun["amplitude"]
        return (tun["section_start"], -self.Rb - self.w / 2 - pad_y, tun["section_end"],
                -self.Rb + a + self.w / 2 + pad_y)

    def thumb(self, p, box, g, lit=True):
        """A small plan of a tuned board near its bend, the tuning lit."""
        d = self.plan(p, box, g, xr=(6.6, self.L + self.Rb + self.s + 0.35),
                      yr=(-(self.Rb + self.s) - 0.35, -self.Rb + 1.15), ports=False,
                      lit=[self.section(g)] if lit else ())
        return d

    # -- shots ------------------------------------------------------------------------

    def title_shot(self, shape):
        M, R = self.M, self.R
        g = R.geo["C"]

        def figure(p, box):
            # the tuned board as the drawings show it: the tuning lit, each trace outlined,
            # and its centreline, the line a length report measures, dash-dotted in white
            x0, y0, x1, y1 = box
            d = Drawing(p, (x0, y0 + (y1 - y0) * 0.18, x1, y1 - (y1 - y0) * 0.18),
                        (5.5, self.L + self.Rb + self.s + 0.4), (-(self.Rb + self.s) - 0.5, self.Rb + self.s + 0.5))
            sx0, sy0, sx1, sy1 = self.section(g)
            pad = 0.22
            d.ax.add_patch(FancyBboxPatch(
                (sx0 - pad, sy0 - pad), sx1 - sx0 + 2 * pad, sy1 - sy0 + 2 * pad,
                boxstyle=f"round,pad=0,rounding_size={d.mm(6)}", fc=GLOW, ec="none", zorder=1))
            d.poly(g["copper"]["N"], M.TEAL, "#00505c", 0.8, z=3)
            d.poly(g["copper"]["P"], M.COPPER, "#5e3408", 0.8, z=3)
            for net in ("P", "N"):
                d.centre(g["centreline"][net], "#ffffff", 1.2, z=4)
            d.paste()

        line = ("A U-bend makes one trace of a differential pair shorter. This video shows why that "
                "matters and how much of it a serpentine fixes.")
        if shape.page[0] < shape.page[1]:
            shape = _padded(M, shape)
        return M._title_shot(shape, line, title=TITLE, figure=figure)

    def pair_scene(self, shape):
        """Scene 2: what a differential receiver does. An illustration, not a run."""
        M = self.M
        p, box = self.scene(shape, "A differential pair", "Two traces carry equal and opposite signals",
                            "The receiver reads the difference between the two traces. Noise that "
                            "reaches both traces cancels in the difference.", tag="Illustration")
        t = p.type
        n = t.note
        if p.wide:
            xs_box, lanes_box = self.split(box, True, 0.3)
        else:
            xs_box, lanes_box = self.split(box, False, 0.24)
        self.xsection(p, xs_box, signs=True, dims=False)
        xs = [i / 400 * 10 for i in range(401)]
        step = lambda u: 0.5 * (1 + math.tanh((u - 2.6) * 2.2))  # noqa: E731
        bump = lambda u: 0.22 * math.exp(-((u - 6.6) / 0.35) ** 2)  # noqa: E731
        lanes = [("P", [step(u) + bump(u) for u in xs], M.COPPER, (-0.1, 1.3), r"$V_P$"),
                 ("N", [-step(u) + bump(u) for u in xs], M.TEAL, (-1.3, 0.3), r"$V_N$"),
                 ("Difference", [2 * step(u) for u in xs], M.INK, (-0.2, 2.4), r"$V_d = V_P - V_N$")]
        lx0, ly0, lx1, ly1 = lanes_box
        gap = n * 0.7
        lane_h = (ly1 - ly0 - gap * 2 - n * 1.4) / 3
        plots = []
        for i, (name, ys, colour, (lo, hi), tex) in enumerate(lanes):
            top = ly0 + i * (lane_h + gap)
            last = i == 2
            pl = Plot(M, p, (lx0, top + n * 1.3, lx1, top + lane_h + (n * 1.4 if last else 0)), 0, 10, lo, hi,
                      (), (), "Time" if last else None, None, grid=False)
            p.text(lx0, top + n * 0.95, name, "bold", n, colour)
            put_math(p, lx0 + p.width_of(name, "bold", n) + n * 0.8, top + n * 0.6, tex, n * 1.05, M.SOFT)
            plots.append((pl, ys, colour))
        base = p.image

        def frame(upto, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for pl, ys, colour in plots:
                pl.series(xs, ys, upto, colour)
                if not final:
                    pl.cursor(upto)
            if final:
                j = 264
                for (pl, ys, colour), word in zip(plots, ("noise", "noise", "cancels")):
                    pl.leader(xs[j], ys[j], word, M.INK, n * 2.0, -n * 1.0, dot=False)
            return p.image.reduce(M.SS)

        return frame, 10.0

    def skew_scene(self, shape):
        """Scene 3: skew in principle. P and -N on one axis with N late, the gap
        between their 50 % crossings, and the common mode it leaves. An
        illustration: the delay is drawn large and there are no numbers."""
        M = self.M
        p, box = self.scene(shape, "Skew", "If one half arrives early, the two do not cancel",
                            "For a moment both traces move the same way. We call this part of the "
                            "signal common mode. Common mode does not carry data, and it can radiate "
                            "from the cables.", tag="Illustration")
        t = p.type
        n = t.note
        xs = [i / 600 * 10 for i in range(601)]
        lag = 0.9
        edge = lambda u, c: 0.5 * (1 + math.tanh((u - c) * 1.6))  # noqa: E731
        vp = [edge(u, 4.4) for u in xs]
        vn = [edge(u, 4.4 + lag) for u in xs]          # -N, drawn positive
        vc = [(a - b) / 2 for a, b in zip(vp, vn)]
        x0, y0, x1, y1 = box
        split = y0 + (y1 - y0) * 0.6
        top = Plot(M, p, (x0, y0 + n * 1.3, x1, split), 0, 10, -0.05, 1.08, (), (), None, "Voltage", grid=False)
        low = Plot(M, p, (x0, split + n * 1.9, x1, y1), 0, 10, -0.02, 0.3, (), (), "Time", r"$V_c$", grid=False,
                   ytitle_math=True)
        p.text(top.left, y0 + n * 0.95, "P", "bold", n, M.COPPER)
        p.text(top.left + n * 1.3, y0 + n * 0.95, "and", "medium", n, M.SOFT)
        p.text(top.left + n * 3.6, y0 + n * 0.95, MINUS + "N", "bold", n, M.TEAL)
        p.text(low.left, split + n * 1.35, "Common mode", "bold", n, M.SOFT)
        put_math(p, low.right, split + n * 1.0, r"$V_c = (V_P + V_N)\,/\,2$", n * 1.05, M.SOFT, anchor="rm")
        base = p.image
        tp = 4.4
        tn = 4.4 + lag

        def frame(upto, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            low.series(xs, vc, upto, GLOW, width=10)
            low.series(xs, vc, upto, M.COPPER)
            top.series(xs, vp, upto, M.COPPER)
            top.series(xs, vn, upto, M.TEAL)
            if final:
                top.hdash(0.5, OLD)
                y = top.Y(0.5)
                p.disc(top.X(tp), y, 5, M.COPPER)
                p.disc(top.X(tn), y, 5, M.TEAL)
                arrow(p, (top.X(tp), y - n * 1.4), (top.X(tn), y - n * 1.4), M.INK)
                for x in (tp, tn):
                    p.line([(top.X(x), y - 6), (top.X(x), y - n * 1.9)], M.INK, 1.0)
                p.text((top.X(tp) + top.X(tn)) / 2, y - n * 2.2, "skew", "bold", n, M.INK, anchor="ms")
                p.text(top.right, top.Y(0.5) - 6, "50 %", "medium", n * 0.9, M.NOTE, anchor="rs")
            else:
                top.cursor(upto)
                low.cursor(upto)
            return p.image.reduce(M.SS)

        return frame, 10.0

    def board_shot(self, shape):
        """Scene 4: fixture B dimensioned in plan, and its cross-section."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "The board", "A differential pair turns through a U-bend",
                            f"The traces are {self.w:g} mm wide on {self.h:g} mm of dielectric. Their "
                            f"centres are {self.s:g} mm (20 mil) apart. We send a step in at one end and "
                            "measure when each trace arrives at the other.")
        t = p.type
        n = t.note
        board_box, xs_box = self.split(box, p.wide, 0.66 if p.wide else 0.62)
        x0, y0, x1, y1 = board_box
        g = R.geo["B"]
        tagw = n * 6.2
        d = self.plan(p, (x0 + tagw, y0, x1, y1), g, dims=True, centres=True,
                      yr=(-(self.Rb + self.s) - 0.5, self.Rb + self.s + 1.6))
        for q, text in ((g["ports"][1], "Step in"), (g["ports"][3], "Arrival time measured here")):
            px, py = d.P(q["x"], q["y"])
            yy = py + (n * 1.2 if q["number"] == 2 else -n * 0.2)
            p.paragraph(x0, yy, tagw - n * 0.6, [(nb(text), "medium", M.INK)], n, n * 1.2)
        self.xsection(p, xs_box)
        return p.image.reduce(M.SS)

    def bend_scene(self, shape):
        """Scene 5: the bend as the report's figure 1, its arcs lit in turn, then
        the length difference and the skew it makes, set as mathematics."""
        M, R = self.M, self.R
        a_ = R.r["analytic"]
        p, box = self.scene(shape, "Where the skew comes from",
                            f"The inner trace is {a_['bend_mismatch_mm']:.3f} mm shorter",
                            "Around the bend the outer trace runs pi times the pitch further. At "
                            f"20 mil that is {a_['bend_mismatch_mil']:.1f} mil, whatever the radius. "
                            f"Geometry predicts {a_['single_line']['skew_ps']:.2f} ps of skew.")
        t = p.type
        n = t.note
        g = R.geo["B"]
        Rb, s, L = self.Rb, self.s, self.L
        xr = (L - 2.4, L + Rb + s + 0.4)
        yr = (-(Rb + s) - 0.4, Rb + s + 0.4)
        if p.wide:
            draw_box, words_box = self.split(box, True, 0.5)
        else:
            draw_box, words_box = self.split(box, False, 0.56)
        d = Drawing(p, draw_box, xr, yr)
        d.poly(g["copper"]["N"], M.TEAL, "#00505c", 0.8, z=3)
        d.poly(g["copper"]["P"], M.COPPER, "#5e3408", 0.8, z=3)
        for net in ("P", "N"):
            d.centre(g["centreline"][net], "#ffffff", 1.0, z=4)
        d.line([(L - 0.3, 0), (L + 0.3, 0)], M.INK, 1.0, z=6)
        d.line([(L, -0.3), (L, 0.3)], M.INK, 1.0, z=6)
        d.centre([(xr[0] + 0.1, 0), (L - 0.4, 0)], M.INK, 0.8)
        for r, ang, lab, yl in ((Rb, 62, f"$R = {Rb:g}$", 0.55), (Rb + s, -34, f"$R + s = {Rb + s:.3f}$", -0.55)):
            a = math.radians(ang)
            d.arrow((L, 0), (L + r * math.cos(a), r * math.sin(a)), both=False)
            d.text(L - d.mm(10), yl, lab, n, ha="right")
        xd = L - 0.55
        d.arrow((xd, -Rb), (xd, -(Rb + s)))
        d.text(xd - d.mm(9), -(Rb + s / 2), f"$s = {s:g}$", n, ha="right")
        drawing = d.render()
        arc = lambda r: [(L + r * math.cos(u), r * math.sin(u))  # noqa: E731
                         for u in np.linspace(-math.pi / 2, math.pi / 2, 90)]
        inner, outer = arc(Rb), arc(Rb + s)
        base = p.image
        rows = [("P, the inner trace", rf"$\pi R = {math.pi * Rb:.3f}\ \mathrm{{mm}}$", M.COPPER),
                ("N, the outer trace", rf"$\pi (R + s) = {math.pi * (Rb + s):.3f}\ \mathrm{{mm}}$", M.TEAL),
                ("The difference", rf"$\Delta L = \pi s = {a_['bend_mismatch_mm']:.3f}\ \mathrm{{mm}}$",
                 M.INK),
                ("The skew it makes",
                 r"$\Delta t = \Delta L\,\sqrt{\varepsilon_\mathrm{eff}}\,/\,c = "
                 rf"{a_['single_line']['skew_ps']:.2f}\ \mathrm{{ps}}$", M.INK)]
        note = rf"$\varepsilon_\mathrm{{eff}} = {a_['single_line']['eps_eff']:.3f}$, one line alone"

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            b = Board(M, p, draw_box, xr, yr)
            glow = self.w * b.k * 2.8
            if stage > 0 or final:
                pts = [b.P(*q) for q in partial(inner, 1.0 if final else ease(stage))]
                if len(pts) > 1:
                    p.line(pts, GLOW, glow)
            if stage > 1 or final:
                pts = [b.P(*q) for q in partial(outer, 1.0 if final else ease(stage - 1))]
                if len(pts) > 1:
                    p.line(pts, TEAL_GLOW, glow)
            p.image.paste(drawing, (round(d.x0 * p.ss), round(d.y0 * p.ss)), drawing)
            wx0, wy0, wx1, wy1 = words_box
            step = (wy1 - wy0) / (len(rows) + 0.6)
            for i, (name, tex, colour) in enumerate(rows):
                alpha = 1.0 if final else clamp((stage - i) / 0.35)
                if alpha <= 0:
                    continue
                y = wy0 + step * i + n
                before = p.image.copy()
                p.text(wx0, y, name, "bold", n, colour if colour != M.INK else M.SOFT)
                put_math(p, wx0, y + n * 0.5, tex, n * 1.3, M.INK, anchor="lt")
                if i == 3:
                    put_math(p, wx0, y + n * 2.6, note, n * 0.95, M.NOTE, anchor="lt")
                if alpha < 1:
                    p.image = Image.blend(before, p.image, alpha)
                    p.draw = ImageDraw.Draw(p.image)
            return p.image.reduce(M.SS)

        return frame, 4.0

    def model3d_image(self, w, h, ss, azim, lit, pulse, zoom=1.0):
        """Fixture B's model in 3D at azimuth `azim`: the slab on the PEC floor,
        the copper, the four lumped ports (port `lit` bright, by `pulse`) and
        the air box's edges. The height is drawn 4 times true scale; the air
        above is drawn shorter than that, with break marks on its edges, so the
        box does not dwarf the board. Returns the image and where three
        features land on it, in its own pixels: the top face of the air box,
        the floor's front corner and port 2's top."""
        from mpl_toolkits.mplot3d import proj3d
        from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
        R = self.R
        g = R.geo["B"]
        X, Y = R.mesh["x"], R.mesh["y"]
        ze = 4.0
        H = self.h * ze
        TOP = H + AIR_DRAWN
        with plt.rc_context(MPL):
            fig = plt.figure(figsize=(w / 100, h / 100), dpi=100 * ss)
            fig.patch.set_alpha(0)
            ax = fig.add_axes([0, 0, 1, 1], projection="3d", computed_zorder=False)
            x0, x1, y0, y1 = X[0], X[-1], Y[0], Y[-1]
            c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            ax.add_collection3d(Poly3DCollection([[(x, y, 0) for x, y in c]], fc="#B9BCC2", ec="#6B6E75", lw=0.5,
                                                 zorder=1))
            faces = ([[(x, y, H) for x, y in c]]
                     + [[(*c[k], 0), (*c[(k + 1) % 4], 0), (*c[(k + 1) % 4], H), (*c[k], H)] for k in range(4)])
            ax.add_collection3d(Poly3DCollection(faces, fc=SUBSTRATE, ec=SUBSTRATE_EDGE, lw=0.6, alpha=0.9,
                                                 zorder=2))
            for net in ("P", "N"):
                ax.add_collection3d(Poly3DCollection([[(x, y, H) for x, y in g["copper"][net]]], fc=METAL,
                                                     ec=METAL_EDGE, lw=0.5, zorder=4))
            for q in g["ports"]:
                y = q["y"]
                on = lit is None or q["number"] == lit
                colour = PORT_RED if on else "#d9a39e"
                hh = H * (1.0 + (1.2 * pulse if (on and lit is not None) else 0.0))
                sheet = [(0, y - self.w / 2, 0), (0, y + self.w / 2, 0), (0, y + self.w / 2, hh),
                         (0, y - self.w / 2, hh)]
                ax.add_collection3d(Poly3DCollection([sheet], fc=colour, ec=colour, lw=1.0, zorder=5))
            # the air box: its top, and each vertical edge broken half-way with a break mark
            za, zb = H + AIR_DRAWN * 0.42, H + AIR_DRAWN * 0.58
            edges = [[(*c[k], TOP), (*c[(k + 1) % 4], TOP)] for k in range(4)]
            for k in range(4):
                edges += [[(*c[k], H), (*c[k], za)], [(*c[k], zb), (*c[k], TOP)]]
            ax.add_collection3d(Line3DCollection(edges, colors="#7C7F86", lw=0.8, linestyles=(0, (3, 2)), zorder=6))
            ticks = []
            d = (x1 - x0) * 0.025
            for x, y in c:
                for z in (za, zb):
                    ticks.append([(x - d, y, z - AIR_DRAWN * 0.04), (x + d, y, z + AIR_DRAWN * 0.04)])
            ax.add_collection3d(Line3DCollection(ticks, colors="#57575e", lw=1.0, zorder=7))
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_zlim(0, TOP)
            ax.set_box_aspect((x1 - x0, y1 - y0, TOP), zoom=zoom)
            ax.view_init(elev=30, azim=azim)
            ax.set_axis_off()
            ax.patch.set_visible(False)       # else its white ground counts as ink when the model is fitted
            fig.canvas.draw()
            img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()).copy(), "RGBA")
            anchors = {}
            for key, (x, y, z) in {"top": (x0 + (x1 - x0) * 0.62, y1, TOP), "floor": (x1, y0, 0.0),
                                   "port": (0.0, g["ports"][1]["y"], H), "air": (x1, y0, (za + zb) / 2)}.items():
                xp, yp, _ = proj3d.proj_transform(x, y, z, ax.get_proj())
                dx, dy = ax.transData.transform((xp, yp))
                anchors[key] = (dx, img.height - dy)
            plt.close(fig)
        return img, anchors

    def model_scene(self, shape):
        """Scene 6: the model as openEMS gets it, in 3D, turning a little, with
        the four runs as the four ports pulse in turn. The model takes all the
        room the sentences leave; its labels sit outside its outline (above it,
        under it, and the ports' to its left), each with a leader."""
        M, R = self.M, self.R
        text = ("Each run sends a pulse into one of the four ports. Four runs give the full response of the "
                "board. From it we calculate the waveforms at the receiver.")
        wide = shape.page[0] > shape.page[1]
        p, box = self.scene(shape, "How we simulate it", "openEMS solves Maxwell's equations around the copper",
                            "" if wide else text)
        t = p.type
        n = t.note
        size = n * 0.95
        x0, y0, x1, y1 = box
        note = "Height drawn 4 times true scale. The air above is drawn shorter."
        port_lines = ["Lumped ports,", "50 ohm"]
        port_w = max(p.width_of(s, "bold", size) for s in port_lines) + n * 1.2
        if wide:
            y0 -= n * 1.08
            col = (x1 - x0) * 0.27
            s_ = n * 1.08
            yy = p.paragraph(x0, y0 + s_, col, [(nb(text), "medium", M.SOFT)], s_, s_ * 1.35)
            run_at = (x0, yy + n * 1.6)
            p.paragraph(x0, y1 - n * 1.5, col, [(nb(note), "medium", M.NOTE)], n * 0.85, n * 1.15)
            bx0, by0, bx1, by1 = x0 + col + n * 1.2 + port_w, y0 + n * 2.0, x1, y1 - n * 2.0
        else:
            run_at = (x0, y0 + n * 0.95)
            p.text((x0 + x1) / 2, y1 - n * 0.2, nb(note), "medium", n * 0.85, M.NOTE, anchor="ms")
            bx0, by0, bx1, by1 = x0 + port_w, y0 + n * 3.6, x1, y1 - n * 3.4
        w, h = bx1 - bx0, by1 - by0
        # A 3D axes draws inside a square of its shorter side, so the model is
        # drawn on a square canvas: zoom it to fill that square, then scale it
        # down until its ink fits the box, and centre the ink in the box.
        side = max(w, h)
        zoom = 1.0
        for _ in range(3):
            probe, _ = self.model3d_image(side, side, 0.5, -59, None, 0.0, zoom)
            bb = probe.getchannel("A").getbbox()
            zoom *= 0.97 * min(probe.width / (bb[2] - bb[0]), probe.height / (bb[3] - bb[1]))
        probe, _ = self.model3d_image(side, side, 0.5, -59, None, 0.0, zoom)
        bb = probe.getchannel("A").getbbox()
        iw, ih = (bb[2] - bb[0]) * 2, (bb[3] - bb[1]) * 2        # page pixels: the probe was at ss 0.5
        zoom *= min(1.0, 0.94 * min(w / iw, h / ih))
        base = p.image
        cache = {}
        # centre the finished view's ink in the box once: re-centring every frame would
        # snap the turning model and its labels a pixel at a time
        final_img, _ = self.model3d_image(side, side, p.ss, -54.0, None, 0.0, zoom)
        fl, ft, fr, fb = (v / p.ss for v in final_img.getchannel("A").getbbox())
        ox = bx0 + (w - (fr - fl)) / 2 - fl
        oy = by0 + (h - (fb - ft)) / 2 - ft
        ox0, oy0, ox1, oy1 = ox + fl, oy + ft, ox + fr, oy + fb

        def frame(stage, final):
            u = 1.0 if final else clamp(stage / 4.0)
            # not rounded: as the turn eases to a stop, rounded steps would land a few frames apart and jump
            azim = -64 + 10 * ease(u)
            if final:
                lit, pulse = None, 0.0
            else:
                lit = min(int(stage), 3) + 1
                pulse = math.sin(math.pi * clamp(stage - int(stage)))
            key = (round(azim, 4), lit, round(pulse, 4))
            if key not in cache:
                cache[key] = self.model3d_image(side, side, p.ss, azim, lit, pulse, zoom)
            img, anchors = cache[key]
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            p.image.paste(img, (round(ox * p.ss), round(oy * p.ss)), img)
            at = {k: (ox + v[0] / p.ss, oy + v[1] / p.ss) for k, v in anchors.items()}
            for key, text_, colour, place in (("top", "Mur boundary: the fields leave here", M.SOFT, "above"),
                                              ("floor", "PEC floor: the return plane", M.SOFT, "below")):
                ax_, ay_ = at[key]
                tw = p.width_of(nb(text_), "bold", size)
                lx = min(max(ax_ - tw / 2, bx0 - port_w), x1 - tw)
                ly = oy0 - n * 0.6 if place == "above" else oy1 + n * 1.45
                end = (min(max(ax_, lx), lx + tw), ly + n * 0.25 if place == "above" else ly - size * 0.9)
                p.line([(ax_, ay_), end], colour, 1.4)
                p.disc(ax_, ay_, 3.5, colour)
                p.text(lx, ly, nb(text_), "bold", size, colour)
            ax_, ay_ = at["port"]
            lx, ly = ox0 - port_w + n * 0.2, ay_ - size * 0.3
            p.line([(ax_, ay_), (lx + port_w - n * 1.0, ly - size * 0.35)], PORT_RED, 1.4)
            p.disc(ax_, ay_, 3.5, PORT_RED)
            for k_, s in enumerate(port_lines):
                p.text(lx, ly + k_ * size * 1.2, s, "bold", size, PORT_RED)
            # the run's line and the closing caption sit on different lines, so the fade
            # from one to the other never sets two texts on top of each other
            if final:
                p.text(run_at[0], run_at[1] + n * 1.5, "The four ports, one run each", "bold", n, M.SOFT)
            else:
                p.text(run_at[0], run_at[1], f"Run {lit}: a pulse into port {lit}", "bold", n, PORT_RED)
            return p.image.reduce(M.SS)

        return frame, 4.0

    def mesh_scene(self, shape):
        """Scene 7: the domain in plan, the medium mesh over D's corners with
        the cells in the copper filling in, and the bend's skew on three meshes."""
        M, R = self.M, self.R
        cb = R.r["convergence"]["B"]["skew_50"]
        levels = R.p["simulation"]["levels"]
        p, box = self.scene(shape, "The mesh", f"{R.cells / 1e6:.2f} million cells, checked on three meshes",
                            f"The cells are {self.cell_um:.0f} {MU}m over the copper. On a "
                            f"{levels['fine'] * 1000:.0f} {MU}m mesh the bend's skew moves by only "
                            f"{abs(cb['medium'] - cb['fine']):.2f} ps.",
                            source=f"openEMS  ·  board B on three meshes, board D at {self.cell_um:.0f} {MU}m")
        t = p.type
        n = t.note
        X, Y = R.mesh["x"], R.mesh["y"]
        g, gd = R.geo["B"], R.geo["D"]
        if p.wide:
            left, right = self.split(box, True, 0.5, gap=28)
            close, chart = self.split(right, False, 0.5, gap=18)
        else:
            left, rest = self.split(box, False, 0.32, gap=18)
            close, chart = self.split(rest, True, 0.5, gap=24)
        # the domain, the solver's view
        lx0, ly0, lx1, ly1 = left
        dom = (X[0], X[-1]), (Y[0], Y[-1])
        d = Drawing(p, (lx0 + n * 1.6, ly0 + n * 1.3, lx1, ly1 - n * 2.9), *dom)
        d.rect(X[0], Y[0], X[-1] - X[0], Y[-1] - Y[0], SUBSTRATE, ec=SUBSTRATE_EDGE, lw=1.0, z=1)
        for net in ("P", "N"):
            d.poly(g["copper"][net], METAL, METAL_EDGE, 0.5, z=3)
        for q in g["ports"]:
            d.line([(q["x"], q["y"] - self.w / 2), (q["x"], q["y"] + self.w / 2)], PORT_RED, 5.0, z=4)
            d.text(q["x"] - d.mm(n * 0.75), q["y"], str(q["number"]), n * 0.85, weight=700, colour="white")
        win = (8.16, 9.34, -1.68, -1.06)
        d.rect(win[0], win[2], win[1] - win[0], win[3] - win[2], "none", ec="white", lw=1.4, z=6)
        d.paste()
        p.text(lx0 + n * 1.6, ly0 + n * 0.95, "The domain, as openEMS gets it", "bold", n, M.SOFT)
        for xv in (0, 4, 8, 12, 16):
            px, py = d.P(xv, Y[0])
            p.rect((px - 0.75, py, px + 0.75, py + 5), fill=M.AXIS)
            p.text(px, py + n * 1.2, f"{xv}", "sans", n * 0.9, M.NOTE, anchor="ms")
        px, py = d.P(X[-1], Y[0])
        p.text(px, py + n * 2.55, "x (mm)", "medium", n * 0.9, M.SOFT, anchor="rs")
        # the close-up: mesh lines, then the cells in the copper filled behind a cursor
        cx0, cy0, cx1, cy1 = close
        p.text(cx0, cy0 + n * 0.95, nb(f"The {self.cell_um:.0f} {MU}m mesh over board D's corners" if p.wide
                                       else f"The {self.cell_um:.0f} {MU}m mesh, board D"), "bold", n, M.SOFT)
        zb = (cx0, cy0 + n * 1.4, cx1, cy1)
        xs_ = [x for x in X if win[0] - 0.1 <= x <= win[1] + 0.1]
        ys_ = [y for y in Y if win[2] - 0.1 <= y <= win[3] + 0.1]
        z = Drawing(p, zb, win[:2], win[2:])
        z.rect(win[0], win[2], win[1] - win[0], win[3] - win[2], SUBSTRATE, z=1)
        for x in xs_:
            z.line([(x, win[2]), (x, win[3])], "#ffffff", 0.5, z=3)
        for y in ys_:
            z.line([(win[0], y), (win[1], y)], "#ffffff", 0.5, z=3)
        for net in ("P", "N"):
            z.poly(gd["copper"][net], "none", METAL, 2.0, z=4)
        under = z.render()
        f = Drawing(p, zb, win[:2], win[2:])
        from matplotlib.path import Path as MPath
        paths = [MPath(gd["copper"][net]) for net in ("P", "N")]
        for i in range(len(xs_) - 1):
            for j in range(len(ys_) - 1):
                cx, cy = (xs_[i] + xs_[i + 1]) / 2, (ys_[j] + ys_[j + 1]) / 2
                if any(pa.contains_point((cx, cy)) for pa in paths):
                    f.rect(xs_[i], ys_[j], xs_[i + 1] - xs_[i], ys_[j + 1] - ys_[j], METAL, z=2)
        for x in xs_:
            f.line([(x, win[2]), (x, win[3])], "#ffffff", 0.5, z=3)
        for y in ys_:
            f.line([(win[0], y), (win[1], y)], "#ffffff", 0.5, z=3)
        filled = f.render()
        # the convergence chart
        hx0, hy0, hx1, hy1 = chart
        pts = [(levels[l] * 1000, cb[l]) for l in ("coarse", "medium", "fine")]
        pl = Plot(M, p, (hx0, hy0 + n * 1.3, hx1, hy1), 66, 20, 9.0, 9.8,
                  [(60, "60"), (40, "40"), (27, "27")], [(9.0, "9.0"), (9.4, "9.4"), (9.8, "9.8")],
                  f"Finest cell ({MU}m)", "Skew (ps)")
        p.text(hx0, hy0 + n * 0.95, "The bend's skew on three meshes" if p.wide else "Skew on three meshes", "bold",
               n, M.SOFT)
        base = p.image
        unc = R.unc("B")

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            p.image.paste(under, (round(z.x0 * p.ss), round(z.y0 * p.ss)), under)
            u = 1.0 if final else clamp(stage / 2.0)
            if u > 0:
                cut = max(1, round(filled.width * u))
                part = filled.crop((0, 0, cut, filled.height))
                p.image.paste(part, (round(z.x0 * p.ss), round(z.y0 * p.ss)), part)
                if not final and u < 1:
                    xc = z.x0 + z.w * u
                    p.rect((xc - 1.25, z.y0, xc + 1.25, z.y0 + z.h), fill=M.COPPER)
            k = 3 if final else min(3, max(0, int((stage - 2.0) / 0.3) + 1)) if stage >= 2.0 else 0
            if k > 1:
                p.line([(pl.X(x), pl.Y(v)) for x, v in pts[:k]], M.COPPER, 2.4)
            for i, (x, v) in enumerate(pts[:k]):
                p.disc(pl.X(x), pl.Y(v), 5.5, M.COPPER)
                if i == 1:
                    pl.errbar(pl.X(x), v - unc, v + unc, M.INK, cap=6, width=1.6)
                # first above right, the middle below left (clear of its error bar), the last above left
                dx, dy, anchor = ((12, -10, "ls"), (-12, n * 1.15, "rs"), (-12, -10, "rs"))[i]
                p.text(pl.X(x) + dx, pl.Y(v) + dy, f"{v:.2f}", "bold", n * 0.9, M.INK, anchor=anchor)
            return p.image.reduce(M.SS)

        return frame, 3.0

    def scope_scene(self, shape, kicker, headline, text, main, old=None, panel=None, source=None,
                    old_name="Untuned"):
        """A scope: far-end P and -N for a 50 ps edge behind a cursor, on the
        window all scopes share. Once it has run: the 50 % level, each trace's
        crossing, the skew between them dimensioned, and a readout of each skew
        with its bound in the plot's empty lower right, a leader to its
        dimension; the common mode's peak marked by a dashed level carried to
        the lane's right margin, where its value sits. `old` is a variant kept
        in grey behind. `panel(p, box)` draws beside it."""
        M, R = self.M, self.R
        p, box = self.scene(shape, kicker, headline, text, source=source)
        t = p.type
        n = t.note
        if panel:
            box, pbox = self.split(box, p.wide, 0.64 if p.wide else 0.66, gap=30)
            panel(p, pbox)
        x0, y0, x1, y1 = box
        a, b = SCOPE
        margin = n * 4.4
        split = y0 + (y1 - y0) * (0.5 if p.wide else 0.58)
        xt = [(v, f"{v:g}") for v in range(int(a), int(b) + 1, 25)]
        top = Plot(M, p, (x0, y0 + n * 1.3, x1 - margin, split), a, b, -0.03, 0.55, xt,
                   [(0, "0"), (0.25, "0.25"), (0.5, "0.5")], None, "Voltage (V)", xlabels=False)
        low = Plot(M, p, (x0, split + n * 1.9, x1 - margin, y1), a, b, -4, 58, xt, [(0, "0"), (50, "50")],
                   "Time (ps)", r"$V_c$ (mV)", ytitle_math=True)
        cap = "Far end: P and " + MINUS + "N"
        p.text(top.left, y0 + n * 0.95, cap, "bold", n, M.SOFT)
        p.text(low.left, split + n * 1.35, "Common mode", "bold", n, M.SOFT)
        note = f"Shown {grouped(self.M._times_slower((b - a) * 1e-12, SWEEP))} times slower"
        wn = p.width_of(note, "medium", n * 0.9)
        if p.width_of(cap, "bold", n) + wn + n * 2 < top.right - top.left:
            self.slower(p, top.right, y0 + n * 0.95, b - a)
        elif p.width_of("Common mode", "bold", n) + wn + n * 2 < low.right - x0:
            self.slower(p, low.right, split + n * 1.35, b - a)
        if old:
            wo = R.wave[old]
            top.series(wo["t"], wo["p_far"], b, OLD, 2.4)
            top.series(wo["t"], [-v for v in wo["n_far"]], b, OLD, 2.4)
            low.series(wo["t"], [v * 1000 for v in wo["vc_far"]], b, OLD, 2.4)
        base = p.image
        w = R.wave[main]
        neg = [-v for v in w["n_far"]]
        vc = [v * 1000 for v in w["vc_far"]]

        def level(v):
            ww = R.wave[v]
            return (np.mean(ww["p_far"][-20:]) - np.mean(ww["n_far"][-20:])) / 4

        def gap_mark(v, colour, readout_y, drop=0.0):
            tp, tn = R.t50(v, "t50_P"), R.t50(v, "t50_N")
            y = top.Y(level(v))
            grey = colour == OLD
            p.disc(top.X(tp), y, 5, OLD if grey else M.COPPER)
            p.disc(top.X(tn), y, 5, OLD if grey else M.TEAL)
            ya = y + drop
            if drop:
                for x in (tp, tn):
                    p.line([(top.X(x), y + 6), (top.X(x), ya + 6)], colour, 1.0)
            arrow(p, (top.X(tp), ya), (top.X(tn), ya), colour, width=1.8, size=8)
            text = nb(f"{old_name + ': ' if grey else ''}{ps(R.skew(v), R.unc(v))} ps")
            size = n * (0.95 if grey else 1.05)
            lx = top.left + n * 0.7
            tw = p.width_of(text, "bold", size)
            p.line([(top.X(tp) - 4, ya - 2), (lx + tw + 6, readout_y - size * 0.35)], colour, 1.4)
            p.rect((lx - 4, readout_y - size * 0.82, lx + p.width_of(text, "bold", size) + 4, readout_y + size * 0.3),
                   fill=M.CARD, radius=3)
            p.text(lx, readout_y, text, "bold", size, colour)

        def peak(ts, vs):
            k = max(range(len(vs)), key=lambda i: vs[i] if a <= ts[i] <= b else -1)
            return low.X(ts[k]), low.Y(vs[k]), vs[k]

        def peak_mark(px, py, value, colour, ty):
            p.disc(px, py, 4.5, colour)
            xx = px + 8
            while xx < low.right + 6:
                p.rect((xx, py - 0.8, min(xx + 7, low.right + 6), py + 0.8), fill=colour)
                xx += 12
            if abs(ty - py) > 1:
                p.line([(low.right + 6, py), (low.right + 10, ty - n * 0.35)], colour, 1.2)
            p.text(low.right + 12, ty, nb(f"{value:.0f} mV"), "bold", n * 0.95, colour)

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            upto = a + stage
            top.series(w["t"], w["p_far"], upto, M.COPPER)
            top.series(w["t"], neg, upto, M.TEAL)
            low.series(w["t"], vc, upto, M.COPPER)
            if final:
                top.hdash(level(main), OLD, x_to=R.t50(main, "t50_P") - 6)
                main_y = top.Y(0.47)
                gap_mark(main, M.INK, main_y)
                pm = peak(w["t"], vc)
                tm = pm[1] + n * 0.35
                if old:
                    gap_mark(old, OLD, main_y + n * 1.5, drop=n * 1.2)
                    wo = R.wave[old]
                    po = peak(wo["t"], [v * 1000 for v in wo["vc_far"]])
                    to = po[1] + n * 0.35
                    if tm - to < n * 1.15:             # keep the two readouts a line apart
                        mid = (tm + to) / 2
                        to, tm = mid - n * 0.6, mid + n * 0.6
                    peak_mark(*po, OLD, to)
                peak_mark(*pm, M.COPPER, tm)
            else:
                top.cursor(upto)
                low.cursor(upto)
            return p.image.reduce(M.SS)

        return frame, b - a

    def fix_shot(self, shape):
        """Scene 9: the usual fix, dimensioned as the report's figure 2, and the
        length report that calls it done."""
        M, R = self.M, self.R
        g = R.geo["C"]
        p, box = self.scene(shape, "The usual fix",
                            f"Add {R.r['analytic']['bend_mismatch_mm']:.3f} mm to the inner trace",
                            "A serpentine gives P the missing length. The CAD length report then shows "
                            "P and N equal. A line model that sees only length predicts "
                            f"{R.V['C']['mtl_skew_50']:.1f} ps of skew.")
        t = p.type
        n = t.note
        draw_box, rep_box = self.split(box, p.wide, 0.66 if p.wide else 0.6)
        tu = g["tuning"]
        Rb, s, w, L = self.Rb, self.s, self.w, self.L
        c = tu["chamfer"]
        A, top_, bottom = tu["amplitude"], tu["top"], tu["bottom"]
        xs0 = tu["section_start"]
        xr = (xs0 - 1.3, L + Rb + s + 0.4)
        yr = (-(Rb + s) - 0.75, -Rb + A + 0.95)
        d = Drawing(p, draw_box, xr, yr)
        d.poly(g["copper"]["N"], M.TEAL, "#00505c", 0.8, z=3)
        d.poly(g["copper"]["P"], M.COPPER, "#5e3408", 0.8, z=3)
        for net in ("P", "N"):
            d.centre(g["centreline"][net], "#ffffff", 0.9, z=4)
        x1 = xs0 + c
        x2, x3, x4 = x1 + top_, x1 + top_ + bottom, x1 + 2 * top_ + bottom
        ytop = -Rb + A
        yd = ytop + w / 2 + d.mm(n * 1.3)
        for xa, xb, lab in ((x1, x2, "$a$"), (x2, x3, "$b$"), (x3, x4, "$a$")):
            for xx in (xa, xb):
                d.line([(xx, ytop + w / 2 + d.mm(4)), (xx, yd + d.mm(5))], M.INK, 0.9, z=7)
            d.arrow((xa, yd), (xb, yd))
            d.text((xa + xb) / 2, yd + d.mm(n * 0.75), lab, n * 1.1)
        xa_ = xs0 - 0.45
        d.line([(xa_ - d.mm(5), ytop), (x1 - d.mm(4), ytop)], M.INK, 0.9, z=7)
        d.arrow((xa_, -Rb), (xa_, ytop))
        d.text(xa_ - d.mm(8), (-Rb + ytop) / 2, "$A$", n * 1.1, ha="right")
        d.text(xr[0] + d.mm(4), -Rb - w / 2 - d.mm(n * 0.75), "P", n, weight=700, ha="left")
        d.text(xr[0] + d.mm(4), -(Rb + s) - w / 2 - d.mm(n * 0.75), "N", n, weight=700, ha="left")
        d.text((x1 + x4) / 2, -(Rb + s) - w / 2 - d.mm(n * 1.1),
               rf"Two excursions, $A = {A:.3f}\ \mathrm{{mm}}$", n * 0.95, colour=M.SOFT)
        d.paste()
        x0, y0, x1_, y1 = rep_box
        size = t.body
        rows = [("P", f"{g['length']['P']:.3f} mm", M.COPPER), ("N", f"{g['length']['N']:.3f} mm", M.TEAL)]
        h = size * 1.4 * 4.4
        top = y0 + (y1 - y0 - h) / 2
        bw = min(x1_ - x0, size * 13)
        bx0 = x0 + (x1_ - x0 - bw) / 2
        p.rect((bx0, top, bx0 + bw, top + h), fill=M.PAGE, radius=10)
        yy = top + size * 1.5
        p.text(bx0 + size * 0.8, yy, "Length report", "bold", n, M.SOFT)
        for name, value, colour in rows:
            yy += size * 1.45
            p.text(bx0 + size * 0.8, yy, name, "bold", size, colour)
            p.text(bx0 + bw - size * 0.8, yy, nb(value), "bold", size, M.INK, anchor="rs")
        yy += size * 1.6
        p.tick(bx0 + size * 1.2, yy, size, M.PASS)
        p.text(bx0 + size * 2.0, yy, "Equal", "bold", size, M.PASS)
        return p.image.reduce(M.SS)

    def bars_scene(self, shape):
        """Scene 10: three serpentines of exactly the right length, the skew each
        leaves with its error bar, and the line model's prediction on each."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "Three serpentines, each exactly the right length",
                            f"{R.skew('F'):.1f} to {R.skew('D'):.1f} ps of the skew stays",
                            f"One broad excursion removes {R.removed('F'):.0f} % of the skew. Two "
                            f"remove {R.removed('C'):.0f} %. Four small ones remove only "
                            f"{R.removed('D'):.0f} %.",
                            source=f"openEMS  ·  {self.cell_um:.0f} {MU}m mesh  ·  error bars: the bound from "
                                   "three meshes")
        t = p.type
        n = t.note
        cases = [("F", "1 excursion"), ("C", "2 excursions"), ("D", "4 excursions")]
        if p.wide:
            draws, chart = self.split(box, True, 0.3)
        else:
            draws, chart = self.split(box, False, 0.26)
        dx0, dy0, dx1, dy1 = draws
        for i, (v, name) in enumerate(cases):
            if p.wide:
                hh = (dy1 - dy0) / 3
                cell = (dx0, dy0 + i * hh, dx1, dy0 + (i + 1) * hh)
            else:
                ww = (dx1 - dx0 - 2 * 16) / 3
                cell = (dx0 + i * (ww + 16), dy0, dx0 + i * (ww + 16) + ww, dy1)
            cx0, cy0, cx1, cy1 = cell
            p.text(cx0, cy0 + n, name, "bold", n, M.SOFT)
            self.thumb(p, (cx0, cy0 + n * 1.4, cx1, cy1 - 4), R.geo[v], lit=False)
        cx0, cy0, cx1, cy1 = chart
        ky = self.key(p, cx0, cx1, cy0, [(OLD, "Untuned", False), (M.COPPER, "Exact length, full wave", False),
                                         (M.TEAL, "Line model", False)])
        items = [("B", "Untuned", OLD)] + [(v, name, M.COPPER) for v, name in cases]
        top = math.ceil(R.skew("B") / 2.5) * 2.5 + 1.0
        pl = Plot(M, p, (cx0, ky, cx1, cy1), -0.5, 3.5, 0, top, [(i, name) for i, (_, name, _) in enumerate(items)],
                  [(0, "0"), (2.5, "2.5"), (5, "5"), (7.5, "7.5"), (10, "10")], None, "Skew at the receiver (ps)")
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            slot = pl.X(1) - pl.X(0)
            for i, (v, name, colour) in enumerate(items):
                u = 1.0 if final else ease(stage - i)
                if u <= 0:
                    continue
                val = R.skew(v) * u
                cx = pl.X(i)
                bw = slot * 0.46
                p.rect((cx - bw / 2, pl.Y(val), cx + bw / 2, pl.bottom), fill=colour, radius=3)
                if u >= 1:
                    un = R.unc(v) or 0.0
                    pl.errbar(cx, R.skew(v) - un, R.skew(v) + un, M.INK, cap=8, width=2.0)
                    p.text(cx, pl.Y(R.skew(v) + un) - n * 0.55, nb(ps(R.skew(v), un)), "bold", n * 1.0, M.INK,
                           anchor="ms")
                    if v != "B":
                        y = pl.Y(R.V[v]["mtl_skew_50"])
                        p.rect((cx - bw / 2 - 6, y - 2.5, cx + bw / 2 + 6, y + 2.5), fill=M.TEAL, radius=2)
            return p.image.reduce(M.SS)

        return frame, 4.0

    def corner_scene(self, shape):
        """Scene 12: one excursion, its centre line and the path the current
        takes, with a 45-degree corner chamfer dimensioned."""
        M, R = self.M, self.R
        lo, hi = self.per_exc()
        p, box = self.scene(shape, "Why the fix falls short", "The current takes the inside of each corner",
                            "That path is shorter than the centre line that the length report "
                            "measures. Each excursion has four corners. In these serpentines each one "
                            f"loses {lo:.1f} to {hi:.1f} ps of the delay its length predicts.",
                            source="openEMS less the line model  ·  boards F, C and D")
        t = p.type
        n = t.note
        g = R.geo["C"]
        tun = g["tuning"]
        xs0 = tun["section_start"]
        c = tun["chamfer"]
        bump_end = xs0 + tun["top"] + 2 * c
        a = tun["amplitude"]
        xr = (xs0 - 0.45, bump_end + 0.45)
        yr = (-self.Rb - 0.4, -self.Rb + a + 0.4)
        centre = [tuple(q) for q in g["centreline"]["P"] if xr[0] - 1 <= q[0] <= xr[1] + 1 and q[1] < 0]
        centre = [q for q in centre if -self.Rb - 0.01 <= q[1] <= -self.Rb + a + 0.01]
        path = inside_path(centre, 0.62 * self.w / 2)
        ky = self.key(p, box[0], box[2], box[1], [(M.INK, "Centre line: what the length report measures", True),
                                                  (M.COPPER, "The path the current takes", False)])
        if p.wide:
            draw_box, det_box = self.split((box[0], ky, box[2], box[3]), True, 0.7, gap=24)
        else:
            draw_box, det_box = self.split((box[0], ky, box[2], box[3]), False, 0.66, gap=18)
        # detail: one chamfer, its leg c dimensioned on the centreline
        x1 = xs0 + c
        ytop = -self.Rb + a
        dx0, dy0, dx1, dy1 = det_box
        k = 0.17
        aspect = (dy1 - dy0 - n * 1.6) / (dx1 - dx0)
        dd = Drawing(p, (dx0, dy0 + n * 1.4, dx1, dy1), (x1 - k, x1 + k), (ytop - k * aspect * 1.2, ytop + k * aspect * 0.8))
        dd.poly(g["copper"]["P"], TINT, M.INK, 1.0, z=2)
        dd.centre(g["centreline"]["P"], M.INK, 1.2, z=5)
        yh = ytop + dd.mm(n * 1.0)
        dd.line([(x1, ytop - c + dd.mm(4)), (x1, yh + dd.mm(4))], M.INK, 0.9, z=7)
        dd.line([(x1 + c, ytop + dd.mm(4)), (x1 + c, yh + dd.mm(4))], M.INK, 0.9, z=7)
        dd.arrow((x1, yh), (x1 + c, yh))
        dd.text(x1 + c / 2, yh + dd.mm(n * 0.75), rf"$c = {c * 1000:.0f}\ \mu\mathrm{{m}}$", n * 0.95)
        dd.paste()
        p.text(dx0, dy0 + n * 0.95, "Detail: one corner", "bold", n, M.SOFT)
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            b = Board(M, p, draw_box, xr, yr)
            b.poly(g["copper"]["P"], TINT)
            u1 = 1.0 if final else ease(stage)
            u2 = 1.0 if final else ease(stage - 1)
            if u1 > 0:
                b.dashed(partial(centre, u1), M.INK, 2.2, dash=9, gap=6)
            if u2 > 0:
                b.line(partial(path, u2), M.COPPER, 4.0)
            b.paste()
            return p.image.reduce(M.SS)

        return frame, 2.0

    def per_exc(self):
        R = self.R
        per = [(R.skew(v) - R.V[v]["mtl_skew_50"]) / R.V[v]["tuning"]["excursions"] for v in ("C", "D", "F")]
        return min(per), max(per)

    def folds_scene(self, shape):
        """Scene 13: loose and tight folds with their spacing dimensioned, and
        the delay efficiency of each on its axis, its spread over three meshes
        as an error bar, under the definition of the efficiency."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "Why the fix falls short", "Close folds let the signal cross the gap",
                            "Neighbouring folds carry current in opposite directions and couple to each "
                            f"other. Folds 1.0 mm apart give {R.eta('S_loose') * 100:.0f} % of the "
                            f"predicted delay. Folds 0.15 mm apart give {R.eta('S_tight') * 100:.0f} %.",
                            source="openEMS  ·  6 mm added on a straight pair  ·  error bars: three meshes")
        t = p.type
        n = t.note
        cases = [("S_loose", "Folds 1.0 mm apart"), ("S_tight", "Folds 0.15 mm apart")]
        if p.wide:
            draws, chart = self.split(box, True, 0.56, gap=30)
            cells = self.split(draws, False, 0.5, gap=14)
        else:
            draws, chart = self.split(box, False, 0.5, gap=22)
            cells = self.split(draws, True, 0.5, gap=24)
        geos = {v: R.geo[v] for v, _ in cases}
        a = geos["S_loose"]["tuning"]["amplitude"]
        yr = (-(self.Rb + self.s) - 0.25, -self.Rb + a + 0.3)
        spans = {v: (geos[v]["tuning"]["section_start"] - 0.35, geos[v]["tuning"]["section_end"] + 0.35)
                 for v, _ in cases}
        ks = []
        for (v, _), (cx0, cy0, cx1, cy1) in zip(cases, cells):
            xr = spans[v]
            ks.append(min((cx1 - cx0) / (xr[1] - xr[0]), (cy1 - cy0 - n * 3.0) / (yr[1] - yr[0])))
        k = min(ks)
        hx0, hy0, hx1, hy1 = chart
        eqh = put_math(p, hx0, hy0 + n * 0.3,
                       r"$\eta = \Delta t_\mathrm{added}\,/\,(\Delta L_\mathrm{added}\,\sqrt{\varepsilon_\mathrm{eff}}\,/\,c)$",
                       n * 1.15, M.INK, anchor="lt")[1]
        pl = Plot(M, p, (hx0, hy0 + eqh + n * 1.4, hx1, hy1), -0.6, 1.6, 0, 1.12,
                  [(0, "1.0 mm"), (1, "0.15 mm")], [(0, "0"), (0.25, "0.25"), (0.5, "0.5"), (0.75, "0.75"), (1, "1")],
                  "Fold spacing", r"Delay efficiency $\eta$", ytitle_math=True)
        pl.hdash(1.0, M.PURPLE)
        p.text(pl.right, pl.Y(1.0) - 6, "Length predicts", "medium", n * 0.9, M.PURPLE, anchor="rs")
        el = R.r["eta_by_level"]
        base = p.image

        def verticals(g):
            tun = g["tuning"]
            xs, out = tun["section_start"], []
            for i in range(tun["excursions"]):
                xl = xs + tun["chamfer"] + i * (tun["top"] + tun["bottom"])
                out += [(xl, +1), (xl + tun["top"], -1)]
            return out

        def paint(stage, final, arrows, glow):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for i, ((v, name), (cx0, cy0, cx1, cy1)) in enumerate(zip(cases, cells)):
                g = geos[v]
                p.text(cx0, cy0 + n, nb(name), "bold", n, M.SOFT)
                b = Board(M, p, (cx0, cy0 + n * 1.5, cx1, cy1 - n * 1.5), spans[v], yr, k=k)
                vs = verticals(g)
                tun = g["tuning"]
                if v == "S_tight" and glow:
                    (xa, _), (xb, _) = vs[1], vs[2]
                    b.box((xa, -self.Rb + 0.12), (xb, -self.Rb + a - 0.12), GLOW, radius=4)
                b.copper(g)
                b.paste()
                if arrows:
                    for x, dd in vs:
                        ym = -self.Rb + a / 2
                        cx, cy = b.P(x, ym)
                        hh = max(6.0, min(14.0, 0.18 * b.k))
                        tip = cy - dd * hh
                        p.line([(cx - hh * 0.6, tip + dd * hh * 0.9), (cx, tip), (cx + hh * 0.6, tip + dd * hh * 0.9)],
                               M.INK, 2.4)
                # the fold spacing g, between the first two verticals' edges, under the folds
                (xa, _), (xb, _) = vs[1], vs[2]
                ga, gb = b.P(xa + self.w / 2, -self.Rb - 0.0), b.P(xb - self.w / 2, -self.Rb)
                yg = b.P(0, -(self.Rb + self.s) - 0.18)[1] + n * 0.6
                for gx in (ga[0], gb[0]):
                    p.line([(gx, ga[1] + 4), (gx, yg + 4)], M.INK, 1.0)
                if gb[0] - ga[0] > 18:
                    arrow(p, (ga[0], yg), (gb[0], yg), M.INK, width=1.6, size=7)
                else:
                    arrow(p, (ga[0] - 18, yg), (ga[0], yg), M.INK, width=1.6, size=7, both=False)
                    arrow(p, (gb[0] + 18, yg), (gb[0], yg), M.INK, width=1.6, size=7, both=False)
                gv = tun["fold_edge_spacing"]
                put_math(p, gb[0] + 22, yg, rf"$g = {gv:.1f}\ \mathrm{{mm}}$" if gv >= 1 else
                         rf"$g = {gv:.2f}\ \mathrm{{mm}}$", n * 0.95, M.INK, anchor="lm")
                # the bar
                u = 1.0 if final else ease(stage - 1 - i * 0.3)
                if u > 0:
                    eta = R.eta(v)
                    cx = pl.X(i)
                    bw = (pl.X(1) - pl.X(0)) * 0.42
                    p.rect((cx - bw / 2, pl.Y(eta * u), cx + bw / 2, pl.bottom), fill=M.COPPER, radius=3)
                    if u >= 1:
                        vals = [el[v][l] for l in el[v]]
                        pl.errbar(cx, min(vals), max(vals), M.INK, cap=8, width=2.0)
                        p.text(cx + bw / 2 + 12, pl.Y(eta) + n * 0.35, f"{eta:.2f}", "bold", n * 1.05, M.INK)
            return p.image

        def frame(stage, final):
            # the current arrows and the glow on the gap fade in over 0.3 of the sweep, rather than pop
            a1 = 1.0 if final else clamp((stage - 0.4) / 0.3)
            a2 = 1.0 if final else clamp((stage - 1.0) / 0.3)
            img = paint(stage, final, a1 >= 1, a2 >= 1)
            if 0 < a1 < 1:
                img = Image.blend(paint(stage, final, False, False).copy(), img.copy(), a1)
            elif 0 < a2 < 1:
                img = Image.blend(paint(stage, final, True, False).copy(), img.copy(), a2)
            return img.reduce(M.SS)

        return frame, 2.0

    def stripline_scene(self, shape):
        """Scene 14: the same copper in stripline, the share each tuning removes
        in each medium."""
        M, R = self.M, self.R
        sl_err = abs(R.r["skew_geometric_sl"] - R.skew("B_sl")) / R.r["skew_geometric_sl"] * 100
        fold_sl = (R.eta("S_loose_sl") - R.eta("S_tight_sl")) * 100
        p, box = self.scene(shape, "The same copper in stripline", "Stripline has the same problem",
                            f"Geometry predicts the stripline bend to {sl_err:.1f} %. The serpentines remove "
                            f"{R.removed('F_sl', 'B_sl'):.0f} %, {R.removed('C_sl', 'B_sl'):.0f} % and "
                            f"{R.removed('D_sl', 'B_sl'):.0f} % of the skew. Close folds still cost "
                            f"{fold_sl:.0f} points of delay.",
                            source=f"openEMS  ·  {self.cell_um:.0f} {MU}m mesh  ·  the stripline set")
        t = p.type
        n = t.note
        xs_box, chart = self.split(box, p.wide, 0.32 if p.wide else 0.3, gap=28)
        self.xsection(p, xs_box, strip=True)
        cx0, cy0, cx1, cy1 = chart
        ky = self.key(p, cx0, cx1, cy0, [(M.COPPER, "Microstrip", False), (M.TEAL, "Stripline", False)])
        groups = [("F", "1 excursion"), ("C", "2 excursions"), ("D", "4 excursions")]
        pl = Plot(M, p, (cx0, ky, cx1, cy1), -0.5, 2.5, 0, 100, [(i, nm) for i, (_, nm) in enumerate(groups)],
                  [(0, "0"), (25, "25"), (50, "50"), (75, "75"), (100, "100")], None, "Skew removed (%)")
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            slot = pl.X(1) - pl.X(0)
            for i, (v, _) in enumerate(groups):
                u = 1.0 if final else ease(stage - i)
                if u <= 0:
                    continue
                cx = pl.X(i)
                bw = slot * 0.3
                for dx, var, ref, colour in ((-bw * 0.56, v, "B", M.COPPER), (bw * 0.56, v + "_sl", "B_sl", M.TEAL)):
                    val = R.removed(var, ref)
                    p.rect((cx + dx - bw / 2, pl.Y(val * u), cx + dx + bw / 2, pl.bottom), fill=colour, radius=3)
                    if u >= 1:
                        p.text(cx + dx, pl.Y(val) + n * 1.25, f"{val:.0f}", "bold", n * 0.95, M.CARD, anchor="ms")
            return p.image.reduce(M.SS)

        return frame, 3.0

    def placement_scene(self, shape):
        """Scene 15: the same two excursions next to the bend and at the launch,
        and the skew read at each frequency, under the expression it comes from."""
        M, R = self.M, self.R
        fd = R.V["C_far"]["skew_fd_ps"]
        p, box = self.scene(shape, "Where the serpentine goes", "Put the fix next to the bend",
                            f"At the launch the same serpentine leaves {R.skew('C_far'):.1f} ps instead of "
                            f"{R.skew('C'):.1f} ps. Its skew also grows with frequency, from "
                            f"{fd['5']:.1f} ps at 5 GHz to {fd['25']:.1f} ps at 25 GHz.",
                            source=f"openEMS  ·  {self.cell_um:.0f} {MU}m mesh  ·  boards C and C far")
        t = p.type
        n = t.note
        draws, chart = self.split(box, p.wide, 0.34 if p.wide else 0.28)
        dx0, dy0, dx1, dy1 = draws
        cases = [("C", "Next to the bend", M.TEAL), ("C_far", "At the launch", M.COPPER)]
        for i, (v, name, colour) in enumerate(cases):
            if p.wide:
                hh = (dy1 - dy0) / 2
                cell = (dx0, dy0 + i * hh, dx1, dy0 + (i + 1) * hh)
            else:
                ww = (dx1 - dx0 - 16) / 2
                cell = (dx0 + i * (ww + 16), dy0, dx0 + i * (ww + 16) + ww, dy1)
            cx0, cy0, cx1, cy1 = cell
            p.text(cx0, cy0 + n, name, "bold", n, colour)
            self.plan(p, (cx0, cy0 + n * 1.4, cx1, cy1 - 6), R.geo[v], lit=[self.section(R.geo[v])], ports=False)
        cx0, cy0, cx1, cy1 = chart
        eqh = put_math(p, cx1, cy0 + n * 0.2, r"$\tau(f) = 2\arctan|S_{cd21}\,/\,S_{dd21}|\,/\,\omega$", n * 1.1,
                       M.INK, anchor="rt")[1]
        pl = Plot(M, p, (cx0, cy0 + eqh + n * 0.6, cx1, cy1), 1, 30, 0, 9,
                  [(1, "1"), (10, "10"), (20, "20"), (30, "30")], [(0, "0"), (2, "2"), (4, "4"), (6, "6"), (8, "8")],
                  "Frequency (GHz)", "Skew read at each frequency (ps)")
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            upto = 1 + stage
            for v, _, colour in cases:
                f, tau = R.fd[v]
                pl.series(f, tau, upto, colour)
            if final:
                pl.leader(5.0, fd["5"], f"{fd['5']:.1f} ps at 5 GHz", M.COPPER, n * 1.0, -n * 2.6)
                pl.leader(25.0, fd["25"], f"{fd['25']:.1f} ps at 25 GHz", M.COPPER, -n * 1.4, -n * 1.6)
                f, tau = R.fd["C"]
                j = min(range(len(f)), key=lambda i: abs(f[i] - 15))
                pl.leader(f[j], tau[j], f"{R.skew('C'):.1f} ps, flat", M.TEAL, n * 1.0, n * 2.2)
            else:
                pl.cursor(upto)
            return p.image.reduce(M.SS)

        return frame, 29.0

    def tdr_scene(self, shape):
        """Scene 16: the impedance along the line, the broad excursion's peak lit."""
        M, R = self.M, self.R
        zf, zb = R.V["F"]["tdr_35ps"]["zdiff_max"], R.V["B"]["tdr_35ps"]["zdiff_max"]
        p, box = self.scene(shape, "The cost of a broad excursion", "The impedance rises where P leaves N",
                            f"Over the broad excursion the pair impedance rises to {zf:.0f} ohm, against "
                            f"{zb:.0f} ohm for the plain bend. It reflects more signal than the other "
                            "length-matched serpentines.",
                            source="openEMS  ·  differential TDR, 35 ps edge  ·  boards B and F")
        t = p.type
        n = t.note
        tb, zbs = R.tdr["B"]
        tf, zfs = R.tdr["F"]
        jf = max(range(len(zfs)), key=lambda i: zfs[i])
        ky = self.key(p, box[0], box[2], box[1], [(OLD, "Plain bend", False), (M.COPPER, "Broad excursion", False)])
        pl = Plot(M, p, (box[0], ky, box[2], box[3]), 0, 400, 88, 120,
                  [(0, "0"), (100, "100"), (200, "200"), (300, "300"), (400, "400")],
                  [(90, "90"), (100, "100"), (110, "110"), (120, "120")], "Round-trip time (ps)",
                  "Differential impedance (ohm)")
        lo, hi = tf[jf] - 28, tf[jf] + 28
        p.rect((pl.X(lo), pl.top, pl.X(hi), pl.bottom), fill=GLOW)
        p.text((pl.X(lo) + pl.X(hi)) / 2, pl.bottom - n * 0.5, "the excursion", "medium", n * 0.9, M.COPPER_TEXT,
               anchor="ms")
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            pl.series(tb, zbs, stage, OLD)
            pl.series(tf, zfs, stage, M.COPPER)
            if final:
                pl.leader(tf[jf], zfs[jf], f"{zf:.0f} ohm", M.COPPER, n * 2.0, -n * 0.1)
                jb = max((i for i in range(len(zbs)) if 140 < tb[i] < 200), key=lambda i: zbs[i])
                pl.leader(tb[jb], zbs[jb], f"{zb:.0f} ohm", OLD, n * 1.8, -n * 1.3)
            else:
                pl.cursor(stage)
            return p.image.reduce(M.SS)

        return frame, 400.0

    def eye_scene(self, shape):
        """Scene 17: 16 Gb/s eyes of the straight pair and the untuned bend, as
        revision 1 drew them (the user preferred it, 2026-10-20), with the
        source line every result card now carries."""
        M, R = self.M, self.R
        ea, eb = R.eyes["A"], R.eyes["B"]
        p, box = self.scene(shape, f"What {R.skew('B'):.1f} ps does at 16 Gb/s",
                            "The eye barely closes, but common mode grows",
                            f"The eye height falls only from {ea['height']:.1f} % to {eb['height']:.1f} % of "
                            f"the swing. Common mode grows to {eb['vc_pp']:.1f} % of the swing, and that is "
                            "the real cost.",
                            source="openEMS  ·  PRBS7 at 16 Gb/s, 35 ps edges  ·  boards A and B")
        t = p.type
        cols = self.split(box, True, 0.5, gap=30)
        panels = []
        for (v, name), (cx0, cy0, cx1, cy1) in zip((("A", "Straight pair"), ("B", "Untuned bend")), cols):
            e = dict(R.eyes[v])
            # revision 1 kept the eye's time in ps and the common mode's in ps
            e["x"] = [x * e["ui_ps"] for x in e["x"]]
            e["vc_t"] = [x * 1000 for x in e["vc_t"]]
            p.text(cx0, cy0 + t.note, name, "bold", t.note, M.SOFT)
            split = cy0 + (cy1 - cy0) * 0.62
            ui = e["ui_ps"]
            eye = LanePlot(M, p, (cx0, cy0 + t.note * 1.6, cx1, split), 0, 2 * ui, -0.05, 1.0, (0, 0.5, 1),
                       ((0, "0"), (ui, f"{ui:.1f}"), (2 * ui, nb(f"{2 * ui:.0f} ps"))), "V")
            cm = LanePlot(M, p, (cx0, split + t.note * (2.0 if p.wide else 3.0), cx1, cy1), 0, e["vc_t"][-1], -75, 75,
                      (-50, 0, 50),
                      ((0, "0"), (e["vc_t"][-1], nb(f"{e['vc_t'][-1] / 1000:.1f} ns"))), "mV")
            panels.append((v, e, eye, cm))
        base = p.image
        cache = {"n": 0, "img": None}

        def frame(stage, final):
            u = 1.0 if final else min(max(stage, 0.0), 1.0)
            n_draw = {v: int(len(e["traces"]) * u) for v, e, _, _ in panels}
            if cache["img"] is None or n_draw[panels[0][0]] < cache["n"]:
                cache["img"], cache["n"] = base.copy(), 0
            p.image = cache["img"]
            p.draw = ImageDraw.Draw(p.image)
            for v, e, eye, cm in panels:
                for tr in e["traces"][cache["n"]: n_draw[v]]:
                    eye.series(e["x"], tr, 1e9, M.COPPER, 1.0, columns=200)
            cache["n"] = n_draw[panels[0][0]]
            cache["img"] = p.image
            p.image = cache["img"].copy()
            p.draw = ImageDraw.Draw(p.image)
            for v, e, eye, cm in panels:
                cm.series(e["vc_t"], e["vc"], e["vc_t"][-1] * u, M.TEAL, 1.6, columns=500)
                if final:
                    x = eye.X(eye.x1 * 0.5)
                    hgt = nb(f"Eye height {e['height']:.1f} %")
                    wide = p.width_of(hgt, "bold", t.note)
                    p.rect((x - wide / 2 - 6, eye.Y(0.5) - t.note * 0.9, x + wide / 2 + 6, eye.Y(0.5) + t.note * 0.45),
                           fill=M.CARD, radius=4)
                    p.text(x, eye.Y(0.5) + t.note * 0.3, hgt, "bold", t.note, M.INK, anchor="ms")
                    pass
            for v, e, eye, cm in panels:
                share = nb(f"{e['vc_pp']:.1f} % of the swing") if final else ""
                colour = M.TEAL if (share and v == "B") else M.SOFT
                if p.wide:
                    p.text(cm.left - t.note * 2.2, cm.top - t.note * 0.55,
                           "Common mode" + (f": {share}" if share else ""), "bold", t.note * 0.95, colour)
                else:
                    p.text(cm.left - t.note * 2.2, cm.top - t.note * 1.6, "Common mode", "bold", t.note * 0.95,
                           M.SOFT)
                    if share:
                        p.text(cm.left - t.note * 2.2, cm.top - t.note * 0.45, share, "bold", t.note * 0.95, colour)
            return p.image.reduce(M.SS)

        return frame, 1.0

    def calibrated_scene(self, shape):
        """Scene 18: the broad excursion sized in the solver, on the scope, with
        the three before-and-after results stacked beside it on every shape."""
        M, R = self.M, self.R
        p_fix = (f"We add back the delay that each serpentine lost. The broad excursion goes to "
                 f"{R.skew('F_cal'):.2f} ps and two excursions go to {R.skew('C_cal'):.2f} ps. Four small "
                 "ones still need a second run.")
        rows = [("1 broad excursion", "F"), ("2 excursions", "C"), ("4 small excursions", "D")]

        def panel(p, box):
            t = p.type
            n = t.note
            x0, y0, x1, y1 = box
            size = n * 1.05
            p.text(x0, y0 + n * 0.95, "Equal length, then sized in the solver", "bold", n * 0.95, M.SOFT)
            if p.wide:
                row_h = (y1 - y0 - n * 1.6) / len(rows)
                for i, (name, v) in enumerate(rows):
                    y = y0 + n * 1.6 + row_h * i + n * 1.1
                    p.text(x0, y, name, "medium", n * 0.95, M.INK)
                    yy = y + size * 1.45
                    xb = p.text(x0, yy, nb(f"{ps(R.skew(v))} ps"), "bold", size, OLD)
                    arrow(p, (xb + n * 0.6, yy - size * 0.35), (xb + n * 2.4, yy - size * 0.35), M.SOFT, width=1.8,
                          size=8, both=False)
                    p.text(xb + n * 2.8, yy, nb(f"{ps(R.skew(v + '_cal'), R.unc(v + '_cal'))} ps"), "bold", size,
                           M.COPPER)
            else:
                cols = (x1 - x0) / len(rows)
                for i, (name, v) in enumerate(rows):
                    xc = x0 + cols * (i + 0.5)
                    y = y0 + n * 3.0
                    p.text(xc, y, name, "medium", n * 0.9, M.INK, anchor="ms")
                    p.text(xc, y + size * 1.5, nb(f"{ps(R.skew(v))} ps"), "bold", size, OLD, anchor="ms")
                    arrow(p, (xc, y + size * 1.9), (xc, y + size * 3.0), M.SOFT, width=1.8, size=8, both=False)
                    p.text(xc, y + size * 4.1, nb(f"{ps(R.skew(v + '_cal'), R.unc(v + '_cal'))} ps"), "bold",
                           size, M.COPPER, anchor="ms")

        return self.scope_scene(shape, "Size the serpentine by its delay, not its length",
                                "One more solver run removes most of the rest", p_fix, "F_cal", old="F",
                                panel=panel, old_name="Equal length",
                                source=f"openEMS  ·  {self.cell_um:.0f} {MU}m mesh  ·  boards F, C and D, "
                                       "sized from their own residual")

    def rules_scene(self, shape):
        """Scene 19: four rules, each fading in beside a small drawing, with the
        run result behind it. On the landscape shape they sit in a 2 by 2 grid
        of panels, so the card has no empty half; on the tall shapes, one under
        another."""
        M, R = self.M, self.R
        M_ = M
        p = shape.new()
        t = p.type
        n = t.note
        y = M._heading(p, p.top, "For a bent pair at this pitch", nb(f"Four rules from {R.runs} solver runs"))
        ix0, iy0, ix1, iy1 = p.card((M.MARGIN, y + t.body * 0.4, p.right, shape.bottom(p)))
        cals = [R.skew(v) for v in ("F_cal", "C_cal", "D_cal")]
        rules = [("Use few excursions.",
                  f"One excursion leaves {R.skew('F'):.1f} ps. Four leave {R.skew('D'):.1f} ps."),
                 ("Keep the folds apart.",
                  f"Folds 1.0 mm apart give {R.eta('S_loose') * 100:.0f} % of the delay. "
                  f"At 0.15 mm, {R.eta('S_tight') * 100:.0f} %."),
                 ("Put the fix next to the bend.",
                  f"{R.skew('C'):.1f} ps next to the bend. {R.skew('C_far'):.1f} ps at the launch."),
                 ("Size it by delay, not length.",
                  f"One more solver run: {min(cals):.2f} to {max(cals):.1f} ps.")]
        cells = []
        if p.wide:
            g = 22
            cw, ch = (ix1 - ix0 - g) / 2, (iy1 - iy0 - g) / 2
            for i in range(4):
                cx, cy = ix0 + (i % 2) * (cw + g), iy0 + (i // 2) * (ch + g)
                cells.append((cx, cy, cx + cw, cy + ch))
        else:
            step = (iy1 - iy0) / 4
            for i in range(4):
                cells.append((ix0, iy0 + i * step, ix1, iy0 + (i + 1) * step))
        base = p.image

        def icon(i, box):
            x0, y0, x1, y1 = box
            w, h = x1 - x0, y1 - y0
            ym = y0 + h * 0.62
            cp = M_.COPPER
            if i == 0:
                p.line([(x0, ym), (x0 + w * 0.32, ym), (x0 + w * 0.32, y0 + h * 0.2), (x0 + w * 0.68, y0 + h * 0.2),
                        (x0 + w * 0.68, ym), (x1, ym)], cp, 4)
                p.line([(x0, ym + h * 0.22), (x1, ym + h * 0.22)], M_.TEAL, 4)
            elif i == 1:
                pts = [(x0, ym)]
                for k in range(3):
                    xa = x0 + w * (0.08 + k * 0.3)
                    pts += [(xa, ym), (xa, y0 + h * 0.15), (xa + w * 0.14, y0 + h * 0.15), (xa + w * 0.14, ym)]
                pts.append((x1, ym))
                p.line(pts, cp, 4)
                p.line([(x0, ym + h * 0.22), (x1, ym + h * 0.22)], M_.TEAL, 4)
            elif i == 2:
                r1, r2 = h * 0.24, h * 0.42
                cx, cy = x0 + w * 0.7, y0 + h * 0.5
                for r, col in ((r1, cp), (r2, M_.TEAL)):
                    arcp = [(cx + r * math.cos(u), cy + r * math.sin(u)) for u in np.linspace(-math.pi / 2, math.pi / 2, 30)]
                    p.line([(x0, cy - r), (cx, cy - r)] + arcp + [(x0, cy + r)], col, 4)
                p.rect((cx - w * 0.36, cy - r1 - h * 0.14, cx - w * 0.06, cy - r1 + h * 0.14), fill=GLOW, radius=6)
            else:
                xs = np.linspace(x0, x1, 40)
                for col in (M_.COPPER, M_.TEAL):
                    p.line([(x, y1 - h * 0.1 - (h * 0.75) * 0.5 * (1 + math.tanh((x - (x0 + w / 2)) / (w * 0.09))))
                            for x in xs], col, 4)

        def draw_rule(i):
            x0, y0, x1, y1 = cells[i]
            rule, why = rules[i]
            if p.wide:
                p.rect((x0, y0, x1, y1), fill=M.PAGE, radius=12)
                pad = n * 1.1
                iw = min((x1 - x0) * 0.34, (y1 - y0) * 1.1)
                ih = iw * 0.5
                icon(i, (x0 + pad, (y0 + y1) / 2 - ih / 2, x0 + pad + iw, (y0 + y1) / 2 + ih / 2))
                tx = x0 + pad * 2 + iw
                width = x1 - pad - tx
            else:
                iw = min((x1 - x0) * 0.3, (y1 - y0) * 2.6)
                icon(i, (x0 + 6, y0 + (y1 - y0) * 0.22, x0 + 6 + iw, y0 + (y1 - y0) * 0.78))
                tx = x0 + iw + t.body * 1.4
                width = x1 - tx
            size, note = t.body * 1.05, n
            bal = p.wide                              # no line left with one word on it
            with p.measuring():
                h1 = p.paragraph(tx, 0, width, [(rule, "bold", M.INK)], size, size * 1.2, balance=bal)
                h2 = p.paragraph(tx, 0, width, [(nb(why), "medium", M.SOFT)], note, note * 1.3, balance=bal)
            gap = size * 0.35 + note * 1.3          # first block's last baseline to the second's first
            total = size * 0.75 + h1 + gap + h2 + note * 0.25
            top = (y0 + y1) / 2 - total / 2 + size * 0.75
            yy = p.paragraph(tx, top, width, [(rule, "bold", M.INK)], size, size * 1.2, balance=bal)
            p.paragraph(tx, yy + gap, width, [(nb(why), "medium", M.SOFT)], note, note * 1.3, balance=bal)

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for i in range(len(rules)):
                alpha = 1.0 if final else clamp((stage - i) / 0.35)
                if alpha <= 0:
                    continue
                if alpha < 1:
                    before = p.image.copy()
                    draw_rule(i)
                    p.image = Image.blend(before, p.image, alpha)
                    p.draw = ImageDraw.Draw(p.image)
                else:
                    draw_rule(i)
            return p.image.reduce(M.SS)

        return frame, 4.0

    def summary_shot(self, shape):
        """Scene 20: the summary card, with a foot line naming the runs and the
        bounds behind it."""
        M, R = self.M, self.R
        cals = [abs(R.skew(v)) for v in ("C_cal", "D_cal", "F_cal")]
        line = (f"Untuned bend: {R.skew('B'):.1f} ps. Serpentines of exactly the right length: "
                f"{R.skew('F'):.1f} to {R.skew('D'):.1f} ps. Serpentines sized in the solver: "
                f"{min(cals):.2f} to {max(cals):.1f} ps.")
        bounds = [R.unc(v) for v in ("B", "C", "D", "F") if R.unc(v)]
        foot = (f"{R.runs} runs  ·  3 meshes  ·  numerical bound {PM}{min(bounds):.2f} to "
                f"{PM}{max(bounds):.1f} ps")
        p = shape.new()
        t = p.type

        def block(top):
            y = top + t.note
            p.text(p.width / 2, y, f"Run in openEMS {R.version}", "bold", t.note, M.TEAL, anchor="ms")
            y = p.paragraph(M.MARGIN, y + t.title * 1.25, p.right - M.MARGIN,
                            M._runs(("Equal length is not equal delay", "bold")), t.title, t.title * 1.14, align="c")
            y = p.paragraph(M.MARGIN, y + t.subtitle * 2, p.right - M.MARGIN, M._runs((nb(line), "medium", M.SOFT)),
                            t.subtitle, t.subtitle * 1.42, align="c")
            p.text(p.width / 2, y + t.subtitle * 1.6, nb(foot), "medium", t.note, M.NOTE, anchor="ms")
            return y + t.subtitle * 1.6

        p.centred(block, bottom=shape.bottom(p))
        return p.image.reduce(M.SS)

    # -- the sequence -----------------------------------------------------------------------

    def shots(self, shape):
        """Each shot in order: ("still", image, seconds) or ("play", (frame, end),
        sweep seconds, None, hold seconds)."""
        R = self.R
        sk_b = R.skew("B")
        geo_err = math.ceil(abs(R.r["analytic"]["single_line"]["skew_ps"] - sk_b)
                            / R.r["analytic"]["single_line"]["skew_ps"] * 100)
        mesh = f"openEMS  ·  {self.cell_um:.0f} {MU}m mesh"
        out = [
            ("still", lambda: self.title_shot(shape), 4.0),
            ("play", lambda: self.pair_scene(shape), SWEEP, None, 4.6),
            ("play", lambda: self.skew_scene(shape), SWEEP, None, 4.8),
            ("still", lambda: self.board_shot(shape), 7.0),
            ("play", lambda: self.bend_scene(shape), 3.6, None, 5.0),
            ("play", lambda: self.model_scene(shape), 4.0, None, 3.4),
            ("play", lambda: self.mesh_scene(shape), 3.0, None, 4.6),
            ("play", lambda: self.scope_scene(shape, "The untuned bend in openEMS", f"P arrives {sk_b:.1f} ps before N",
                                              f"The field solver agrees with geometry to within {geo_err:.0f} %. "
                                              f"The skew puts a {R.vc_peak('B'):.0f} mV common-mode pulse on the "
                                              "line.", "B", source=f"{mesh}  ·  board B"), SWEEP, None, 4.6),
            ("still", lambda: self.fix_shot(shape), 7.0),
            ("play", lambda: self.bars_scene(shape), 3.0, None, 5.4),
            ("play", lambda: self.scope_scene(shape, "Four small excursions at the receiver",
                                              "The lengths match but P still arrives first",
                                              f"The skew falls from {sk_b:.1f} ps to {R.skew('D'):.1f} ps, not to "
                                              f"zero. The common-mode pulse falls from {R.vc_peak('B'):.0f} mV to "
                                              f"{R.vc_peak('D'):.0f} mV.", "D", old="B",
                                              source=f"{mesh}  ·  board D, board B in grey"), SWEEP, None, 4.2),
            ("play", lambda: self.corner_scene(shape), 2.4, None, 5.0),
            ("play", lambda: self.folds_scene(shape), 2.4, None, 5.8),
            ("play", lambda: self.stripline_scene(shape), 2.4, None, 4.6),
            ("play", lambda: self.placement_scene(shape), SWEEP, None, 4.8),
            ("play", lambda: self.tdr_scene(shape), SWEEP, None, 4.2),
            ("play", lambda: self.eye_scene(shape), SWEEP, None, 4.8),
            ("play", lambda: self.calibrated_scene(shape), SWEEP, None, 4.8),
            ("play", lambda: self.rules_scene(shape), 3.2, None, 3.6),
            ("still", lambda: self.summary_shot(shape), 5.0),
        ]
        return out

    def frames(self, shape):
        M = self.M
        previous = None

        def fade(into, seconds=M.FADE):
            if previous is not None:
                steps = round(seconds * M.FPS)
                for step in range(1, steps + 1):
                    yield Image.blend(previous, into, step / (steps + 1)).tobytes()

        def hold(image, seconds):
            for _ in range(round(seconds * M.FPS)):
                yield image.tobytes()

        for shot in self.shots(shape):
            if shot[0] == "still":
                _, make, seconds = shot
                image = make()
                yield from fade(image)
                yield from hold(image, seconds)
                previous = image
            else:
                _, make, seconds, _, after = shot
                frame, end = make()
                still = frame(0.0, False)
                yield from fade(still)
                yield from hold(still, 0.4)
                count = round(seconds * M.FPS)
                last = None
                for i in range(1, count + 1):
                    last = frame(end * i / count, False)
                    yield last.tobytes()
                done = frame(end, True)
                # the end labels fade in rather than pop (skill, section 3, rule 9)
                for k in range(1, FADE_IN + 1):
                    yield Image.blend(last, done, k / FADE_IN).tobytes()
                yield from hold(done, after - FADE_IN / M.FPS)
                previous = done
        brand = M._brand_shot(shape)
        yield from fade(brand, M.BRAND_FADE)
        yield from hold(brand, M.BRAND_HOLD)

    def poster(self, shape):
        frame, end = self.bars_scene(shape)
        return frame(end, True)


def inside_path(pts, d):
    """The centre line pulled toward the inside of each turn by d (mm): the
    way the current cuts each corner."""
    out = [pts[0]]
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        ux, uy = b[0] - a[0], b[1] - a[1]
        vx, vy = c[0] - b[0], c[1] - b[1]
        la, lb = math.hypot(ux, uy), math.hypot(vx, vy)
        if la < 1e-9 or lb < 1e-9:
            out.append(b)
            continue
        cross = ux * vy - uy * vx
        if abs(cross) < 1e-9:
            out.append(b)
            continue
        sign = 1 if cross > 0 else -1          # +1: a left turn, the inside is to the left
        n1 = (-uy / la * sign, ux / la * sign)
        n2 = (-vy / lb * sign, vx / lb * sign)
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        lbis = math.hypot(bx, by)
        out.append((b[0] + bx / lbis * d, b[1] + by / lbis * d))
    out.append(pts[-1])
    return out


def _padded(M, shape):
    class Padded(M.Shape):
        def new(self, zoom=None):
            p = super().new(zoom)
            p.top += p.type.title * 0.6
            return p

    return Padded(**{f.name: getattr(shape, f.name) for f in dataclasses.fields(shape)})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--make", type=Path, default=FANG / "site" / "social" / "make.py")
    parser.add_argument("--stills", type=Path, help="write the finished frame of each shot here instead")
    parser.add_argument("--only", help="draw only the shape with this name")
    parser.add_argument("--shots", help="with --stills, only these shots (1-based, comma separated)")
    parser.add_argument("--mid", action="store_true", help="with --stills, also save each sweep half-way")
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location("social_make", args.make)
    M = importlib.util.module_from_spec(spec)
    sys.modules["social_make"] = M
    spec.loader.exec_module(M)
    video = Video(M, Runs())
    shapes = {k: v for k, v in video.shapes.items() if not args.only or k == args.only}

    if args.stills:
        args.stills.mkdir(parents=True, exist_ok=True)
        want = {int(s) for s in args.shots.split(",")} if args.shots else None
        for name, shape in shapes.items():
            for i, shot in enumerate(video.shots(shape)):
                if want and i + 1 not in want:
                    continue
                if shot[0] == "still":
                    image = shot[1]()
                else:
                    frame, end = shot[1]()
                    if args.mid:
                        frame(end * 0.5, False).save(args.stills / f"{name}-{i + 1:02d}-mid.png")
                    image = frame(end, True)
                image.save(args.stills / f"{name}-{i + 1:02d}.png")
        print("stills in", args.stills)
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for name, shape in shapes.items():
        out = OUT / f"{name}.mp4"
        # No track for now, at the user's request (2026-10-19).
        seconds = M._encode(video.frames(shape), out, shape.size)
        video.poster(shape).save(OUT / f"{name}.png", optimize=True)
        print(out, f"{seconds:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

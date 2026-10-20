"""The explainer video for the meander study, in the three shapes fang's
site/social/make.py draws its videos in, from the scene script in
/home/animesh/fang/renders/diffpair-meanders/video/script.md.

    python scripts/video.py [--make PATH] [--stills DIR] [--only SHAPE]

It draws with make.py's pieces (the page, the head, the title and closing
cards, the colours and type, the encoder and the track's levelling), loaded
from --make, as site/social/decoupling.py does. Every number on it comes from
this study's runs: build/results/results.json, the four-ports in
build/sparams/ (waveforms, eyes, TDR and the skew against frequency are
computed from them as the frames are drawn), the copper from geometry.py and
the solver's grid from model.py. Nothing is typed in by hand.

Scene 2 is the one drawing that is not a run: a schematic of what a
differential receiver does, with no axes and no numbers.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FANG = Path("/home/animesh/fang")
OUT = FANG / "renders" / "diffpair-meanders" / "video"
sys.path.insert(0, str(HERE))
import analysis as an  # noqa: E402
import geometry  # noqa: E402
import model  # noqa: E402

MU, NB, MINUS = "µ", " ", "−"

#: The video's title, in the form of the user's other videos (the user asked
#: for the fang prefix on 2026-10-19).
TITLE = ("Fang", "Simulating Serpentine Length Matching")

#: A sweep plays for this long behind its cursor.
SWEEP = 2.6

#: Grey for a reading that a later one replaces, and the tint behind a part
#: a scene is about.
OLD, GLOW, TINT = "#a9a9b2", "#ecd3b8", "#e9c9a6"

#: The edge every time-domain scene uses (10 to 90 %), and the scope window
#: either side of the differential 50 % crossing.
EDGE, HALF = 50e-12, 45.0


def nb(text: str) -> str:
    """A number and its unit stay on one line."""
    import re
    return re.sub(r"(\d) (?=[A-Za-zµ%])", "\\1" + NB, text)


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
        x = (np.arange(0, 2 * per, 5) * dt * 1e12).tolist()
        vc_t = ((t[n0: n0 + 40 * per] - t[n0]) * 1e12)[::4].tolist()
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

    def t50(self, v, which):
        return self.V[v]["timing"]["50"][which]

    def removed(self, v, ref="B"):
        return (1 - self.skew(v) / self.skew(ref)) * 100

    def vc_peak(self, v):
        return max(self.wave[v]["vc_far"]) * 1000

    def eta(self, v):
        return self.V[v]["timing"]["50"]["eta"]


# --------------------------------------------------------------------------
# Drawing pieces
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

    def grid(self, xs, ys, colour="#b4b7c2", width=0.55):
        for x in xs:
            if self.xr[0] <= x <= self.xr[1]:
                self.line([(x, self.yr[0]), (x, self.yr[1])], colour, width)
        for y in ys:
            if self.yr[0] <= y <= self.yr[1]:
                self.line([(self.xr[0], y), (self.xr[1], y)], colour, width)

    def paste(self):
        if self.p.drawing:
            self.p.image.paste(self.layer, (round(self.x0 * self.p.ss), round(self.y0 * self.p.ss)))

    def ports(self, g, lit=None):
        """The four lumped ports as small ink squares; `lit` ports glow copper."""
        side = max(4.0, 0.22 * self.k)
        for q in g["ports"]:
            x, y = self.P(q["x"], q["y"])
            if lit and q["number"] in lit:
                self.p.disc(x, y, side * 1.6, GLOW)
            self.p.rect((x - side / 2, y - side / 2, x + side / 2, y + side / 2), fill=self.M.INK)


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


class Plot:
    """Axes drawn once, series drawn up to a cursor on each frame: the
    decoupling video's Plot, with ticks given as (value, text)."""

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

    # -- the scene frame --------------------------------------------------------

    def scene(self, shape, kicker, headline, text):
        """The heading, a white card under it, the scene's sentences at the
        top of the card. Returns the page and the room left in the card."""
        M = self.M
        p = shape.new()
        t = p.type
        y = M._heading(p, p.top, kicker, nb(headline))
        ix0, iy0, ix1, iy1 = p.card((M.MARGIN, y + t.body * 0.4, p.right, shape.bottom(p)))
        size = t.note * 1.08
        yy = p.paragraph(ix0, iy0 + size, ix1 - ix0, [(nb(text), "medium", M.SOFT)], size, size * 1.35)
        return p, (ix0, yy + size * 1.0, ix1, iy1)

    def key(self, p, x0, x1, y, entries, size=None):
        """A key centred over x0..x1 from y; returns its foot."""
        M, t = self.M, p.type
        size = size or t.note
        rows = M._key_rows(p, entries, size, x1 - x0)
        M._legend(p, (x0 + x1) / 2, y + size, rows, size)
        return y + size + (len(rows) - 1) * size * 1.75 + size * 0.7

    def tag(self, p, x, y, text, colour=None, anchor="ls", size=None):
        size = size or p.type.note
        p.text(x, y, nb(text), "medium", size, colour or self.M.INK, anchor=anchor)

    def slower(self, p, x, y, span_ps):
        factor = self.M._times_slower(span_ps * 1e-12, SWEEP)
        text = f"Shown {grouped(factor)} times slower"
        size = p.type.note * 0.9
        wide = p.width_of(text, "medium", size)
        p.rect((x - wide - 6, y - size * 0.95, x + 2, y + size * 0.35), fill=self.M.CARD, radius=4)
        p.text(x, y, text, "medium", size, self.M.NOTE, anchor="rs")

    @staticmethod
    def split(box, wide, share=0.5, gap=24):
        x0, y0, x1, y1 = box
        if wide:
            m = x0 + (x1 - x0) * share
            return (x0, y0, m - gap / 2, y1), (m + gap / 2, y0, x1, y1)
        m = y0 + (y1 - y0) * share
        return (x0, y0, x1, m - gap / 2), (x0, m + gap / 2, x1, y1)

    # -- drawings -------------------------------------------------------------------

    def xsection(self, p, box, strip=False, signs=False, sizes=True):
        """The pair in cross-section, true scale, its sizes in a line or two
        under it. `signs` marks P plus and N minus instead of naming them."""
        M, t = self.M, p.type
        h, w, s = self.R.p["stackup"]["dielectric_height"], self.w, self.s
        slab = self.R.p["stripline"]["plane_spacing"] if strip else h
        plane = 0.035
        lab = t.note
        span = 1.5
        tall = slab + 2 * plane + (0 if strip else 0.12)
        x0, y0, x1, y1 = box
        lines = []
        if sizes:
            lines = [f"w {w:g} mm, pitch s {s:g} mm",
                     f"{slab:g} mm between the planes" if strip else f"h {slab:g} mm over the plane"]
        under = lab * 1.35 * len(lines) + lab * 0.6
        k = min((x1 - x0) * 0.92 / span, (y1 - y0 - under - lab * 2.4) / tall)
        cx = (x0 + x1) / 2
        top = y0 + (y1 - y0 - (tall * k + under + lab * 2.0)) / 2 + lab * 2.0
        base = top + tall * k
        X = lambda v: cx + v * k  # noqa: E731
        Y = lambda v: base - v * k  # noqa: E731
        p.rect((X(-span / 2), Y(0), X(span / 2), Y(-plane)), fill="#c9cbd1")
        p.rect((X(-span / 2), Y(slab), X(span / 2), Y(0)), fill="#eef0e2")
        if strip:
            p.rect((X(-span / 2), Y(slab + plane), X(span / 2), Y(slab)), fill="#c9cbd1")
        z = slab / 2 if strip else slab
        for xc, colour in ((-s / 2, M.COPPER), (s / 2, M.TEAL)):
            p.rect((X(xc - w / 2), Y(z + 0.035), X(xc + w / 2), Y(z)), fill=colour)
        mark = Y(slab + plane) if strip else Y(z + 0.035)
        names = (("+", "bold"), (MINUS, "bold")) if signs else (("P", "bold"), ("N", "bold"))
        for (name, face), xc, colour in zip(names, (-s / 2, s / 2), (M.COPPER, M.TEAL)):
            p.text(X(xc), mark - lab * 0.45, name, face, lab * (1.5 if signs else 1.0),
                   colour if signs else M.INK, anchor="ms")
        y = Y(-plane) + lab * 1.4
        for line in lines:
            p.text(cx, y, nb(line), "sans", lab * 0.92, M.SOFT, anchor="ms")
            y += lab * 1.35
        return y

    def board(self, p, box, g, xr=None, yr=None, lit=(), ports=True, k=None, glow_pad=0.22, bg=None):
        xr = xr or (-0.6, self.L + self.Rb + self.s + 0.5)
        yr = yr or (-(self.Rb + self.s) - 0.6, self.Rb + self.s + 0.6)
        b = Board(self.M, p, box, xr, yr, k, bg)
        for x0, y0, x1, y1 in lit:
            b.glow(x0, y0, x1, y1, glow_pad)
        b.copper(g)
        b.paste()
        if ports:
            b.ports(g)
        return b

    def section(self, g, pad_y=0.15):
        tun = g["tuning"]
        a = tun["amplitude"]
        return (tun["section_start"], -self.Rb - self.w / 2 - pad_y, tun["section_end"],
                -self.Rb + a + self.w / 2 + pad_y)

    # -- shots ------------------------------------------------------------------------

    def title_shot(self, shape):
        M, R = self.M, self.R
        g = R.geo["C"]

        def figure(p, box):
            x0, y0, x1, y1 = box
            self.board(p, (x0, y0 + (y1 - y0) * 0.18, x1, y1 - (y1 - y0) * 0.18), g,
                       xr=(5.5, self.L + self.Rb + self.s + 0.4),
                       yr=(-(self.Rb + self.s) - 0.5, self.Rb + self.s + 0.5), lit=[self.section(g)],
                       ports=False, bg=M.PAGE)

        line = ("A U-bend makes one trace of a differential pair shorter. This video shows why that "
                "matters and how much of it a serpentine fixes.")
        if shape.page[0] < shape.page[1]:
            shape = _padded(M, shape)
        return M._title_shot(shape, line, title=TITLE, figure=figure)

    def pair_scene(self, shape):
        """Scene 2: what a differential receiver does (a schematic, no axes)."""
        M = self.M
        p, box = self.scene(shape, "A differential pair", "Two traces carry equal and opposite signals",
                            "The receiver reads the difference between the two traces. Noise that "
                            "reaches both traces cancels in the difference.")
        x0, y0, x1, y1 = box
        t = p.type
        if p.wide:
            xs_box, lanes_box = self.split(box, True, 0.3)
        else:
            xs_box, lanes_box = self.split(box, False, 0.26)
        self.xsection(p, xs_box, signs=True, sizes=False)
        xs = [i / 400 * 10 for i in range(401)]
        step = lambda u: 0.5 * (1 + math.tanh((u - 2.6) * 2.2))  # noqa: E731
        bump = lambda u: 0.22 * math.exp(-((u - 6.6) / 0.35) ** 2)  # noqa: E731
        lanes = [("P", [step(u) + bump(u) for u in xs], M.COPPER, (-0.1, 1.3)),
                 ("N", [-step(u) + bump(u) for u in xs], M.TEAL, (-1.3, 0.1)),
                 ("Difference, P " + MINUS + " N", [2 * step(u) for u in xs], M.INK, (-0.2, 2.2))]
        lx0, ly0, lx1, ly1 = lanes_box
        gap = t.note * 0.9
        lane_h = (ly1 - ly0 - gap * 2) / 3
        plots = []
        for i, (name, ys, colour, (lo, hi)) in enumerate(lanes):
            top = ly0 + i * (lane_h + gap)
            pl = Plot(M, p, (lx0, top + t.note * 1.2, lx1, top + lane_h), 0, 10, lo, hi, (), (), "",
                      left_pad=0.4)
            p.text(lx0, top + t.note * 0.95, name, "bold", t.note, colour)
            plots.append((pl, ys, colour))
        base = p.image

        def frame(upto, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for pl, ys, colour in plots:
                pl.series(xs, ys, upto, colour)
                if not final:
                    pl.cursor(upto)
            if upto >= 7.2:
                for pl, ys, colour in plots[:2]:
                    pl.label(6.6, ys[264], "noise", M.INK, dot=False)
                pl, ys, colour = plots[2]
                pl.label(6.6, ys[264], "cancels", M.INK, above=False, dot=False)
            return p.image.reduce(M.SS)

        return frame, 10.0

    def skew_lanes_scene(self, shape):
        """Scene 3: the untuned bend's own far-end waveforms, as four lanes."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "Skew", "If one half arrives early, the two do not cancel",
                            "For a moment both traces move the same way. We call this part of the "
                            "signal common mode. Common mode does not carry data, and it can radiate "
                            "from the cables.")
        t = p.type
        w = R.wave["B"]
        mid = R.t50("B", "t50_d")
        a, b = mid - HALF, mid + HALF
        lanes = [("P at the far end", w["p_far"], M.COPPER, (-0.03, 0.55)),
                 ("N at the far end", w["n_far"], M.TEAL, (-0.55, 0.03)),
                 ("Difference, what the receiver reads", w["vd_far"], M.INK, (-0.05, 1.05)),
                 ("Common mode", w["vc_far"], M.COPPER, (-0.004, 0.05))]
        x0, y0, x1, y1 = box
        gap = t.note * 0.6
        lane_h = (y1 - y0 - gap * 3 - t.note * 1.6) / 4
        plots = []
        for i, (name, ys, colour, (lo, hi)) in enumerate(lanes):
            top = y0 + i * (lane_h + gap)
            last = i == 3
            pl = Plot(M, p, (x0, top + t.note * 1.15, x1, top + lane_h + (t.note * 1.6 if last else 0)),
                      a, b, lo, hi, (), ((a, ""), (b, "")) if last else (), "", left_pad=0.4)
            p.text(x0, top + t.note * 0.95, name, "bold", t.note, colour)
            plots.append((pl, ys, colour, i == 3))
        self.slower(p, x1, y1 + t.note * 0.1, b - a)
        base = p.image

        def frame(upto, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for pl, ys, colour, cm in plots:
                if cm:
                    # the common mode glows where the halves do not cancel
                    pl.series(w["t"], ys, a + (upto - a), GLOW, width=10)
                pl.series(w["t"], ys, a + (upto - a), colour)
                if not final:
                    pl.cursor(a + (upto - a))
            return p.image.reduce(M.SS)

        def at(stage, final):
            return frame(a + stage, final)

        return at, b - a

    def board_shot(self, shape):
        """Scene 4: the fixture and its cross-section."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "The board", "A differential pair turns through a U-bend",
                            f"The traces are {self.w:g} mm wide on "
                            f"{R.p['stackup']['dielectric_height']:g} mm of dielectric. Their centres "
                            f"are {self.s:g} mm (20 mil) apart. We send a step in at one end and "
                            "measure when each trace arrives at the other.")
        t = p.type
        board_box, xs_box = self.split(box, p.wide, 0.68 if p.wide else 0.66)
        x0, y0, x1, y1 = board_box
        g = R.geo["B"]
        lab = t.note
        b = self.board(p, (x0 + lab * 7.5, y0, x1, y1), g)
        for q, text in ((g["ports"][0], "Step in"), (g["ports"][2], "Arrival time measured here")):
            px, py = b.P(q["x"], q["y"])
            yy = py + (lab * 1.4 if q["number"] == 1 else -lab * 0.8)
            p.paragraph(x0, yy, lab * 7, [(nb(text), "medium", M.INK)], lab, lab * 1.2)
        self.xsection(p, xs_box)
        return p.image.reduce(M.SS)

    def bend_scene(self, shape):
        """Scene 5: the two arcs light up in turn, then their difference."""
        M, R = self.M, self.R
        a_ = R.r["analytic"]
        p, box = self.scene(shape, "Where the skew comes from",
                            f"The inner trace is {a_['bend_mismatch_mm']:.3f} mm shorter",
                            "Around the bend the outer trace runs pi times the pitch further. At "
                            f"20 mil that is {a_['bend_mismatch_mil']:.1f} mil, whatever the radius. "
                            f"Geometry predicts {a_['single_line']['skew_ps']:.2f} ps of skew.")
        t = p.type
        g = R.geo["B"]
        Rb, s, L = self.Rb, self.s, self.L
        xr = (L - 3.2, L + Rb + s + 0.6)
        yr = (-(Rb + s) - 0.5, Rb + s + 0.5)
        if p.wide:
            draw_box, words_box = self.split(box, True, 0.55)
        else:
            draw_box, words_box = self.split(box, False, 0.62)
        arc = lambda r: [(L + r * math.cos(u), r * math.sin(u))  # noqa: E731
                         for u in np.linspace(-math.pi / 2, math.pi / 2, 90)]
        inner, outer = arc(Rb), arc(Rb + s)
        base = p.image
        size = t.body * 0.9
        rows = [("P, the inner trace: pi R", f"{math.pi * Rb:.3f} mm", M.COPPER),
                ("N, the outer trace: pi (R + s)", f"{math.pi * (Rb + s):.3f} mm", M.TEAL),
                ("The difference: pi s", f"{a_['bend_mismatch_mm']:.3f} mm", M.INK)]

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            b = Board(M, p, draw_box, xr, yr)
            glow = self.w * b.k * 2.6
            if stage > 0:
                b.line(partial(inner, ease(stage)), GLOW, glow)
            if stage > 1:
                b.line(partial(outer, ease(stage - 1)), GLOW, glow)
            b.copper(g)
            b.paste()
            c = b.P(L, 0)
            p.disc(*c, 4, M.INK)
            wx0, wy0, wx1, wy1 = words_box
            big = t.value * 0.55
            y = wy0 + size * 1.4 if p.wide else wy0 + size
            for i, (name, value, colour) in enumerate(rows):
                if stage >= i + 1 or final:
                    p.text(wx0, y, nb(name), "bold", size, colour)
                    p.text(wx0, y + big * 1.2, nb(value), "bold", big, M.INK)
                y += big * 1.2 + size * 2.0
            return p.image.reduce(M.SS)

        return frame, 3.0

    def mesh_scene(self, shape):
        """Scene 6: the solver's grid over the bend, and the four runs."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "How we simulate it",
                            f"openEMS solves the fields on {R.cells / 1e6:.2f} million cells",
                            "Each run sends a pulse into one of the four ports. Four runs give the "
                            "full response of the board. From it we calculate the waveforms at the "
                            "receiver.")
        t = p.type
        g = R.geo["B"]
        if p.wide:
            left, right = self.split(box, True, 0.5)
        else:
            left, right = self.split(box, False, 0.42)
        mx = R.mesh
        base = p.image
        Rb, s, L = self.Rb, self.s, self.L

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            lit = None if final else [min(int(stage) + 1, 4)]
            lx0, ly0, lx1, ly1 = left
            b = self.board(p, (lx0 + t.note * 2.2, ly0, lx1, ly1 - t.note * 1.6), g, ports=False)
            b.ports(g, lit=lit or [1, 2, 3, 4])
            for q in g["ports"]:
                px, py = b.P(q["x"], q["y"])
                on = final or (lit and q["number"] in lit)
                p.text(px - t.note * 0.7, py + t.note * 0.35, str(q["number"]), "bold", t.note,
                       M.COPPER_TEXT if on else M.NOTE, anchor="rs")
            p.text((lx0 + lx1) / 2, ly1, "The four ports" if final else
                   f"Run {min(int(stage) + 1, 4)}: pulse into port {min(int(stage) + 1, 4)}",
                   "bold", t.note, M.SOFT, anchor="ms")
            rx0, ry0, rx1, ry1 = right
            z = Board(M, p, (rx0, ry0, rx1, ry1 - t.note * 1.6), (L - 0.6, L + Rb + s + 0.45),
                      (-(Rb + s) - 0.4, Rb + s + 0.4))
            z.copper(g)
            z.grid(mx["x"], mx["y"])
            z.paste()
            p.text((rx0 + rx1) / 2, ry1, "The grid over the bend", "bold", t.note, M.SOFT, anchor="ms")
            return p.image.reduce(M.SS)

        return frame, 4.0

    def scope_scene(self, shape, kicker, headline, text, main, old=None, panel=None):
        """A scope: far-end P and inverted N for a 50 ps edge behind a cursor,
        their 50 % crossings marked, and the common mode under it. `old` is a
        variant kept in grey behind. `panel(p, box)` draws beside it."""
        M, R = self.M, self.R
        p, box = self.scene(shape, kicker, headline, text)
        t = p.type
        if panel:
            box, pbox = self.split(box, p.wide, 0.66 if p.wide else 0.7)
            panel(p, pbox)
        x0, y0, x1, y1 = box
        mid = R.t50(main, "t50_d")
        a, b = mid - HALF, mid + HALF
        split = y0 + (y1 - y0) * 0.62
        ticks = [(v, f"{v:g}") for v in range(int(math.ceil(a / 20) * 20), int(b), 20)]
        ticks[-1] = (ticks[-1][0], f"{ticks[-1][0]:g} ps")
        top = Plot(M, p, (x0, y0 + t.note * 0.4, x1, split), a, b, -0.02, 0.52, (0, 0.25, 0.5), (), "V")
        low = Plot(M, p, (x0, split + t.note * 0.5, x1, y1 - t.note * 0.3), a, b, -2, 50, (0, 25, 50),
                   ticks, "mV")
        p.text(top.left + 8, top.top + t.note * 0.95, "Far end: P and " + MINUS + "N", "bold", t.note,
               M.SOFT)
        p.text(low.left + 8, low.top + t.note * 0.95, "Common mode", "bold", t.note, M.SOFT)
        self.slower(p, top.right, top.bottom - t.note * 0.6, b - a)
        if old:
            wo = R.wave[old]
            top.series(wo["t"], wo["p_far"], b, OLD, 2.4)
            top.series(wo["t"], [-v for v in wo["n_far"]], b, OLD, 2.4)
            low.series(wo["t"], [v * 1000 for v in wo["vc_far"]], b, OLD, 2.4)
        base = p.image
        w = R.wave[main]
        neg = [-v for v in w["n_far"]]
        vc = [v * 1000 for v in w["vc_far"]]

        def gap_mark(v, colour, level):
            tp, tn = R.t50(v, "t50_P"), R.t50(v, "t50_N")
            top.vdash(tp, M.COPPER if colour != OLD else OLD)
            top.vdash(tn, M.TEAL if colour != OLD else OLD)
            y = top.Y(level)
            p.line([(top.X(tp), y), (top.X(tn), y)], colour, 2.5)
            sk = R.skew(v)
            text = nb(f"{sk:.2f} ps" if abs(sk) < 1 else f"{sk:.1f} ps")
            wide = p.width_of(text, "bold", t.note * 1.1)
            lx = max(top.X(tn) + 10, top.X(tp) + 10)
            p.rect((lx - 4, y - t.note * 0.9, lx + wide + 4, y + t.note * 0.4), fill=M.CARD, radius=4)
            p.text(lx, y + t.note * 0.3, text, "bold", t.note * 1.1, colour)

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            upto = a + stage
            top.series(w["t"], w["p_far"], upto, M.COPPER)
            top.series(w["t"], neg, upto, M.TEAL)
            low.series(w["t"], vc, upto, M.COPPER)
            if final:
                if old:
                    gap_mark(old, OLD, 0.12)
                gap_mark(main, M.INK, 0.25)
                pk = max(range(len(vc)), key=lambda i: vc[i] if a <= w["t"][i] <= b else -1)
                main_side, old_side = "right", "left"
                if old:
                    wo = R.wave[old]
                    vo = [v * 1000 for v in wo["vc_far"]]
                    po = max(range(len(vo)), key=lambda i: vo[i] if a <= wo["t"][i] <= b else -1)
                    if w["t"][pk] < wo["t"][po]:
                        main_side, old_side = "left", "right"
                    low.label(wo["t"][po], vo[po], f"{vo[po]:.0f} mV", OLD, above=vo[po] < 30, side=old_side)
                low.label(w["t"][pk], vc[pk], f"{vc[pk]:.0f} mV", M.COPPER, above=vc[pk] < 30, side=main_side)
            else:
                top.cursor(upto)
                low.cursor(upto)
            return p.image.reduce(M.SS)

        return frame, b - a

    def fix_shot(self, shape):
        """Scene 8: the usual fix, and the length report that calls it done."""
        M, R = self.M, self.R
        g = R.geo["C"]
        p, box = self.scene(shape, "The usual fix",
                            f"Add {R.r['analytic']['bend_mismatch_mm']:.3f} mm to the inner trace",
                            "A serpentine gives P the missing length. The CAD length report then shows "
                            "P and N equal. A line model that sees only length predicts "
                            f"{R.V['C']['mtl_skew_50']:.1f} ps of skew.")
        t = p.type
        draw_box, rep_box = self.split(box, p.wide, 0.66 if p.wide else 0.68)
        self.board(p, draw_box, g, lit=[self.section(g)])
        x0, y0, x1, y1 = rep_box
        size = t.body
        rows = [("P", f"{g['length']['P']:.3f} mm", M.COPPER), ("N", f"{g['length']['N']:.3f} mm", M.TEAL)]
        h = size * 1.4 * 4.4
        top = y0 + (y1 - y0 - h) / 2
        w = min(x1 - x0, size * 13)
        bx0 = x0 + (x1 - x0 - w) / 2
        p.rect((bx0, top, bx0 + w, top + h), fill=M.PAGE, radius=10)
        yy = top + size * 1.5
        p.text(bx0 + size * 0.8, yy, "Length report", "bold", t.note, M.SOFT)
        for name, value, colour in rows:
            yy += size * 1.45
            p.text(bx0 + size * 0.8, yy, name, "bold", size, colour)
            p.text(bx0 + w - size * 0.8, yy, nb(value), "bold", size, M.INK, anchor="rs")
        yy += size * 1.6
        p.tick(bx0 + size * 1.2, yy, size, M.PASS)
        p.text(bx0 + size * 2.0, yy, "Equal", "bold", size, M.PASS)
        return p.image.reduce(M.SS)

    def bars_scene(self, shape):
        """Scene 9: three serpentines of exactly the right length, and the skew
        each leaves, the line model's prediction marked on each."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "Three serpentines, each exactly the right length",
                            f"{R.skew('F'):.1f} to {R.skew('D'):.1f} ps of the skew stays",
                            f"One broad excursion removes {R.removed('F'):.0f} % of the skew. Two "
                            f"remove {R.removed('C'):.0f} %. Four small ones remove only "
                            f"{R.removed('D'):.0f} %.")
        t = p.type
        cases = [("F", "1 excursion"), ("C", "2 excursions"), ("D", "4 excursions")]
        if p.wide:
            draws, chart = self.split(box, True, 0.36)
        else:
            draws, chart = self.split(box, False, 0.3)
        dx0, dy0, dx1, dy1 = draws
        n = len(cases)
        for i, (v, name) in enumerate(cases):
            g = R.geo[v]
            if p.wide:
                hh = (dy1 - dy0) / n
                cell = (dx0, dy0 + i * hh, dx1, dy0 + (i + 1) * hh)
            else:
                ww = (dx1 - dx0 - 2 * 16) / n
                cell = (dx0 + i * (ww + 16), dy0, dx0 + i * (ww + 16) + ww, dy1)
            cx0, cy0, cx1, cy1 = cell
            p.text(cx0, cy0 + t.note, name, "bold", t.note, M.SOFT)
            self.board(p, (cx0, cy0 + t.note * 1.4, cx1, cy1 - 4), g, xr=(7.0, 12.2),
                       yr=(-(self.Rb + self.s) - 0.25, -self.Rb + 1.1), ports=False)
        cx0, cy0, cx1, cy1 = chart
        ky = self.key(p, cx0, cx1, cy0, [(OLD, "Untuned", False), (M.COPPER, "Exact length, full wave", False),
                                         (M.TEAL, "Line model", False)])
        top = math.ceil(R.skew("B") / 2.5) * 2.5
        pl = Plot(M, p, (cx0, ky, cx1, cy1), 0, 4, 0, top, (0, 5, 10) if top >= 10 else (0, 5), (), "ps")
        items = [("B", "Untuned", OLD)] + [(v, name, M.COPPER) for v, name in cases]
        slot = (pl.right - pl.left) / len(items)
        for i, (v, name, _) in enumerate(items):
            p.text(pl.left + slot * (i + 0.5), pl.bottom + t.note * 1.25, name, "sans", t.note, M.NOTE,
                   anchor="ms")
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for i, (v, name, colour) in enumerate(items):
                u = 1.0 if final else ease(stage - i)
                if u <= 0:
                    continue
                val = R.skew(v) * u
                cx = pl.left + slot * (i + 0.5)
                bw = slot * 0.5
                p.rect((cx - bw / 2, pl.Y(val), cx + bw / 2, pl.bottom), fill=colour, radius=4)
                if u >= 1:
                    p.text(cx, pl.Y(val) - t.note * 0.45, nb(f"{R.skew(v):.1f} ps"), "bold", t.note * 1.1,
                           M.INK, anchor="ms")
                    if v != "B":
                        y = pl.Y(R.V[v]["mtl_skew_50"])
                        p.rect((cx - bw / 2 - 6, y - 2.5, cx + bw / 2 + 6, y + 2.5), fill=M.TEAL, radius=2)
            return p.image.reduce(M.SS)

        return frame, 4.0

    def corner_scene(self, shape):
        """Scene 11: one excursion, its centre line and the path the current takes."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "Why the fix falls short", "The current takes the inside of each corner",
                            "That path is shorter than the centre line that the length report "
                            "measures. Each excursion has four corners. In these serpentines each one "
                            f"loses {self.per_exc()[0]:.1f} to {self.per_exc()[1]:.1f} ps of the delay "
                            "its length predicts.")
        t = p.type
        g = R.geo["C"]
        tun = g["tuning"]
        xs0 = tun["section_start"]
        bump_end = xs0 + tun["top"] + 2 * tun["chamfer"]
        a = tun["amplitude"]
        xr = (xs0 - 0.45, bump_end + 0.45)
        yr = (-self.Rb - 0.4, -self.Rb + a + 0.4)
        centre = [tuple(q) for q in g["centreline"]["P"] if xr[0] - 1 <= q[0] <= xr[1] + 1 and q[1] < 0]
        centre = [q for q in centre if -self.Rb - 0.01 <= q[1] <= -self.Rb + a + 0.01]
        path = inside_path(centre, 0.62 * self.w / 2)
        ky = self.key(p, box[0], box[2], box[1], [(M.INK, "Centre line: what the length report measures", True),
                                                  (M.COPPER, "The path the current takes", False)])
        draw_box = (box[0], ky, box[2], box[3])
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
        """Scene 12: loose and tight folds, current in opposite directions, the
        delay each gives against the delay its length predicts."""
        M, R = self.M, self.R
        p, box = self.scene(shape, "Why the fix falls short", "Close folds let the signal cross the gap",
                            "Neighbouring folds carry current in opposite directions and couple to each "
                            f"other. Folds 1.0 mm apart give {R.eta('S_loose') * 100:.0f} % of the "
                            f"predicted delay. Folds 0.15 mm apart give {R.eta('S_tight') * 100:.0f} %.")
        t = p.type
        cases = [("S_loose", "Folds 1.0 mm apart"), ("S_tight", "Folds 0.15 mm apart")]
        cols = self.split(box, True, 0.62, gap=34) if p.wide else self.split(box, False, 0.5, gap=28)
        geos = {v: R.geo[v] for v, _ in cases}
        a = geos["S_loose"]["tuning"]["amplitude"]
        yr = (-(self.Rb + self.s) - 0.25, -self.Rb + a + 0.3)
        spans = {v: (geos[v]["tuning"]["section_start"] - 0.35, geos[v]["tuning"]["section_end"] + 0.35)
                 for v, _ in cases}
        bar_h = t.note * 3.4
        ks = []
        for (v, _), (cx0, cy0, cx1, cy1) in zip(cases, cols):
            xr = spans[v]
            ks.append(min((cx1 - cx0) / (xr[1] - xr[0]), (cy1 - cy0 - bar_h - t.note * 1.6) / (yr[1] - yr[0])))
        k = min(ks)
        base = p.image

        def verticals(g):
            tun = g["tuning"]
            xs, out = tun["section_start"], []
            for i in range(tun["excursions"]):
                xl = xs + tun["chamfer"] + i * (tun["top"] + tun["bottom"])
                out += [(xl, +1), (xl + tun["top"], -1)]
            return out

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for (v, name), (cx0, cy0, cx1, cy1) in zip(cases, cols):
                g = geos[v]
                p.text(cx0, cy0 + t.note, nb(name), "bold", t.note, M.SOFT)
                b = Board(M, p, (cx0, cy0 + t.note * 1.5, cx1, cy1 - bar_h), spans[v], yr, k=k)
                vs = verticals(g)
                if v == "S_tight" and (final or stage >= 1):
                    (xa, _), (xb, _) = vs[1], vs[2]
                    b.box((xa, -self.Rb + 0.12), (xb, -self.Rb + a - 0.12), GLOW, radius=4)
                b.copper(g)
                b.paste()
                tun = g["tuning"]
                if final or stage >= 0.4:
                    for x, d in vs:
                        ym = -self.Rb + a / 2
                        cx, cy = b.P(x, ym)
                        hh = max(6.0, min(14.0, 0.18 * b.k))
                        tip = cy - d * hh
                        p.line([(cx - hh * 0.6, tip + d * hh * 0.9), (cx, tip), (cx + hh * 0.6, tip + d * hh * 0.9)],
                               M.INK, 2.4)
                # the bar: delay given against delay predicted
                bx0, bx1 = cx0, cx1
                by = cy1 - bar_h + t.note * 1.4
                u = 1.0 if final else ease(stage - 1)
                frac = R.eta(v) * u
                p.rect((bx0, by, bx1, by + t.note * 0.9), fill=M.PAGE, radius=5)
                p.rect((bx0, by, bx0 + (bx1 - bx0) * frac, by + t.note * 0.9), fill=M.COPPER, radius=5)
                p.text(bx0, by + t.note * 2.3, nb(f"{R.eta(v) * 100:.0f} % of the predicted delay"
                                                   if u >= 1 else ""), "bold", t.note, M.INK)
            return p.image.reduce(M.SS)

        return frame, 2.0

    def stripline_scene(self, shape):
        """Scene 13: the same copper in stripline, the share each removes."""
        M, R = self.M, self.R
        sl_err = abs(R.r["skew_geometric_sl"] - R.skew("B_sl")) / R.r["skew_geometric_sl"] * 100
        fold_sl = (R.eta("S_loose_sl") - R.eta("S_tight_sl")) * 100
        p, box = self.scene(shape, "The same copper in stripline", "Stripline has the same problem",
                            f"Geometry predicts the stripline bend to {sl_err:.1f} %. The serpentines remove "
                            f"{R.removed('F_sl', 'B_sl'):.0f} %, {R.removed('C_sl', 'B_sl'):.0f} % and "
                            f"{R.removed('D_sl', 'B_sl'):.0f} % of the skew. Close folds still cost "
                            f"{fold_sl:.0f} points of delay.")
        t = p.type
        xs_box, chart = self.split(box, p.wide, 0.3 if p.wide else 0.34)
        self.xsection(p, xs_box, strip=True)
        cx0, cy0, cx1, cy1 = chart
        ky = self.key(p, cx0, cx1, cy0, [(M.COPPER, "Microstrip", False), (M.TEAL, "Stripline", False)])
        pl = Plot(M, p, (cx0, ky, cx1, cy1), 0, 3, 0, 100, (0, 50, 100), (), "%")
        groups = [("F", "1 excursion"), ("C", "2 excursions"), ("D", "4 excursions")]
        slot = (pl.right - pl.left) / 3
        for i, (_, name) in enumerate(groups):
            p.text(pl.left + slot * (i + 0.5), pl.bottom + t.note * 1.25, name, "sans", t.note, M.NOTE,
                   anchor="ms")
        p.text(pl.left + 8, pl.top + t.note * 0.95, "Share of the skew removed", "bold", t.note, M.SOFT)
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for i, (v, _) in enumerate(groups):
                u = 1.0 if final else ease(stage - i)
                if u <= 0:
                    continue
                cx = pl.left + slot * (i + 0.5)
                bw = slot * 0.26
                for dx, var, ref, colour in ((-bw * 0.56, v, "B", M.COPPER), (bw * 0.56, v + "_sl", "B_sl", M.TEAL)):
                    val = R.removed(var, ref)
                    p.rect((cx + dx - bw / 2, pl.Y(val * u), cx + dx + bw / 2, pl.bottom), fill=colour, radius=4)
                    if u >= 1:
                        p.text(cx + dx, pl.Y(val) - t.note * 0.4, nb(f"{val:.0f} %"), "bold", t.note, M.INK,
                               anchor="ms")
            return p.image.reduce(M.SS)

        return frame, 3.0

    def placement_scene(self, shape):
        """Scene 14: the same two excursions next to the bend and at the launch,
        and the skew read at each frequency."""
        M, R = self.M, self.R
        fd = R.V["C_far"]["skew_fd_ps"]
        p, box = self.scene(shape, "Where the serpentine goes", "Put the fix next to the bend",
                            f"At the launch the same serpentine leaves {R.skew('C_far'):.1f} ps instead of "
                            f"{R.skew('C'):.1f} ps. Its skew also grows with frequency, from "
                            f"{fd['5']:.1f} ps at 5 GHz to {fd['25']:.1f} ps at 25 GHz.")
        t = p.type
        draws, chart = self.split(box, p.wide, 0.36 if p.wide else 0.3)
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
            p.text(cx0, cy0 + t.note, name, "bold", t.note, colour)
            g = R.geo[v]
            self.board(p, (cx0, cy0 + t.note * 1.4, cx1, cy1 - 6), g, lit=[self.section(g)], ports=False)
        cx0, cy0, cx1, cy1 = chart
        pl = Plot(M, p, (cx0, cy0, cx1, cy1), 1, 30, 0, 9, (0, 4, 8),
                  ((1, "1"), (10, "10"), (20, "20"), (30, "30 GHz")), "ps")
        p.text(pl.left + 8, pl.top + t.note * 0.95, "Skew read at each frequency", "bold", t.note, M.SOFT)
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            upto = 1 + stage
            for v, _, colour in cases:
                f, tau = R.fd[v]
                pl.series(f, tau, upto, colour)
            if final:
                for fq in ("5", "25"):
                    pl.label(float(fq), fd[fq], f"{fd[fq]:.1f} ps", M.COPPER, above=True)
                f, tau = R.fd["C"]
                j = min(range(len(f)), key=lambda i: abs(f[i] - 15))
                pl.label(f[j], tau[j], f"{R.skew('C'):.1f} ps", M.TEAL, above=False)
            else:
                pl.cursor(upto)
            return p.image.reduce(M.SS)

        return frame, 29.0

    def tdr_scene(self, shape):
        """Scene 15: the impedance along the line, the broad excursion's peak lit."""
        M, R = self.M, self.R
        zf, zb = R.V["F"]["tdr_35ps"]["zdiff_max"], R.V["B"]["tdr_35ps"]["zdiff_max"]
        p, box = self.scene(shape, "The cost of a broad excursion", "The impedance rises where P leaves N",
                            f"Over the broad excursion the pair impedance rises to {zf:.0f} ohm, against "
                            f"{zb:.0f} ohm for the plain bend. It reflects more signal than the other "
                            "length-matched serpentines.")
        t = p.type
        tb, zbs = R.tdr["B"]
        tf, zfs = R.tdr["F"]
        jf = max(range(len(zfs)), key=lambda i: zfs[i])
        pl = Plot(M, p, box, 0, 400, 88, 120, (90, 100, 110, 120),
                  ((0, "0"), (100, "100"), (200, "200"), (300, "300"), (400, "400 ps")), "ohm")
        p.text(pl.left + 8, pl.top + t.note * 0.95, "Pair impedance against round-trip time, 35 ps edge",
               "bold", t.note, M.SOFT)
        lo, hi = tf[jf] - 28, tf[jf] + 28
        p.rect((pl.X(lo), pl.top + t.note * 1.6, pl.X(hi), pl.bottom), fill=GLOW)
        p.text((pl.X(lo) + pl.X(hi)) / 2, pl.bottom - t.note * 0.5, "the broad excursion", "medium", t.note,
               M.COPPER_TEXT, anchor="ms")
        base = p.image

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            pl.series(tb, zbs, stage, OLD)
            pl.series(tf, zfs, stage, M.COPPER)
            if final:
                pl.label(tf[jf], zfs[jf], f"{zf:.0f} ohm", M.COPPER)
                jb = max((i for i in range(len(zbs)) if 140 < tb[i] < 200), key=lambda i: zbs[i])
                pl.label(tb[jb], zbs[jb], f"{zb:.0f} ohm", OLD, above=True, side="right")
            else:
                pl.cursor(stage)
            return p.image.reduce(M.SS)

        return frame, 400.0

    def eye_scene(self, shape):
        """Scene 16: 16 Gb/s eyes of the straight pair and the untuned bend."""
        M, R = self.M, self.R
        ea, eb = R.eyes["A"], R.eyes["B"]
        p, box = self.scene(shape, f"What {R.skew('B'):.1f} ps does at 16 Gb/s",
                            "The eye barely closes, but common mode grows",
                            f"The eye height falls only from {ea['height']:.1f} % to {eb['height']:.1f} % of "
                            f"the swing. Common mode grows to {eb['vc_pp']:.1f} % of the swing, and that is "
                            "the real cost.")
        t = p.type
        cols = self.split(box, True, 0.5, gap=30)
        panels = []
        for (v, name), (cx0, cy0, cx1, cy1) in zip((("A", "Straight pair"), ("B", "Untuned bend")), cols):
            e = R.eyes[v]
            p.text(cx0, cy0 + t.note, name, "bold", t.note, M.SOFT)
            split = cy0 + (cy1 - cy0) * 0.62
            ui = e["ui_ps"]
            eye = Plot(M, p, (cx0, cy0 + t.note * 1.6, cx1, split), 0, 2 * ui, -0.05, 1.0, (0, 0.5, 1),
                       ((0, "0"), (ui, f"{ui:.1f}"), (2 * ui, nb(f"{2 * ui:.0f} ps"))), "V")
            cm = Plot(M, p, (cx0, split + t.note * (2.0 if p.wide else 3.0), cx1, cy1), 0, e["vc_t"][-1], -75, 75,
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
        """Scene 17: the broad excursion before and after sizing by its delay."""
        M, R = self.M, self.R
        p_fix = (f"We add back the delay that each serpentine lost. The broad excursion goes to "
                 f"{R.skew('F_cal'):.2f} ps and two excursions go to {R.skew('C_cal'):.2f} ps. Four small "
                 "ones still need a second run.")
        rows = [("1 broad excursion", "F"), ("2 excursions", "C"), ("4 small excursions", "D")]

        def panel(p, box):
            t = p.type
            x0, y0, x1, y1 = box
            size = t.note
            big = t.body * 1.05
            n = len(rows)
            if p.wide:
                step = (y1 - y0) / n
                for i, (name, v) in enumerate(rows):
                    y = y0 + step * i + step * 0.38
                    p.text(x0, y, name, "bold", size, M.SOFT)
                    xb = p.text(x0, y + big * 1.25, nb(f"{R.skew(v):.1f} ps"), "bold", big, OLD)
                    ax = xb + 10
                    p.line([(ax, y + big * 0.9), (ax + 24, y + big * 0.9)], M.SOFT, 2.4)
                    p.line([(ax + 16, y + big * 0.9 - 6), (ax + 24, y + big * 0.9), (ax + 16, y + big * 0.9 + 6)],
                           M.SOFT, 2.4)
                    after = R.skew(v + "_cal")
                    p.text(ax + 34, y + big * 1.25, nb(f"{after:.2f} ps" if after < 1 else f"{after:.1f} ps"),
                           "bold", big, M.COPPER)
            else:
                step = (x1 - x0) / n
                for i, (name, v) in enumerate(rows):
                    xc = x0 + step * (i + 0.5)
                    p.text(xc, y0 + size * 1.2, name, "bold", size, M.SOFT, anchor="ms")
                    p.text(xc, y0 + size * 1.2 + big * 1.3, nb(f"{R.skew(v):.1f} ps"), "bold", big, OLD,
                           anchor="ms")
                    after = R.skew(v + "_cal")
                    p.text(xc, y0 + size * 1.2 + big * 2.7,
                           nb(f"{after:.2f} ps" if after < 1 else f"{after:.1f} ps"), "bold", big, M.COPPER,
                           anchor="ms")

        return self.scope_scene(shape, "Size the serpentine by its delay, not its length",
                                "One more solver run removes most of the rest", p_fix, "F_cal", old="F",
                                panel=panel)

    def rules_scene(self, shape):
        """Scene 18: four rules, one at a time, each beside a small drawing."""
        M, R = self.M, self.R
        M_ = M
        p = shape.new()
        t = p.type
        y = M._heading(p, p.top, "For a bent pair at this pitch", nb(f"Four rules from {R.runs} solver runs"))
        ix0, iy0, ix1, iy1 = p.card((M.MARGIN, y + t.body * 0.4, p.right, shape.bottom(p)))
        rules = ["Use few excursions.", "Keep the folds apart.", "Put the fix next to the bend.",
                 "Size it by delay, not length."]
        n = len(rules)
        step = (iy1 - iy0) / n
        icon_w = min((ix1 - ix0) * 0.3, step * 2.6)
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
                    p.line([(x0, cy - r)] + arcp[::-1][::-1][:0] + [(cx, cy - r)] + arcp + [(x0, cy + r)], col, 4)
                p.rect((cx - w * 0.36, cy - r1 - h * 0.14, cx - w * 0.06, cy - r1 + h * 0.14), fill=GLOW, radius=6)
            else:
                xs = np.linspace(x0, x1, 40)
                for col in (M_.COPPER, M_.TEAL):
                    p.line([(x, y1 - h * 0.1 - (h * 0.75) * 0.5 * (1 + math.tanh((x - (x0 + w / 2)) / (w * 0.09))))
                            for x in xs], col, 4)

        def frame(stage, final):
            p.image = base.copy()
            p.draw = ImageDraw.Draw(p.image)
            for i, rule in enumerate(rules):
                if not final and stage < i:
                    continue
                y0 = iy0 + i * step
                ib = (ix0 + 6, y0 + step * 0.18, ix0 + 6 + icon_w, y0 + step * 0.82)
                icon(i, ib)
                p.text(ix0 + icon_w + t.body * 1.4, y0 + step * 0.5 + t.body * 0.38, rule, "bold", t.body * 1.05,
                       M.INK)
            return p.image.reduce(M.SS)

        return frame, 4.0

    def summary_shot(self, shape):
        R = self.R
        cals = [abs(R.skew(v)) for v in ("C_cal", "D_cal", "F_cal")]
        line = (f"Untuned bend: {R.skew('B'):.1f} ps. Serpentines of exactly the right length: "
                f"{R.skew('F'):.1f} to {R.skew('D'):.1f} ps. Serpentines sized in the solver: "
                f"{min(cals):.2f} to {max(cals):.1f} ps.")
        return self.M._card_shot(shape, f"Run in openEMS {R.version}", "Equal length is not equal delay", nb(line))

    # -- the sequence -----------------------------------------------------------------------

    def shots(self, shape):
        """Each shot in order: ("still", image, seconds) or ("play", frame,
        sweep seconds, end, hold seconds)."""
        R = self.R
        sk_b = R.skew("B")
        out = [
            ("still", self.title_shot(shape), 4.0),
            ("play", self.pair_scene(shape), SWEEP, None, 4.6),
            ("play", self.skew_lanes_scene(shape), SWEEP, None, 4.8),
            ("still", self.board_shot(shape), 7.0),
            ("play", self.bend_scene(shape), 3.0, None, 4.4),
            ("play", self.mesh_scene(shape), 3.0, None, 4.6),
            ("play", self.scope_scene(shape, "The untuned bend in openEMS", f"P arrives {sk_b:.1f} ps before N",
                                      f"The field solver agrees with geometry to within "
                                      f"{math.ceil(abs(R.r['analytic']['single_line']['skew_ps'] - sk_b) / R.r['analytic']['single_line']['skew_ps'] * 100):.0f} %. "
                                      f"The skew puts a {R.vc_peak('B'):.0f} mV common-mode pulse on the line.",
                                      "B"), SWEEP, None, 4.6),
            ("still", self.fix_shot(shape), 7.0),
            ("play", self.bars_scene(shape), 3.0, None, 5.4),
            ("play", self.scope_scene(shape, "Four small excursions at the receiver",
                                      "The lengths match but P still arrives first",
                                      f"The skew falls from {sk_b:.1f} ps to {R.skew('D'):.1f} ps, not to zero. "
                                      f"The common-mode pulse falls from {R.vc_peak('B'):.0f} mV to "
                                      f"{R.vc_peak('D'):.0f} mV.", "D", old="B"), SWEEP, None, 4.2),
            ("play", self.corner_scene(shape), 2.4, None, 5.0),
            ("play", self.folds_scene(shape), 2.4, None, 5.8),
            ("play", self.stripline_scene(shape), 2.4, None, 4.6),
            ("play", self.placement_scene(shape), SWEEP, None, 4.8),
            ("play", self.tdr_scene(shape), SWEEP, None, 4.2),
            ("play", self.eye_scene(shape), SWEEP, None, 4.8),
            ("play", self.calibrated_scene(shape), SWEEP, None, 4.8),
            ("play", self.rules_scene(shape), 3.2, None, 3.6),
            ("still", self.summary_shot(shape), 4.6),
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
                _, image, seconds = shot
                yield from fade(image)
                yield from hold(image, seconds)
                previous = image
            else:
                _, (frame, end), seconds, _, after = shot
                still = frame(0.0, False)
                yield from fade(still)
                yield from hold(still, 0.4)
                count = round(seconds * M.FPS)
                for i in range(1, count + 1):
                    yield frame(end * i / count, False).tobytes()
                previous = frame(end, True)
                yield from hold(previous, after)
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


def looped_track(track: Path, seconds: float, folder: Path) -> Path:
    """The track played end to end until it outlasts the video, each join a
    2 s crossfade, as a WAV the levelling then reads like any track."""
    length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "csv=p=0", str(track)], capture_output=True, text=True).stdout)
    copies = max(1, math.ceil((seconds + 2) / (length - 2)))
    out = folder / f"{track.stem}-looped.wav"
    inputs, graph, last = [], "", "[0:a]"
    for i in range(copies):
        inputs += ["-i", str(track)]
    for i in range(1, copies):
        graph += f"{last}[{i}:a]acrossfade=d=2:c1=tri:c2=tri[a{i}];"
        last = f"[a{i}]"
    command = ["ffmpeg", "-v", "error", "-y", *inputs]
    if copies > 1:
        command += ["-filter_complex", graph.rstrip(";"), "-map", last]
    command += ["-c:a", "pcm_s16le", str(out)]
    if subprocess.run(command).returncode:
        raise SystemExit("ffmpeg could not loop the track")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--make", type=Path, default=FANG / "site" / "social" / "make.py")
    parser.add_argument("--stills", type=Path, help="write the finished frame of each shot here instead")
    parser.add_argument("--only", help="draw only the shape with this name")
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location("social_make", args.make)
    M = importlib.util.module_from_spec(spec)
    sys.modules["social_make"] = M
    spec.loader.exec_module(M)
    video = Video(M, Runs())
    shapes = {k: v for k, v in video.shapes.items() if not args.only or k == args.only}

    if args.stills:
        args.stills.mkdir(parents=True, exist_ok=True)
        for name, shape in shapes.items():
            for i, shot in enumerate(video.shots(shape)):
                if shot[0] == "still":
                    image = shot[1]
                else:
                    frame, end = shot[1]
                    image = frame(end, True)
                image.save(args.stills / f"{name}-{i + 1:02d}.png")
        print("stills in", args.stills)
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for name, shape in shapes.items():
        out = OUT / f"{name}.mp4"
        # No track for now, at the user's request (2026-10-19). looped_track()
        # and M._mux are here for when one is chosen.
        seconds = M._encode(video.frames(shape), out, shape.size)
        video.poster(shape).save(OUT / f"{name}.png", optimize=True)
        print(out, f"{seconds:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

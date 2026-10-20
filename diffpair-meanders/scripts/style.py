"""Figure style.

Two targets. `blog` is copperhead's light theme in Inter and IBM Plex Mono,
PNG at twice its layout size. `report` is a paper's: vector PDF sized for a
two-column page, 8 pt Latin Modern (the face the report is set in) with
Computer Modern mathematics, black type and inward ticks. Both use the same
chart colours: copper for the series a chart is about, teal for what it is
compared with, purple for a requirement; all three were checked together
with the dataviz validator (all pairs, light surface). Anything past three
series is drawn as small multiples rather than another hue.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
# copperhead's faces and Latin Modern, put there by scripts/fonts.py; without
# them, matplotlib's defaults
for f in sorted(FONTS.glob("*.ttf")) + sorted(FONTS.glob("*.otf")):
    font_manager.fontManager.addfont(str(f))
HAVE_FONTS = any(FONTS.glob("Inter-*.ttf"))
HAVE_LM = (FONTS / "lmroman10-regular.otf").exists() and (FONTS / "latinmodern-math.otf").exists()
MONO = "IBM Plex Mono"   # set by use(): the face for file and function names

COPPER = "#A75F14"
COPPER_TEXT = "#8F5210"
TEAL = "#008B9F"
PURPLE = "#8650C4"
INK = "#0A0A0A"
SOFT = "#57575E"
NOTE = "#5E5E66"
GRID = "#E8E8EC"
AXES = "#BCBCC4"
CONTEXT = "#9A9AA3"     # context lines and fills that carry no identity
PAGE = "#F1F1F3"
COPPER_FILL = "#E9C9A6"  # copper polygons in plan views
PLANE = "#C9CBD1"
DIELECTRIC = "#EEF0E2"

TARGETS = {
    "report": {"base": 8.0, "dpi": 300, "single": 3.45, "double": 7.0, "ext": ("pdf",)},
    "blog": {"base": 11.0, "dpi": 200, "single": 6.4, "double": 9.6, "ext": ("png", "svg")},
}


def use(target: str):
    t = TARGETS[target]
    b = t["base"]
    plt.rcParams.update({
        "font.family": "Inter" if HAVE_FONTS else "DejaVu Sans", "font.size": b, "font.weight": "regular",
        "axes.titlesize": b + 0.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlecolor": INK, "axes.labelsize": b, "axes.labelcolor": SOFT,
        "axes.edgecolor": AXES, "axes.linewidth": 0.8, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "xtick.color": AXES, "ytick.color": AXES, "xtick.labelcolor": NOTE, "ytick.labelcolor": NOTE,
        "xtick.labelsize": b - 0.5, "ytick.labelsize": b - 0.5,
        "legend.fontsize": b - 0.5, "legend.frameon": False, "legend.labelcolor": SOFT,
        "lines.linewidth": 1.6 if target == "report" else 2.2, "lines.solid_capstyle": "round",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "pdf.fonttype": 42, "svg.fonttype": "none",
        "mathtext.fontset": "dejavusans",
    })
    global MONO
    MONO = "IBM Plex Mono"
    if target == "report":
        MONO = "Latin Modern Mono" if HAVE_LM else "DejaVu Sans Mono"
        plt.rcParams.update({
            "font.family": ["Latin Modern Roman", "Latin Modern Math"] if HAVE_LM else ["DejaVu Serif"],
            "mathtext.fontset": "cm", "axes.formatter.use_mathtext": True,
            "axes.titleweight": "bold", "axes.labelcolor": INK, "axes.edgecolor": "#3A3A3A",
            "axes.linewidth": 0.6, "grid.color": "#E4E4E4", "grid.linewidth": 0.4,
            "xtick.color": "#3A3A3A", "ytick.color": "#3A3A3A", "xtick.labelcolor": INK, "ytick.labelcolor": INK,
            "xtick.direction": "in", "ytick.direction": "in", "xtick.major.size": 3, "ytick.major.size": 3,
            "xtick.major.width": 0.6, "ytick.major.width": 0.6, "legend.labelcolor": INK,
            "lines.linewidth": 1.3,
            # fill the figure, so a plot prints at the width it is laid out at
            "figure.constrained_layout.use": True,
            "figure.constrained_layout.w_pad": 0.02, "figure.constrained_layout.h_pad": 0.02,
        })
    return t


def save(fig, name: str, target: str):
    t = TARGETS[target]
    out = ROOT / "figures" / target
    out.mkdir(parents=True, exist_ok=True)
    for ext in t["ext"]:
        meta = {"CreationDate": None} if ext == "pdf" else ({"Date": None} if ext == "svg" else None)
        fig.savefig(out / f"{name}.{ext}", dpi=t["dpi"], bbox_inches="tight", pad_inches=0.03,
                    metadata=meta)
    plt.close(fig)


def mono(size=None):
    return {"family": "IBM Plex Mono", "size": size}

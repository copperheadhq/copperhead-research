"""The figure fonts, for matplotlib.

The blog's figures use copperhead's faces, Inter and IBM Plex Mono. They are
not committed: `main` builds static TTFs from the @fontsource woff2 files (an
npm install of @fontsource-variable/inter and @fontsource/ibm-plex-mono, or
any directory holding those files), instancing Inter's variable font at 400,
560 and 700 and merging its Latin and Greek subsets.

The report's figures use Latin Modern, the face the report is set in.
`latin_modern` copies its OpenType files out of a TeX installation: the
directory given, else whatever `kpsewhich` finds, else tectonic's cache.
Latin Modern Roman has no lowercase Greek, so Latin Modern Math is copied
too and the figures fall back to it glyph by glyph.

Without these files the figures fall back to matplotlib's default faces.

Run: python scripts/fonts.py <directory holding the woff2 files>
     python scripts/fonts.py latin-modern [directory holding the .otf files]
"""

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / "fonts"


def find(src, pattern):
    hits = sorted(glob.glob(str(Path(src) / "**" / pattern), recursive=True))
    if not hits:
        raise SystemExit(f"no {pattern} under {src}")
    return hits[0]


def main(src):
    OUT.mkdir(exist_ok=True)
    subsets = [find(src, "inter-latin-wght-normal*.woff2"), find(src, "inter-greek-wght-normal*.woff2")]
    for weight, name in ((400, "Regular"), (560, "Medium"), (700, "Bold")):
        parts = []
        for k, path in enumerate(subsets):
            f = TTFont(path)
            f.flavor = None
            tmp = OUT / f"_part{k}.ttf"
            instancer.instantiateVariableFont(f, {"wght": weight}).save(tmp)
            parts.append(str(tmp))
        merged = Merger().merge(parts)
        for rec in merged["name"].names:
            if rec.nameID in (1, 16):
                rec.string = "Inter"
            if rec.nameID in (2, 17):
                rec.string = name
            if rec.nameID == 4:
                rec.string = f"Inter {name}"
            if rec.nameID == 6:
                rec.string = f"Inter-{name}"
        merged["OS/2"].usWeightClass = weight
        merged.save(OUT / f"Inter-{name}.ttf")
        for p in parts:
            os.remove(p)
    for weight in (400, 500):
        f = TTFont(find(src, f"ibm-plex-mono-latin-{weight}-normal*.woff2"))
        f.flavor = None
        f.save(OUT / f"IBMPlexMono-{weight}.ttf")
    print("wrote", OUT)


LATIN_MODERN = ("lmroman10-regular.otf", "lmroman10-bold.otf", "lmroman10-italic.otf",
                "latinmodern-math.otf", "lmmono10-regular.otf")


def latin_modern(src=None):
    OUT.mkdir(exist_ok=True)
    for name in LATIN_MODERN:
        hits = sorted(glob.glob(str(Path(src) / "**" / name), recursive=True)) if src else []
        if not hits:
            found = subprocess.run(["kpsewhich", name], capture_output=True, text=True).stdout.strip() \
                if shutil.which("kpsewhich") else ""
            hits = [found] if found else sorted(glob.glob(str(Path.home() / ".cache" / "tectonic" / "**" / name),
                                                          recursive=True))
        if not hits:
            raise SystemExit(f"no {name}: give the directory that holds it")
        shutil.copy(hits[0], OUT / name)
    print("wrote", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "latin-modern":
        latin_modern(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else ".")

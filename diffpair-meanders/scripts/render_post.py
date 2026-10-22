"""Fill the blog post's numbers from build/results/results.json.

The post is written as blog/post.template.mdx in the site's own form (the
copperhead-site blog collection, as the Crompton teardown is): `${name}`
placeholders for every number, and `::figure NAME` blocks with an `alt:` and a
`caption:` line. This writes:

- blog/post.mdx, the post for src/content/blog/, its figures imported from
  ../../assets/ under the names in blog/assets/ (copied there from
  figures/blog/);
- blog/post.md, the same text with plain HTML figures, for the preview page.

Run: python scripts/render_post.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from string import Template

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convergence  # noqa: E402
import geometry  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "build" / "results" / "results.json").read_text())
V = R["variants"]
FIGURE = re.compile(r"^::figure (\w+)\nalt: (.*)\ncaption: (.*)\n::$", re.M)


def values() -> dict:
    p = geometry.params()
    a = R["analytic"]
    sb = V["B"]["timing"]["50"]["skew"]
    val = {
        "dl": f"{a['bend_mismatch_mm']:.3f}", "dl_mil": f"{a['bend_mismatch_mil']:.1f}",
        "skew_38": f"{a['skew_ps_at_eps_3.8']:.1f}", "eps_95": f"{a['eps_for_9.5ps']:.2f}",
        "eps_single": f"{a['single_line']['eps_eff']:.2f}", "skew_single": f"{a['single_line']['skew_ps']:.2f}",
        "bend_err": f"{abs(a['single_line']['skew_ps'] - sb) / a['single_line']['skew_ps'] * 100:.0f}",
        "unc_B": f"{R['uncertainty_ps']['untuned']:.2f}",
        "unc_C": f"{R['uncertainty_ps']['tuned_C']:.1f}",
        "unc_D": f"{R['uncertainty_ps']['tuned_D']:.1f}",
        "runs": str(len(list((ROOT / "runs").glob("*/*/p*/provenance.json")))),
        "record_ns": f"{p['simulation']['record_time'] * 1e9:g}",
        "trunc_db": f"{-max(max(r['checks']['truncation_dB'].values()) for r in V.values()):.0f}",
    }
    prov = json.loads((ROOT / "runs" / "medium" / "B" / "p1" / "provenance.json").read_text())
    val["solver"] = prov["solver_version"]
    names = {"B": "B", "C": "C", "C_far": "Cfar", "D": "D", "E": "E", "F": "F", "C_cal": "Ccal",
             "D_cal": "Dcal", "F_cal": "Fcal", "A": "A", "S_loose": "Sloose", "S_tight": "Stight",
             "C_sl": "Csl", "D_sl": "Dsl", "F_sl": "Fsl", "S_loose_sl": "Sloosesl", "S_tight_sl": "Stightsl"}
    for v, k in names.items():
        if v not in V:
            continue
        t = V[v]["timing"]["50"]
        val[f"skew_{k}"] = f"{t['skew']:.2f}" if abs(t["skew"]) < 1 else f"{t['skew']:.1f}"
        val[f"removed_{k}"] = f"{(1 - t['skew'] / sb) * 100:.0f}"
        if "eta" in t:
            val[f"eta_{k}"] = f"{t['eta']:.2f}"
        if "mtl_skew_50" in V[v]:
            val[f"mtl_{k}"] = f"{V[v]['mtl_skew_50']:.1f}"
        val[f"zmax_{k}"] = f"{V[v]['tdr_35ps']['zdiff_max']:.0f}"
        val[f"sdd_{k}"] = f"{V[v]['bands']['0.1-20GHz']['Sdd11_max_dB']:.1f}".replace("-", "−")
        val[f"eyeh_{k}"] = f"{V[v]['eye']['16']['eye_height_rel'] * 100:.1f}"
        val[f"eyevc_{k}"] = f"{V[v]['eye']['16']['vc_pp_rel'] * 100:.1f}"
    val["fd_Cfar_5"] = f"{V['C_far']['skew_fd_ps']['5']:.1f}"
    val["fd_Cfar_25"] = f"{V['C_far']['skew_fd_ps']['25']:.1f}"
    # per excursion, net of the line model's own error on the bare bend
    bend_err = sb - V["B"]["mtl_skew_50"]
    per = [(V[v]["timing"]["50"]["skew"] - V[v]["mtl_skew_50"] - bend_err) / V[v]["tuning"]["excursions"]
           for v in ("C", "D", "F")]
    val["per_exc_min"], val["per_exc_max"] = f"{min(per):.1f}", f"{max(per):.1f}"
    val["per_exc_F"], val["per_exc_C"], val["per_exc_D"] = (f"{x:.1f}" for x in (per[2], per[0], per[1]))
    el = R["eta_by_level"]
    # in points, from the efficiencies as the figures print them (two decimals)
    pen = [(round(el["S_loose"][l], 2) - round(el["S_tight"][l], 2)) * 100 for l in el["S_loose"] if l in el["S_tight"]]
    val["fold_pen_min"], val["fold_pen_max"] = f"{min(pen):.0f}", f"{max(pen):.0f}"
    for v in ("C", "D", "F"):
        extra = V[v + "_cal"]["P_len"] - V[v]["P_len"]
        gain = V[v]["timing"]["50"]["skew"] - V[v + "_cal"]["timing"]["50"]["skew"]
        val[f"marg_{v}"] = f"{gain / (extra * R['ps_per_mm_single']) * 100:.0f}"
    # stripline
    sbs = V["B_sl"]["timing"]["50"]["skew"]
    val["skew_Bsl"] = f"{sbs:.2f}"
    val["skew_geo_sl"] = f"{R['skew_geometric_sl']:.2f}"
    val["bend_err_sl"] = f"{abs(R['skew_geometric_sl'] - sbs) / R['skew_geometric_sl'] * 100:.1f}"
    for v in ("C", "D", "F"):
        val[f"removed_{v}sl"] = f"{(1 - V[v + '_sl']['timing']['50']['skew'] / sbs) * 100:.0f}"
    val["fold_pen_sl"] = f"{(round(V['S_loose_sl']['timing']['50']['eta'], 2) - round(V['S_tight_sl']['timing']['50']['eta'], 2)) * 100:.0f}"
    ratio = R["ps_per_mm_stripline"] / R["ps_per_mm_single"]
    val["sl_inflation"] = f"{(ratio - 1) * 100:.0f}"
    val["eta_wrong_sl"] = f"{V['S_loose_sl']['timing']['50']['eta'] * ratio:.2f}"
    # the dense accordion's meshes
    cd = R["convergence"]["D"]["skew_50"]
    for l in ("coarse", "medium", "fine", "xfine"):
        val[f"conv_D_{l}"] = f"{cd[l]:.2f}"
    cells = p["simulation"]["levels"]
    three = convergence.gci(cd["fine"], cd["medium"], cd["coarse"], (cells["coarse"] / cells["fine"]) ** 0.5)
    val["gci_D_three"] = f"{three['gci']:.1f}"
    val["conv_D_ext"] = f"{R['convergence']['D']['extrapolated']:.1f}"
    # the serpentines' section lengths: the tight pair packs the same added length shorter
    for v, k in (("S_loose", "sec_loose"), ("S_tight", "sec_tight")):
        tu = geometry.build(v, p)["tuning"]
        val[k] = f"{tu['section_end'] - tu['section_start']:.2f}"
    # the report
    import pymupdf
    val["report_pages"] = str(pymupdf.open(ROOT / "report" / "report.pdf").page_count)
    val["report_refs"] = str(len(re.findall(r"^@\w+\{", (ROOT / "report" / "references.bib").read_text(), re.M)))
    return val


TAG = re.compile(r"<[^>]*>")


def reflow(body: str, width: int = 88) -> str:
    """Wrap prose paragraphs and list items to the house's 88 columns once the
    numbers are in, leaving headings, figures, tables, references and code alone.
    Spaces inside a tag are held fixed, so a line never breaks inside one."""
    import textwrap
    out = []
    lead = body[:len(body) - len(body.lstrip("\n"))]
    for block in body.lstrip("\n").split("\n\n"):
        lines = block.split("\n")
        first = lines[0]
        if re.match(r"^\d+\. ", first) and any("](" in l for l in lines):
            # a reference: wrap the note after its link, as one paragraph indented 3
            k = max(i for i, l in enumerate(lines) if "](" in l)
            note = " ".join(l.strip() for l in lines[k + 1:])
            if note:
                lines = lines[:k + 1] + textwrap.wrap(note, width, initial_indent="   ",
                                                      subsequent_indent="   ", break_long_words=False)
            out.append("\n".join(lines))
            continue
        if not first.strip() or first.startswith(("#", "|", "<", "::", "import", " ", "`")) \
                or re.match(r"^\d+\. ", first) or any(l.startswith("|") for l in lines):
            out.append(block)
            continue
        items, cur = [], []
        for line in lines:
            if line.startswith("- ") and cur:
                items.append(cur)
                cur = []
            cur.append(line.strip())
        items.append(cur)
        wrapped = []
        for item in items:
            text = " ".join(item)
            text = TAG.sub(lambda m: m.group(0).replace(" ", "\x00"), text)
            bullet = text.startswith("- ")
            lines_ = textwrap.wrap(text, width, subsequent_indent="  " if bullet else "",
                                   break_long_words=False, break_on_hyphens=False)
            wrapped.append("\n".join(l.replace("\x00", " ") for l in lines_))
        out.append("\n".join(wrapped))
    return lead + "\n\n".join(out)


def camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


def main():
    text = Template((ROOT / "blog" / "post.template.mdx").read_text()).substitute(values())
    assets = ROOT / "blog" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    figures = FIGURE.findall(text)
    imports = []
    for name, _, _ in figures:
        target = f"diffpair-{name.removeprefix('fig_').replace('_', '-')}.png"
        shutil.copy(ROOT / "figures" / "blog" / f"{name}.png", assets / target)
        imports.append(f'import {camel(name)} from "../../assets/{target}";')

    def mdx_figure(m):
        name, alt, caption = m.groups()
        return (f"<figure>\n  <Image\n    src={{{camel(name)}}}\n    alt=\"{alt}\"\n  />\n"
                f"  <figcaption>\n    {caption}\n  </figcaption>\n</figure>")

    def md_figure(m):
        name, alt, caption = m.groups()
        return (f'<figure><img src="../figures/blog/{name}.png" alt="{alt}">'
                f"<figcaption>{caption}</figcaption></figure>")

    head, body = text.split("\n---\n", 1)
    body = reflow(body)
    mdx = (head + "\n---\n\n" + 'import { Image } from "astro:assets";\n' + "\n".join(imports) + "\n"
           + FIGURE.sub(mdx_figure, body))
    (ROOT / "blog" / "post.mdx").write_text(mdx)
    (ROOT / "blog" / "post.md").write_text(head + "\n---\n" + FIGURE.sub(md_figure, body))
    print("wrote blog/post.mdx and blog/post.md,", len(figures), "figures")


if __name__ == "__main__":
    main()

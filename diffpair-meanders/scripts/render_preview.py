"""A preview page of the blog post, in copperhead's palette and faces.

Converts blog/post.md to HTML and writes blog/preview/index.html with the
figures it references copied beside it under img/. The page is a review copy;
the post itself is blog/post.md and figures/blog/.

Run: python scripts/render_preview.py
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "blog" / "preview"

STYLE = """
<title>Equal Length, Unequal Delay</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;560;700&display=swap">
<style>
/* One reading column, figures allowed to run wider than the text; copperhead's
   tokens from site/BRAND.md, light first (a blog is read on light ground),
   dark as its own palette. */
:root {
  --ground: #ffffff; --raised: #f7f8fa; --hairline: #e3e7ed;
  --text: #2b2d32; --muted: #545962; --dim: #686f7a;
  --accent: #a35d1f; --accent-text: #9a5619; --accent-low: #f8e9db;
  --plate: #ffffff; --plate-edge: #e3e7ed;
  --sans: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
  --measure: 40rem; --wide: 56rem;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --ground: #1b1b1c; --raised: #232425; --hairline: #343638;
  --text: #e3e5e8; --muted: #b3b8be; --dim: #8a9098;
  --accent: #c47a3a; --accent-text: #e6a366; --accent-low: #3b2614;
  --plate: #ffffff; --plate-edge: #343638; color-scheme: dark } }
:root[data-theme="dark"] {
  --ground: #1b1b1c; --raised: #232425; --hairline: #343638;
  --text: #e3e5e8; --muted: #b3b8be; --dim: #8a9098;
  --accent: #c47a3a; --accent-text: #e6a366; --accent-low: #3b2614;
  --plate: #ffffff; --plate-edge: #343638; color-scheme: dark }
body { background: var(--ground); color: var(--text); font: 400 1.0625rem/1.65 var(--sans);
  -webkit-font-smoothing: antialiased; }
.page { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 3rem 5rem; }
.page > * { max-width: var(--measure); margin-inline: auto; }
.page > p:has(> img), .page > .table, .page > figure { max-width: var(--wide); }
.band { height: 4px; background: var(--accent); }
.eyebrow { font: 500 0.75rem/1 var(--mono); letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent-text);
  display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; margin-bottom: 1.25rem; }
.eyebrow span { color: var(--dim); }
h1 { font: 700 clamp(2rem, 1.4rem + 2.4vw, 2.9rem)/1.12 var(--sans); letter-spacing: -0.02em; text-wrap: balance;
  margin: 0 auto 0.75rem; }
.dek { color: var(--muted); font-size: 1.15rem; margin-bottom: 2.5rem; }
h2 { font: 700 1.45rem/1.25 var(--sans); letter-spacing: -0.01em; text-wrap: balance; margin: 3rem auto 0.75rem; }
p, ul { margin-top: 0; margin-bottom: 1.1rem; }
ul { padding-left: 1.25rem; }
li { margin-bottom: 0.4rem; }
li::marker { color: var(--accent); }
a { color: var(--accent-text); text-underline-offset: 0.18em; }
a:hover { color: var(--accent); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
strong { font-weight: 700; }
code { font: 0.92em var(--mono); }
.page > p:has(> img) { margin-block: 1.75rem; }
img { display: block; width: 100%; height: auto; background: var(--plate); border: 1px solid var(--plate-edge);
  border-radius: 6px; padding: 0.75rem; box-sizing: border-box; }
.caption { display: block; font-size: 0.875rem; color: var(--dim); margin-top: 0.5rem; }
.table { overflow-x: auto; margin-block: 1.5rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.95rem; font-variant-numeric: tabular-nums; }
th { text-align: left; font: 500 0.75rem/1.3 var(--mono); letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--muted); border-bottom: 1.5px solid var(--text); padding: 0.4rem 0.75rem 0.4rem 0; }
td { border-bottom: 1px solid var(--hairline); padding: 0.45rem 0.75rem 0.45rem 0; vertical-align: top; }
.note { border-top: 1px solid var(--hairline); margin-top: 3rem; padding-top: 1.25rem; color: var(--muted);
  font-size: 0.95rem; }
</style>
"""


def main():
    text = (ROOT / "blog" / "post.md").read_text()
    meta, body = {}, text
    if text.startswith("---"):
        head, body = text[3:].split("---", 1)
        for line in head.strip().splitlines():
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    body = re.sub(r"^# .*\n", "", body.lstrip(), count=1)   # the title comes from the front matter
    html = markdown.markdown(body, extensions=["tables", "sane_lists"])
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "img").mkdir(parents=True)
    used = []

    def image(m):
        alt, src = m.group(1), m.group(2)
        name = Path(src).name
        shutil.copy(ROOT / "figures" / "blog" / name, OUT / "img" / name)
        used.append(name)
        return f'<img src="img/{name}" alt="{alt}" loading="lazy"><span class="caption">{alt}</span>'

    html = re.sub(r'<img alt="([^"]*)" src="([^"]*)" ?/?>', image, html)
    html = html.replace("<table>", '<div class="table"><table>').replace("</table>", "</table></div>")
    page = (STYLE + '<div class="band"></div>\n<main class="page">\n'
            f'<div class="eyebrow">Signal integrity<span>{meta.get("date", "")}</span><span>{meta.get("author", "")}</span></div>\n'
            f'<h1>{meta.get("title", "")}</h1>\n<p class="dek">{meta.get("description", "")}</p>\n'
            f"{html}\n</main>\n")
    (OUT / "index.html").write_text(page)
    print("wrote", OUT / "index.html", "images:", len(used))


if __name__ == "__main__":
    main()

# Report, version 1: brand-style figures

Snapshot taken on 2026-10-20, before the figures were redrawn in paper
style. Fixed at that point:

- `report/report.pdf`, 12 pages, the version sent for review;
- `report/main.tex`, `report/references.bib` and `report/generated/`, the
  source it was built from;
- `figures/report/`, the figures it includes (Inter, copperhead's colours);
- `scripts/style.py`, `fig_geometry.py` and `fig_results.py`, the scripts
  that drew those figures.

To rebuild this version, copy the three scripts back into `scripts/`, run
them with the `report` target, and build `report/main.tex` with tectonic.

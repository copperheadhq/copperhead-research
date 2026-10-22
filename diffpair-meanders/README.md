# Differential-pair meanders under a field solver

A reproducible study of whether serpentine length tuning removes the intra-pair skew of a 180-degree U-bend.
A controlled microstrip fixture and its tuned variants are solved as full four-ports in openEMS (FDTD),
converted to mixed-mode S-parameters, and taken to receiver waveforms. A transmission-line model calibrated on
the same solver sits beside it to separate what length explains from what it does not.

- `report/main.pdf`: the two-column report, *Beyond Length Matching: Electromagnetic Verification and
  Optimization of Differential-Pair Meanders*.
- `blog/post.md`: the write-up for a general engineering audience, with its figures in `figures/blog/`.

Everything is simulated. Nothing was built or measured; `report/main.pdf` section 9 is the coupon plan for doing so.

## Layout

| Path | What it holds |
| --- | --- |
| `parameters.yaml` | Every geometric, material and numerical parameter (proposed values, not calibrated ones) |
| `scripts/geometry.py` | Centrelines, solved tuning amplitudes, copper polygons, P-N clearance |
| `scripts/kicad_export.py` | Each variant as a `.kicad_pcb`, checked with `kicad-cli pcb drc` |
| `scripts/model.py` | openEMS XML (mesh, materials, ports) for one variant, mesh level and excited port |
| `scripts/run.py`, `scripts/run_pool.py` | Runs openEMS once per excited port, with a provenance record per run |
| `scripts/sparams.py` | Port waves to a 4-port `.s4p`, with reciprocity, passivity and truncation checks |
| `scripts/mtl.py` | The two-conductor line model, calibrated on the full-wave straight fixture |
| `scripts/analysis.py` | Mixed mode, waveforms, skew, TDR, eye, area, Pareto |
| `scripts/convergence.py` | Richardson extrapolation and grid convergence index over three meshes |
| `scripts/calibrate.py` | The EM-informed added lengths recorded in `parameters.yaml` |
| `scripts/results.py` | Gathers every quoted number into `build/results/results.json` |
| `scripts/fig_diagrams.py` | The report's diagrams in a paper's style: the model views (domain, ports, mesh, 3D), the dimensioned cross-sections, bend and tuning section, and the pipeline |
| `scripts/fig_teaser.py` | The report's first-page figure: board D from above as openEMS meshes it (the medium mesh drawn, with an inset of the staircased excursions), beside its receiver waveforms |
| `scripts/fig_geometry.py` | The post's geometry figures, in copperhead's style |
| `scripts/fig_results.py` | The data plots, PDF for the report (Latin Modern) and PNG/SVG for the post (Inter) |
| `scripts/tex_numbers.py`, `scripts/render_post.py` | The report's macros and tables, and the post, from `results.json` |
| `runs/<level>/<variant>/p<k>/` | Each run's model, solver log, probe signals and `provenance.json` |
| `build/sparams/<level>/` | The `.s4p` files and their checks; `build/sparams/mtl/` the line model's |
| `build/kicad/` | The exported boards and KiCad's DRC reports |

Port numbering in every `.s4p`: 1 P near end, 2 N near end, 3 P far end, 4 N far end, 50 ohm each. P is the
inner trace of the bend. This is the order scikit-rf's `se2gmm(p=2)` expects.

## Requirements

- Python 3.12 with `requirements.txt` (`uv venv && uv pip install -r requirements.txt`).
- openEMS on the `PATH`; the study used v0.37.0-rc3-31-g6761a36. The model is written as XML, so openEMS's own
  Python bindings are not needed.
- Optional: `kicad-cli` (KiCad 10) for the DRC step; [tectonic](https://tectonic-typesetting.github.io) to
  build the PDF (any LaTeX with `newtx` and `IEEEtran.bst` works too); the figure fonts: for the post,
  Inter and IBM Plex Mono, built by `scripts/fonts.py` from their `@fontsource` packages; for the report,
  Latin Modern, copied out of a TeX installation by `scripts/fonts.py latin-modern` (without them the
  figures use matplotlib's default faces).

## Reproducing

From this folder, with its virtual environment's Python:

```sh
python scripts/geometry.py                 # build/geometry/*.json, lengths and clearances
python scripts/kicad_export.py             # optional: KiCad boards and DRC
python scripts/analytic.py                 # build/results/analytic.json
python scripts/run_pool.py 5               # every variant: 64 runs
python scripts/run_pool.py 5 --plan2       # D and the serpentines on the coarse and fine meshes
python scripts/run_pool.py 5 --plan3       # the EM-sized variants (after calibrate.py)
python scripts/run_pool.py 5 --plan4       # the stripline set
python scripts/run_pool.py 4 --plan5       # D on the 18 um mesh
python scripts/sparams.py medium A B C C_far D E F C_cal D_cal F_cal S_ref S_loose S_tight B_R075 B_R3 \
    B_sl C_sl D_sl F_sl S_ref_sl S_loose_sl S_tight_sl
python scripts/sparams.py xfine D
python scripts/sparams.py coarse B C D S_ref S_loose S_tight
python scripts/sparams.py fine B C D S_ref S_loose S_tight
python scripts/mtl.py medium
python scripts/results.py
python scripts/fig_diagrams.py && python scripts/fig_teaser.py && python scripts/fig_geometry.py && python scripts/fig_results.py
python scripts/tex_numbers.py && python scripts/render_post.py
cd report && tectonic main.tex   # the report (report.pdf is a copy of main.pdf)
cd report && tectonic ieee.tex   # the same text in IEEEtran, Times
```

A run whose `provenance.json` names the same model hash is skipped, so the pool can be stopped and started
again. On the host used here (8 cores, shared), five single-thread solver processes side by side ran about three
times faster than one process on six threads.

## What was run

- Fifteen geometries at the medium mesh (40 um finest cell): the straight reference A, the untuned bend B, five
  tunings (C, C far, D, F, and the pair-level control E), their three EM-sized versions, the bend at two more
  radii, and a straight pair with a 6 mm serpentine at two fold spacings and its reference.
- B, C, D, F and the serpentine set in stripline (the same copper between two planes 0.7 mm apart), medium mesh.
- B, C, D and the serpentine set again on the coarse (60 um) and fine (27 um) meshes, and D on an 18 um mesh.
- Four runs per geometry and mesh, one per excited port: every `provenance.json` under `runs/` is one of them.
- A short diagnostic set on the coarse mesh (not committed) that traced the solver's energy floor to the pulse's
  DC content; it is why every run stops at a fixed 2 ns.

## What remains unvalidated

- No hardware: no coupon, no VNA measurement, no microsection. The predictions to test are listed in the report.
- One trace width and one pitch, in one microstrip and one stripline stackup. The stripline ports run to the
  lower plane only, and the stripline variants were solved on one mesh.
- A perfect return plane, a conducting-sheet copper model with no roughness, and a dielectric loss that falls
  as 1/f.
- Lumped ports instead of connectors or probes; absolute return loss includes their launch.
- Mesh convergence was checked for B, C, D and the serpentines only; the other variants carry the tuned
  variants' bound.
- Edges faster than 35 ps and frequencies above 30 GHz are outside the simulated band.
- Mode conversion and common-mode voltage are reported; radiated emission is not modelled and not claimed.

The manuscript is split so the report and the IEEE version share one text: `report/body.tex` (sections), `report/abstract.tex`, `report/common.tex` (macros and float settings) and `report/teaser-caption.tex`; `report/main.tex` and `report/ieee.tex` are only front ends.

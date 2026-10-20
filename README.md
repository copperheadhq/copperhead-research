# copperhead-research

Copperhead's research studies: simulations and analyses that stand behind a report or a post,
kept with everything needed to rerun them. Private for now.

## Layout

One folder per study. Each is standalone: its own `README.md` with the commands to reproduce it,
its own `requirements.txt`, its parameters, scripts, raw solver runs, extracted data, figures and
the report or post built from them. Nothing is shared between folders, so a study can be read,
rerun or moved on its own.

| Study | What it asks | Answered with |
| --- | --- | --- |
| [`diffpair-meanders/`](diffpair-meanders/) | Does serpentine length tuning remove the intra-pair skew of a differential-pair U-bend? | openEMS (FDTD) four-port extraction, mixed-mode S-parameters, a calibrated line model |

## Conventions

- Every number in a report or post is generated from the study's results by a script, never typed in.
- Raw solver outputs and their provenance records are committed beside the scripts that made them,
  so a reader can check a figure against the run behind it without a solver installed.
- Binaries and fonts are not committed; each study's `README.md` says where to get them.

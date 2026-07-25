# G-Amazon — Mode A spatial point-process screen — NOTES

**Verdict: `STRUCTURE_ONLY`** (spatial clustering). Run `outputs/amazon/run.json`.
Authored by **Ulfberht** (Geoglyf agent not provisioned; Captain reassigned).
Reviewer separation collapsed → shipped on a branch, merge held for a second reader.

## Stance
Structure ≠ meaning. This is a *screening* test of whether earthwork/geoglyph
**coordinates** depart from Complete Spatial Randomness (CSR). It says nothing
about intent, geometry-by-design, chronology, or any "lost civilisation." A
positive result here is the *least surprising* outcome for anthropogenic
features and reflects rivers, terra-firme soils, and — importantly — **survey
coverage**, not a signal.

## What Zenodo contains vs. what we analysed
Zenodo `10.5281/zenodo.7750985` (record 10214943; Peripato et al., *Science*
2023) is primarily: a site/earthwork **coordinate database** (`Earthworks.rds`),
1 km **IPP predictive-probability rasters** (`.tif`), and R reproducibility code.
It is **not** a basin-wide raw canopy-LIDAR point cloud.

- **Analysed:** `Earthworks.rds` → 961 georeferenced earthwork sites
  (`data/amazon/earthworks_zenodo.csv`). Read with the pure-python `rdata`
  package (no R available in the environment).
- **Not analysed / not committed:** the two IPP `.tif` rasters (~32 MB + ~36 MB)
  and the GLM model outputs. Mode A does not need them, and we make **no**
  raster/LIDAR-geometry claim. Mode B = `BLOCKED` (no public dense DEM/LAS for a
  named geoglyph located).

## Method (pure numpy, `tools/geo/amazon_earthworks_probe.py`)
- Project lon/lat → local equirectangular **km** about the centroid (self-consistent
  distances/areas; screening approximation over a wide latitude band).
- **Study mask** = convex hull of the point set (documented approximation of the
  paper's true basin window — this slightly *inflates* apparent clustering near
  the boundary, i.e. it is a conservative direction to be honest about).
- **Clark-Evans** nearest-neighbour ratio R = mean_NN_obs / mean_NN_csr.
- **Ripley's L(r) − r** at 8 radii vs a CSR envelope.
- **Shared negative control:** CSR = N uniform points re-drawn inside the *same*
  hull (matched N, matched edge effects), `n_sims = 199`.

## Result — Zenodo Peripato (N = 961)
| Statistic | Observed | CSR mean | z | Read |
|-----------|----------|----------|---|------|
| Mean nearest-neighbour | **5.31 km** | 30.36 km | **−46.7** | far closer than random |
| Clark-Evans R | **0.175** | 1.0 | — | strong clustering (R≪1) |
| Ripley L−r (all 8 radii, 37–463 km) | above envelope | 0 | **+111 … +557** | clustered at every scale |

Hull area ≈ 3.43 M km². All Ripley radii sit outside the CSR envelope.

## Negative & known-answer controls (offline, `tools/geo/tests/…`, all PASS)
- **Known-answer:** planted tight clusters → `STRUCTURE_ONLY`, R = 0.60, z = −16.1. Probe fires on real structure. ✔
- **Negative control (CSR-as-data):** uniform points → `NO_SIGNAL`, R = 0.98, z = −1.31. Probe does **not** hallucinate structure. ✔ *(This is a probe-validation, not a verdict on real data.)*
- **Small-N guard:** N < 30 → `UNDERDETERMINED` (never a fabricated verdict). ✔

## Independent cross-check — jqjacobs (LOCAL only, not committed)
jqjacobs *Amazonian Geoglyphs* KML (6,036 placemarks in the Amazon bbox;
© James Q. Jacobs, all rights reserved — **not redistributed here**). NN-only
Clark-Evans: obs 0.84 km vs CSR 9.80 km, **R = 0.086, z ≈ −140** →
`STRUCTURE_ONLY`. Clustering **replicates on an independent coordinate source**.

## Honest prior / caveats
- Clustering of anthropogenic sites is expected; the dominant confound is
  **non-uniform survey/detection effort** (roads, deforestation arcs, remote-
  sensing coverage) — the null does not model detection bias, so "clustering"
  partly measures where people *looked*. Stated plainly, not corrected away.
- Convex-hull window and equirectangular projection are screening choices; a
  basin-polygon window + equal-area projection would refine magnitudes (not the
  qualitative verdict).
- **No** decipherment, orientation-code, or civilisation-tech claim is made or
  implied. Structure ≠ lost civilisation.

## Verdict
`STRUCTURE_ONLY` — earthwork/geoglyph coordinates are strongly, multi-scale
clustered vs CSR, replicated across two independent sources. This is spatial
structure consistent with anthropogenic + environmental + survey-coverage
constraints. It is **not** evidence of message, intent, or design.

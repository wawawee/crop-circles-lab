# data/amazon — sources, licenses, provenance

G-Amazon runs in **Mode A** (spatial point-process screen). We analyse
earthwork / geoglyph **coordinates** only. We do **not** download the 1 km IPP
probability rasters or any canopy-LIDAR product, and we make **no** LIDAR-geometry
claims (Mode B stays `BLOCKED` — no public dense DEM/LAS located for a named site).

## What is committed here

| File | Rows | Source | License |
|------|------|--------|---------|
| `earthworks_zenodo.csv` | 961 | Peripato et al. 2023 database (`Earthworks.rds`) | Zenodo deposit (open) — cite below |

Columns: `id, lat, lon, type, source`. `type` = the `Database` provenance field
from the Peripato deposit (e.g. `Amazon Arch`, `CNSA`, `PAST`, `INRAP & DAC`,
`TREES/INPE`, and `Multiple: (...)` combinations).

## What is NOT committed (fetched locally, git-ignored)

- **Zenodo `ade2541-v1.0.0.zip`** (~20 MB) — code + `Database/`. We extract only
  `Earthworks.rds` and convert it to the CSV above. The GLM/IPP model outputs
  (`.rds`, `.zip`) and the two `IPPModel_EarthworkProb-*.tif` rasters
  (~32 MB + ~36 MB) are **not** needed for Mode A and are **not** committed.
- **jqjacobs geoglyph coordinates** (`amazon_geoglyphs.kml`, ~6,036 placemarks).
  **© James Q. Jacobs, all rights reserved.** We do **not** redistribute his raw
  coordinates in this repo. They are fetched locally (git-ignored) and used only
  as an **independent cross-check** reported as aggregate statistics in
  `outputs/amazon/NOTES.md`. Source, with thanks:
  <https://www.jqjacobs.net/archaeology/geoglyph.html>

## Reproduce

```bash
python3 data/amazon/fetch_data.py        # downloads to data/amazon/raw/ (git-ignored)
python3 tools/geo/amazon_earthworks_probe.py \
    --csv data/amazon/earthworks_zenodo.csv --out outputs/amazon/run.json --n-sims 199
python3 tools/geo/tests/test_amazon_earthworks_probe.py   # offline known-answer + neg control
```

`fetch_data.py` needs `pip install rdata` (pure-python; no R, no C toolchain).

## Citations

- Peripato, V., et al. (2023). *More than 10,000 pre-Columbian earthworks are
  still hidden throughout Amazonia.* **Science** 382, 103–109.
  DOI: [10.1126/science.ade2541](https://doi.org/10.1126/science.ade2541).
  Data: Zenodo concept DOI [10.5281/zenodo.7750985](https://doi.org/10.5281/zenodo.7750985)
  (resolved record 10214943).
- Jacobs, J. Q. *Amazonian Geoglyphs* (coordinate compilation, KML).
  <https://www.jqjacobs.net/archaeology/geoglyph.html> — cross-check only, not redistributed.

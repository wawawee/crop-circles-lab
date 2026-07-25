---
name: amazon-earthworks-spatial
description: >-
  Analyze Amazon pre-Columbian earthworks with OPEN Zenodo data (Peripato 2023).
  Use for G-Amazon / Hyper Fable or Opus. Prefer site-point + IPP rasters; do NOT
  claim raw canopy LIDAR Hough unless a real dense DEM/LAS subset is located.
---

# Amazon earthworks — Hyper skill (Fable 5 / Opus 4.8)

## Lab stance
Structure ≠ meaning. Confirm human earthworks geometry / spatial clustering vs nulls.
No lost-civilization tech claims. Zetetic: measure, control, report.

## Critical data fact (read first)
Zenodo **10.5281/zenodo.7750985** (Peripato et al., Science 2023, DOI 10.1126/science.ade2541) is primarily:
- site / earthwork **database** (coordinates + types),
- **1 km** IPP predictive probability rasters (`.tif`),
- R code for reproducibility.

It is **NOT** a basin-wide raw canopy LIDAR point-cloud dump. Do not invent LAZ tiles.

**Enrichment (Kimi scout):** Also ingest **jqjacobs** Amazon geoglyph coordinate dumps (~1,370 features, KML/CSV/Excel) from
https://www.jqjacobs.net/archaeology/geoglyph.html — cite and attribute in README. Prefer these
point/polygon coords for network/NN/orientation nulls alongside Zenodo site tables.

## Mission modes (pick ONE; prefer A)

### Mode A — Spatial point-process + ratio screen (DEFAULT, Effort M)
1. Download Zenodo deposit; inventory `Database/` and raster folders; document exact files in `data/amazon/README.md` (license/citation).
2. Build `data/amazon/earthworks.csv` (id, lat, lon, type, source).
3. Reuse / extend `tools/ccat/spatial_report.py` ideas OR new `tools/geo/amazon_earthworks_probe.py`:
   - nearest-neighbor distances, Ripley's K or simple density vs landmask,
   - type-stratified counts (geoglyph / ring ditch / etc. if present).
4. **Negative control:** Monte Carlo Poisson (or CSR) points inside the **same** Amazon land polygon / study mask as the paper — same N.
5. Optional: load 1 km probability `.tif` with rasterio; report whether known sites sit in high-P cells vs random sites (replication of paper spirit, not scoop).
6. If shapefiles of **individual enclosure polygons** exist in the deposit, run `ratios` / eccentricity / orthogonality on those polygons only — never on 1 km rasters.

### Mode B — True LIDAR geometry (ONLY if verified)
If (and only if) you find a **public** dense DEM/LAS for a named geoglyph region (document URL + license):
- orthometric DEM → Canny/Hough or contour → circle/rect RANSAC,
- known-answer: inject perfect circle/rect into noisy DEM, recover <1% distortion,
- negative: natural oxbow / drainage loops from same DEM outside sites.
If no such public dense product → **stay in Mode A** and mark Mode B `BLOCKED`.

## Forbidden
- Claiming “we ran canopy LIDAR Hough” on 1 km IPP rasters.
- Committing multi-GB rasters without Captain approval (prefer scripts that download + `.gitignore` large binaries; commit CSV + small previews + JSON metrics).
- Ancient-astronaut framing.

## Deliverables
- `tools/geo/amazon_earthworks_probe.py` (+ tests with tiny synthetic points)
- `data/amazon/README.md` + small CSV (coordinates OK)
- `outputs/amazon/run.json` + `NOTES.md` with mode (A/B), null result, honest prior
- Update `MISSION_BOARD.md` / `docs/gemini_research_leads_2026-07-25.md` status

## Acceptance
- Null comparison present and quantitative.
- NOTES explicitly states what Zenodo contains vs what was analyzed.
- Verdict string one of: `STRUCTURE_ONLY` | `NO_SIGNAL` | `UNDERDETERMINED` | `BLOCKED`.

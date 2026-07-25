# EAMENA — Endangered Archaeology in the Middle East and North Africa

## Source

**EAMENA Database:** <https://database.eamena.org/>  
**Project:** <https://eamena.org/>  
**Zenodo community:** <https://zenodo.org/communities/eamena>

The EAMENA project, based at the Universities of Oxford, Leicester, and
Durham, records archaeological sites and heritage at risk across the MENA
region. The database runs on the Arches platform (CIDOC-CRM ontology).

## Data access status — 2026-07-25

**BLOCKED — no public read-only REST endpoint for GeoJSON export.**

The Arches API routes we tested:
- `/api/search/resources/?format=geojson` → 404
- `/api/resources/HeritagePlace?format=geojson` → `{"message":"Route not found"}`

GeoJSON export is available *interactively* through the web interface
(search → "Export Search Results" → copy GeoJSON URL), but the EAMENA
citation plugin workflow is the recommended path for citable exports
(via Zenodo). At time of writing, the Zenodo community contains
region-specific subsets but no single unified 338k-site GeoJSON dump
suitable for a bulk ingest pipeline.

## Real EAMENA subset (G18++)

Via the EAMENA Zenodo community, we downloaded a small regional subset:

| Dataset | Record | Points | Size | License |
|---------|--------|--------|------|---------|
| Bani Walid, Libya | [zenodo.org/records/12801265](https://zenodo.org/records/12801265) | 178 | 1.3 MB (subset: 262 KB) | CC BY 4.0 |

The Bani Walid dataset (MLACD — Management of Libyan Antiquities and
Cultural Database) contains 178 Point features with rich archaeological
metadata (dating, cultural periods, assessment activities, etc.).

**G18++ finding:** When run through the same probe pipeline, the real
EAMENA data produces `LEY_LINE_SIGNAL` with Clark-Evans R=0.37 (z=-15.3)
— but this is a **false positive** driven by natural spatial clustering
of archaeological sites along environmental gradients (water, soil,
trade routes). The naive CSR null assumes uniform spatial intensity,
which real archaeology violates. An inhomogeneous Poisson (Cox process)
null conditioned on environmental covariates is needed for honest
evaluation of real data.

## Synthetic fallback (G18 primary)

Because the full 338k EAMENA corpus is not available via a simple
programmatic API, this probe uses a **synthetic Complete Spatial
Randomness (CSR) point cloud** of N sites with known geometry:

- **N = 500** synthetic sites (≈ matched to a small Jordan/Zarqa subset
  scale documented in EAMENA case studies).
- **Bounding box:** 34.0–35.5°E, 30.0–32.5°N (northern Jordan / Syria
  border region, a known high-density EAMENA survey zone).
- **Distribution:** Uniform within the bounding box (CSR by construction).
- **Purpose:** Calibrate the false-positive rate (FPR) of "ley line"
  detection when the underlying point process is known to be random.
  Any detected alignments are, by definition, false positives.
- **Ground truth:** `distribution = "csr"`, `expected_fpr_nominal = 0.05`.
- **G18++ comparison:** Synthetic CSR at matched N=178 yields
  `NO_SIGNAL | FPR_CALIBRATED` (R=0.98, z=-0.37), confirming the probe
  correctly identifies CSR when the null matches the generating process.

## License notes

EAMENA data is published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
unless otherwise noted. Synthetic points generated for this analysis
carry no license restrictions (they are random coordinates).

## Files

| File | Description |
|------|-------------|
| `synthetic_csr_sites.json` | Synthetic CSR point cloud (N=500, known random) |
| `bani_walid_libya_subset.geojson` | Real EAMENA subset — Bani Walid, Libya (178 Point features) |
| `README.md` | This file |

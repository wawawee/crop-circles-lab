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

## Synthetic fallback (this analysis)

Because the full 338k EAMENA corpus is not available via a simple
programmatic API, this probe uses a **synthetic Complete Spatial
Randomness (CSR) point cloud** of N sites with known geometry:

- **N = 500** synthetic sites (≈ matched to a small Jordan/Zarqa subset
  scale documented in EAMENA case studies — see
  `docs/research_leads_kimi_2026-07-25.md`).
- **Bounding box:** 34.0–35.5°E, 30.0–32.5°N (northern Jordan / Syria
  border region, a known high-density EAMENA survey zone).
- **Distribution:** Uniform within the bounding box (CSR by construction).
- **Purpose:** Calibrate the false-positive rate (FPR) of "ley line"
  detection when the underlying point process is known to be random.
  Any detected alignments are, by definition, false positives.
- **Ground truth:** `distribution = "csr"`, `expected_fpr_nominal = 0.05`.

A future G18+ ticket can ingest a real EAMENA GeoJSON subset when a
convenient Zenodo dump is published (or when the Arches API is opened
for programmatic access). The probe is designed to accept a GeoJSON
file via `--geojson` flag, so swapping in real data requires zero
pipeline changes.

## License notes

EAMENA data is published under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
unless otherwise noted. Synthetic points generated for this analysis
carry no license restrictions (they are random coordinates).

## Files

| File | Description |
|------|-------------|
| `synthetic_csr_sites.json` | Synthetic CSR point cloud (N=500, known random) |
| `README.md` | This file |

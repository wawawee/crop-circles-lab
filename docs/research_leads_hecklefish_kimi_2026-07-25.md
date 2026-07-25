# Research leads — Hecklefish Kimi cold list (2026-07-25 evening)

Source: Lead Hecklefish Kimi chat brief (9 proposals).  
Stance: **structure ≠ message**. Measure → control → report.

Cross-ref: [`research_leads_kimi_2026-07-25.md`](research_leads_kimi_2026-07-25.md) (G16–G20),
[`research_leads_anomalistics_2026-07-25.md`](research_leads_anomalistics_2026-07-25.md).

---

## Priority executed this session

| # | Proposal | Deliverable | Status |
|---|----------|-------------|--------|
| 1 | Voynich plant pages × botany/CCAT | `tools/scripts/voynich_botany_probe.py` | 🟢 Beinecke IIIF sample (16 folios) + PD Thomé controls |
| 2 | Barbara West Indus negcontrol | `tools/scripts/indus_west_negcontrol.py` | 🟢 pipeline prefers `west_plaintext_real.json`; Barbara West 2004 blocked — JL West 2026 fair-use sample |
| 4 | Language Entropy Atlas | `data/catalog/entropy_atlas.json` + `tools/scripts/atlas_query.py` | 🟢 seeded |
| — | Anomaly JSON schema | `data/catalog/anomaly_schema.json` + `anomalies.json` | 🟢 |

## Light scaffolds

| # | Proposal | Path |
|---|----------|------|
| 3 | Rongorongo refrain×calendar | `tools/scripts/rongorongo_refrain.py` (G4 already has parallels) |
| 5 | Göbekli × Taurid | `tools/astro/goebekli_taurid.py` |
| 6 | Amazon LiDAR negatives | `tools/geo/lidar_negative_probe.py` |

## Weekend backlog (do not deep-implement)

| # | Proposal | Stub |
|---|----------|------|
| 7 | α variation dipole | `tools/scripts/stubs/alpha_variation_probe.py` |
| 8 | VASCO missing stars (G13) | `tools/scripts/stubs/vasco_missing.py` |
| 9 | Earthquake lights / EM | not stubbed — needs seismo corpus design |

---

## How to run

```bash
cd crop-circles
.venv/bin/python tools/scripts/voynich_botany_probe.py          # auto Beinecke folios + PD controls
.venv/bin/python tools/scripts/voynich_botany_probe.py --demo   # synthetic fixtures only
.venv/bin/python tools/scripts/indus_west_negcontrol.py --also-english-ka  # prefers west_plaintext_real.json
.venv/bin/python tools/scripts/atlas_query.py --domain script --sort z
.venv/bin/python tools/scripts/rongorongo_refrain.py --dry-run
.venv/bin/python tools/astro/goebekli_taurid.py --dry-run
.venv/bin/python tools/geo/lidar_negative_probe.py --dry-run
```

## Stack reuse map (Kimi → existing)

| Need | Existing |
|------|----------|
| Symbol entropy | `tools/forensics/symbolseq.py` |
| Image edges / shape | `tools/ccat/ccat.py` |
| Geometry info theory | `tools/ccat/info_theory.py` |
| Feature table | `tools/ccat/feature_table.py` |
| Spatial | `tools/ccat/spatial_report.py` |
| Astro | `tools/astro/astro_probe.py` |
| Captain dashboard | `reports/mission_dashboard.html` + `tools/mission_status.py` |

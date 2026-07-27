# G17 — TESS SN 1987A SETI Ellipsoid Re-analysis

Generated: 2026-07-27T00:54:25.833847+00:00

## Stance

Structure != message. The SETI Ellipsoid is a geometric target-prioritisation strategy, not a technosignature detection. Cabrales+2024 found no anomalous signatures in any TESS lightcurve (non-detection is the ground truth). This pipeline validates epoch-fold math and null calibration, not the presence of extraterrestrial signals. No periodicity or dip structure at an Ellipsoid crossing time constitutes evidence of artificial engineering without independent multi-wavelength confirmation.

## Catalog

- Source: Cabrales+2024, AJ 167:101 (DOI: 10.3847/1538-3881/ad2064)
- N targets: 32 (real TIC IDs from Table 2)
- First target: TIC 279055252
- First target tcross: 1330.75 BJD

## Known-Answer Path

- Target TIC: 279055252
- tcross BJD: 1330.75
- Planted period: 2.5 days
- N injected dips: 30
- Recovery pass: True
- Recovered period: 2.5050000000000003 days
- Recovered Z2: 56.52696173290552
- Recovery error: 0.0050000000000003375 days
- p-value: 5.312833679143812e-13

## Negative Controls

### Quiet-star null (uniform random times)

- Trials: 200
- Null Z2 mean: 11.777168816357827
- Null Z2 95th percentile: 15.682490520655321
- Null Z2 max: 20.917039002234148

### Time-shuffle null (permuted tcross assignments)

- Trials: 200
- Null Z2 mean: 11.603138314706506
- Null Z2 95th percentile: 16.434968913421258
- Null Z2 max: 21.70357022439058

## Cohort Analysis

- Targets: 32
- Anomalous count: 0 (at Z2 > 21.0)
- Threshold calibration: max(quiet95=15.682490520655321, shuffle95=16.434968913421258, floor=21.0) — cohort anomaly threshold now calibrated above null (FPR-controlled).
- Note: Fixture-only (no real TESS data). Per-target epoch-fold using random dip times. Threshold calibrated above null 95ths (floor=21.0).

## Real TESS Data

- Not available. Run with --fetch to attempt MAST download via lightkurve.

## Verdict

**PIPELINE_VALIDATED | No real TESS data fetched. Without lightkurve / MAST access the result is computational only. | UNDERDETERMINED**

TESS SN 1987A SETI Ellipsoid (Cabrales+2024) re-analysis. N_targets=32 from real catalog. Known-answer: injected dip at TIC 279055252, recovery_pass=True, Z2=56.5. Quiet-star null 95th Z2=15.682490520655321, time-shuffle null 95th Z2=16.434968913421258. Cohort null: 0/32 anomalous (threshold Z2 > 21.0; calibrated above null). Real TESS data: not available (run with --fetch).

Verdict: PIPELINE_VALIDATED | No real TESS data fetched. Without lightkurve / MAST access the result is computational only. | UNDERDETERMINED

Structure != message. The SETI Ellipsoid is a geometric target-prioritisation strategy, not a technosignature detection. Cabrales+2024 found no anomalous signatures in any TESS lightcurve (non-detection is the ground truth). This pipeline validates epoch-fold math and null calibration, not the presence of extraterrestrial signals. No periodicity or dip structure at an Ellipsoid crossing time constitutes evidence of artificial engineering without independent multi-wavelength confirmation.


This analysis validates the epoch-fold pipeline and null calibration. It uses the real Cabrales+2024 Table 2 catalog with 32 real TIC IDs. The known-answer injects a synthetic dip into one target; the cohort analysis verifies that a fixture-only path does not over-claim dips. For real results, run with --fetch (requires lightkurve + MAST access). The published ground truth is a non-detection (Cabrales+2024). Structure != message.


### Paper context

- Cabrales et al. 2024, AJ 167:101 — non-detection ground truth
- 32 targets from Table 2 (real TIC IDs, Gaia EDR3 distances)
- No anomalous signatures found by the original authors
- This pipeline validates the math, not the hypothesis

---
*G17 TESS Ellipsoid — structure != message. Ellipsoid geometry != technosignature.*
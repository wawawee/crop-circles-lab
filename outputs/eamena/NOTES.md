# G18 — EAMENA ley-line null probe (spatial FPR calibration)

**Verdict:** `FPR_CALIBRATED`  

Real collinearity exceeds null envelope at one or more primary tolerances ([1.0, 2.0]). FPR per tolerance is reported above. This warrants extension to a larger EAMENA sample.

## What this is

This probe tests whether EAMENA archaeological site coordinates show
collinearity (ley-like alignment) beyond what Complete Spatial
Randomness (CSR) or coordinate permutation would produce. It is a
**false-positive rate calibration** — not a claim about ancient leys.

## Dataset

- Source: EAMENA Sistan part 1 (CC BY 4.0)
- DOI: 10.5281/zenodo.10375902
- Sites: 80
- Bbox: {'lon_min': 61.1812, 'lat_min': 30.3, 'lon_max': 62.1694, 'lat_max': 31.4946}

## Method

- Collinearity detector: great-circle bearing deviation for all
  triples, at tolerances 0.1°, 0.5°, 1.0°, 2.0°, 5.0°.
- Null CSR: uniform random points in the same bounding box.
- Null scramble: independent coordinate permutation.
- 199 simulations per null.
- Threshold: 99% quantile of the combined null distribution.

## Results

| tolerance | stat | real | CSR 99% | CSR FPR | scramble 99% | scramble FPR |
|---|---|---|---|---|---|---|
| 0.1° | triples | 317 | 232.1 | 0.0 | 282.12 | 0.0 |
| 0.1° | max_run | 80 | 80.0 | 0.8241 | 80.0 | 0.9146 |
| 0.5° | triples | 1749 | 1017.06 | 0.0 | 1184.02 | 0.0 |
| 0.5° | max_run | 80 | 80.0 | 1.0 | 80.0 | 1.0 |
| 1.0° | triples | 3240 | 2016.68 | 0.0 | 2300.8 | 0.0 |
| 1.0° | max_run | 80 | 80.0 | 1.0 | 80.0 | 1.0 |
| 2.0° | triples | 5834 | 3966.72 | 0.0 | 4377.42 | 0.0 |
| 2.0° | max_run | 80 | 80.0 | 1.0 | 80.0 | 1.0 |
| 5.0° | triples | 11586 | 9823.18 | 0.0 | 10189.0 | 0.0 |
| 5.0° | max_run | 80 | 80.0 | 1.0 | 80.0 | 1.0 |

**Mean alignment error:** real=27.4404°, CSR mean=28.3727° (sd=0.5325°), scramble mean=27.8045° (sd=0.3875°)

## Caveats

- Collinearity detection uses great-circle bearings on a random subsample of the full dataset (--max-points).
- CSR null is uniform in bbox; does not model terrain or cultural settlement patterns that constrain site placement.
- Structure detection is not a message or civilisation claim.
- FPR_CALIBRATED means the real collinearity count exceeds the null envelope — it does NOT imply intentional alignment.

## Honest bottom line

Real collinearity exceeds null envelope at one or more primary tolerances ([1.0, 2.0]). FPR per tolerance is reported above. This warrants extension to a larger EAMENA sample.

No ancient grid, no ET roads, no mystical leys. This is a null-model calibration exercise.

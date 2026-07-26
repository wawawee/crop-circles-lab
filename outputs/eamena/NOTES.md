# G18 — EAMENA ley-line null probe (spatial FPR calibration)

**Verdict:** `UNDERDETERMINED`  

n=14 is small; collinearity statistics are unreliable until tested on larger EAMENA subsets.

## What this is

This probe tests whether EAMENA archaeological site coordinates show
collinearity (ley-like alignment) beyond what Complete Spatial
Randomness (CSR) or coordinate permutation would produce. It is a
**false-positive rate calibration** — not a claim about ancient leys.

## Dataset

- Source: EAMENA Wadi Naqqat subset (14 sites, CC BY 4.0)
- DOI: 10.5281/zenodo.15554618
- Sites: 14
- Bbox: {'lon_min': 33.2825, 'lat_min': 27.0431, 'lon_max': 33.287, 'lat_max': 27.0502}

## Method

- Collinearity detector: great-circle bearing deviation for all
  triples, at tolerances 0.1°, 0.5°, 1.0°, 2.0°, 5.0°.
- Null CSR: uniform random points in the same bounding box.
- Null scramble: independent coordinate permutation.
- 999 simulations per null.
- Threshold: 99% quantile of the combined null distribution.

## Results

| tolerance | stat | real | CSR 99% | CSR FPR | scramble 99% | scramble FPR |
|---|---|---|---|---|---|---|
| 0.1° | triples | 1 | 4.0 | 0.5806 | 3.02 | 0.5035 |
| 0.1° | max_run | 3 | 7.0 | 0.5806 | 7.0 | 0.5035 |
| 0.5° | triples | 5 | 12.0 | 0.4114 | 10.0 | 0.2402 |
| 0.5° | max_run | 7 | 13.0 | 0.5716 | 13.0 | 0.4284 |
| 1.0° | triples | 7 | 21.0 | 0.7027 | 17.0 | 0.4915 |
| 1.0° | max_run | 7 | 14.0 | 0.9329 | 14.0 | 0.8609 |
| 2.0° | triples | 17 | 35.0 | 0.5015 | 31.02 | 0.2833 |
| 2.0° | max_run | 14 | 14.0 | 0.5676 | 14.0 | 0.4414 |
| 5.0° | triples | 37 | 76.0 | 0.6897 | 64.02 | 0.3964 |
| 5.0° | max_run | 14 | 14.0 | 0.989 | 14.0 | 0.979 |

**Mean alignment error:** real=29.2894°, CSR mean=27.0411° (sd=2.3222°), scramble mean=28.3218° (sd=1.968°)

## Caveats

- Subset is only 14 sites in a ~500 m area — too few for reliable ley-line statistics. These results are a calibration exercise.
- Collinearity detection uses great-circle bearings, not planar approximations, appropriate for the Wadi Naqqat extent.
- CSR null is uniform in bbox; does not model terrain or cultural settlement patterns that constrain site placement.
- Structure detection is not a message or civilisation claim.

## Honest bottom line

n=14 is small; collinearity statistics are unreliable until tested on larger EAMENA subsets.

No ancient grid, no ET roads, no mystical leys. This is a null-model calibration exercise.

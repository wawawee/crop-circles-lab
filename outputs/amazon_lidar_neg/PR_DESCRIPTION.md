# Hecklefish #6 — Amazon LiDAR negative / control probe (re-run CLEAN)

## One-line summary

Harden the Amazon geoglyph/earthwork pipeline against false-positive "geoglyph"
claims using synthetic LiDAR negative tiles (CSR, forest texture, and pixel-
scrambled planted controls). The detector is calibrated at the 99 % quantile and
returns **FPR_CALIBRATED** for the synthetic negatives, while real Amazon
LiDAR/DEM remains **UNDERDETERMINED** because no public dense tile was located.

## Scope

This PR is strictly limited to the Amazon LiDAR negative probe. It does **not**
re-run or modify G-Amazon Mode A (`tools/geo/amazon_earthworks_probe.py`).

| Allowlist path | What changed |
|---|---|
| `tools/geo/lidar_negative_probe.py` | New negative/control probe (tile generation, elongation + high-pass FFT detector, FPR calibration, forbidden-phrase guard) |
| `tools/geo/tests/test_lidar_negative_probe.py` | 13 unit/integration tests |
| `data/geo/amazon_lidar_neg/` | Synthetic control tiles + README |
| `outputs/amazon_lidar_neg/` | `run.json`, `NOTES.md`, `PR_DESCRIPTION.md` |

## What's in this PR

### 1. Synthetic control tiles (`data/geo/amazon_lidar_neg/`)

- `README.md` — provenance and caveats.
- `tiles.json` — deterministic archive of:
  - `csr`: independent Bernoulli masks (Complete Spatial Randomness)
  - `forest`: smoothed random-field texture (canopy/terrain surrogate)
  - `scramble`: pixel-shuffled planted masks (structure destroyed, density preserved)
  - `planted`: synthetic straight-line geoglyphs (known-answer positives)

All tiles are synthetic; no real LiDAR/DEM is committed.

### 2. Probe — `tools/geo/lidar_negative_probe.py`

- Generates synthetic tiles and computes a false-geoglyph score.
- Detector combines:
  - 8-connected component **elongation** score (long thin lines vs compact blobs)
  - High-pass **2D-FFT peakiness** (suppresses low-frequency forest blobs)
  - Dominant-period correlation
- Calibrates at the 99 % quantile of the combined CSR+forest+scramble null
  distribution.
- Verdict vocabulary: `NO_SIGNAL` | `FPR_CALIBRATED` | `UNDERDETERMINED`.
- Forbidden-phrase guard scans `NOTES.md`, `run.json`, data `README.md`, and
  `tiles.json`.

### 3. Tests — `tools/geo/tests/test_lidar_negative_probe.py`

**13 tests**, all passing:

- Density matching for CSR tiles
- Forest texture is smoother than CSR
- Scramble preserves density
- Planted/stripe scores exceed CSR
- Calibration returns an allowed verdict
- Calibration separates planted positives from nulls (power ≥ 0.8, FPR ≤ 0.10)
- CLI `main()` writes expected output and data files
- Forbidden phrases absent from generated notes
- Sample tiles round-trip correctly

```bash
python tools/geo/tests/test_lidar_negative_probe.py
# ALL TESTS PASS
```

### 4. Outputs — `outputs/amazon_lidar_neg/`

| File | Purpose |
|---|---|
| `run.json` | Calibration scores, FPR, power, verdict |
| `NOTES.md` | Human-readable notes and caveats |

Latest run:

```
verdict:             FPR_CALIBRATED
real_data_verdict:   UNDERDETERMINED
threshold:           17.784
power_planted:       100.00 %
FPR (csr):           0.00 %
FPR (scramble):      0.00 %
FPR (forest):        5.00 %
FPR (combined):      1.67 %
```

## Stance / honest caveats

- Structure detection ≠ message, intent, or lost civilisation.
- Tiles are synthetic; no public dense LiDAR/DEM tile for a named Amazon
  geoglyph was located.
- A calibrated FPR on synthetic negatives does not imply any real geoglyph
  signal.
- Forbidden-phrase guard passes on generated artefacts (phrase list lives in
  the probe; this file does not restate the literal strings).

## Reviewers

Per `MISSION_BOARD.md` merge-gate rules: Captain / Cursor / Ulfberht.

## Branch policy

- Source branch: `feat/amazon-lidar-neg` (off `main`).
- Author: **Kimi 2.7 Code** (Hecklefish #6 ticket).
- Merge gate: Cursor (or Captain / Ulfberht as fallback).
- No push to `main`.

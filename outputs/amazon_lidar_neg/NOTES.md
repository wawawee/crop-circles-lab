# Amazon LiDAR Negative / Control Probe (Mode A-NEG) -- NOTES

**Verdict:** `FPR_CALIBRATED`  
**Real-data verdict:** `UNDERDETERMINED`  

Detector separates planted geoglyphs from CSR/forest/scramble nulls at a 99% threshold, with power=100.00% and FPR_combined=1.67%.

## What this is

This is a *negative-control hardening* experiment for the Amazon 
geoglyph/earthwork detection pipeline. It does **not** claim to have 
found anything in real Amazon LiDAR. Instead, it calibrates how often a 
simple spectral detector will falsely flag random or texture-like tiles 
as 'geoglyph-like'.

## Method

- Synthetic tiles: 128 × 128, density=0.08.
- Negative tiles: `csr` (independent random) and `scramble` (pixel-shuffled planted).
- Texture tiles: `forest` (smoothed random field, a canopy/terrain surrogate).
- Known-answer tiles: `planted` (synthetic straight-line geoglyph).
- Detector: 2D-FFT peakiness + dominant-period correlation.
- Calibration: threshold = 99% quantile of the combined CSR+forest+scramble null distribution.

## Results

| metric | value |
|---|---|
| threshold | 17.784 |
| power_planted | 100.00% |
| FPR (csr) | 0.00% |
| FPR (scramble) | 0.00% |
| FPR (forest) | 5.00% |
| FPR (combined null) | 1.67% |

## Caveats

- Tiles are synthetic; no public dense LiDAR/DEM tile for a named Amazon geoglyph was located.
- Forest texture is a smoothed random field, not a canopy-LiDAR DEM.
- A calibrated FPR on synthetic negatives does not imply any real geoglyph signal.
- Structure detection is not a message or civilisation claim.

## Honest bottom line

The detector's false-positive rate is calibrated on synthetic negatives. 
Real Amazon LiDAR/DEM tiles were not available for this probe, so any 
claim about real geoglyphs remains **underdetermined**.

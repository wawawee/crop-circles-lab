# G22 — Nazca Line Detection Probe -- NOTES

**Verdict:** `FPR_CALIBRATED`  
**Real-data verdict:** `FIXTURE_ONLY`  

Line detector separates planted long-line tiles from desert nulls at the 99% threshold, with power=100.00% and FPR_combined=1.67%. Applied to synthetic Nazca-like tiles: LINE_STRUCTURE detected.

## What this is

A geometry detector calibrated on synthetic tiles to identify
long-thin line structure (Nazca line-type geoglyph geometry).
It does NOT detect figurative reliefs (<50 m) which are
underdetermined at Sentinel-2 10 m GSD.

## Tile types

- **planted**: 2-3 long thin lines on desert-varnish background (known-answer)
- **csr**: random Bernoulli noise
- **ridge_clutter**: smoothed texture with ridge artifacts
- **desert_noise**: low-contrast perlin-like surface
- **scramble**: pixel-shuffled planted tile (density-matched)

## Pipeline

1. CLAHE contrast enhancement (clipLimit=3.0, 8x8 tiles)
2. Gaussian blur (3x3)
3. Sobel gradient magnitude → 90th-percentile threshold
4. HoughLinesP (rho=1, theta=pi/360, tuned thresholds)
5. Score = f(longest_segment, n_segments_>_30%_tile_size)

## Results

| metric | value |
|---|---|
| threshold | 59.043 |
| power_planted | 100.00% |
| FPR (csr) | 0.00% |
| FPR (ridge_clutter) | 0.00% |
| FPR (desert_noise) | 3.33% |
| FPR (scramble) | 3.33% |
| FPR (combined) | 1.67% |

## Caveats

- Tiles are synthetic; no real Nazca Sentinel-2 tile was fetched.
- Sentinel-2 (10 m GSD) UNDERDETERMINED for figurative reliefs <50 m.
- Bing/ESRI programmatic download is FORBIDDEN by ToS.
- Synthetic desert noise includes CSR, ridge clutter, and perlin-like texture.
- Detecting line geometry does NOT imply artificial origin.
- Structure != meaning. This is a geometry detector, not a claims engine.
- Figurative reliefs (e.g. hummingbird, spider) are below resolution threshold.

## Honest bottom line

The detector's line geometry score is calibrated on synthetic tiles. 
No real Nazca imagery was fetched (Sentinel-2 not downloaded; 
Bing/ESRI programmatic access is FORBIDDEN by ToS). 
All results are FIXTURE_ONLY.

*Structure != meaning. Long lines ≠ message.*

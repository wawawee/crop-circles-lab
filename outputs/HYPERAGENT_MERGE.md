# Hyperagent `crop-circle-forensics-v0.1` vs our CCAT lab

## Verdict
Hyperagent spent time on **validated math cores** (no images). Our CCAT spent time on
**CV pipeline + image acquisition**. Complementary — now merged.

## What hyperagent shipped (23/23 tests PASS)

| Module | Status | Value |
|--------|--------|-------|
| `ratios.py` | ✅ complete | Hawkins diatonic + Euclidean theorems |
| `fractal.py` | ✅ complete | Box-count with R² window selection; Koch/Sierpinski validated |
| `encoding.py` | ✅ complete | Barbury π, Crabwood ASCII, Arecibo/Chilbolton diffs, Julia ≠ true z²+c |
| `preprocess.py` | stub | Correct philosophy: mask before Hough |
| `geometry.py` | stub | Same |
| `symmetry.py` | stub | Swirl planned |
| `metadata.py` | stub | ELA planned |
| `spatial.py` | stub | Monument coords listed |
| `acquire.py` | stub | — |
| **Images** | none | empty `data/raw` |

## Key hyperagent findings (logic, not pixels)
- Barbury π decodes to `3.141592654` (10th digit rounded up) ✔
- 1996 Stonehenge “Julia Set” classified as **log-spiral of ~150 circles**, not a true Julia set ✔
- Chilbolton reply: Si(14), triple helix, figure height 14→8 units (~176→101 cm)

## What we already had that they stubbed
Dashboard, Hough+DBSCAN, swirl heuristic, ExifTool, vision probe, pandas report, image corpus.

## Integration
Solid cores copied → `crop-circles/tools/forensics/`

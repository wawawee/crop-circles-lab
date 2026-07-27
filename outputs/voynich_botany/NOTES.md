# G10++ — Voynich plant pages × CCAT shape metrics  🟢
Generated: 2026-07-27T02:31:21.893321+00:00

## Stance
G10++ probes SHAPE STRUCTURE of synthetic botanical drawings against synthetic null controls. It does NOT identify plant species, decipher herbarium labels, make pharma claims, or map Voynich plant pages to real-world flora. All images are synthetic (generated programmatically). No Beinecke IIIF or POWO data is processed. STRUCTURE != HERBAL ID / DECIPHERMENT.

**Motto:** *structure != herbal ID / decipherment.* No species identification, no medicinal claims, no alien botany.

## Data

- **Type:** SYNTHETIC (all images generated programmatically)
- **Real IIIF fetch:** NEVER_ATTEMPTED
- **POWO fetch:** NEVER_ATTEMPTED
- **Path:** `data/voynich_botany/`

## Synthetic setup
- N plants (KA): 30
- N per null control: 30
- Image size: 300×300
- Controls: noise, scramble, random_shapes, silhouette
- Generator seed: 0

## Metrics tested
- edge_pixel_ratio
- fractal_dimension
- lines_detected
- circles_detected
- mirror_symmetry
- rotational_symmetry_2fold

## Comparisons (KA plants vs null)

### vs_noise
| Metric | KA mean | Null mean | Cohen's d | z-score | Separates? |
|--------|---------|-----------|-----------|---------|------------|
| edge_pixel_ratio | 0.0108 | 0.3701 | -364.0152 | -1409.82 | ✓ |
| fractal_dimension | 1.148 | 1.9792 | -56.6197 | -219.29 | ✓ |
| lines_detected | 3.5 | 395.1667 | -47.4265 | -183.68 | ✓ |
| circles_detected | 0.3 | 0.0 | 0.9103 | 3.53 | ✓ |
| mirror_symmetry | 0.9969 | 0.9442 | 90.803 | 351.68 | ✓ |
| rotational_symmetry_2fold | 0.9882 | 0.9444 | 36.661 | 141.99 | ✓ |

### vs_scramble
| Metric | KA mean | Null mean | Cohen's d | z-score | Separates? |
|--------|---------|-----------|-----------|---------|------------|
| edge_pixel_ratio | 0.0108 | 0.1916 | -23.8615 | -92.42 | ✓ |
| fractal_dimension | 1.148 | 1.8401 | -38.9007 | -150.66 | ✓ |
| lines_detected | 3.5 | 383.5667 | -13.254 | -51.33 | ✓ |
| circles_detected | 0.3 | 0.0 | 0.9103 | 3.53 | ✓ |
| mirror_symmetry | 0.9969 | 0.9926 | 6.046 | 23.42 | ✓ |
| rotational_symmetry_2fold | 0.9882 | 0.9926 | -3.4635 | -13.41 | ✓ |

### vs_random_shapes
| Metric | KA mean | Null mean | Cohen's d | z-score | Separates? |
|--------|---------|-----------|-----------|---------|------------|
| edge_pixel_ratio | 0.0108 | 0.0225 | -2.8473 | -11.03 | ✓ |
| fractal_dimension | 1.148 | 1.2713 | -2.7591 | -10.69 | ✓ |
| lines_detected | 3.5 | 8.0333 | -1.4689 | -5.69 | ✓ |
| circles_detected | 0.3 | 2.5333 | -2.1642 | -8.38 | ✓ |
| mirror_symmetry | 0.9969 | 0.9442 | 3.927 | 15.21 | ✓ |
| rotational_symmetry_2fold | 0.9882 | 0.9377 | 2.946 | 11.41 | ✓ |

### vs_silhouette
| Metric | KA mean | Null mean | Cohen's d | z-score | Separates? |
|--------|---------|-----------|-----------|---------|------------|
| edge_pixel_ratio | 0.0108 | 0.0072 | 6.5206 | 25.25 | ✓ |
| fractal_dimension | 1.148 | 1.0352 | 6.7238 | 26.04 | ✓ |
| lines_detected | 3.5 | 3.2 | 0.3221 | 1.25 | ✗ |
| circles_detected | 0.3 | 0.0 | 0.9103 | 3.53 | ✓ |
| mirror_symmetry | 0.9969 | 0.9847 | 1.3601 | 5.27 | ✓ |
| rotational_symmetry_2fold | 0.9882 | 0.9646 | 4.1792 | 16.19 | ✓ |

## Verdict
**FIXTURE_ONLY | SHAPE_STRUCTURE**

All data is synthetic — no real IIIF or POWO images processed. Plants separate from controls on 23/24 metric×control pairs. Strong shape structure signal. noise: 6/6 metrics separate (|z|>2). scramble: 6/6 metrics separate (|z|>2). random_shapes: 6/6 metrics separate (|z|>2). silhouette: 5/6 metrics separate (|z|>2).

## Caveats
All results are on SYNTHETIC botanical images. Shape structure in synthetic plants vs null controls does NOT imply real plant pages contain similar structure. CCAT metrics may not transfer to ink-on-parchment botanical drawings. STRUCTURE != HERBAL ID / DECIPHERMENT. No real Beinecke IIIF or POWO data was processed (NEVER_ATTEMPTED).

### Forbidden phrases (logged so a code-reviewer catches drift)
- `identifies as`
- `is a known plant`
- `herbal identification`
- `species identified`
- `botanical match`
- `corresponds to`
- `this plant is`
- `use as medicine`
- `Voynich decoded`
- `translates to`
- `deciphered`
- `herbal remedy`
- `ethnobotanical`
- `plant species found`
- `aliens`
- `extraterrestrial botany`
- `healing property`
- `pharma application`

---
*G10++ — Synthetic botanical shape structure via CCAT. No real Voynich page images were processed.*
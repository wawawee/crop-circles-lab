# B4 — Julia Set circle extract (real aerial)

- Image: `data/images/julia_set_1996_tt_oh.jpg` (800×533)
- Params: adaptive binarize, open/close=1, min_circularity=0.35, min_radius=3.0
- **Recovered: 152 circles** vs claimed **151** (rel err ≈ 0.7%)
- Getty same params: 465 (over-segment — different contrast/compression; do not trust raw)
- Overlay: `outputs/julia_circles_overlay.jpg`
- JSON: `outputs/julia_circles.json`
- `is_true_julia_set`: **False** — classified as *julia-set-inspired log-spiral (single-resolution)*; radius-ratio CV ≈ 0.022 (very regular geometric shrink)

This is the first local CV hit that lands near the published circle count without Hough explosion.

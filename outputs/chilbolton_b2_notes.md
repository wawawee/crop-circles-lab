# B2 — Chilbolton message panel bbox + 73×23 grid

## Assets
- Manual bbox: `data/catalog/chilbolton_bbox.json` → `[22, 28, 275, 572]` on `chilbolton_message_2001_tt.jpg` (295×600)
- Overlay: `outputs/chilbolton_bbox_overlay.jpg`
- Bits: `outputs/chilbolton_bits_73x23.json` + `.png` (+ `_inv.png`)

## Checks
- Grid shape 73×23, semiprime OK
- Fill ≈ 0.50 (median threshold) — expected noise on web-res + tramline streaks
- Published reply diffs (from forensics, not pixels): Si=14, helix double→triple, height 176.5→100.8 cm

## Verdict
Manual bbox wired; sampler stretches photo aspect (~2.0) into 73×23. Cell recovery is a structural probe only — not a clean re-decode at this resolution.

# B3 — Edmonton 1999 ortho

- Source: `data/images/edmonton_1999.png` (600×324, oblique, caption overlays)
- Corners: `data/catalog/edmonton_corners.json` → mid box `[[180,90],[490,95],[505,265],[160,255]]` (TL,TR,BR,BL)
- Ortho: `data/images/edmonton_1999_ortho.png` (800×700)
- Stubble mask (ExG on ortho): `outputs/edmonton_1999_stubble_mask.png`
- Preview: `outputs/local_prep/edm_box_mid.jpg` / `edm_ortho_mid.jpg`
- CLI: `python tools/ccat/preprocess.py data/images/edmonton_1999.png --corners-json data/catalog/edmonton_corners.json --stubble`

Caveat: source is low-res + caption chrome; ortho is usable for layout/stubble fraction, not node biophysics.

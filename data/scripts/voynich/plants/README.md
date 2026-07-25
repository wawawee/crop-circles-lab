# Voynich plant-page assets (botany probe)

## What ships here

| Path | Role |
|------|------|
| `folios/` | Beinecke IIIF herbal folio sample (~16 plant pages, max-width 900) |
| `folios/manifest.json` | Folio IDs + IIIF source URLs + attribution |
| `fixtures/` | Synthetic plant-like silhouettes for offline CI / `--demo` |
| `manifest.json` | Merged folio IDs + local paths (updated by probe) |
| `botany_controls/` | Synthetic “real plant” silhouettes |
| `botany_controls/real/` | PD Thomé botanical plates (Wikimedia Commons) |

## Beinecke IIIF

- Catalog: https://collections.library.yale.edu/catalog/2002046
- Manifest: https://collections.library.yale.edu/manifests/2002046
- Image API (example): `https://collections.library.yale.edu/iiif/2/{imageId}/full/900,/0/default.jpg`
- Attribution: Beinecke Rare Book & Manuscript Library, Yale University — MS 408

Re-fetch a sample (rate-limit ~0.6s between requests):

```bash
# folios already present; probe auto-detects folios/ + botany_controls/real/
python tools/scripts/voynich_botany_probe.py
python tools/scripts/voynich_botany_probe.py --demo   # synthetic only
```

## Stance

Shape similarity ≠ species ID ≠ decipherment. STRUCTURE ≠ MESSAGE.

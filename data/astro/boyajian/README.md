# Boyajian's Star — TESS Epoch-Fold Data (G20)

## Target

- **Name:** Boyajian's Star / Tabby's Star / KIC 8462852 / TIC 272172248
- **Constellation:** Cygnus
- **V mag:** ~11.7
- **Spectral type:** F3 V

## TESS lightcurve — fetch instructions

Use `lightkurve` + `astroquery.mast` to download TESS SPOC lightcurves:

```python
import lightkurve as lk
# Sectors 14-16 (2019), Sector 55 (2022+)
lc = lk.search_lightcurve("TIC 272172248", mission="TESS").download_all()
# Or specific sector:
lc = lk.search_lightcurve("TIC 272172248", mission="TESS",
                          sector=14).download()
```

**Manual download:** <https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html>
Search: `TIC 272172248`

Data products in this directory:

| File | Description |
|------|-------------|
| `README.md` | This file — provenance, fetch instructions, references |
| `boyajian_dip_times_fixture.json` | Synthetic dip timestamps emulating Kepler-era dip structure; used by known-answer path |
| `boyajian_template_lc.csv` | Optional: small fixture TESS-like lightcurve snippet if MAST is unreachable |

## Dips

Kepler (2009–2013) observed aperiodic dimming events up to ~22% depth at:
- Day ~800 (D800)
- Day ~1200–1220 complex
- Day ~1500–1590 complex (D1519, D1568)

TESS (2019+) observed additional shallow dips (~1–3%) at sector-specific timestamps. Broadband dimming across years is also observed (Meng+2016).

## References

- **Boyajian, T. S., et al. (2016).** "Planet Hunters IX. KIC 8462852 – where's the flux?" *MNRAS* 457(4): 3988–4004. doi:10.1093/mnras/stw218
- **Boyajian, T. S., et al. (2018).** "The First Post-Kepler Brightness Dips of KIC 8462852." *ApJ* 853(1): L8. doi:10.3847/2041-8213/aaaae9
- **Meng, H. Y. A., et al. (2017).** "Extinction of KIC 8462852 from 1890 to 2015." *ApJ* 847(2): 131. doi:10.3847/1538-4357/aa889c

## Stance

Structure ≠ message. Aperiodic dips at Boyajian's Star are astrophysical phenomena — most likely circumstellar dust (exocomets / debris) — not megastructures. No dip structure, even if periodic, would constitute evidence of Dyson/ET engineering without independent electromagnetic or infrared signatures.

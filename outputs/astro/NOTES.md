# N4 astro_probe — Opencode landing notes (2026-07-25)

## Landed
- Backend priority: **skyfield** (JPL DE441) > astropy > pure-Python fallback
- Sites: Göbekli, Stonehenge, Giza, Chichén — solstice/eq, star rise, crop lunar from `formations.csv`
- Random site/date controls → reported verdict: *no separation from random*
- Output: `outputs/astro/run.json`

## Ephemeris (DO NOT commit)
`de441.bsp` is ~3.3 GB and **gitignored** (`*.bsp`). Download once into repo root or `~/.skyfield/`:

```bash
# Skyfield will fetch if missing, or:
python -c "from skyfield.api import Loader; Loader('.').download('de441.bsp')"
```

Optional lighter: `de421.bsp` for modern-only runs (not deep BCE).

## Honest caveats (Captain review)
1. **Deep BCE solstice timestamps look calendar-wrong** in `run.json` (e.g. “mar equinox” in October for year −9600). Sunrise azimuths for fixed civil dates (−9600-06-21) are still useful; **do not treat ancient equinox *calendar labels* as authoritative** until the ecliptic-longitude root finder is validated against a known BCE almanac.
2. Random-control “hit” definition (azimuth near 50°/60°/65°) is a **weak / possibly vacuous** proxy — both real and random scored 0 hits. Verdict “no signal” is therefore **conservative but not a strong null test** of monument alignments. Next improvement: cite documented axis bearings per site, then test Δaz vs random bearings.
3. Horizon DEM via rasterio/elevation is optional; flat-horizon fallback is fine for v1.

## Stance
Structure / geometry facts only. No alien or divine claims.

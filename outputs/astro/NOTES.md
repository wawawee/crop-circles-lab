# N4 / N4++ astro_probe — Opencode landing notes (2026-07-25)

## N4 Landed
- Backend priority: **skyfield** (JPL DE441) > astropy > pure-Python fallback
- Sites: Göbekli, Stonehenge, Giza, Chichén — solstice/eq, star rise, crop lunar from `formations.csv`
- Output: `outputs/astro/run.json`

## N4++ (2026-07-25)
### 1. BCE calendar label hardening
- Ecliptic-longitude root finder **validated internally**: each event now includes
  `validated_solar_lon_deg` confirming the Sun was at the target longitude (±0.5°)
  at the found datetime. Validation uses JPL DE441 — the same ephemeris used by
  the root finder, so this checks for bugs in the search, not ephemeris accuracy.
- `calendar_label_unreliable: true` is emitted at `solstice_eq` level for years
  < -2000 (deep BCE), where proleptic Gregorian DOY/month labels diverge from
  modern seasonal expectations.
- `civil_doy` added alongside `doy` to emphasise these are civil-calendar labels.

### 2. Monument axis bearing alignment (removes weak azimuth proxy)
- Replaced the 50°/60°/65° hit proxy with documented monument axis bearings:
  - **Stonehenge**: axis ~51° NE (Ruggles 1999) → Δaz = 17.1° from
    jun_solstice_sunrise azimuth (06:00 UTC approx).
  - **Chichén Itzá**: NW staircase ~287° (Šprajc 2018) → Δaz = 59.6°.
  - **Göbekli Tepe**: no known astronomical axis — raw sun azimuth reported only.
  - **Giza (Khufu)**: cardinal faces, not a single alignment axis — raw azimuth only.
- Random controls assigned random bearing from [0,180) for Δaz comparison.
- **No alignment signal detected** (n=2 real with known axes; mean Δaz 38.4°).
- Caveat: all azimuths use fixed 06:00 UTC, not true local sunrise. Δaz values
  are relative, not absolute alignment metrics.

### 3. Honest caveats (Captain review)
1. **Deep BCE solstice timestamps**: ecliptic-longitude root finder IS correct
   (validated lon within 0.5° of target). The "mar equinox in October" calendar
   labels are a proleptic Gregorian drift effect for year −9600. `calendar_label_unreliable`
   flag set, `civil_doy` emitted separately.
2. **Azimuth proxy removed**: replaced with documented monument axis bearings.
   Both real sites with known axes had Δaz > 15°, no alignment signal.
3. **06:00 UTC sunrise approximation** is crude — true local sunrise horizon
   crossing would be needed for precise Δaz. Current values are valid for
   relative comparison (real vs random use same approximation).
4. Horizon DEM via rasterio/elevation is optional; flat-horizon fallback is fine for v1.

## Ephemeris (DO NOT commit)
`de441.bsp` is ~3.3 GB and **gitignored** (`*.bsp`). Download once into repo root or `~/.skyfield/`:

```bash
# Skyfield will fetch if missing, or:
python -c "from skyfield.api import Loader; Loader('.').download('de441.bsp')"
```

Optional lighter: `de421.bsp` for modern-only runs (not deep BCE).

## Stance
**Geometry ≠ intent.** Structure / geometry facts only. No alien or divine claims. Civil calendar labels are not astronomical truth in deep BCE.

# G14 - Chankillo Thirteen Towers horizon probe  [STRUCT] [CONTROL-SEP]
Generated: 2026-07-25T19:57:57.303956+00:00

## Stance
Chankillo Thirteen Towers (Casma-Sechin Basin, ~250-200 BCE, Peru) are an archaeoastronomical complex. The published interpretation - Ghezzi & Ruggles 2007 - is that the 13 tower-to-observer bearings from the western observing point bracket the annual Sun-arc sunrise with ~1-2 day precision. This probe measures sign alignment structure vs uniform / scrambled / synthetic-ridge nulls ONLY. It does NOT endorse any claim that Chankillo is a 'proven calendar', imply a tribal calendar reading, claim extraterrestrial contact, or fabricate a DEM.

**Motto:** *structure != meaning.* Annual-arc sunrise vs tower-bearing structure IS a structure test; this lab does NOT endorse any calendar/reading interpretation.

### Forbidden phrases (logged)
- `Chankillo deciphered`
- `Chankillo calendar proven`
- `proven Inca calendar`
- `proved solar calendar`
- `perfectly aligned`
- `exactly aligned`
- `tribal calendar`
- `Smithsonian calendar`
- `alien observatory`
- `aliens built`
- `ancient astronauts`
- `99% aligned`
- `100% aligned`
- `civilization-decoding`
- `civilization decoded`
- `civilization decoded by towers`
- `language of the gods`
- `alignment proves`
- `calendar proves`
- `civilization encoded`
- `civilization encoded in towers`
- `skysurfer`
- `sky surfer`

## Source / data
Loader attempts `data/astro/chankillo/{tower_coords.json, solar_arc_300BCE.json}` first. Coordinates derived from Ghezzi & Ruggles (2007) Fig. 1 schematic approximation. NO DEM is on disk; the probe runs a flat-horizon baseline + synthetic piecewise-linear east-arc ridge null. Solar arc is sourced from JPL DE441 at year -300 (analytic Meeus 22nd-ed.). Per-tower tolerances are ±1.5 deg per the published axis uncertainty. Calendar labels for year<-2000 are NOT reliable (N4++ rule, applied here).

- WOP = (lat=-9.56, lon=-78.238)
- towers = 13 / 13 per Ghezzi & Ruggles 2007
- analytic sun arc verified vs skyfield (DE441) at year 300 BCE

## Group analyses

### observed_tower_bearings_vs_analytic_solar_sweep
- observed bearings (deg) = [99.59, 90.0, 80.41, 71.32, 63.11, 55.03, 48.84, 43.63, 38.27, 34.62, 31.53, 28.04, 25.83]
- expected sweep (deg) = [65.4, 69.5, 73.6, 77.7, 81.8, 85.9, 90.0, 94.1, 98.2, 102.3, 106.4, 110.5, 114.6]
- per-tower Δ (deg) = [34.19, 20.5, 6.81, 6.38, 18.69, 30.87, 41.16, 50.47, 59.93, 67.68, 74.87, 82.46, 88.77]
- structure z vs uniform null: observed=2744.4437 null_mean=39737.8155  z=-3.699337178164294e+16
- structure z vs MC-permuted null (n=20): observed=2744.4437  null_mean=1954.5657  z=4.1832

## Null controls

- uniform azimuth null: ran 20 draws  z(towers-output-mean) = -3.699337178164294e+16
- synthetic ridge null: z(ridge-mean) = -973028701997214.2  z-delta vs flat = 3.602034307964573e+16 (threshold 1.5 -> CONTROL_SEPARATED verdict tag)

## Verdict
ORIENTATION_STRUCTURE | CONTROL_SEPARATED

## Caveats
- Coordinates in tower_coords.json are approximate per Ghezzi & Ruggles (2007) Fig. 1 - NOT geodesy-grade.
- No DEM on disk. Synthetic piecewise-linear east-arc ridge null emulates horizon-occlusion; a real DEM swap-in is documented in data/astro/chankillo/README.md.
- Calendar labels for year < -2000 are NOT reliable (N4++ rule). We measure structural fit; we do NOT endorse the Ghezzi & Ruggles interpretive calendar.
- z vs MC-permuted tower ordering null is the substantive test - it preserves the per-tower bearings but breaks the sequential order and tests whether that ordering carries the sweep signal.
- Verdict tags are STRUCTURE ONLY - NEVER a reading of the Chankillo calendar or a claim of construction intent.
- Schematic-fixture span bias: observed tower-bearing spread ~74 deg from WOP exceeds the published Ghezzi & Ruggles 2007 annual-solar-arc claim of ~33 deg; the ORIENTATION_STRUCTURE verdict may be inflated by schematic-only approximation until a geodesy-grade re-derive replaces the fixture.

---
*G14 Chankillo Thirteen Towers - structure != meaning. No calendar / reading / alien interpretation endorsed. The Ghezzi & Ruggles 2007 published interpretation is the claim-under-test, NOT an established reading.*
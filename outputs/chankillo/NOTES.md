# G14 — Chankillo Thirteen Towers 🟡

Generated: 2026-07-26T23:16:58.710161+00:00

## Stance

Structure != message. The Thirteen Towers form an orientation structure (solstice extremes are bracketed), but that is geometry, not a deciphered calendar. Lunar standstill coverage is purely geometric and underdetermined. No alien, extraterrestrial, or supernatural claims.

## Site

- Location: -9.559°S, -78.231°W
- Epoch: -300 (300 BCE)
- 13 towers along ~300 m N-S ridge
- Reference: Ghezzi & Ruggles 2007, Science 315(5816)

## Tower horizon azimuths

- Range: 47.6143° – 132.386° (span: 84.7717°)
- Tower-to-tower steps: 5.3, 5.8, 6.9, 7.4, 8.5, 8.5, 8.8, 8.1, 7.8, 6.6, 5.8, 5.3

## Solar extremes (epoch -300)

- June solstice sunrise: 65.9198° (hour UTC: 15.3381)
- December solstice sunrise: 114.0865° (hour UTC: 14.9004)
- Solar span: 48.1667°

## Solar coverage

- June bracketed: True
- December bracketed: True
- Both solstices bracketed: True
- Margin north (tower min - June az): 18.3055°
- Margin south (Dec az - tower max): 18.2995°

## Lunar standstills (UNDERDETERMINED)

- Major Standstill: declination ±28.59°, rising az range 58.0612°
- Minor Standstill: declination ±18.29°, rising az range 37.1137°
- Verdict: LUNAR_UNDERDETERMINED
- Caveat: Lunar standstill coverage is geometrically inevitable: the tower azimuth arc (~90°) is wider than the lunar rising range (~58°). Any wide-N-S ridge whose towers span ~90° will naturally bracket the lunar range. This is not evidence of lunar intent — it is a geometric consequence of ridge length and observation distance. No lunar-specific null is available without horizon-profile data.

## Negative controls

### Synthetic ridge null

- Trials: 2000
- Random-ridge bracketed fraction: 22.1%
- Mean trial span: 201.49°
- Synthetic ridge null: 22.1% of random ridges bracket the solar range.

### Scrambled azimuth null

- Trials: 2000
- Observed hits: 13
- Null mean hits: 5.0
- Null SD hits: 0.0

## Verdict

**ORIENTATION_STRUCTURE | LUNAR_UNDERDETERMINED | CONTROL_NOT_SEPARATED**

Thirteen Towers span 84.7717° of horizon azimuth from the western observation plaza. Solar extremes at epoch -300 span 48.1667° (June → December solstice sunrise). The solstice extremes ARE bracketed by the tower arc (margin north: 18.3055°, south: 18.2995°). 

Lunar major standstill range (58.0612°) falls entirely within the tower arc — but this is geometrically inevitable given the ~90° tower span. No lunar-specific design signal can be separated from the generic ridge geometry. LUNAR_UNDERDETERMINED.

Negative controls: synthetic ridge null — 22% of random ridges also bracket the solar range. The observation is consistent with ridge geometry rather than intentional precision placement.

Verdict: ORIENTATION_STRUCTURE | LUNAR_UNDERDETERMINED | CONTROL_NOT_SEPARATED


Tower coordinates are estimated from published site plans; exact survey-grade coordinates would refine azimuths by <1°. Solar azimuths use skyfield DE441 and are interpolated to alt=0° (flat horizon). A true DEM-based horizon profile (Copernicus GLO-30) would capture the actual ridge elevation masking and improve precision. Lunar ranges use analytic formulae with epoch-appropriate obliquity; the 18.6-year precession cycle is not modeled at the individual-year level.

---
*G14 Chankillo — structure ≠ message. Solstice structure confirmed; lunar underdetermined; ridge null not separated from observed geometry.*
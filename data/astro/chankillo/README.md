# Chankillo Thirteen Towers — Horizon Solar/Lunar Geometry

## Site

- **Location:** 9°33′36″S, 78°13′48″W (approximate), Ancash Region, Peru
- **Epoch:** ~300 BCE (construction period, Late Formative)
- **Monument:** 13 rectangular stone towers along a 300 m N-S ridge crest; western and eastern observation plazas
- **Discovery:** Ghezzi & Ruggles (2007) demonstrated the towers bracket the solar rising/setting arc over the seasonal year

## Data files

| File | Description |
|------|-------------|
| `README.md` | This file — provenance, coordinates, references |
| `tower_coords.json` | Approximate WGS84 coordinates for the 13 towers + western observation point |
| `solar_arc_300BCE.json` | Expected Sun-arc solstice/equinox azimuths at ~300 BCE (analytic + JPL DE441) |

## Tower coordinates

Approximate coordinates along the ridge (south to north), estimated from Ghezzi & Ruggles 2007 site plan. All towers are on a N–S ridge ≈0.0015° east of the western observation plaza.

| Tower | Latitude (°S) | Longitude (°W) | Estimated azimuth from obs. point |
|-------|---------------|----------------|-----------------------------------|
| T1 (southmost) | −9.56035 | −78.2295 | ~136° SE |
| T2 | −9.56012 | −78.2295 | ~130° SE |
| T3 | −9.55990 | −78.2295 | ~125° SE |
| T4 | −9.55968 | −78.2295 | ~119° ESE |
| T5 | −9.55945 | −78.2295 | ~114° ESE |
| T6 | −9.55923 | −78.2295 | ~108° ESE |
| T7 (center) | −9.55900 | −78.2295 | ~102° ESE |
| T8 | −9.55878 | −78.2295 | ~96° E |
| T9 | −9.55855 | −78.2295 | ~90° E |
| T10 | −9.55833 | −78.2295 | ~83° E |
| T11 | −9.55810 | −78.2295 | ~77° ENE |
| T12 | −9.55788 | −78.2295 | ~70° ENE |
| T13 (northmost) | −9.55765 | −78.2295 | ~64° ENE |

Observation point (western plaza): −9.559° lat, −78.231° lon.

## DEM source

Copernicus GLO-30 (30 m resolution) recommended for horizon-profile analysis. Available via:

- OpenTopography: <https://portal.opentopography.org/datasets>
- Copernicus: <https://dataspace.copernicus.eu/>

The probe currently runs a flat-horizon baseline AND a synthetic ridge null; a real DEM tile can be dropped into `dem.tif` (gitignored) for future refinement.

## References

- **Ghezzi, I. & Ruggles, C. (2007).** "Chankillo: A 2300-Year-Old Solar Observatory in Coastal Peru." *Science* 315(5816): 1239–1243. doi:10.1126/science.1136415
- **Ghezzi, I. (2006).** "Nuevas evidencias sobre el observatorio solar de Chankillo." *Arqueología y Sociedad* 17: 9–30.
- **Ruggles, C. (2014).** *Handbook of Archaeoastronomy and Ethnoastronomy*. Springer. (Chankillo: pp. 823–832)

## Stance

Structure ≠ message. The towers form a solar observatory-structure (the solstice extremes ARE bracketed), but that does not constitute calendar decipherment or intentional alignment at the singular-tower level. Lunar standstill coverage is purely geometric — the tower arc is wide enough to contain any rising body within ±30° declination.

The published interpretation (Ghezzi & Ruggles 2007) is the claim-under-test, not a verified reading. No alien, extraterrestrial, or supernatural claims.

# Göbekli Tepe × Taurid — Site Geometry & Radiant Data

## Site

- **Location:** 37.2231°N, 38.9223°E, 760 m ASL
- **Epoch:** ~9 600 BCE (Enclosure D construction)
- **Enclosure D:** ~20 m diameter circle of 12 T-shaped limestone pillars linked by bench walls, plus 2 central T-pillars
- **Pillar 43 (Vulture Stone):** NW quadrant, ~320°–330° azimuth from enclosure centre

## Pillar orientations

Each pillar in Enclosure D faces a discernible azimuth (the direction its "face" — the broad flat side of the T — points). See `pillars.json` for the full catalogue.

| Pillar | Azimuth (°) | Carving theme | Source |
|--------|-------------|---------------|--------|
| P43 (Vulture Stone) | 325 | vulture, scorpion, disk, fox | Schmidt 2006; Sweatman & Tsikritsis 2017 |
| P18 | 215 | fox | Peters & Schmidt 2004 |
| P27 | 45 | aurochs | Schmidt 2006 |
| P30 | 135 | crane/bird | Peters & Schmidt 2004 |
| P31 | 225 | snake | Schmidt 2006 |
| P32 | 180 | quadruped | Notroff et al. 2014 |
| P33 | 270 | fox/wild ass | Schmidt 2006 |
| P34 | 90 | wild ass | Schmidt 2006 |
| P35 | 315 | bird | Notroff et al. 2014 |
| P36 | 35 | aurochs | Schmidt 2006 |
| P37 | 135 | crane | Peters & Schmidt 2004 |
| P38 | 255 | fox | Schmidt 2006 |
| Central E | 0 | — | — |
| Central W | 180 | — | — |

## Taurid radiant

The Taurid meteor complex radiates from the constellation Taurus. The modern radiant is split into Northern and Southern branches, converging precessionally at deep BCE.

| Name | RA (J2000, h) | Dec (J2000, °) | Association |
|------|-------------|---------------|-------------|
| Taurid complex centre | 3.50 | +15.0 | 2P/Encke + debris stream |
| Northern Taurids | 3.87 | +22.0 | Nodal separation |
| Southern Taurids | 3.53 | +14.0 | Sibling stream |

At epoch –9 600 BCE (precessed via Skyfield DE441), these coordinates shift substantially. The analysis in `goebekli_taurid.py` precesses the radiant centre to the epoch year and compares pillar face azimuths against the radiant set-point direction.

## Negative controls

1. **Random-azimuth null** — each pillar's reported azimuth replaced by a uniform random draw from [0°, 360°). Same Taurid alignment analysis run 10 000×.
2. **Scrambled-date null** — pillar azimuths shuffled across the epoch-year distribution (Monte Carlo sampling of dates from 11 000–7 000 BCE). Same analysis run 10 000×.
3. **No claim** escapes the control band without corroborating evidence.

## References

- Peters, J. & Schmidt, K. (2004). "Animals in the symbolic world of Pre-Pottery Neolithic Göbekli Tepe." *Paléorient* 30(1): 89–104.
- Schmidt, K. (2006). *Sie bauten die ersten Tempel*. C.H. Beck.
- Sweatman, M.B. & Tsikritsis, D. (2017). "Decoding Göbekli Tepe with archaeoastronomy." *Mediterranean Archaeology and Archaeometry* 17(1): 233–250.
- Notroff, J., Dietrich, O. & Schmidt, K. (2014). "Building monuments — creating a landscape." In *Defining the Sacred*, Oxbow Books.
- Clube, S.V.M. & Napier, W.M. (1984). "The microstructure of terrestrial catastrophism." *MNRAS* 211: 953–968. (Taurid complex age / YDB hypothesis)

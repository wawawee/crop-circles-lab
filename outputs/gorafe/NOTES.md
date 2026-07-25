# G7 — Gorafe megalith landscape  🟢

Generated: 2026-07-25T06:30:10.260462+00:00

## Dataset

- Source: Cabrero et al. 2023, CC BY 4.0 — 10.5281/zenodo.10049759
- 151 dolmens, 108 with corridor orientation
- Bounding box: {'lon_min': -3.111, 'lon_max': -2.9338, 'lat_min': 37.3881, 'lat_max': 37.5118}

## Corridor orientation

- Circular mean: 117.2°
- Distribution: {'N': 3, 'NE': 7, 'E': 34, 'SE': 51, 'S': 15}
- Rayleigh test: R=0.8213, z=72.8493, p=0.0
- Uniform-random control: observed R vs uniform z=17.773

## Spatial clustering

- Mean NND: 0.1179 km
- vs uniform random: z=-19.492

## Solar alignment (epoch -3000)

- jun: 78.52° alt 25.72°
- dec: 124.35° alt 3.75°
- mar: 97.94° alt 8.55°
- sep: 98.32° alt 10.43°
- corridor mean 117° vs jun solstice 79° (Δ=39°)
- corridor mean 117° vs dec solstice 124° (Δ=7°)

## Verdict

**ORIENTATION_STRUCTURE | SPATIAL_CLUSTER_UNDERDETERMINED | CONTROL_SEPARATED**

Corridor orientations are strongly non-uniform (E/SE dominant, 85/108 ≈ 79%), which is typical for Mediterranean megalithic corridors facing the rising sun.  The corridor circular mean (117°) is closer to the December solstice sunrise (124°) than the June solstice (79°), but this is also consistent with a generic SE bias — astronomical intent is underdetermined.  The uniform-random control confirms the orientation structure is real (z vs uniform = 17.8), but the interpretation as intentional astronomical alignment requires independent evidence.  Spatial NND is lower than uniform-rectangle expectation (z < -10), but this is expected for a river-valley survey — the rectangular bbox null includes areas of unsuitable terrain.  Verdict: ORIENTATION_STRUCTURE, astronomical alignment UNDERDETERMINED.


Corridor orientation is only measurable for ~108/151 tombs (those with preserved corridors).  Solar azimuths computed for epoch -3000 with ±1° ephemeris precision; precession over the megalithic period (~4000–2000 BCE) shifts solstice azimuth by <1°.  The 'alignment' comparison is illustrative, not a claim.

---
*G7 Gorafe — structure ≠ message. Orientation structure confirmed; astronomical intent underdetermined.*
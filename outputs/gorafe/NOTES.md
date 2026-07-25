# G7 — Gorafe megalith landscape 🟢

Generated: 2026-07-25T10:49:48.563361+00:00

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
- vs convex-hull (valley-aware) null: z=-15.572
  (10 hull vertices)
- vs uniform-rectangle null (reference, known-biased): z=-19.492

## Solar alignment (epoch -3000)

- jun: 78.52° alt 25.72°
- dec: 124.35° alt 3.75°
- mar: 97.94° alt 8.55°
- sep: 98.32° alt 10.43°
- corridor mean 117° vs jun solstice 79° (Δ=39°)
- corridor mean 117° vs dec solstice 124° (Δ=7°)

## G7++ Per-tomb sunrise alignment

- N=108 tombs with corridor + coordinates
- Epoch: -3000
  - jun_solstice: mean Δ=60.48°, median Δ=60.79°, hit@15°=7%, z_vs_uniform=-3.065
  - dec_solstice: mean Δ=27.62°, median Δ=20.87°, hit@15°=40%, z_vs_uniform=6.996
  - mar_equinox: mean Δ=36.58°, median Δ=34.19°, hit@15°=21%, z_vs_uniform=3.387
- Best alignment: dec_solstice (mean Δ=27.62°, hit@15°=40%)

## Verdict

**ORIENTATION_STRUCTURE | SPATIAL_CLUSTER_UNDERDETERMINED | CONTROL_SEPARATED | PER_TOMB_UNDERDETERMINED**

Corridor orientations are strongly non-uniform (E/SE dominant, 85/108 ≈ 79%), typical for Mediterranean megalithic corridors facing the rising sun.

Rayleigh: R=0.8213, z=72.85, p≈0 — confirmed orientation structure (z vs uniform circular = 17.8).

--- G7++ per-tomb solar alignment ---
Favourites: Dec solstice — mean Δ=27.62°, median=20.87°, hit rate @15°=40% (108/108 tombs).  Jun solstice: mean Δ=60.48°.
Uniform-bearing null (1000×) vs Dec: null mean Δ=50.4°, z=6.996.  The Dec solstice alignment separates from random orientation (z≈7), but ~60% of tombs miss the 15° window — consistent with a generic SE bias toward the winter sunrise arc rather than precision targeting.

--- G7++ valley-aware spatial null ---
Convex hull NND: z=-15.57 (vs -19.49 for rectangular bbox).  The convex hull constrains null points to the river-valley corridor traced by the tombs themselves.  z is still negative (tomb spacing denser than hull-uniform expectation) but less extreme than the rectangular null which inflated the bias by sampling high plateau.
Remaining: slope/aspect filtering within the hull would need a DEM.

Verdict: ORIENTATION_STRUCTURE confirmed.  Per-tomb alignment favours Dec solstice (mean Δ=27.62°, z vs uniform = 6.996), but this is largely driven by the SE corridor bias — PER_TOMB_UNDERDETERMINED.  Convex hull spatial null reduces the exaggerated clustering signal of the rectangular bbox; spatial cluster remains UNDERDETERMINED.


Corridor orientation is only measurable for ~108/151 tombs (those with preserved corridors).  Solar azimuths computed for epoch -3000 with ±1° ephemeris precision; precession over the megalithic period (~4000–2000 BCE) shifts solstice azimuth by <1°.  The 'alignment' comparison is illustrative, not a claim.  Convex hull null improves on the rectangular bbox but still does not model micro-topographic suitability (slope, aspect) — a true valley-aware null would require a DEM.

---
*G7++ Gorafe — structure ≠ message. Orientation structure confirmed; null models hardened; astronomical intent still underdetermined.*
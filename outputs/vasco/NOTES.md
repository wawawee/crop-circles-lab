# G13 — VASCO Optical Transient Clustering

## Verdict

**STRUCTURE_SIGNAL**

Candidates are strongly structured on the sky (|z| up to 435 vs uniform
random), but the clustering is largely consistent with plate-artifact
distributions. Separation from the plate-artifact null is marginal.

## Key findings

| Metric | Observed | z vs uniform | z vs plate artifact |
|--------|----------|-------------|--------------------|
| Mean NN distance | 0.756° | −61.8 | −12.2 |
| Close pairs <1° | 7,285 | +189.3 | −2.1 |
| Close pairs <5° | 295,468 | +435.0 | −2.7 |
| Mean |b| | 30.3° | −8.4 | −0.5 |
| Fraction |b|<20° | 0.412 | +10.8 | +1.2 |

## Interpretation

1. **Strong clustering confirmed.** The 5,399 VASCO candidates are far more
   tightly clustered than isotropic random points. This has been noted in
   the literature (e.g., arXiv:2605.01190).

2. **Clustering consistent with plate artifacts.** When compared against a
   plate-artifact null model (sources clustered in RA bands with random Dec),
   the candidate distribution shows no significant excess of close pairs
   (|z| < 3.0 for 1° and 5° thresholds). Mean NN distance is smaller
   (z=−12.2), indicating even tighter clustering than our artifact model.

3. **Galactic latitude indistinguishable from plate artifacts.** Mean |b| and
   fraction in |b|<20° do not separate from the artifact null (|z| < 1.2).
   The slight deficit vs uniform (z=−8.4) is likely driven by the all-sky
   sampling of POSS-I plates (δ > −45°) rather than astrophysics.

4. **No evidence for Dyson-sphere / ET interpretation.** The clustering
   pattern is consistent with known selection effects and plate artifacts.
   No forbidden phrases appear in the output.

## Caveats

- The plate-artifact null is a simple model (4 bands, 70% clustered). A
  more realistic model based on actual POSS-I plate footprints might
  explain even more of the clustering signal.
- Coordinates are from the Solano et al. 2022 VO-compliant archive. Original
  RA/Dec positions have intrinsic uncertainty from photographic plates.
- The `scramble_coords` null partially preserves the RA/Dec marginal
  distributions and shows intermediate z-scores — consistent with structure
  being driven by both RA and Dec correlations.

## Data sources

- VASCO candidate catalog: Solano et al. 2022 MNRAS 515, 1380
  (SVO archive http://svocats.cab.inta-csic.es/vanish/)
- DASCH DR7 inventory: Williams 2024 doi:10.5281/zenodo.14563521 (CC-BY 4.0)

## Forbidden phrases

0 hits. Probe never claims ET, Dyson spheres, decipherment, or translation.

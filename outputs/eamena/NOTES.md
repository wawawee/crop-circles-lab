# G18 — EAMENA ley-line null  [NO-CLUSTER] [NO-LEYS] [CTRL-!SEP] [FPR-CAL]
*Generated: 2026-07-25T20:45:43.588240+00:00*

## Stance
EAMENA (Endangered Archaeology in the Middle East and North Africa) records ~338,000 archaeological sites. This probe tests the fringe claim that 3+ sites on a straight line constitute a 'ley line.' We measure spatial structure (collinear-triple frequency) relative to Complete Spatial Randomness (CSR) and scrambled-coordinate nulls. We do NOT endorse ley-line mysticism, ancient-highway claims, or any 'Earth energy' interpretation. The honest prior is NO_SIGNAL — spatial clustering in archaeological site distributions is well-known to follow environmental settlement patterns (water, soil, trade routes), not intentional geometric networks.

**Motto:** *structure != meaning.* Ley-line/collinear-triple frequency is a STRUCTURE test; this lab does NOT endorse fringe ley-line or Earth-energy interpretations.

### Forbidden phrases (logged)
- `ancient highways`
- `ET corridors`
- `proves ley network`
- `ley line network`
- `ley network confirmed`
- `ancient alien roads`
- `energy lines`
- `earth energy grid`
- `earth energy lines`
- `global grid`
- `planetary grid`
- `sacred geometry network`
- `ley system`
- `ley alignment proves`
- `ley discovered`
- `alien ley`
- `99% ley`
- `ley verified`
- `ley confirmed`
- `ancient aliens`
- `alien architectures`

## Source / data
- Source: `synthetic_csr`
- Distribution: csr
- N sites: 100
- Bounding box: [34.0, 30.0, 35.5, 32.5]
- **NOTE:** Synthetic CSR data — ground truth is NO SIGNAL

## Nearest-neighbour (Clark-Evans)
- Observed mean NN: 10.086 km
- CSR null mean NN: 10.2881 km
- Clark-Evans R: 0.9804
- z vs CSR: -0.34
- Density: 0.00261 sites/km²

## Ley-line (collinear triple) FPR analysis
- Tolerance corridor: 0.5 km
- Pairs evaluated: 200
- Observed collinear triples per pair: 0.545

### Scrambled-coordinate null
- Mean: 0.561552
- SD: 0.058326
- z: -0.284
- Empirical FPR: 0.6207 (<0.05 = beats null)

### CSR Monte-Carlo null
- Mean: 0.556034
- SD: 0.064131
- z: -0.172
- Empirical FPR: 0.6207 (<0.05 = beats null)

## Verdict
**NO_SPATIAL_SIGNAL | NO_LEY_SIGNAL | CONTROL_NOT_SEPARATED | FPR_CALIBRATED**

## Interpretation
**Ground truth:** SYNTHETIC CSR (ground truth: NO SIGNAL by construction)

CSR synthetic data: 100 points uniformly distributed in bounding box.
Clark-Evans R=0.980, z=-0.34 — consistent with CSR expectation.

**Ley-line (collinear triple) FPR calibration:**
- Scrambled-coord null: empirical FPR = 0.6207 (threshold 0.05)
- CSR Monte-Carlo null: empirical FPR = 0.6207 (threshold 0.05)
- Observed collinear triples per pair: 0.545000

For CSR synthetic data, both null FPRs should be >> 0.05,
confirming that 'ley line' detection on random points produces
chance-expected false positives.

**FPR Calibration result:** NO_SIGNAL — 'ley line' alignments
in CSR data do not exceed null expectation. The empirical FPR
is consistent with the nominal α=0.05 threshold.

## Caveats
- Synthetic CSR data — ground truth is NO SIGNAL by construction. Results for real EAMENA data may differ.
- Collinear triple detection is sampled (not exhaustive), capped at 200 pairs for performance.
- Collinearity tolerance of 0.5 km is arbitrary; different tolerances produce different FPRs.
- Ley-line claims typically cherry-pick sites — this probe uses ALL sites in the dataset without selection bias.
- Scrambled-coordinate null preserves the 1D marginal distributions but breaks spatial structure — it is a weaker null than CSR.
- CSR Monte-Carlo null assumes uniform intensity across the bounding box, which is almost never true for real archaeology (inhomogeneous Poisson process would be more realistic).
- For real EAMENA data, environmental covariates (rivers, soils, topography) must be modeled as a Cox process to avoid conflating settlement pattern with 'ley' signal.
- The EAMENA full 338k-site corpus is BLOCKED from programmatic access; this probe uses synthetic CSR data as an FPR calibration benchmark. See data/geo/eamena/README.md.

---
*G18 EAMENA ley-line null — structure != meaning. No fringe ley-line / Earth-energy / alien interpretation endorsed. The collinear-triple FPR calibration is a spatial statistics exercise, not a claim about intentional geometric networks.*
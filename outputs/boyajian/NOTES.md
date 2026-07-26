# G20 --- Boyajian's Star TESS Epoch-Fold

Generated: 2026-07-26T23:37:25.070058+00:00

## Stance

Structure != message. Aperiodic dips at Boyajian's Star are astrophysical phenomena (circumstellar dust / exocomets / debris), not artifacts of exogenous construction. No dip structure, even if periodic, constitutes evidence of artificial engineering without independent electromagnetic or infrared signatures.

## Target

- TIC 272172248 (KIC 8462852 / Boyajian's Star)
- Constellation: Cygnus
- V mag: ~11.7, Spectral type: F3 V

## Fixture

- Source: Kepler
- Synthetic: True
- Planted period: 24.5 days
- N dip timestamps: 30

### References

- Boyajian et al. 2016, MNRAS 457(4): 3988-4004
- Boyajian et al. 2018, ApJ 853(1): L8
- Meng et al. 2017, ApJ 847(2): 131

## Known-Answer Path

- Recovery pass: True
- Planted period: 24.5 days
- Recovered period: 24.415 days
- Recovered Z2: 59.96230478993004
- Recovery error: 0.08500000000000085 days
- p-value: 9.535664306559391e-14

## Negative Controls

### Quiet-star null (uniform random times)

- Trials: 200
- Null Z2 mean: 7.779507218540284
- Null Z2 95th percentile: 13.280685064234627
- Null Z2 max: 20.925320187691845
- Note: Uniform-random dip times with no planted period.

### Random-phase null (independent uniform offsets)

- Trials: 200
- Null Z2 mean: 7.60644648352012
- Null Z2 95th percentile: 11.49363773933782
- Null Z2 max: 16.08369645384447
- Note: Independent uniform phase offsets U[-P/2, P/2] added to each dip time.

## Real TESS Data

- Not available. Run with --fetch to attempt MAST download.

## Verdict

**DIP_STRUCTURE (known-answer recovery confirms epoch-fold pipeline)**

Boyajian's Star (TIC 272172248) epoch-fold analysis. Known-answer fixture: planted period 24.5 d, recovered 24.415 d with Z2=60.0 (recovery_pass=True). Quiet-star null 95th percentile Z2=13.280685064234627, random-phase null 95th percentile Z2=11.49363773933782. Real TESS data: not available (run with --fetch).

Verdict: DIP_STRUCTURE (known-answer recovery confirms epoch-fold pipeline)

Structure != message. Aperiodic dips at Boyajian's Star are astrophysical phenomena (circumstellar dust / exocomets / debris), not artifacts of exogenous construction. No dip structure, even if periodic, constitutes evidence of artificial engineering without independent electromagnetic or infrared signatures.


This analysis uses a synthetic fixture for math validation. The fixture emulates Kepler-era dip structure but does NOT replicate the full Kepler lightcurve. Epoch-fold on real TESS data (--fetch) uses heuristic dip extraction. For authoritative dip timing, see Boyajian et al. 2016 and 2018. DIP_STRUCTURE is a mathematical result, not evidence of exogenous artifacts. Structure != message.


### Kepler-era dip context (not reprocessed)

- D800: ~day 800, ~15% depth
- D1200: ~day 1200-1220 complex, ~22% max depth
- D1500: ~day 1500-1590 complex (D1519, D1568)

---
*G20 Boyajian's Star --- structure != message. Dip epoch-fold validates math, not exogenous artifacts.*
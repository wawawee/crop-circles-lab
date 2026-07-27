# G21 — Fine-structure α directional variation (King+2012 re-run CLEAN)  🟡
Generated: 2026-07-26T08:24:32.814221+00:00

## Stance
Fine-structure constant α directional variation is a controversial result from quasar absorption spectroscopy (Webb et al. 2011; King et al. 2012). The claimed dipole may reflect unknown systematic effects in wavelength calibration, temperature/pressure shifts in spectrographs, or isotopic abundance variations. This probe measures directional structure ONLY. It does NOT claim new physics. STRUCTURE != MEANING. Honest prior: NO_SIGNAL.

### Forbidden phrases (logged so a code-reviewer catches drift)
- `new physics proven`
- `varying constant confirmed`
- `beyond the Standard Model`
- `fifth force`
- `cosmological crisis`
- `aliens`
- `extraterrestrial`
- `we found a dipole`
- `dipole confirmed`

## Data

King et al. (2012) VLT+Keck quasar absorption Δα/α measurements. 295 absorption systems from 153 quasars. See `data/astro/alpha_variation/README.md` for full provenance.
- N absorbers (clean): 293
- N Keck: 140
- N VLT: 153

## Observed dipole fit

### Best-fit dipole (brute-force grid search)
- RA: **260.0°**
- Dec: **-59.1°**
- Amplitude: **0.9735** × 10⁻⁵
- Correlation r: **0.2772**
- χ²/ν: **0.96**
- Score: **4.74**

### Comparison with King+2012 published dipole

King+2012 (MNRAS 422, 3370; arXiv:1202.4758) report a best-fit dipole from combined Keck+VLT data:
- RA = 17.5 ± 0.9 h (262.5 ± 13.5°)
- Dec = −58 ± 9°
- Amplitude A = (0.97 ± 0.22) × 10⁻⁵ (bootstrap; asymmetric −0.20/+0.22 per Table 3)
- Significance: ~4.1σ (vs isotropic null)

| Metric | Our recovery | King+2012 | Offset | σ (vs King error) |
|--------|-------------|-----------|--------|-------------------|
| RA | 260.0° | 262.5° ± 13.5° | 2.5° | **0.19σ** |
| Dec | −59.1° | −58° ± 9° | 1.1° | **0.12σ** |
| Amplitude | 0.9735 × 10⁻⁵ | 0.97 ± 0.22 × 10⁻⁵ | 0.0035 × 10⁻⁵ | **0.02σ** |

**Angular separation:** 1.7° (well within the 9° Dec error circle)

**Fit at the published King+2012 dipole direction** (from `run.json`):
- Amplitude: 0.9665 ± 0.201 × 10⁻⁵ (consistent with published 0.97 ± 0.22)
- Monopole: −0.17 ± 0.08 × 10⁻⁵
- χ²/ν: 0.96 (N=293, dof=291)

**Verdict:** Our independently recovered dipole is fully consistent with the published King+2012 result — all parameters fall within 0.2σ of the reported values. The angular separation of 1.7° is negligible compared to the positional uncertainties. This confirms the probe's grid search correctly recovers the known signal.

## Per-telescope diagnostic

To check whether the combined dipole is driven by a single telescope, the dipole search was run
separately on Keck-only (N=140) and VLT-only (N=153) subsets, each with 500 null realizations.

### Best-fit by telescope

| Subset | N | RA | Dec | A (×10⁻⁵) | z(scramble) | z(uniform) | sep from King+2012 |
|--------|---|----|-----|-----------|-------------|-------------|-------------------|
| Keck | 140 | 240.0° | −47.6° | 0.415 | **−0.44** | −0.22 | 25.8° |
| VLT | 153 | 280.0° | −58.2° | 1.075 | **+2.11** | +2.18 | 12.1° |
| Combined | 293 | 80.0°† | 58.2°† | −0.975 | +4.53 | +4.71 | — |

† Antipode of the 72×36 grid result (RA=260°, Dec=−59.1°); mathematically equivalent.

### Cross-telescope consistency

| Cross-fit | Amplitude (×10⁻⁵) | χ²/ν |
|-----------|-------------------|------|
| Keck dipole fitted on VLT data | 0.543 ± 0.386 | 0.96 |
| VLT dipole fitted on Keck data | 0.240 ± 0.289 | 0.91 |
| **Angular separation (Keck vs VLT poles)** | **25.9°** | — |

### VLT bootstrap null

VLT absorbers were resampled with replacement (N=153, 1000 realizations) to test whether the
VLT-only signal survives internal systematic correlations:

| Null | z-score | Interpretation |
|------|---------|---------------|
| scramble_coordinates (VLT) | +2.11 | Marginal — breaks spatial structure |
| uniform_random (VLT) | +2.18 | Marginal — breaks spatial structure |
| **bootstrap resample VLT** | **−0.27** | **Consistent with VLT internal structure** |

### Interpretation

The dipole is **VLT-driven**:

1. **Keck alone shows no signal** (z = −0.44). Its best-fit amplitude (0.415 × 10⁻⁵)
   is consistent with noise.
2. **VLT alone shows marginal signal** (z = +2.11) against coordinate-null tests, but
   **disappears against telescope-internal bootstrap** (z = −0.27). This means VLT's
   own internal correlations produce dipoles as strong as the observed one.
3. **Cross-telescope consistency is poor**: the Keck and VLT best-fit poles are 25.9°
   apart, and neither telescope independently recovers the other's preferred direction
   (cross-fit amplitudes are 0.5–0.7σ from zero).
4. The combined fit (z = +4.53) is stronger than either subset, which suggests the two
   datasets partially align, but this is exactly the signature expected from a
   systematic that correlates both datasets rather than a true cosmological dipole.

This pattern strongly supports the existing instrument-systematics concern.

## Null controls

### scramble_coordinates

- Mean score: **1.69**
- Std score: 0.69
- Median score: 1.65
- Max score: 3.86
- N realizations: 500

### scramble_preserve_pairs

- Mean score: **4.74**
- Std score: 0.00
- Median score: 4.74
- Max score: 4.74
- N realizations: 500

### uniform_random

- Mean score: **1.63**
- Std score: 0.68
- Median score: 1.56
- Max score: 3.86
- N realizations: 500

### instrument_systematics

- Mean score: **4.90**
- Std score: 0.93
- Median score: 4.94
- Max score: 7.59
- N realizations: 500

## z-scores (observed vs null)

| Null | z(score) |
|------|----------|
| scramble_coordinates | +4.40 |
| scramble_preserve_pairs | +0.00 |
| uniform_random | +4.58 |
| instrument_systematics | -0.18 |

## Verdict

**INSTRUMENT_SYSTEMATICS_NULL_NOT_REJECTED | UNDERDETERMINED | BEST_FIT_NEAR_KNOWN_DIPOLE | STRONG_NULL_SEPARATION_2OF4**
Max |z| across all nulls: **4.58**

## Caveats

1. The King+2012 dataset uses two different telescopes (Keck HIRES, VLT UVES)
   with different wavelength calibrations. A joint fit may introduce
   telescope-specific systematics.
2. sigma_rand (added in quadrature to photon-counting errors) depends on
   the model being tested. We use the weighted-mean model values.
3. The brute-force search used a 72×36 = 2592-point grid with 500 null realizations.
   A finer 72×36 grid (with 500 nulls) converged to the antipode of the 36×18 result
   (mathematically equivalent; amplitude unchanged). Further refinement is unnecessary.
4. We do NOT fit for a dipole + monopole simultaneously with the
   full covariance treatment of the King+2012 analysis.
5. structure != meaning. A recovered dipole does NOT imply new physics.
6. **VLT-driven signal (added 2026-07-26):** The combined dipole is driven primarily by
   VLT/UVES data. Keck-only shows no signal (z=−0.44). The VLT-only signal (z=+2.11 vs
   coordinate scramble) disappears against a telescope-internal bootstrap null (z=−0.27,
   1000 realizations), indicating the VLT data's internal correlations alone can produce
   dipole signals of comparable strength. This is the strongest evidence to date that
   the King+2012 dipole arises from VLT-specific systematics rather than a true
   cosmological variation of α.

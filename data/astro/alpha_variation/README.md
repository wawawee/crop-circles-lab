# Fine-structure constant α directional variation — quasar absorption dataset

## Source

King et al. (2012), *"Spatial variation in the fine-structure constant — new results from VLT/UVES"*, MNRAS 422, 3370–3414. [arXiv:1202.4758](https://arxiv.org/abs/1202.4758)

## Public dataset

The catalogue (`catalog.json`) contains all 295 quasar absorption systems from the combined VLT+Keck analysis, transcribed from the public file:

> `http://astronomy.swin.edu.au/~mmurphy/files/KingJ_12a_VLT+Keck.dat`

## Columns

| Column | Description | Unit |
|--------|-------------|------|
| `id` | Sequential index (1–295) | — |
| `name` | J2000 quasar name | — |
| `ra_deg` | Right Ascension (J2000, derived from name) | degrees |
| `dec_deg` | Declination (J2000, derived from name) | degrees |
| `z_em` | Emission redshift of the quasar | — |
| `z_abs` | Absorption redshift of the absorber | — |
| `da_a` | Δα/α = (α_absorber − α_lab) / α_lab | ×10⁻⁵ |
| `err` | Statistical error (from Voigt profile covariance matrix) | ×10⁻⁵ |
| `sample` | Sample code: A, B1, B2, C (Keck) or D (VLT) | — |
| `source` | Telescope: Keck or VLT | — |
| `sig_rand_flag` | Extra-error group: 1=Keck LC, 2=Keck HC, 3=VLT | — |
| `outlier` | 1 = LTS-identified outlier (excluded from primary analysis) | — |

## sigma_rand values (from Table 2)

For the **weighted-mean model**, the extra error added in quadrature is:

| Sample | σ_rand (×10⁻⁵) |
|--------|----------------|
| VLT (flag=3) | 0.905 |
| Keck LC (flag=1) | 0.000 |
| Keck HC (flag=2) | 1.743 |

Total error: `σ_total = √(err² + σ_rand²)`

## Known dipole (King et al. 2012)

Best-fit dipole (from joint Keck+VLT analysis):

- **RA:** 17.5 ± 0.9 h (262.5 ± 13.5°)
- **Dec:** −58 ± 9°
- **Amplitude:** A = (0.97 ± 0.22) × 10⁻⁵ (bootstrap; asymmetric −0.20/+0.22 per Table 3)

*Note: The ±0.12 error cited in some secondary literature likely omits the σ_rand* 
*inflation or uses a subsample. The bootstrap-derived ±0.22 is the canonical* 
*combined-sample error from the paper.*

## Provenance

This is a **re-analysis** of the published dataset. The probe (tools/scripts/alpha_variation_probe.py) performs an independent dipole search using brute-force direction scanning + linear regression, and compares the observed dipole strength against two null distributions:

1. **Coordinate scramble**: RA and Dec independently shuffled, breaking spatial correlation.
2. **Instrument-systematics**: Telescope-bootstrap resample, preserving Keck/VLT-specific error distributions.

## Stance

**Structure ≠ meaning.** The published dipole may reflect unknown systematic effects in quasar absorption spectroscopy (wavelength calibration, temperature/pressure shifts, isotopic abundances, etc.). This probe measures **directional structure only**. It does not claim new physics.

Forbidden phrases: "new physics proven", "varying constant confirmed", "aliens", "beyond the Standard Model", "fifth force", "cosmological crisis".

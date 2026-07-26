# lde_probe — G19 Long Delayed Echoes NOTES

> **Verdict: CLAIM_FAILS_NULL**
> Stance: **structure ≠ message.** Historic delay values only, not IQ baseband.
> Generated from `/Users/perbrinell/Documents/TIN-STUDY/crop-circles/data/radio/lde/lde_master.json` (100 observations).

---

## Descriptive Statistics

| Metric | Value |
|--------|-------|
| Total observations | 100 |
| Unique delay values | 34 |
| Delay range | 0.2–40.0 s |
| Mean delay | 12.22 s |
| Median delay | 11.00 s |
| Std deviation | 8.20 s |
| Mode (most frequent) | 8.0 s (13×) |
| Integer delays | 96/100 (96.0%) |
| Repeated values | 22 |
| Shannon entropy | 4.72 bits |

### Per-source breakdown

| Source | Count |
|--------|-------|
| Appleton_1934 | 32 |
| vdPol_1928_oct24 | 20 |
| Crawford_1970 | 17 |
| Stormer_1928 | 14 |
| Hals_1934 | 11 |
| Crawford_1978 | 6 |

---

## Structure Tests (Full Corpus)

### integer_multiplicity

- **test**: integer_multiplicity
- **statistic**: n_repeated_values
- **observed**: 22
- **null_mean**: 22.0
- **null_p95**: 22.0
- **null_max**: 22
- **p_value**: 1.0
- **exceeds_null**: False
- **n_shuffle**: 200
- *Note:* Tests whether integer-delay multiplicity exceeds a shuffle of the same multiset. NOT a time-series test. structure != message.

### mode_concentration_8s

- **test**: mode_concentration
- **mode_value_s**: 8.0
- **observed_count**: 13
- **observed_fraction**: 0.13
- **null_mean**: 13.0
- **null_p95**: 13.0
- **p_value**: 1.0
- **exceeds_null**: False
- **n_shuffle**: 200
- *Note:* Tests whether 8.0s concentration exceeds shuffle null. Crawford 1970: '2 and 8 seconds were the most frequent.' structure != message.

### entropy_vs_uniform

- **test**: entropy_vs_uniform
- **observed_entropy_bits**: 4.721
- **uniform_null_mean_entropy**: 5.665
- **uniform_null_std_entropy**: 0.0919
- **p_value_low_entropy**: 0.0
- **n_unique_observed**: 34
- *Note:* Shannon entropy of delay distribution vs uniform null. Low entropy = concentrated distribution. structure != message; concentration can arise from rounding (1920s integer-second reporting) or from prosaic clustering.

### epoch_fold_values

- **test**: delay_value_epoch_fold
- **best_period_s**: 0.5
- **best_z2**: 192.83629270227522
- **best_phase_rad**: 0.005986071363889992
- **shuffled_z2_max**: 24.3
- **exceeds_shuffle**: True
- *Note:* Epoch-fold on delay VALUES (not arrival times). A positive result means delay values repeat at a regular interval, NOT that echoes are periodic in real time. structure != message.

---

## Corpus Verdict

- **UNDERDETERMINED**
- Any excess structure over uniform null: True
- Shannon entropy p-value (low = concentrated): 0.0

---

## Lunan Claim-Under-Test (Stormer 1928 Oct 11, n=14)

- **Verdict: CLAIM_FAILS_NULL**
- Observed structure score: 0.8
- Shuffle null: mean=0.8, std=0.0, p=1.0
- Prosaic null: mean=0.7228, std=0.1399, p=0.403
- Beats shuffle null: False
- Beats prosaic null: False
- Reason: Lunan-structure score does NOT exceed shuffle null. The delay-value multiset has no more 'Bootes-like' structure than a random permutation of the same values.

> Lunan's 'Bootes constellation / moon-relay' hypothesis is UNDER-TEST here. Verdict is CLAIM_FAILS_NULL or UNDERDETERMINED. Never validates Lunan. Structure != message.

---

## Accuracy Caveat

> 1920s timing: ±1–2 s uncertainty. Størmer 1955: 'The times noted by me can lay no claim to great accuracy, because I was not adequately prepared.' Van der Pol 1928: timing with stopwatch + second hand of ordinary watch.

---

## Controls Ledger

| Control | Where | Expected |
|---------|-------|----------|
| Shuffle null (multiset permute) | All structure tests | Structure must NOT exceed |
| Prosaic null (2s/8s weighted) | Lunan claim | Lunan structure must NOT exceed |
| Uniform null (random delays) | Entropy test | Observed entropy must NOT be lower |

---

## Forbidden

- No ET/alien probe claims
- No Lunan/Filipenko/Bracewell confirmation
- No IQ/baseband fabrication
- No Skinwalker / modern SDR crossover

*structure != message. Historic delay values, not IQ baseband. We analyse delay-value multiset structure only. Never validates Lunan/Filipenko/Bracewell.*

# `data/radio/` — provenance for the R1 radio probe

This directory carries the *citations* and *honest framing* for the R1 radio
scaffold. There are no raw time-series data files in this directory: the
scaffold uses **synthesised plants** (clean sin waves for the periodic-train
known-answer; tight Gaussian-jitter multiples of 16.35 d for the FRB 180916
scaffold) so we can verify the math without claiming anything about real
Wow! or real FRBs.

## The 6-sample Wow! signal (1977)

| Field | Value | Source |
|---|---|---|
| Frequency | **1420.40575 MHz** (21 cm hydrogen line) | Big Ear Ohio State, 1977-08-15 |
| Sample window | 12 s per bin | Big Ear spectrometer dump rate |
| Total on-source | **72 s** (6 × 12 s) | Big Ear single-beam shutter |
| Data shape | **6 intensity samples**, NOT a time series | "6EQUJ5" column header |
| Sample values (σ) | 6.5, 14.5, **26.5**, 30.5, 19.5, **5.5** | Ehman's handwritten transcript (`6EQUJ5`) |

**Why we say "audit-only":** with N = 6 samples, the rfft produces **4
bins** (DC + 3 unique frequency bins at `k / (6 · 12 s) ≈ k · 0.01389 Hz`,
k = 1, 2, 3). ANY prominent-frequency claim on N = 6 is a single-bin
resampling — by construction it has no false-rejection power and no
statistical significance. The 2024 PHL@UPR reanalysis (arXiv:2408.08513,
CC BY 4.0) attributes the signal to a **cold hydrogen cloud** near a
solar-type star — natural, not artificial. Our scaffold's `claim_blocked:
True` reflects this honestly.

### G3 — Wow! SIDEREAL TRANSIT beam-fit (underdetermined)

The 6-sample Wow! signal is **not a time series** in the conventional
sense — it is a 6-bin intensity profile that *could* be consistent with
a sidereal horn-beam transit. The G3 scaffold fits one Gaussian AND one
sinc beam to the 6 samples, reports r² for each against a constant
baseline, surfaces the **degeneracy-pair** (μ ↔ 6-μ on a symmetric plant),
and emits a **24-permutation scramble null** for comparison.

**Crucial caveat: with N=6 samples and K=3 fit parameters, only 3 d.o.f.
remain.** A Gaussian fit on 6 samples can NEVER statistically distinguish
a horn-beam transit from a transient single-pulse signal of the same
shape. The 2024 PHL@UPR reanalysis (arXiv:2408.08513, CC BY 4.0) confirms
this: the natural explanation is a hydrogen cloud near a solar-type
star, NOT ET. We compute r² for clarity but **do not** claim detection
of artificial origin.

| Field | Value | Source |
|---|---|---|
| Intensities | `[6.5, 14.5, 26.5, 30.5, 19.5, 5.5]` σ | Ehman's handwritten transcript (6EQUJ5 in column header) |
| Sample window | 12 s each, 72 s total | Big Ear single-beam shutter |
| Underdetermined DOF | 3 (after a Gaussian fit) | N=6 − K=3 |
| Degeneracy pair | `(μ_rec, 6 − μ_rec)` symmetric on symmetric plants | Symmetry of Gaussian fit residuals |
| 2024 PHL@UPR reanalysis | Hydrogen cloud near a solar-type star | arXiv:2408.08513, CC BY 4.0 |

#### G3 CLI flags

| Flag | Mode | What it does |
|---|---|---|
| `--wow-beam-fit` | synthetic default | runs synthetic plant recovery + real-data baseline |
| `--wow-beam-fit-synthetic` | synthetic only | plants noise-free Gaussian at `(μ=2.5, σ=1.5, A=30)`. Recovers within tolerance. |
| `--wow-beam-fit-real` | real only | Ehman's handwritten 6 values; reports underdetermined r² + scramble null |

#### G3 output schema (per sub-run)

| Field | Purpose |
|---|---|
| `samples[6]` | the 6 intensity values (plant or real) |
| `plant` (synthetic only) | ground-truth (μ, σ, A) |
| `fit.r²_constant` | r² for a 1-parameter (mean) baseline (DO=5) |
| `fit.r²_gaussian` | r² for a 3-parameter Gaussian fit (DO=3)  |
| `fit.r²_sinc` | r² for a 3-parameter sinc fit (DO=3) |
| `fit.recovered_gaussian.{mu_idx, sigma_idx, amplitude}` | best Gaussian beam params |
| `fit.recovered_sinc.{mu_idx, sigma_idx, amplitude}` | best sinc beam params |
| `fit.degeneracy_pair` | `(μ_rec, 6-μ_rec)` symmetry note |
| `fit.underdetermined_note` | mathematical + PHL@UPR caveat |
| `scramble_null.{r²_median, r²_p5, r²_p95}` | 24-permutation null distribution |
| `cross_check_scramble` | `structure_above_scramble_median` boolean |
| `known_answer` | recovery_pass + per-parameter errors (synthetic only) |
| `stance` | lab motto + PHL@UPR 2024 cite |

#### What G3 does NOT do (forbidden claims)

- ❌ Claim Wow! is a confirmed technosignature.
- ❌ Claim that ANY r² ≈ 1 from a Gaussian fit implies detection (the
       3 d.o.f. shortage means any peaked profile fits equally well).
- ❌ Distinguish horn-beam transit from a transient pulse using only 6
       bins. Both produce a peaked profile that a 3-parameter Gaussian
       can fit. Both have the same r² under our fit. We cannot tell
       them apart.
- ❌ Claim periodicity / beam-crossing implies artificial origin. It is
       necessary, NOT sufficient.

## FRB 180916.J0158+65 — 16.35-d activity cycle

| Field | Value | Source |
|---|---|---|
| Discovery | CHIME/FRB | CHIME/FRB Collaboration, *Nature* 2020 |
| Activity cycle | **16.35 d** ± ~0.04 d | Pastor-Marazuela et al. 2020/2021 |
| Hypothesised cause | Orbital precession of companion | (natural — favoured explanation) |
| Public data | CHIME/FRB Catalog 1 (536 FRBs, CSV) | `https://www.chime-frb.ca/catalog` |

**DO NOT confuse with FRB 121102.**

| Field | FRB 121102 | FRB 180916 |
|---|---|---|
| Activity cycle | **~157–161 d** (Rajwade 2020; Cruces 2021) | **16.35 d** (Pastor-Marazuela 2020) |
| Rep. host | Star-forming dwarf galaxy (at z ≈ 0.19) | Nearby spiral arm |
| Why conflating them is wrong | Distinct source, distinct repetition cadence | Distinct burst morphology |

If the period search grid in our scaffold is set to **10–30 d**, the FRB
121102 cycle (~157 d) **lies outside the search range** — it cannot spuriously
match. The scaffold's `plant.decoy_period_d_for_frb_121102 = 157.0` field is
a defensive marker: it documents the period we explicitly DID NOT use.

## Negative controls baked into the JSON output

For every scaffold run, the JSON includes a `negative_controls` block:

- `white_noise_peak_freq_hz` for the periodic train (white noise has no
  preferred frequency; its FFT peak should be noise-floor).
- `shuffled_uniform_z2_max` for the FRB scaffold (uniform-random arrival
  times should yield a Rayleigh Z² max < 5; the plant's tight clustering
  yields Z² ≫ 10).

If either negative control matches the plant's signal-level result, the
conclusion is "no signal" — both are *necessary* but *not sufficient* —
because the universe's natural clocks (pulsars with sub-microsecond
periodicity) demonstrate beyond doubt that periodicity is necessary
but not sufficient for artificiality.

## Honest framing

> Structure ≠ message. This scaffold is a math-validation tool. It does NOT
> detect, classify, or claim signals from real Wow! or real FRBs. Replace
> the synthesised plant with a real CHIME/FRB Catalog 1 CSV (after writing
> a fetcher) if you want to test the epoch-fold pipeline against reality —
> and remember: a positive Z² there is **necessary, NOT sufficient** for
> artificiality.

---

## Real-data fetch path (`--frb-180916-real`)

As of **2026-07-25**, the canonical CHIME/FRB Catalog 1 mirror is **offline**
(verified by direct HTTP probes against `https://www.chime-frb.ca/catalog`,
CANFAR AstroDataCitationDOI 21.0007, GitHub raw content paths, and S3
mirrors — all return HTML parking pages or 404s). The lab motto prohibits
silent fabrication, so the real-data path surfaces this honestly.

### What the path does

1. **Live fetch attempt** (`chime_frb_fetcher.try_fetch_chime_frb_catalog_1_csv`)
   probes 5 candidate URLs in order:

   | URL | Role |
   |---|---|
   | `https://www.chime-frb.ca/catalog/frb_catalog_1.csv` | CHIME primary |
   | `https://www.chime-frb.ca/catalog/catalog_1.csv` | CHIME alt filename |
   | `https://www.canfar.net/storage/download/.../catalog1.csv` | CANFAR mirror |
   | `https://raw.githubusercontent.com/CHIME-FRB-Open-Data/catalog/main/csv/catalog1.csv` | GitHub raw |
   | `https://chime-frb-open-data.s3.ca-central-1.amazonaws.com/catalog1.csv` | S3 mirror |

   Each attempt is recorded with URL, HTTP status, content-type, byte count,
   and a verdict (`CSV_HEADER`/`HTML_PARKING`/`NETWORK_ERROR`/`4XX`/`5XX`/...).

2. **Burst-source resolution** (`frb_real_sources.load_published_frb_180916_bursts`)
   returns a `PublishedBurstSource` with one of:
   - `source_type="user_provided"` (when `--bundled-mjd-json` was given)
   - `source_type="chime_csv_fetch"` (when a live CSV was fetched)
   - `source_type="empty"` (when fetch failed; populated provenance note)

3. **Orchestration** (`radio_probe.run_frb_180916_real`) runs the standard
   epoch-fold + shuffled-uniform null on the resolved MJDs. **If zero MJDs
   are obtained, NO synthetic plant is inserted** — the run returns
   `epochfold=None`, `n_bursts=0`, and a top-level `warnings` list. A 🟡
   banner is rendered in the markdown.

### How to populate real MJDs today (manual path)

Until the chime-frb.ca CSV mirror comes back online, the only honest way to
inject real MJDs is to manually transcribe the Pastor-Marazuela 2021 burst
table (ApJ 923 L6; arXiv:2001.08645 — PDF tables are image-only, so
`pdftotext` cannot extract them automatically) and feed it via:

```bash
# 1. Save MJDs as a flat JSON list under data/radio/cache/:
echo '[58700.123, 58716.456, 58732.789, ...]' > data/radio/cache/pastor_marazuela_2021_frb_180916.json

# 2. Run the real-data path with the override:
python3 tools/radio/radio_probe.py \
    --frb-180916-real \
    --bundled-mjd-json data/radio/cache/pastor_marazuela_2021_frb_180916.json \
    --out-json outputs/radio/radio_real_data.json
```

This produces a JSON whose `data_source` is `user_provided`, `fetch_status`
is `USER_OVERRIDE`, and `known_answer.recovery_pass` is the math-validation
of the wired-real-data path.

### What it does NOT do (forbidden claims)

- ❌ Claim a fetch succeeded when the mirror is offline.
- ❌ Silently fall back to a synthetic 30-arrival plant when MJDs are not
  available (this would be a labeled mistake that breaks the lab motto).
- ❌ Claim periodicity implies artificiality. Pulsars are periodic. Coastlines
  are fractal. Noise is high-entropy. Periodicity is **necessary, NOT sufficient**
  for artificiality.

## Vela pulsar (PSR B0833-45 / J0835-4510) — positive-control anchor

| Field | Value | Source |
|---|---|---|
| B1950 name | **B0833-45** | ATNF Pulsar Catalogue (Manchester+ 2005) |
| J2000 name | **J0835-4510** | ATNF Pulsar Catalogue |
| Published period P0 | **~89.328 ms** (0.089328386 s, 9-decimal precision) | Manchester+ 2005, AJ 129 1993, DOI 10.1086/428488 |
| Spin-down | ~1.4 dP/dt (subtle; the constant-P0 plant ignores this) | PPTA DR3 (Zic+ 2023) |
| Glitches | 1988/1991/1994/1996/1997/1998/1999/2000/2003 large; the synthetic plant IGNORES | ATNF Pulsar Catalogue; PPTA DR3 (Zic+ 2023) |
| Data license | **CC BY 4.0** | ATNF Pulsar Catalogue user agreement |

**Role:** this pulsar is the universe's most famous **NATURAL** periodic
clock. Vela is deliberately wired as a **positive-control scaffold**
because:

1. If `radio_probe` recovers P0 cleanly from a known periodic source,
   the FFT / autocorr / epoch-fold math is verified.
2. The recovery **does NOT** imply artificial origin — Vela is famously
   natural (supernova remnant; Crab-like; not a construct of technology).
3. This anchors the lab motto: **periodicity is necessary, NOT sufficient,
   for artificiality.** A pos-control that returns "I found P0" *and* the
   canonical conclusion is "this is a natural pulsar" is the most honest
   proof-of-pipeline we can publish.

### Real-data path (`--pulsar-vela-real`)

As of **2026-07-25**, direct ATNF/Parkes Vela timing endpoints in our
candidate list (5 URLs: PSRCAT CSV export, Parkes Pulsar Timing Archive raw,
PPTA DR3 access points) often return **HTML parking pages** or **404s**
when probed anonymously. Like the CHIME path, we **NEVER silently
fabricate** arrival MJDs — the real-data path returns the honest-empty
shape (`n_arrivals: 0`, `YELLOW BANNER`, pending fetch probe list).

### Honest paths to populate real Vela MJDs today

1. **Manual transcription from a published paper.** Manchester+ 2005
   Table 1 contains ~30 PSR B0833-45 timing residuals; transcribe to a
   CSV with header `name,mjd`:

   ```bash
   # data/radio/cache/vela_timing.csv
   cat > data/radio/cache/vela_timing.csv <<EOF
   name,mjd
   B0833-45,58000.000123456
   B0833-45,58001.893734567
   ...
   EOF

   python3 tools/radio/radio_probe.py \
       --pulsar-vela-real \
       --bundled-pulsar-csv data/radio/cache/vela_timing.csv \
       --out-json outputs/radio/vela_real_data.json
   ```

2. **Run the synthetic scaffold first** (`--pulsar-vela-synthetic`) to
   verify the math pipeline recovers the published P0 within tolerance
   (`|recovered - P0| ≤ 5e-6 s` for the synthetic plant). It is the
   "nothing's broken" sanity check before any real-data attempt.

### Vela CLI summary

| Flag | Mode | What it does |
|---|---|---|
| `--pulsar-vela` | synthetic, fallback to real if `--bundled-pulsar-csv` is given | sensible default |
| `--pulsar-vela-synthetic` | synthetic only | math-validation plant proof |
| `--pulsar-vela-real` | real only | honest-empty fallback if fetch fails |
| `--bundled-pulsar-csv <file>` | override | inject transcribed MJDs |
| `--fetch-status-test-force UNREACHABLE` | test hook | mirrors the CHIME `force_status` shim |

**No fabricated MJDs. Ever.** If `n_arrivals == 0`, the JSON's
`warnings` list spells out what was attempted.

## G-BLC1 (Breakthrough Listen Candidate 1) — RFI known-answer scaffold

| Field | Value | Source |
|---|---|---|
| Detection | **~982.002 MHz**, drift **~−0.26 Hz/s** | Price+ 2019 (initially leaked as +0.038); corrected by Sheikh 2021 |
| RFI conclusion | **Intermodulation product of clock-oscillator harmonics** (~2 MHz fundamental) | Sheikh et al. 2021, *Nature Astronomy* 5 1169, DOI 10.1038/s41550-021-01508-8 |
| Live TB fetch | **DISABLED by design** — per user brief ('no TB mirror') | `try_fetch_blc1_peaks()` short-circuits to NEVER_ATTEMPTED |
| Public-data reality | BLC1 HDF5/filterbank IS released at seti.berkeley.edu/opendata/blc1/ (Berkeley) | Lab stance: do NOT scrape it for the G-BLC1 scaffold |
| License (bundled override) | **CC BY 4.0** | Sheikh 2021 supplementary tables (transcribed by caller) |

**Lab motto in action.** This scaffold is the
**inverse of the Vela/CHIME/FRB 180916** pattern:

* Vela/CHIME/FRB = **live fetch first**, bundled override as fallback.
* G-BLC1 inverse = **bundled-override first**, live fetch DISABLED.

The G-BLC1 live path explicitly does NOT contact the Berkeley SETI opendata
archive because (a) the user brief forbade it ("no TB mirror"), and (b) the
lab motto forbids treating potentially-unresolved candidate archives as a
detection signal. The 5 administrative URLs are documented in the
`CANDIDATE_URLS` tuple purely for visibility — so a future maintainer can
SEE what is and is NOT permitted. In production every attempt verdict is
`NEVER_ATTEMPTED`.

### Live-data path (`--blc1-real`)

As of **2026-07-25**, the G-BLC1 live path is **disabled by design**. Three
test-booked hooks exist for deterministic tests but production users should
omit them:

| Test hook | What it does |
|---|---|
| `--fetch-status-test-force NEVER_ATTEMPTED` (default) | Returns the honest-empty YELLOW BANNER shape. Documents what was not attempted. |
| `--fetch-status-test-force FETCHED` | Synthesises the 5-peak positive-control set (BLC1 detection + 2 clock harmonics + 2 known Parkes RFI freqs). Useful for the test_force_propagation check. |
| `--fetch-status-test-force PARKING_PAGE` | Returns the PARKING shape with the same YELLOW BANNER text. Tests the markdown renderer. |

### Bundled-override path (`--bundled-blc1-csv`)

This is the realistic landing today. Manually transcribe peak rows from the
Sheikh 2021 supplementary tables (PDF) into a small CSV:

```bash
# 1. Save peaks from Sheikh 2021 supplementary as CSV:
cat > data/radio/cache/blc1_sheikh_2021.csv <<EOF
freq_mhz,snr_db,drift_hz_per_s,t_start_mjd,t_end_mjd,label
982.002,25.0,-0.26,58000.0,58000.0,BLC1_DETECTION
984.002,12.0,-0.26,58000.0,58000.0,BLC1_CLOCK_HARMONIC_+1
986.002,9.0,-0.26,58000.0,58000.0,BLC1_CLOCK_HARMONIC_+2
980.002,8.0,-0.26,58000.0,58000.0,BLC1_CLOCK_HARMONIC_-1
440.0,18.0,0.0,58000.0,58000.0,PARKES_UHF_RFI_NEAR_BLC1_OBS_WINDOW
EOF

# 2. Run the bundled-override path:
python3 tools/radio/radio_probe.py \
    --blc1-real \
    --bundled-blc1-csv data/radio/cache/blc1_sheikh_2021.csv \
    --out-json outputs/radio/blc1_real_data.json
```

The synthetic comb plant (mirror of Vela synthetic) is the math-validation
tool: 5 harmonically-spaced peaks at integer multiples of the 2 MHz clock
around 982.002 MHz. The recovered clock matches the published value within
BLC1_COMB_TOLERANCE_MHZ = 0.01 MHz, AND the scramble-null control drops the
hit count well below the planted value (math-validation).

### G-BLC1 CLI summary

| Flag | Mode | What it does |
|---|---|---|
| `--blc1` | synthetic, fallback to real if `--bundled-blc1-csv` is given | sensible default |
| `--blc1-synthetic` | synthetic only | math-validation plant (5 comb peaks) |
| `--blc1-real` | real only | honest-empty YELLOW BANNER if no bundled override |
| `--bundled-blc1-csv <file>` | override | inject Sheikh 2021 supplementary transcription |
| `--fetch-status-test-force FETCHED` | test hook | mirrors the same flag for Vela/FRB 180916 |

### What it does NOT do (forbidden claims)

- ❌ Claim a fetch succeeded when the Berkeley SETI mirror is offline.
- ❌ Silently fall back to a synthetic peak list when no bundled override is given.
- ❌ Claim that a comb-hit implies artificial origin: BLC1 itself was
       classified as clock-oscillator RFI per Sheikh 2021; periodic/comb
       structure IS RFI here, NOT ET.
- ❌ Scrape the Berkeley SETI open-data archive for candidate scores.

### Known Parkes RFI comb (positive control)

The PARKES_KNOWN_RFI_FREQS_MHZ list (in `radio_probe.py`) drives the
positive-control RFI hit. Any peak within `PARKES_KNOWN_RFI_TOLERANCE_MHZ
= 0.5 MHz` of any of these markers is flagged `RFI_COMB_DETECTED`:

| Freq (MHz) | Likely source |
|---|---|
| 137.0    | GPS L1 / GLONASS L1 down-mix |
| 440.0    | UHF radio astronomy band; Parkes site RFI |
| 715.0    | UHF TV downlink |
| 982.002  | BLC1 detection freq (also classified RFI per Sheikh 2021) |
| 1217.0   | GPS L2 band down-mix |
| 1616.0   | Iridium downlink |

A positive hit on this list is **RFI**, NOT a candidate. Lab motto: structure
≠ message; periodic/comb structure IS NECESSARY, NOT SUFFICIENT for
artificiality.

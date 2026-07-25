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

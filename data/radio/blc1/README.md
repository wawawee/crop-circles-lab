# data/radio/blc1 — BLC1 RFI known-answer data notes

> Owner: **Ozma** · Mission **G-BLC1** · Stance: structure ≠ message;
> technosignature candidates are guilty until proven interesting.

## Status: `BLOCKED_DATA_TOO_LARGE` → synthetic-only (acceptance-compliant)

Per the skill **scope-lock**, this workout may download **at most one ON +
one OFF** filterbank/HDF5 slice around **982 MHz**, and **only** if such a
slice exists as a subset **≪ 1 GB** (hard ceiling ~5–10 GB total). It must
**NEVER** mirror the multi-TB Parkes campaign, and must **never** `git add`
multi-GB binaries.

**Read-only portal check (2026-07-25):**

| URL | role | finding |
|---|---|---|
| `https://seti.berkeley.edu/blc1/` | BLC1 landing page | HTTP 200, 9.6 KB, last-modified 2021-10-29. Links only to the Open Data Archive. |
| `https://seti.berkeley.edu/opendata` | Breakthrough Listen Open Data Archive | Archive index; no isolated small BLC1 ON/OFF slice advertised. |

The Breakthrough Listen Parkes UWL data products for the Proxima campaign are
**multi-GB each**, and the campaign totals are **TB-scale**. No single ON+OFF
slice ≪ 1 GB could be identified without a bulk archive pull. Therefore:

- **Verdict:** mark `BLOCKED_DATA_TOO_LARGE` and ship the **synthetic
  intermodulation-comb known-answer** instead (equal Δf spacing + shared
  linear drift + ON/OFF cadence). This still advances the toolkit and is the
  landing the skill prescribes when no small slice exists.
- **No large binaries were downloaded or committed.** `raw/` below is
  gitignored (`.gitignore`: `data/radio/blc1/raw/`).

## If a small slice is later located

Place raw filterbank/HDF5 files under `data/radio/blc1/raw/` (gitignored) and
record here: exact URL, filename, byte size, and SHA-256. Then run the comb /
ON-OFF detector via a bundled peak CSV:

```
python3 tools/radio/radio_probe.py --blc1-real \
  --bundled-blc1-csv <peaks.csv> --out-json outputs/radio/blc1_real_run.json
```

CSV schema (peaks transcribed from Sheikh 2021 supplementary tables):
`freq_mhz,snr_db,drift_hz_per_s,t_start_mjd,t_end_mjd,label`

The default real-BLC1 verdict is **`NO_SIGNAL`** (terrestrial RFI) and stays
there unless OFF-controlled evidence says otherwise (it will not). We do
**not** re-open the ET question and we do **not** fabricate peaks.

## Expected data products (for reference only — NOT to be mirrored)

- ON-source: Parkes UWL narrowband filterbank around 982.002 MHz.
- OFF-source: interleaved nodding cadence pointings (the ON/OFF discriminator).
- Drift rate of the signal-of-interest: slow negative drift (repo constant
  `BLC1_DRIFT_HZ_PER_S = -0.26`); clock spacing `BLC1_CLOCK_MHZ = 2.0`.

## Citations

- **Smith et al. 2021**, *A radio technosignature search towards Proxima
  Centauri resulting in a signal-of-interest*, Nature Astronomy 5, 1148–1152.
  DOI `10.1038/s41550-021-01479-w`. (Discovery / campaign; ON/OFF nodding.)
- **Sheikh et al. 2021**, *Analysis of the Breakthrough Listen signal of
  interest blc1 with a technosignature verification framework*, Nature
  Astronomy 5, 1153–1162. DOI `10.1038/s41550-021-01508-8`. (BLC1 =
  intermodulation RFI; ON/OFF + lookalike harmonic-family; **NO_SIGNAL**.)
  bibcode `2021NatAs...5.1169S`.
- Data license (bundled Sheikh 2021 supplementary tables, if transcribed):
  CC BY 4.0.
- Portal: Breakthrough Listen Open Data Archive, `seti.berkeley.edu/opendata`.

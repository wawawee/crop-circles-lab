---
name: blc1-rfi-known-answer
description: >-
  Scoped Breakthrough Listen BLC1 RFI known-answer using public seti.berkeley.edu/blc1
  slices + blimpy/turboSETI. For Hyper Fable 5 / Opus 4.8. Never download the full
  multi-TB campaign; reproduce published terrestrial-RFI conclusion on a small slice.
---

# BLC1 RFI known-answer — Hyper skill (Fable 5 / Opus 4.8)

## Lab stance
Technosignature candidates are **guilty until proven interesting**. BLC1 is already
attributed to local RFI (Sheikh et al. 2021, Nature Astronomy). Our job is a
**reusable radio_probe workout**: reproduce the control logic on a **small public slice**,
not re-litigate ET.

## Scope lock (non-negotiable)
| Do | Don't |
|----|-------|
| Use https://seti.berkeley.edu/blc1 + Open Data Archive docs | Mirror the entire Parkes campaign (~TB) into the repo |
| Download **one** ON + **one** OFF filterbank/HDF5 around 982 MHz if available as subset | `git add` multi-GB filterbanks |
| `blimpy` + `turbo_seti` (or thin numpy FFT) | Claim independent ET detection |
| Document file sizes + URLs in README | Run unbounded cloud downloads overnight without caps |

If a “small slice” cannot be identified (<~5–10 GB total download, ideally <<1 GB):
mark `BLOCKED_DATA_TOO_LARGE` and instead build a **synthetic intermodulation comb**
known-answer inside `tools/radio/` that mimics equal frequency spacing + shared drift,
then stop. That still advances the toolkit.

## Pipeline
1. Read Smith et al. 2021 + Sheikh et al. 2021 abstracts/methods (arXiv OK). Summarize in NOTES: why ON/OFF + lookalike harmonics kill BLC1 as ET.
2. Extend `tools/radio/radio_probe.py` **or** add `tools/radio/blc1_probe.py`:
   - load filterbank/HDF5 via blimpy if installed,
   - narrowband drift search (turboSETI) **or** documented stub with same I/O contract,
   - report: hit freq, drift Hz/s, SNR, ON vs OFF presence,
   - optional: spacing test among lookalike hits (Δf regularity).
3. **Known-answer (required):**
   - synthetic: N tones at equal Δf with common linear drift → recover spacing + drift;
   - if real slice present: OFF pointing must not support the same persistent hit as ON (or hit tracks RFI family per Sheikh).
4. **Negative:** Gaussian noise waterfall; shuffled time-order of power spectra.
5. Wire honesty: default verdict for real BLC1 path = `NO_SIGNAL` (terrestrial RFI), unless OFF-controlled evidence says otherwise (it won't).

## Dependencies
```bash
source .venv/bin/activate
pip install blimpy turboSETI h5py  # pin versions in NOTES if conflicts
```
Do not vendor BL into the monorepo. Prefer optional extras in requirements notes.

## Deliverables
- `tools/radio/blc1_probe.py` (or extension) + unit tests on **synthetic** comb (no network in CI)
- `data/radio/blc1/README.md` — URLs, expected filenames, size caps, cite Sheikh/Smith
- `outputs/radio/blc1_run.json` + `NOTES.md`
- Large binaries: `data/radio/blc1/raw/` gitignored
- Update mission board row **G-BLC1**

## Acceptance
- Synthetic known-answer passes offline.
- NOTES states published RFI attribution; lab does not “re-open” ET claim.
- No multi-GB artifacts committed.
- If blocked on data size: synthetic-only path shipped + clear BLOCKED note for real slice.

## Out of scope
Full Breakthrough Listen Data Release 1 reprocess, GPU clusters, unsupervised “find ET” fishing, FRB catalog swaps (that’s R1+).

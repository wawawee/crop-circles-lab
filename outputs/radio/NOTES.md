# radio_probe — G-BLC1 + R1++ (+ G3 interpretation) NOTES

> Owner: **Ozma** (SETI-style radio / technosignature analyst).
> Stance: **structure ≠ message. Technosignature candidates are guilty until
> proven interesting.** Nothing below is a claim of an independent ET
> detection. Every synthetic path is a *math-validation* known-answer; every
> real path either parks honestly or reproduces a *published terrestrial*
> conclusion.

Generated: 2026-07-25. Run with `python3 tools/radio/radio_probe.py …`.
Test suite: `python3 tools/radio/tests/test_radio_probe.py` → **64/64 pass**
(3 pytest-fixture tests skipped by the standalone runner; unchanged from the
50/50 baseline + 14 new G-BLC1/R1++ tests).

---

## G-BLC1 — BLC1 RFI known-answer (verdict: **NO_SIGNAL**)

**What BLC1 is.** Breakthrough Listen Candidate 1: a narrowband signal near
**982.002 MHz** with a slow frequency drift, detected at the Parkes
"Murriyang" telescope during ~30 h of observations toward Proxima Centauri
(Smith et al. 2021, *Nat. Astron.*, DOI 10.1038/s41550-021-01479-w). It
persisted over ~5 h and superficially resembled an artificial transmission —
which is exactly why it became Listen's first formal "signal of interest."

**Why it is NOT a technosignature.** Sheikh et al. 2021 (*Nat. Astron.*, DOI
10.1038/s41550-021-01508-8) applied a technosignature *verification
framework* and attributed BLC1 to **local radio-frequency interference (RFI)**
— specifically an **intermodulation product of ground-based oscillator
clocks**. Two complementary controls settle it, and this repo reproduces the
*logic* of both on a scoped synthetic plant:

### 1. ON/OFF cadence (necessary, not sufficient)
A genuine celestial source is present when the dish points at the target
(**ON**) and absent when it nods off-source (**OFF**). Terrestrial RFI leaks
into both. BLC1 initially looked ON-only (hence "of interest"), but its
lookalike family reappeared during OFF pointings — the fingerprint of a local
source. `blc1_on_off_cadence()` encodes this:

- `run_blc1_synthetic` models the RFI reality: the comb **persists into OFF**
  (`persists_in_off = True`).
- A separate **ON-only contrast control** (OFF = off-comb noise) returns
  `cadence_consistent_with_source = True`, proving the discriminator has real
  power — it is not a dead detector that always says "RFI." Even so, an
  ON-only pass would **not** prove ET: cadence is *necessary, not sufficient*.

### 2. Harmonic-family / Δf regularity (the analysis that killed BLC1)
The lookalikes formed a **comb of nearly equally-spaced frequencies**
(Δf ≈ constant) — the signature of intermodulation between local-oscillator
clocks. `blc1_delta_f_regularity()` reports the coefficient of variation of
successive spacings; a **low CV ⇒ regular comb ⇒ terrestrial RFI**. On the
synthetic plant: `regular_comb = True`, `CV = 0.0`. *Structure ≠ message: a
regular comb is evidence FOR terrestrial RFI, never for ET.*

**Synthetic known-answer** (`outputs/radio/blc1_run.json`): the clock-comb
plant is recovered (`hits_at_clock ≈ N_peaks`, `rfi_comb_detected = True`),
the **scramble null** (uniform freq permutation) drops the hit count to noise,
and the composite **verdict = `RFI_COMB_TERRESTRIAL`**.

**Real-data path** (`outputs/radio/blc1_real_run.json`): the live probe is
**DISABLED by design** ("no TB mirror"; see below). It surfaces
`fetch_status = NEVER_ATTEMPTED`, `n_peaks = 0`, injects **no** synthetic
peaks, and carries the mission-mandated default **`verdict = NO_SIGNAL`**
(Sheikh 2021 terrestrial RFI). A bundled hand-transcribed Sheikh-2021 table
can be injected via `--bundled-blc1-csv`; even a positive comb-hit there is
labeled RFI, not ET.

### Real slice: `BLOCKED_DATA_TOO_LARGE`
Per the skill scope-lock, I attempted to identify a **small** (≪ 1 GB) public
ON+OFF filterbank/HDF5 slice around 982 MHz. Read-only check on 2026-07-25:
`seti.berkeley.edu/blc1` (last modified 2021-10-29) links only to the
Breakthrough Listen **Open Data Archive** (`seti.berkeley.edu/opendata`). The
Parkes UWL data products are multi-GB each and the campaign totals are
TB-scale; **no isolated small ON+OFF slice is identifiable without a bulk
archive pull.** Decision: **`BLOCKED_DATA_TOO_LARGE` → synthetic-only**, which
is the acceptance-compliant landing. No multi-GB binaries were downloaded or
committed; `data/radio/blc1/raw/` is gitignored. See
`data/radio/blc1/README.md` for URLs and size caps.

---

## R1++ — CHIME/FRB Catalog 2 periodicity (recover 16.35 d + scramble null)

The Second CHIME/FRB Catalog (CHIME/FRB Collaboration 2026, *ApJS* 283, 34;
AAS Open Access) lists **83 known repeaters**. `run_cat2_synthetic` plants
recoverable multi-source arrival schedules for the two repeaters with
well-published activity periods and recovers each per-source via epoch-fold
(Rayleigh Z²), with a per-source scramble null:

| source | published | recovered | err | scramble-null Z² < recovered | pass |
|---|---|---|---|---|---|
| **FRB 20180916B** | 16.35 d | 16.35 d | 0.0 d | yes | ✅ |
| FRB 20121102A | ~157 d | 157.0 d | 0.0 d | yes | ✅ |

`known_answer.recovers_16p35d = True`, `all_sources_recovery_pass = True`
(`outputs/radio/cat2_run.json`). A belt-and-suspenders test asserts
FRB 20121102A recovers near **157 d**, never collapsing onto 16.35 d.

**Real-data path** (`outputs/radio/cat2_real_run.json`): `cat2_real_sources.
load_published_cat2_bursts` was completed to mirror `frb_real_sources`
(bundled override → live/cached probe → honest-empty). A genuine live probe on
2026-07-25 returned **`PARKING_PAGE`** across all 5 canonical URLs
(`n_sources = 0`, no epoch-fold attempted, **no fabricated MJDs**). A bundled
`name,mjd` CSV can be injected via `--bundled-cat2-csv`.

*Interpretation:* FRB activity periodicity is a **natural** cycle (e.g. an
orbital / precession clock), not a message. **Periodicity is necessary, NOT
sufficient, for artificiality.**

---

## G3 — Wow! beam-fit interpretation pass (inherited; underdetermined)

The G3 Gaussian+sinc sidereal-transit fit landed earlier (Minimax); Ozma's
job here is the interpretation, not new code. The honest reading:

- The 1977 Wow! signal is a **6-sample intensity table** (`6EQUJ5`), **not** a
  time series. A 3-parameter Gaussian fit on N=6 leaves only **3 d.o.f.** —
  heavily **underdetermined**.
- There is an explicit **μ ↔ (6−μ) degeneracy** (`degeneracy_pair` sums to 6):
  a single horn cannot distinguish an ascending from a descending beam
  crossing. The fit is equally consistent with a **beam transit** or a
  **transient pulse**.
- The 2024 PHL@UPR reanalysis (arXiv:2408.08513, CC BY 4.0) attributes Wow! to
  a **hydrogen cloud near a solar-type star — a natural mechanism.**
- Conclusion: the N=6 fit yields **no statistical power** to separate transient
  from beam-crossing, and **zero** power to infer artificiality. Beam-crossing
  structure is *necessary, not sufficient*. See `outputs/radio/wow_beam_*`.

---

## Controls ledger (lab-wide negative-control rule)

| control | where | expected |
|---|---|---|
| Scramble / shuffle null | BLC1 comb, Cat2 per-source, FRB, Vela | signal must NOT survive |
| ON/OFF cadence | BLC1 (`blc1_on_off_cadence`) | RFI persists in OFF → terrestrial |
| Harmonic-family Δf | BLC1 (`blc1_delta_f_regularity`) | regular comb → intermodulation RFI |
| Uniform-noise / time-order shuffle | epoch-fold nulls | Z² stays low |

**Bottom line.** BLC1 real path → **NO_SIGNAL** (terrestrial RFI, Sheikh 2021).
Cat2 → math validated (16.35 d recovered), real data parks honestly. Wow! →
underdetermined, natural-source-consistent. No independent ET detection is
claimed anywhere. Prove the control before you whisper "signal."

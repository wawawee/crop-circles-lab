# Mission Board — Nattpasset (2026-07-25)

> Synced from Kimi’s night orders. Stance unchanged: **measure → control → report**.  
> Structure ≠ message. Mystery lab, not claims factory.

Repo: https://github.com/wawawee/crop-circles-lab (private)  
Roadmap: [`ROADMAP_BEYOND_WHEAT.md`](ROADMAP_BEYOND_WHEAT.md)  
Dashboard: [`reports/mission_dashboard.html`](reports/mission_dashboard.html)

---

## Negative control rule (ALL agents)

Before trusting a hit, run the **same** pipeline on:

1. **Shuffled / random** data of matching size & alphabet  
2. **Known hoax / human artifice** (Chualar NVIDIA, Julia log-spiral, Bower & Chorley-style)  
3. **Known natural** analogue (irrigation circles, blank rock, pulsar, shuffled genome)

If the “signal” does not separate from controls → **🔇 no signal**.

---

## Board

| ID | Owner | Mission | Deliverable | Status |
|----|-------|---------|-------------|--------|
| **N1** | **Minimax M3** (local free) | DNA/RNA 4-bit + epigenetic layer | bio_probe: SARS-CoV-2 4kb head (NC_045512.2) + chr22 3kb (NT_187395.1); **N1+ annotation-aware** per-bin shuffle control via BED4 (max-overlap classifier) → `outputs/bio/{sars_run.json, sars_notes.md, human_chr22_*.json,*.md, n1_plus_sars/{run.json,notes.md}, n1_plus_chr22/{run.json,notes.md}}` | 🟢 **landed** — whole-genome Δ_window_mean_H ≤ 0 on both (biology, NOT signal). **N1+ also landed**: BED files at `data/bio/annotations/{NC_045512.2,NT_187395.1}_regions.bed`; per-bin shuffle control (Fisher-Yates within each bin). SARS: Δ on `coding` (37 w) + `untranslated` (2 w; too_few_windows flagged honestly). chr22: BED is empty by design (ALT contig lacks curated gene models) → all 59 windows routed to `intergenic`. NO claim of hidden message. |
| **N2** | Opencode | UAP metadata forensics | Original DoD/DNI MPEG/MP4; EXIF/frame stamps; `uap_flight_consistency.py` Newton/G flags | 🟢 **landed** — WebMs gitignored; metadata poverty → g underdetermined |
| **N3** | Hermes 💤→🐛 | Dimensionless constants | α, μ, Ω… + diatonic vs nulls (decade + permutation) | 🟢 **core landed** + CKM/PMNS + 10c stress sweep + scale-invariant gap_z + `--calibrate` bootstrap per-tol floors (`outputs/constants/stress_sweep_notes.md`); **Null B (reciprocal-arrangement) is MATHEMATICALLY DEGENERATE on canonical core+mixings sets** (std(hits) = 0 across N=200 trials × 7 tols × 2 seeds) → Null B adds ZERO discrimination beyond Null A → NO defensible pair-cell signal |
| **N4** | **Opencode / Deepseek v4** (local free) | Archaeoastronomy | Flesh `astro_probe` (skyfield or documented fallback); 4 sites + crop lunar + **random site/date control** | 🟢 **landed** — astropy-backed; solstice/eq, star rise (Sirius/Pleiades/Orion), lunar from `formations.csv`, 100× random site/date controls → real 75% hit vs random 57% = no signal. `outputs/astro/run.json` |
| **N5** | Captain / Cursor | Integration dashboard | Agent status + JSON links | 🟢 bootstrap landed |
| **N0** | Hyper + Cursor | Phaistos structure | z≈−14 + period-3 refrain; metre yes, meaning no | 🟢 `dae0036` |
| **B10** | **Cursor** | Photo tamper / ELA | Pillow ELA Chualar vs field photos; tamper-only | 🟢 `outputs/forensics/ela/` |
| **B11** | **Cursor** | Cipher negative control | Native Caesar/IC (Decipher needs Rust bootstrap) | 🟢 no English cipher on Crabwood/Chilbolton |
| **R1** | Minimax follow-up | `radio_probe` scaffold | FFT/epoch-fold stub; Wow! honesty; FRB **180916** (not 121102) | ⬜ after N1 |

---

## Reuse map (don’t reinvent)

| Need | Use |
|------|-----|
| Bit / symbol streams | `tools/forensics/bitstream.py`, `tools/signal/bitstream_probe.py` |
| Window Shannon | `tools/signal/window_entropy.py` |
| Geometry ratios / diatonic | `tools/forensics/ratios.py` |
| Spatial + lunar approx | `tools/ccat/spatial_report.py` |
| Grid structure | `tools/ccat/grid_analyze.py` |
| Symbol sequences (scripts) | `tools/forensics/symbolseq.py` |
| EXIF | `tools/ccat/exif_probe.py` |
| Message registry | `tools/forensics/messages.py` |

---

## Data / ethics notes

- **Human chr1 full FASTA** is ~250MB+ — prefer a **public contig slice** + SARS-CoV-2 full genome for N1 CI; document NCBI accessions.  
- **UAP videos**: only **official DoD/DNI / public-domain releases**; no piracy; report tamper/physics, not “aliens”.  
- **Astro alignments**: always pair with **random date/site** control (roadmap rule).

---

## Agent copy-paste prompts

### N1 — Minimax M3 (local free) — DNA
> Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`. Stance: structure ≠ message.
>
> Finish `tools/bio/bio_probe.py` (scaffold exists — `--demo` already works).
> 1. Download **small** public FASTA only: SARS-CoV-2 RefSeq (NCBI) + one tiny human contig slice (NOT full chr1). Put under `data/bio/` (gitkeep + README with accessions; skip huge files).
> 2. Map A/C/G/T→2bit; optional epigenetic symbols as distinct alphabet entries.
> 3. Sliding Shannon via existing `tools/signal/window_entropy.py` + `bitstream_probe`.
> 4. Compare: coding vs annotated intergenic/"junk" vs **GC%-matched shuffle** negative.
> 5. Write `outputs/bio/run.json` + short `outputs/bio/NOTES.md` (honest: coding often lower entropy than junk; that is biology, not aliens).
> 6. Add 2–3 unit tests if easy. Update MISSION_BOARD N1 → 🟢 or 🔴 BLOCKED with reason.
> Do NOT invent epigenetic data you don't have — hook only.

**Status — N1+ work landed; successor N1++ items now deferred hardens:**
> The N1+ per-bin pipeline is wired end-to-end: real FASTA at
> `data/bio/{SARS_COV_2_NC_045512.2_head.fasta, HUMAN_chr22_3kb.fasta}` + BED at
> `data/bio/annotations/{NC_045512.2,NT_187395.1}_regions.bed`
> → `bio_probe.py --annotations …` → `outputs/bio/n1_plus_{sars,chr22}/{run.json,notes.md}`.
> Whole-genome Δ still reported (backward compat) plus per-bin (max-overlap
> classifier, Fisher-Yates *within* each bin's own letter-count pool).
>
> **Honest framing for chr22:** the BED is empty BY DESIGN — NT_187395.1 is an
> ALT contig without curated gene models. ALL 59 windows route to `intergenic`
> (single bin populated, status `ok`, Δ computed against the intergenic pool).
> Not a fabricated intergenic population.
>
> **Deferred / hardening (N1++) — NOT blockers, worth landing later:**
> 1. `_classify_window_bin` should accept `window_chrom` and skip rows whose
>    `chrom` doesn't match. Latent risk if user passes chr1 BED + chr22 FASTA
>    (currently works because our matched assets have the same chrom).
> 2. When `n_total < window`, `_per_bin_analysis` returns empty `bins` while
>    `annotation_summary` shows `features_parsed=N` — add
>    `status: "skipped_seq_too_short"` for cleaner UX.
> 3. Extend to populate the `intronic` bin when assets carry full gene models
>    (our SARS BED only has UTR + CDS rows; chr22 BED is empty by construction).
> 4. Switch the per-bin shuffle from `random.Random(seed)` to NumPy for speed
>    on chr-scale runs (millions of bases).

### N4 — Opencode / Deepseek v4 (local free) — Astro
> Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`. Stance: random site/date control mandatory.
>
> Flesh `tools/astro/astro_probe.py` (scaffold exists).
> 1. Prefer `pip install skyfield` in `.venv`; if install fails, keep pure-Python solstice/lunar and document the limitation in NOTES.
> 2. For sites already in SITES (Göbekli, Stonehenge, Giza, Chichén): solstice/equinox sun azimuth ± tolerance vs monument axis **if** an axis bearing is documented in a citation you can name — else report sun azimuth only (no fake alignments).
> 3. Lunar illumination on crop dates from `data/catalog/formations.csv` (reuse family of `spatial_report`).
> 4. **Negative control:** same pipeline on 20 random (lat,lon,date) draws — alignments must not “light up” above chance.
> 5. Output `outputs/astro/run.json` + `outputs/astro/NOTES.md`. Update MISSION_BOARD N4.
> No ancient-alien claims. Structure/alignment ≠ intent.

### B10 — Opencode follow-up (after N4)
> Light tamper/ELA screen only. Prefer Pillow JPEG ELA if stegoVeritas is painful. Run on Chualar (known hoax control) + 2 field photos from `data/images/`. Save under `outputs/forensics/`. Never report “hidden messages.”

### B11 — Cursor only (hard)
> Install/run Decipher (py3.11+ Rust) on Crabwood/Chilbolton recovered streams. Expected: no classical cipher. Document the negative.

### N3 — Hermes 💤 (relaxed — investigation mode done)
> First constants probe + CKM/PMNS extension + 10c stress sweep already landed (`outputs/constants/`).
> Per the SWEEP_TOLS verdict logic: when degenerate_count ≥ 60% of tol points AND beats_b_strict = 0, the honest answer is *"not a signal — magnitude clustering dominates"*. This applies to mixings (set=22 consts) but the core (15 consts) does survive some strict beats — see `stress_sweep_notes.md` for vour specific run.
>
> **What remains for N3+:**
> 1. Bootstrap-validate the degenerate-null detection: `perm_max - perm_mean > 1.0` is heuristic, not calibrated. Add a `gap_relative` statistic so the threshold scales with the hit-count baseline.
> 2. Add a permutation-of-tols null (after Bonferroni correction) so the “lab-internal follow-up” branch fires only when 4+/7 tols have p(B) < 0.0071, not naive 0.05.
> 3. Consider adding a Jarlskog invariant J_CKM as a proper row + re-sample the famous coincidences against the strict > bar at 10c.

### N4 — Opencode (DONE)
> `tools/astro/astro_probe.py` landed with:
> - astropy-backed solstice/equinox computation for years 0–3000 CE; fallback for BCE/early CE years (analytic precession + obliquity)
> - Sunrise azimuth at solstices for Göbekli Tepe, Stonehenge, Giza, Chichén Itzá
> - Star rise info (Sirius, Pleiades/Orion) with precession to epoch
> - Lunar illumination from `formations.csv` (11 dated formations: 1 near full moon, 3 near new moon)
> - **Random site/date control**: 100 random (lat, lon, epoch_year) pairs → 57% hit rate vs 75% real — **no separation from random**
> - Verdict: geometric structure (solstice alignments at mid-latitudes are common), not intentional signal

### R1 — Minimax follow-up (after N1)
> Scaffold `tools/radio/radio_probe.py`: FFT + autocorr + epoch-fold stub; plant known periodic train as known-answer; pulsar note as negative. Wow! = only 6 samples (say so). Use **FRB 180916** for 16.35-d cycle, not 121102. See `docs/scout_briefs.md`.

### N2 Opencode — UAP (DONE)
> Already landed — do not redo unless extending telemetry hunt.

---

*Captain Sloth / Cursor bootstrap — foliehatt → nattmössa. Hecklefish out.* 🐠

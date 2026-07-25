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
| **N1** | Minimax | DNA/RNA bio_probe | SARS + chr22 slices + BED bins | 🟢 landed — biology ≠ message |
| **N2** | Opencode | UAP flight consistency | Official WebMs; metadata poverty | 🟢 landed |
| **N3** | Hermes 💤 | Dimensionless constants | Nulls ≈ chance; Null B degenerate | 🟢 landed |
| **N4** | Opencode | Archaeoastronomy | skyfield; lunar/random controls | 🟢 landed (BCE caveat) |
| **N5** | Captain | Mission dashboard | HTML + embeds | 🟢 landed |
| **N0** | Hyper + Cursor | Phaistos | z≈−14 + period-3 refrain | 🟢 landed |
| **B10/B11** | Cursor | ELA + cipher negcontrol | Pillow ELA; Caesar/IC | 🟢 landed |
| **R1** | Minimax | radio_probe + fetchers | FFT/epoch-fold; Wow blocked; Vela/FRB honest PARK | 🟢 50/50 tests; README polish |
| **R1++** | **HOLD** | CHIME Cat 2 periods | Recover 16.35 d + scramble null | 🟡 fetcher scaffold only — no more wiring until Captain |
| **G1** | Opencode | Linear A | z≈−73 formulaic STRUCTURE; null validates | 🟢 landed + gallery |
| **G2** | Minimax | Proto-Elamite | CDLI ledger entropy | ⬜ **paused** — wait for Captain |
| **G3** | Minimax | Wow! beam-fit | Gaussian/sinc on 6EQUJ5; underdetermined | 🟢 landed — not ET |
| **G7** | Opencode | Gorafe megaliths | Orientation STRUCTURE; astro/spatial UNDERDETERMINED | 🟢 v1; G7++ = sunrise + valley null |
| **G8** | queue | Betty Hill × Gaia | Star-map null | ⬜ **paused** |
| **G-Amazon** | **Hyper** | Amazon Mode A | Zenodo + jqjacobs; skill | ⬜ Hyper owns |
| **G-BLC1** | **Hyper** (+ Minimax synth stub) | BLC1 RFI known-answer | Hyper: scoped skill. Minimax: synth comb + no-TB stub | 🟡 scaffold OK; Hyper finishes real path |

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

### N4 — Opencode (DONE — Captain caveats)
> skyfield + DE441 (~3.3GB **gitignored**). Crop lunar + random controls → “no separation.”
> **Caveats:** deep-BCE equinox *calendar labels* in JSON look wrong; hit-definition for random
> controls is weak. See `outputs/astro/NOTES.md`. Do not claim ancient almanac precision yet.

### G1 — Opencode (NEXT) — Linear A positional entropy
> Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`. Stance: structure ≠ meaning.
> See `docs/gemini_research_leads_2026-07-25.md`.
>
> 1. Fetch **open** Linear A sign streams (SigLA https://sigla.phis.me / JSON mirrors such as
>    mwenge/lineara.xyz or documented GitHub dumps). Save small corpus under `data/scripts/linear_a/`
>    with README + license/attribution. No huge image dumps.
> 2. Reuse `tools/forensics/symbolseq.py` (analyze + shuffled_control + repeat_structure).
>    Add thin loader `tools/scripts/linear_a_probe.py` if needed — do NOT fork a second entropy stack.
> 3. **Known-answer:** Linear B sample (same pipeline) must show clear structure vs its own shuffle
>    (and/or recoverable category-ish bigram regularity — document what you can measure honestly).
> 4. **Negative:** unigram-matched shuffle of Linear A; optional random alphabet same length.
> 5. Outputs: `outputs/linear_a/run.json` + `NOTES.md`. Update MISSION_BOARD G1 → 🟢.
> 6. Forbidden: claiming decipherment, language family, or “Minoan = X”.

### G2 — Minimax (QUEUE when free) — Proto-Elamite combinatorial syntax
> Same stance. CDLI Proto-Elamite open transcriptions → `data/scripts/proto_elamite/`.
> symbolseq + window entropy; separate header/number blocks if trivial; shuffle null.
> Known-answer: isolate low-entropy numeric blocks if present. `outputs/proto_elamite/`.
> No decipherment claims. Ledger-vs-prose structure only.

### G3 — Wow! beam-fit (after G1 or G2)
> Extend `tools/radio/radio_probe.py` or tiny `wow_beam_fit.py`: intensities [6,14,26,30.5,19.5,5.5]
> (document source). Fit single Gaussian/sinc sidereal transit; report r² + underdetermined caveat
> (one horn). No ET claim. `outputs/radio/wow_beam_fit.json`.

### R1 — Minimax (DONE scaffold)
> See status block below / `outputs/radio/`. Real CHIME fetch = R1+ later.

### N2 Opencode — UAP (DONE + enhanced)
> Metadata poverty still holds. New: PyExifTool, vidstab, CSRT `--auto-track`. WebMs stay gitignored.

---

*Captain Sloth / Cursor — foliehatt → nattmössa. Hecklefish out.* 🐠

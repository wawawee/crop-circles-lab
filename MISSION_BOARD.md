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
| **N1** | Hyperagent | DNA/RNA 4-bit + epigenetic layer | `bio_probe`: A/C/G/T→2bit; optional 5mC/5hmC/6mA alphabet; `window_entropy` + `bitstream_probe` on SARS-CoV-2 + tiny human contig; junk vs coding entropy vs shuffle | 🟡 scaffolded — Hyper owns full FASTA runs |
| **N2** | Opencode | UAP metadata forensics | Original DoD/DNI MPEG/MP4; EXIF/frame stamps; `uap_flight_consistency.py` Newton/G flags | 🟢 **landed** — probe + neg-controls in repo; WebMs gitignored (~42MB, see `data/uap/README.md`); verdict: metadata poverty → g-claims underdetermined (`outputs/uap/run.json`) |
| **N3** | Hermes | Dimensionless constants | α, μ, Ω… + diatonic ratio hunt vs random-magnitude controls | 🟢 **first probe done** — 30/136 watchlist-excluded diatonic hits within 20c vs Null A (decade) p50=32, Null B (pair-permutation) p50=30 → hit rate at-or-below both null medians. ‘Structure, not signal.’ `outputs/constants/*.csv\|json\|md` |
| **N4** | Kimi | Archaeoastronomy | `astro_probe`: solstice/eq/moon/stars @ Göbekli/Stonehenge/Giza/Chichén + crop dates | 🟡 scaffolded — needs astropy/skyfield |
| **N5** | Captain / Cursor | Integration dashboard | One HTML board: agent status, JSON links, mystery heatmap | 🟢 bootstrap landed |
| **N0** | Hyper → Cursor land | Beyond-vete first rabbit | `symbolseq` + Phaistos (z≈−14) + **period-3 refrain** `02 12 31 26` @ A16/A19/A22; couplet period-6; 7/7 tests | 🟢 landed locally (Hyper MCP outage; push from Cursor) |

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

### N1 Hyper — DNA
> Implement `tools/bio/bio_probe.py`. Map A/C/G/T→2 bits; optional extended alphabet for 5mC/5hmC/6mA as extra symbols. Run sliding Shannon via `window_entropy` + `bitstream_probe` on: (1) SARS-CoV-2 RefSeq FASTA, (2) a small human contig (not full chr1 in CI). Compare coding vs annotated “junk”/intergenic vs shuffled. Negative: shuffled same GC%. Commit JSON under `outputs/bio/`. Update MISSION_BOARD N1 → DONE or BLOCKED.

### N2 Opencode — UAP
> Locate official public GIMBAL/GOFAST/FLIR1 releases. Build `tools/uap/uap_flight_consistency.py` + frame EXIF via `exif_probe`. Flag unphysical accel if metadata supports it; else document metadata poverty. Negatives: known aircraft clip / synthetic ballistic. No alien claims.
>
> **N2 land (2026-07-25)**
> - Downloaded all 3 official DoD WebM files from Wikimedia Commons (public domain): GIMBAL (34s, 640×480, 16MB), GOFAST (34s, 640×480, 19MB), FLIR1 (76s, 352×264, 4.8MB)
> - `ffprobe` + `exiftool` scan: ZERO telemetry metadata (no range, FOV, GPS, platform state) in any official release
> - OpenCV frame extraction (50+ frames/video): mean entropy 4.5–4.8 bits/pixel across all three
> - `uap_flight_consistency.py` enhanced with: aircraft envelope comparison (F/A-18 7.5g structural, commercial jet 2.5g, missile 40g), synthetic negative controls (ballistic freefall ~1.1g, fighter turn ~3.6g, unphysical jerk ~2712g → flagged CRITICAL)
> - Verdict: **metadata poverty → Newton/G claims are underdetermined.** Official releases are NGA-compressed WebM with no telemetry overlay. Original ATFLIR feeds include MIL-STD-1553 telemetry (range, azimuth, elevation) but it is stripped in public releases. GOPAST resolved as parallax by AARO (2025); GIMBAL/FLIR1 remain officially "unidentified" but unanalyzable from public data.

### N3 Hermes — Constants
> `tools/astro/constants_probe.py`: table of dimensionless constants; correlation + Hawkins-style diatonic nearest-neighbor via `forensics/ratios`. Control: random constants same log-magnitude. Output `outputs/constants/feature_table.csv`.

**Hermes / N3 — first pass landed (2026-07-25)**  
- 15 fundamental dimensionless constants (CODATA / PDG / Planck) + Dirac LNH entries under `--set large`.  
- Two negative-control nulls: **(A)** log-uniform within each constant’s own decade, **(B)** reciprocal-arrangement (pair-permutation, value-permuted, name-fixed).  
- Hit totals reported **with** and **without** the famous-coincidence watchlist (selection-bias loop explicitly neutralised).  
- Derived ratios (e.g. `α/α_G`) flagged and excluded from hit counts.  
- Verdict on the current constant set: real hit rate ≈ random expectation → “structure, not signal.”  
- Tests: 16/16 passing (`python3 tools/astro/tests/test_constants_probe.py`).

### N4 Kimi — Astro
> `tools/astro/astro_probe.py` with skyfield/astropy: solstice/eq at Göbekli, Stonehenge, Giza, Chichén; lunar illum on crop dates from `formations.csv`; optional Sirius/Pleiades/Orion rise at build epochs. Random site/date control mandatory.

---

*Captain Sloth / Cursor bootstrap — foliehatt → nattmössa. Hecklefish out.* 🐠

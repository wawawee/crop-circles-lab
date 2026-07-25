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
| **N2** | Opencode | UAP metadata forensics | Original DoD/DNI MPEG/MP4; EXIF/frame stamps; `uap_flight_consistency.py` Newton/G flags | 🟡 scaffolded — needs public original files (OWNER/Opencode) |
| **N3** | Hermes | Dimensionless constants | α, μ, Ω… + diatonic ratio hunt vs random-magnitude controls | 🟡 scaffolded |
| **N4** | Kimi | Archaeoastronomy | `astro_probe`: solstice/eq/moon/stars @ Göbekli/Stonehenge/Giza/Chichén + crop dates | 🟡 scaffolded — needs astropy/skyfield |
| **N5** | Captain / Cursor | Integration dashboard | One HTML board: agent status, JSON links, mystery heatmap | 🟢 bootstrap landed |
| **N0** | Hyper (done) | Beyond-vete first rabbit | `symbolseq` + Phaistos (H structured vs shuffle, z≈−14; ≠ message) | 🟢 `1d29eea` |

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

### N3 Hermes — Constants
> `tools/astro/constants_probe.py`: table of dimensionless constants; correlation + Hawkins-style diatonic nearest-neighbor via `forensics/ratios`. Control: random constants same log-magnitude. Output `outputs/constants/feature_table.csv`.

### N4 Kimi — Astro
> `tools/astro/astro_probe.py` with skyfield/astropy: solstice/eq at Göbekli, Stonehenge, Giza, Chichén; lunar illum on crop dates from `formations.csv`; optional Sirius/Pleiades/Orion rise at build epochs. Random site/date control mandatory.

---

*Captain Sloth / Cursor bootstrap — foliehatt → nattmössa. Hecklefish out.* 🐠

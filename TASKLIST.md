# TASKLIST — Crop Circles Lab

> **AGENTS: READ THIS FILE FIRST** before changing code, downloading images, or starting analysis.
> Update task status in this file when you finish or block. Prefer small PRs / commits per task ID.

**Repo:** https://github.com/wawawee/crop-circles-lab (private)  
**Local root:** `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`  
**Stance:** Measure first. Do not claim aliens or “decoded messages” without BER / known-answer validation. Copyrighted aerials = personal research only (`data/images/ATTRIBUTION.txt`).

**Authority split:** This file owns **wheat / crop-formation tasks (A–G below)**. Frontier anomalistics (**N\*/G\*/R\***) live in [`MISSION_BOARD.md`](MISSION_BOARD.md) — do not duplicate ticket rows here. Scope / branch / PR rules below apply to **both**.

---

## Status legend

| Tag | Meaning |
|-----|---------|
| `DONE` | Landed on `main` |
| `READY` | Unblocked — pick this up |
| `BLOCKED` | Needs asset / decision / higher-res source |
| `OWNER` | Human only (purchase, legal, hardware) |

---

## 0. Orientation (every agent)

1. Read this file + `README.md` + `data/catalog/ACQUIRED_STATUS.md` + `data/catalog/TOOLS_EVAL.md`. For G\*/N\*/R\* tickets also read **SCOPE LOCK** in `MISSION_BOARD.md`.
2. Activate venv: `source .venv/bin/activate` (create via `pip install -r requirements.txt` if missing).
3. Do **not** redistribute Temporary Temples / Lucy Pringle / Getty originals.
4. Run known-answer tests after touching forensics:  
   `python tools/forensics/tests/test_ratios.py && python tools/forensics/tests/test_fractal.py && python tools/forensics/tests/test_encoding.py`
5. Prefer writing outputs under `outputs/` and notes under `data/catalog/` or this file.

### 0b. Scope & PR hygiene (all tickets)

| Rule | Detail |
|------|--------|
| **One ticket → one branch → one PR** | `feat/<id>-…` only. Never mix two missions in one diff. |
| **Allowlist paths** | `data/<domain>/`, ticket scripts/tests, `outputs/<domain>/`, surgical status row for this ID. |
| **In-scope extras OK** | Extra nulls, splits, plots, tests, deeper NOTES — **go deep** while values are in front of you. Stay under the allowlist. Additive helpers (`*_split.py`, `*_plot.py`) preferred. |
| **Out of scope** | Other probes, other tickets’ leftovers, drive-by refactors, marking other IDs done. |
| **Optional SCOPE AUDIT** | After a wild session, run the tight hygiene-only follow-up in `MISSION_BOARD.md` § *Optional SCOPE AUDIT pass* before opening the PR. |
| **Wheat vs frontier** | Update **this** file for B\*/A\* crop tasks; update **MISSION_BOARD** for G\*/N\*/R\*. |

Canonical paste-blocks (SCOPE LOCK + SCOPE AUDIT): `MISSION_BOARD.md` → *Agent ops*.

---

## A. Done (do not redo unless improving)

| ID | Item |
|----|------|
| A1 | CCAT toolkit: edges, Hough, DBSCAN cluster, swirl, dashboard, report, EXIF |
| A2 | Forensics cores: Hawkins ratios, fractal box-count, encoding (π / Crabwood plaintext / Arecibo / Julia≠z²+c) — 23/23 tests |
| A3 | Image corpus: Julia TT, Edmonton aerial, Eltopia ICCRA, Chilbolton, Milk Hill, DNA, Crabwood Sparsholt, Chualar NVIDIA control, etc. |
| A4 | Preprocess pipeline (`tools/ccat/preprocess.py`) |
| A5 | Crabwood bit sampler (`crabwood_bits.py`) — framework works; web-res BER≈0.5 |
| A6 | Chilbolton 23×73 grid sampler (`chilbolton_grid.py`) — auto-bbox crude |
| A7 | Info-theory probes (`info_theory.py`) — synthetic Julia = log-spiral ✔ |
| A8 | BLT Wayback archive: Edmonton lab + Logan Lab #79 text/photos (`data/reports/blt_wayback/`, `blt_logan/`) |
| A9 | Private GitHub repo + attribution / acquisition docs |
| A10 | `tools/signal/` — bitstream / LSB / window-entropy (Weeks multiplex + genomic-DSP heritage); 5/5 tests; L20 entropy 0.9991 reproduced |

---

## B. Crop formation tasks (status synced 2026-07-25)

### B1 — Manual Crabwood disc crop + parameter sweep — DONE ✅ (resolution floor)
**Goal:** Drive BER well below ~0.4 vs Red Collie / Vigay plaintexts.  
**Result:** Disc crop `crabwood_2002_disc_crop.png` + sweep → BER floor **~0.45–0.49**. Web-res limit; **C1** OWNER for TT master. Mislabelled `*_disc.jpg`/`disc2` — do not use.

### B2 — Chilbolton message panel: manual bbox + cell OCR — DONE ✅
**Goal:** Reliable 73×23 bitmap from `chilbolton_message_2001_tt.jpg` (or better OH).  
**Result:** `chilbolton_bbox.json`; grid export; `grid_analyze` structuredness_z≈24.5 (bitmap structure, not text).

### B3 — Finish preprocess: perspective + crop/stubble helpers — DONE ✅
**Goal:** Implement remaining hyperagent stubs properly.  
**Work:**
1. CLI for `perspective_correct` with 4 clicked/JSON corners (tramline rectangle).
2. `crop_stubble_mask` using color/Lab threshold (green standing vs tan laid).
3. Unit test on synthetic rectangle + Chualar control.
4. Edmonton `edmonton_1999.png` is oblique — produce rectified `edmonton_1999_ortho.png`.

**Acceptance:** Ortho image + mask; short note in `outputs/preprocess_edmonton.md`.

**Result (2026-07-25, Hyperagent/finasteos):** `perspective_correct` already existed; added `crop_stubble_mask` (excess-green ExG = 2G−R−B, Otsu split laid-vs-standing) and a `--corners-json` + `--stubble` CLI to `tools/ccat/preprocess.py`. Tests `tools/ccat/tests/test_preprocess.py` (3/3). Edmonton ortho landed locally: `edmonton_1999_ortho.png` + `edmonton_corners.json`.

### B4 — Circle extraction that survives wheat texture — DONE ✅ (scaffold, Hyperagent/finasteos)
**Goal:** Julia Set ~151 circles measurable (today Hough under-detects on 800px).  
**Work:**
1. Mask-first blob/contour pipeline (not raw Hough on gray).
2. Validate on synthetic log-spiral (must recover N≈150 ±10%).
3. Run on `julia_set_1996_tt_oh.jpg` + Getty; write `outputs/julia_circles.json`.
4. Feed radii into `info_theory.py` / `encoding.is_true_julia_set`.

**Acceptance:** Synthetic pass; real Julia count reported with uncertainty.

**Result (2026-07-25, Hyperagent/finasteos):** `tools/ccat/circle_extract.py` — mask-first extractor. Tests 3/3 synthetic 150/150. Local: Julia TT OH ≈152 vs 151; log-spiral not z²+c.

### B5 — Parse BLT lab texts → structured tables — DONE ✅
**Goal:** Machine-readable biophysics for Logan / Edmonton (Cherhill if found).  
**Work:**
1. Parse `data/reports/blt_wayback/logan_lab.txt` + `edmonton_labreport.txt`.
2. Extract node elongation %, expulsion cavity counts, germination notes, magnetic material mentions → `data/catalog/blt_lab_metrics.json`.
3. One-page summary `outputs/blt_lab_summary.md`.

**Acceptance:** JSON schema documented; numbers cite source line snippets.

**Result (2026-07-25):** `tools/ccat/parse_blt_labs.py` → `data/catalog/blt_lab_metrics.json` (`blt_lab_metrics.v1`) + `outputs/blt_lab_summary.md`. Caveat: BLT claims, not independent remeasurement.

### B6 — Known-hoax vs candidate classifier (lightweight) — DONE ✅ (exploratory only)
**Goal:** Features that separate Chualar (known marketing hoax) from BLT-priority cases.  
**Result:** Feature table / CSV over corpus; tiny-N sklearn exploratory — **no authenticity claim**.

### B7 — Spatial / temporal stub → real catalog CSV — DONE ✅
**Goal:** Make `spatial.py` ideas real.  
**Result (2026-07-25, Hyperagent/finasteos):** `formations.csv` + `coordinates.json` + `spatial_report.py` (haversine + synodic lunar). Wiltshire cluster near Avebury.

### B8 — Vision LLM triage hook (local) — DONE ✅
**Goal:** Use BAMBAM models via LM Studio.  
**Result:** ≥3 Qwen2.5-VL JSONs under `outputs/vision/` (Crabwood disc, Chilbolton, Chualar).

### B9 — Grid structure analyzer ("is this grid encoding info?") — DONE ✅ (Hyperagent/finasteos)
**Goal:** Operationalize the GLYPH question — does a binary formation grid carry structure, and what kind — as scriptable, testable metrics (not a browser toy).  
**Work:** Shannon entropy, bit balance, row/col autocorrelation period, 2D-FFT peakiness, mirror/rot symmetry, and an "absence signal" (neighbour-agreement z-score vs density-matched shuffles). Verdict string; numpy-only.  
**Acceptance:** Known-answer tests separate random vs periodic/symmetric/blocky grids.

**Result (2026-07-25, Hyperagent/finasteos):** `tools/ccat/grid_analyze.py` + tests (6/6). Chilbolton → structuredness_z≈24.5. Structure ≠ message.

### B10 — Tamper / ELA forensics on photos (hoax screen) — DONE ✅ (Cursor, Pillow ELA)
**Goal:** Screen photographs for digital manipulation (splices, resaves) — HOAX detector, NOT message extractor.  
**Result (2026-07-25):** `tools/ccat/ela_screen.py` + known-answer splice test (pass). Batch: Chualar + Julia + Crabwood + Chilbolton → `outputs/forensics/ela/`.  
**Reading:** Field TT web JPEGs are mildly elevated vs Chualar PNG control — **expected multi-generation compression**, not proof of formation fakery. Use ELA for crude Photoshop splices in stills, not circle authentication. stegoVeritas optional later; Pillow path is enough for lab rule.

### B11 — Classical-cipher NEGATIVE CONTROL — DONE ✅ (Cursor, native screen)
**Goal:** Classical ciphers should **not** crack recovered streams.  
**Result (2026-07-25):** `tools/ccat/cipher_negcontrol.py` — Caesar χ² + IC; known-answer Caesar-3 + noise negative + planted ASCII (pass). Crabwood disc-crop bits + Chilbolton 73×23 → **no English cipher** (`outputs/cipher_negcontrol.json`).  
**Note:** PyPI `decipher` ≠ matthewdgreen; full Decipher needs Rust `bootstrap.sh` (bare pip → broken `cli`). Native screen satisfies the negative-control rule.
---

## C. BLOCKED / OWNER

| ID | Item | Blocker |
|----|------|---------|
| C1 | High-res Crabwood disc master | Temporary Temples purchase / higher scan — **OWNER** |
| C2 | Cherhill 1993 iron-glaze lab HTML + micrographs | Lab #104 PHP still 404; **partial DONE** — JSE 1995 text archived + Physiol. Plant. DOIs (1994/1999) in `levengood_citations.json`. PDF/EDS still OWNER |
| C3 | True overhead Logan / Eltopia hi-res | Not found public; ICCRA Eltopia is 300×227 only |
| C4 | Public release of TT/Lucy/Getty images | Must stay private / attributed — **OWNER** legal |

### C2 — progress (2026-07-25, partial)
- ✅ Wayback: `semi_molten_iron_blt` + `anatomical_anomalies_blt` under `data/reports/blt_wayback/`.
- ✅ Crossref DOIs: Levengood 1994 `10.1034/j.1399-3054.1994.920223.x` (Physiol. Plant. 92:356–363); Levengood & Talbott 1999 `10.1034/j.1399-3054.1999.105404.x`; 2001 comment DOIs logged.
- ✅ Fe claim inventory: hematite Fe₂O₃ + magnetite Fe₃O₄ glaze language in JSE/BLT text → `data/catalog/levengood_citations.json`, memo `outputs/levengood_cherhill_sources.md`.
- ⏳ OWNER: PDFs into `data/reports/papers/`; independent EDS/XRD if material exists.
- Lab #104 HTML: still missing public.

---

## D. Parallel split — remote vs local (2026-07-25)

> **Note:** Main image corpus (~60 files under `data/images/`) **is** in the private GitHub repo. Only `data/images/_hires/` is local-only. Remote agents can run CV/ML on tracked images.

| Agent / session | Tasks | Where |
|-----------------|-------|-------|
| **Remote — CV/analysis scaffold** | ~~B4~~ ✅, ~~B3~~ ✅, ~~B9~~ ✅; **B6** (needs images → local-preferred) | Hyperagent / GitHub |
| **Remote — encoding prep** | B1/B2 CLI flags + bbox JSON schema only | Hyperagent |
| **Remote — research** | C3 hunt; C2 tail (text/DOI memo) | Hyperagent |
| **Local Cursor — encoding** | **B1** disc crop + BER sweep; **B2** Chilbolton bbox; **B11** cipher negative-control (Decipher, py3.11+Rust) | Here (judgment) |
| **Local Cursor — forensics** | **B10** tamper/ELA screen over `data/images/` | Here (images on disk) |
| **Local Cursor — vision** | **B8** LM Studio / BAMBAM models | Here (hardware) |
| **Local Cursor — finish B3** | Edmonton corner-JSON → ortho (CLI now landed) | Here |
| **Captain (human)** | C1 (TT master), C4 (legal), PDF OWNER for C2 | Human only |

---

## E. Definition of “interesting information”

We treat a finding as interesting only if **one** of:

1. Independent bit recovery matches published plaintext with BER ≪ 0.25, **or**
2. Geometry ratios pass known-answer tests and replicate on rectified imagery, **or**
3. Lab metrics are transcribed with citations and survive CICAP-style methodology notes, **or**
4. A control (Chualar) cleanly separates on features while candidates do not look identical, **or**
5. A bitstream/LSB probe shows structure that survives shuffle controls (entropy/reshape/ASCII) — authorship still open.

Otherwise: file under `outputs/` as negative / inconclusive — still valuable.

---

## F. Quick commands cheat sheet

```bash
cd /Users/perbrinell/Documents/TIN-STUDY/crop-circles
source .venv/bin/activate

python tools/forensics/tests/test_encoding.py
python tools/ccat/preprocess.py data/images/chualar_2013_nvidia_hoax.png --out outputs/chualar_mask.png
python tools/ccat/preprocess.py data/images/edmonton_1999.png --corners-json data/catalog/edmonton_corners.json --stubble
python tools/ccat/circle_extract.py                      # synthetic self-check (150/150)
python tools/ccat/circle_extract.py data/images/julia_set_1996_tt_oh.jpg --out outputs/julia_circles.json
python tools/ccat/grid_analyze.py                        # random-vs-stripes demo
python tools/ccat/grid_analyze.py outputs/chilbolton_grid.json
python tools/ccat/tests/test_circle_extract.py
python tools/ccat/tests/test_preprocess.py
python tools/ccat/tests/test_grid_analyze.py
python tools/ccat/crabwood_bits.py data/images/crabwood_2002_tt_disc.jpg --out outputs/crabwood_bits.json
python tools/ccat/chilbolton_grid.py data/images/chilbolton_message_2001_tt.jpg --out outputs/chilbolton_grid.json
python tools/ccat/info_theory.py --synthetic-julia
python tools/ccat/blt_archive.py --out data/reports/blt_wayback
python tools/ccat/spatial_report.py
python tools/ccat/parse_blt_labs.py
python tools/signal/bitstream_probe.py --demo-multiplex --out outputs/signal/multiplex_l20.json
python tools/signal/lsb_probe.py data/images/chualar_2013_nvidia_hoax.png --out outputs/signal/chualar_lsb.json
python tools/signal/tests/test_bitstream.py
```

When finishing a task: update the status line for that ID in this file, commit, push.

---

## G. External tools evaluated

See **`data/catalog/TOOLS_EVAL.md`** for the full honest triage of the proposed third-party tool list. Summary: KEEP = GLYPH-style grid analysis (built natively as B9); MAYBE = classical-cipher solvers (B11, as negative controls) + steganalysis (B10, photo tamper-forensics only, never "message extraction"); SKIP = all DNA-genomics / DNA-storage tools and ancient-script decoders (category errors — crop circles have no real DNA or matching symbol corpus). Repo verification complete (2026-07-25): Decipher + stegoVeritas verified real; DecryptionToolkeet is deleted (404); ST3GG / StegMaster / StegoForge skipped as unmaintained/offensive.

**Local complement:** `tools/signal/` (A10) reuses *ideas* from the Weeks multiplex + genomic-DSP Shannon windows as **generic bitstream/LSB probes** (not DNA pipelines) — sits beside B10/B11 for message-hunting on recovered bits.

---

*Last updated: 2026-07-27 — §0b scope/PR hygiene + authority split. SCOPE LOCK / SCOPE AUDIT on MISSION_BOARD for agent paste.*

# TASKLIST — Crop Circles Lab

> **AGENTS: READ THIS FILE FIRST** before changing code, downloading images, or starting analysis.
> Update task status in this file when you finish or block. Prefer small PRs / commits per task ID.

**Repo:** https://github.com/wawawee/crop-circles-lab (private)  
**Local root:** `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`  
**Stance:** Measure first. Do not claim aliens or “decoded messages” without BER / known-answer validation. Copyrighted aerials = personal research only (`data/images/ATTRIBUTION.txt`).

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

1. Read this file + `README.md` + `data/catalog/ACQUIRED_STATUS.md` + `data/catalog/TOOLS_EVAL.md`.
2. Activate venv: `source .venv/bin/activate` (create via `pip install -r requirements.txt` if missing).
3. Do **not** redistribute Temporary Temples / Lucy Pringle / Getty originals.
4. Run known-answer tests after touching forensics:  
   `python tools/forensics/tests/test_ratios.py && python tools/forensics/tests/test_fractal.py && python tools/forensics/tests/test_encoding.py`
5. Prefer writing outputs under `outputs/` and notes under `data/catalog/` or this file.

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

## B. READY — pick up / delegate

### B1 — Manual Crabwood disc crop + parameter sweep
**Goal:** Drive BER well below ~0.4 vs Red Collie / Vigay plaintexts.  
**Why blocked before:** Auto spiral on ~600px TT disc = random bits.  
**Work:**
1. From `crabwood_2002_tt_oh2.jpg` / `*_disc*.jpg`, manually crop the **data disc only** (square, centered).
2. Save as `data/images/crabwood_2002_disc_crop.png`.
3. Extend `crabwood_bits.py` to accept `--cx --cy --r --turns --r-inner` and sweep turns ∈ {8…20}, polarity, MSB.
4. Log best BER + recovered preview to `outputs/crabwood_sweep.json`.
5. Update this file: mark B1 `DONE` or `BLOCKED` (need paid TT master).

**Acceptance:** Documented best BER; if still ≥0.4, note resolution floor and stop.

### B2 — Chilbolton message panel: manual bbox + cell OCR
**Goal:** Reliable 73×23 bitmap from `chilbolton_message_2001_tt.jpg` (or better OH).  
**Work:**
1. Draw/record bbox JSON: `data/catalog/chilbolton_bbox.json` `{x0,y0,x1,y1}`.
2. Wire bbox into `chilbolton_grid.py`.
3. Export `outputs/chilbolton_bits_73x23.png` + `.json`.
4. Diff structural regions vs published Arecibo reply (Si / helix / figure height) — cite `forensics.encoding`.
5. Run `grid_analyze.py` (B9) on the exported grid as a structure sanity check.

**Acceptance:** Stable grid across slight bbox jitter; overlay committed.

### B3 — Finish preprocess: perspective + crop/stubble helpers — scaffold DONE ✅ (Edmonton ortho left to local)
**Goal:** Implement remaining hyperagent stubs properly.  
**Work:**
1. CLI for `perspective_correct` with 4 clicked/JSON corners (tramline rectangle).
2. `crop_stubble_mask` using color/Lab threshold (green standing vs tan laid).
3. Unit test on synthetic rectangle + Chualar control.
4. Edmonton `edmonton_1999.png` is oblique — produce rectified `edmonton_1999_ortho.png`.

**Acceptance:** Ortho image + mask; short note in `outputs/preprocess_edmonton.md`.

**Result (2026-07-25, Hyperagent/finasteos):** `perspective_correct` already existed; added `crop_stubble_mask` (excess-green ExG = 2G−R−B, Otsu split laid-vs-standing) and a `--corners-json` + `--stubble` CLI to `tools/ccat/preprocess.py`. Tests `tools/ccat/tests/test_preprocess.py` (3/3): rectification fills frame >0.9; ExG splits green/tan >0.8 vs <0.2; corner-JSON loader. Edmonton ortho intentionally left to LOCAL — needs hand-picked corners: create `data/catalog/edmonton_corners.json` `{"corners":[[x,y] TL,TR,BR,BL]}` then `python tools/ccat/preprocess.py data/images/edmonton_1999.png --corners-json data/catalog/edmonton_corners.json --stubble`.

### B4 — Circle extraction that survives wheat texture — DONE ✅ (scaffold, Hyperagent/finasteos)
**Goal:** Julia Set ~151 circles measurable (today Hough under-detects on 800px).  
**Work:**
1. Mask-first blob/contour pipeline (not raw Hough on gray).
2. Validate on synthetic log-spiral (must recover N≈150 ±10%).
3. Run on `julia_set_1996_tt_oh.jpg` + Getty; write `outputs/julia_circles.json`.
4. Feed radii into `info_theory.py` / `encoding.is_true_julia_set`.

**Acceptance:** Synthetic pass; real Julia count reported with uncertainty.

**Result (2026-07-25, Hyperagent/finasteos):** `tools/ccat/circle_extract.py` — mask-first extractor (binarize → external contours → circularity+radius filter → `minEnclosingCircle`), NOT raw Hough. Tests `tools/ccat/tests/test_circle_extract.py` (3/3): synthetic log-spiral of 150 non-overlapping shrinking circles recovered **150/150 (0% err)**; 3 clean circles → correct radii; random salt texture → <40 blobs (no Hough-explosion). Steps 3–4 left for LOCAL where images are on disk: `python tools/ccat/circle_extract.py data/images/julia_set_1996_tt_oh.jpg --out outputs/julia_circles.json`.

### B5 — Parse BLT lab texts → structured tables — DONE ✅
**Goal:** Machine-readable biophysics for Logan / Edmonton (Cherhill if found).  
**Work:**
1. Parse `data/reports/blt_wayback/logan_lab.txt` + `edmonton_labreport.txt`.
2. Extract node elongation %, expulsion cavity counts, germination notes, magnetic material mentions → `data/catalog/blt_lab_metrics.json`.
3. One-page summary `outputs/blt_lab_summary.md`.

**Acceptance:** JSON schema documented; numbers cite source line snippets.

**Result (2026-07-25):** `tools/ccat/parse_blt_labs.py` → `data/catalog/blt_lab_metrics.json` (`blt_lab_metrics.v1`) + `outputs/blt_lab_summary.md`. Logan #79 (KS-03-131): node expansion 15–65%, expulsion cavities, diameters 30.4/58 ft. Edmonton #122 (KS-04-176): 7-circle, bent nodes 40–120°, magnetic particles, microwave heating claim. Cherhill metrics pulled from archived JSE/BLT semi-molten page (lab #104 HTML still 404). Caveat baked into JSON: BLT claims, not independent remeasurement.

### B6 — Known-hoax vs candidate classifier (lightweight) — **REMOTE PRIMARY**
**Goal:** Features that separate Chualar (known marketing hoax) from BLT-priority cases.  
**Work:**
1. Feature vector: edge ratio, symmetry, fractal D, circle/line ratio, entropy.
2. Table over current corpus → `outputs/feature_table.csv` (extend `report.py`).
3. Simple sklearn baseline (logistic / RF) — **report as exploratory only**.

**Acceptance:** CSV + short caveats (tiny N, no claim of authenticity).
**Delegate:** Yes — tracked images in repo include Chualar + priority set.
**Note (2026-07-25, Hyperagent):** Bulk-pulling the ~60 image binaries through the GitHub MCP is impractical (per-file raw tokens expire fast; no shell `git clone` from the sandbox). B6 is best run LOCALLY in Cursor (images on disk), or remotely on a small hand-picked subset. `circle_extract.py` (B4) + `preprocess.py` (B3) + `grid_analyze.py` (B9) now provide clean feature inputs.

### B7 — Spatial / temporal stub → real catalog CSV — DONE ✅
**Goal:** Make `spatial.py` ideas real.  
**Work:**
1. `data/catalog/formations.csv` with id, lat, lon, date, tags, image path (from `priority_formations.json`).
2. Monument distances (Stonehenge, Avebury, Chilbolton, …).
3. Optional lunar phase via astropy for dated rows.

**Acceptance:** CSV + script `tools/ccat/spatial_report.py` printing nearest monument.

**Result (2026-07-25, Hyperagent/finasteos):** Landed `data/catalog/formations.csv` (12 formations), `data/catalog/coordinates.json` (approx coords, precision-flagged), and `tools/ccat/spatial_report.py`. Nearest-monument via inline haversine (no geopy). Moon illumination via a pure-Python synodic approximation (dropped astropy: 5.3 breaks on numpy 2 under py3.9, and 6.x needs py3.10 — validated: Windmill Hill Triple Julia 1996-07-29 → 0.97 near full [full moon 30 Jul 1996 ✓]; DNA 1996-06-17 → 0.01 near new [new moon 15 Jun 1996 ✓]). Wiltshire cluster = 7/12 within 30 km of Avebury; 4 non-UK sites have no monument in set. NOTE: coords approximate — verify `allington-cube-1999`.

### B8 — Vision LLM triage hook (local)
**Goal:** Use BAMBAM models via LM Studio.  
**Work:**
1. Document load steps for `Qwen2.5-VL-7B` / `GLM-4.6V-Flash` in `data/catalog/VISION_MODELS.md`.
2. Run `vision_probe.py` on Crabwood disc crop + Chilbolton + Chualar; save JSON under `outputs/vision/`.
3. Prompt must ask for countable geometry only (no alien claims).

**Acceptance:** ≥3 vision JSON outputs committed.

### B9 — Grid structure analyzer ("is this grid encoding info?") — DONE ✅ (Hyperagent/finasteos)
**Goal:** Operationalize the GLYPH question — does a binary formation grid carry structure, and what kind — as scriptable, testable metrics (not a browser toy).  
**Work:** Shannon entropy, bit balance, row/col autocorrelation period, 2D-FFT peakiness, mirror/rot symmetry, and an "absence signal" (neighbour-agreement z-score vs density-matched shuffles). Verdict string; numpy-only.  
**Acceptance:** Known-answer tests separate random vs periodic/symmetric/blocky grids.

**Result (2026-07-25, Hyperagent/finasteos):** `tools/ccat/grid_analyze.py` + `tools/ccat/tests/test_grid_analyze.py` (6/6). Demo: random 73×23 → "random-like"; period-4 stripes → "structured: periodic ~4, spectral peak, symmetry, z=15.6". Feed the B2 Chilbolton bitmap in: `python tools/ccat/grid_analyze.py outputs/chilbolton_grid.json`. **Stance:** detects structure; does NOT "decode messages" — a high score means "worth a look," never "aliens." See `data/catalog/TOOLS_EVAL.md`.

### B10 — Tamper / ELA forensics on photos (hoax screen) — LOCAL (delegate: Cursor / opencode)
**Goal:** Screen the actual photographs for digital manipulation (splices, resaves) — a HOAX detector, NOT a hidden-message extractor. Complements EXIF + ELA in `metadata`.  
**Work:**
1. Run **stegoVeritas** (VERIFIED: github.com/bannsec/stegoVeritas, `pip install stegoveritas`) over `data/images/` (esp. the Chualar known-hoax control + any orb/BOL stills): `stegoveritas IMG.jpg -meta -exif -xmp -imageTransform -trailing -carve -out outputs/forensics/<id>`. Do NOT use `-bruteLSB` / `-password`.
2. Save per-image JSON/PNG under `outputs/forensics/`.
3. Report ELA / JPEG-ghost anomalies; known edits should light up as calibration.

**Guard:** Any "hidden message" output on a field photo is a false positive on noise — report **tamper signals only**.  
**Why local:** needs the ~60 image binaries on disk.

### B11 — Classical-cipher NEGATIVE CONTROL on recovered streams — LOCAL (delegate: Cursor)
**Goal:** Throw classical ciphers/decoders at the recovered Crabwood/Chilbolton bit/symbol streams. Expectation: they should **not** crack (Crabwood = plain 8-bit ASCII; Arecibo = bitmap). Failure is the informative, expected result; a clean crack would be surprising.  
**Work:** Feed `outputs/crabwood_bits.json` / chilbolton symbol streams into **Decipher** (VERIFIED: github.com/matthewdgreen/decipher; `decipher diagnose` then `decipher crack`) and log "no classical cipher found" as a documented negative in `outputs/`. (DecryptionToolkeet was proposed but its repo is 404/deleted — skip it.)  
**Env:** Decipher is GPL-3.0 and needs Python 3.11+ + Rust/C toolchain → run LOCAL, not the py3.9 sandbox.  
**Note:** value is as a control; do not manufacture a "solution."

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

*Last updated: 2026-07-25 — Night-shift bootstrap: `MISSION_BOARD.md` + Captain dashboard; scaffolds N1–N4 (`bio`/`uap`/`astro`). Hyper: Phaistos `symbolseq` DONE. See mission board for owners.*

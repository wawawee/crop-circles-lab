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

1. Read this file + `README.md` + `data/catalog/ACQUIRED_STATUS.md`.
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

**Acceptance:** Stable grid across slight bbox jitter; overlay committed.

### B3 — Finish preprocess: perspective + crop/stubble helpers
**Goal:** Implement remaining hyperagent stubs properly.  
**Work:**
1. CLI for `perspective_correct` with 4 clicked/JSON corners (tramline rectangle).
2. `crop_stubble_mask` using color/Lab threshold (green standing vs tan laid).
3. Unit test on synthetic rectangle + Chualar control.
4. Edmonton `edmonton_1999.png` is oblique — produce rectified `edmonton_1999_ortho.png`.

**Acceptance:** Ortho image + mask; short note in `outputs/preprocess_edmonton.md`.

### B4 — Circle extraction that survives wheat texture
**Goal:** Julia Set ~151 circles measurable (today Hough under-detects on 800px).  
**Work:**
1. Mask-first blob/contour pipeline (not raw Hough on gray).
2. Validate on synthetic log-spiral (must recover N≈150 ±10%).
3. Run on `julia_set_1996_tt_oh.jpg` + Getty; write `outputs/julia_circles.json`.
4. Feed radii into `info_theory.py` / `encoding.is_true_julia_set`.

**Acceptance:** Synthetic pass; real Julia count reported with uncertainty.

### B5 — Parse BLT lab texts → structured tables — DONE ✅
**Goal:** Machine-readable biophysics for Logan / Edmonton (Cherhill if found).  
**Work:**
1. Parse `data/reports/blt_wayback/logan_lab.txt` + `edmonton_labreport.txt`.
2. Extract node elongation %, expulsion cavity counts, germination notes, magnetic material mentions → `data/catalog/blt_lab_metrics.json`.
3. One-page summary `outputs/blt_lab_summary.md`.

**Acceptance:** JSON schema documented; numbers cite source line snippets.

**Result (2026-07-25):** `tools/ccat/parse_blt_labs.py` → `data/catalog/blt_lab_metrics.json` (`blt_lab_metrics.v1`) + `outputs/blt_lab_summary.md`. Logan #79 (KS-03-131): node expansion 15–65%, expulsion cavities, diameters 30.4/58 ft. Edmonton #122 (KS-04-176): 7-circle, bent nodes 40–120°, magnetic particles, microwave heating claim. Cherhill metrics pulled from archived JSE/BLT semi-molten page (lab #104 HTML still 404). Caveat baked into JSON: BLT claims, not independent remeasurement.

### B6 — Known-hoax vs candidate classifier (lightweight)
**Goal:** Features that separate Chualar (known marketing hoax) from BLT-priority cases.  
**Work:**
1. Feature vector: edge ratio, symmetry, fractal D, circle/line ratio, entropy.
2. Table over current corpus → `outputs/feature_table.csv` (extend `report.py`).
3. Simple sklearn baseline (logistic / RF) — **report as exploratory only**.

**Acceptance:** CSV + short caveats (tiny N, no claim of authenticity).

### B7 — Spatial / temporal stub → real catalog CSV — DONE ✅
**Goal:** Make `spatial.py` ideas real.  
**Work:**
1. `data/catalog/formations.csv` with id, lat, lon, date, tags, image path (from `priority_formations.json`).
2. Monument distances (Stonehenge, Avebury, Chilbolton, …).
3. Optional lunar phase via astropy for dated rows.

**Acceptance:** CSV + script `tools/ccat/spatial_report.py` printing nearest monument.

**Result (2026-07-25, Hyperagent/finasteos):** Landed `data/catalog/formations.csv` (12 formations), `data/catalog/coordinates.json` (approx coords, precision-flagged), and `tools/ccat/spatial_report.py`. Nearest-monument via inline haversine (no geopy). Moon illumination via a pure-Python synodic approximation (dropped astropy: 5.3 breaks on numpy 2 under py3.9, and 6.x needs py3.10 — the approximation runs anywhere and was validated: Windmill Hill Triple Julia 1996-07-29 → 0.97 near full [full moon 30 Jul 1996 ✓]; DNA 1996-06-17 → 0.01 near new [new moon 15 Jun 1996 ✓]). Wiltshire cluster = 7/12 within 30 km of Avebury; 4 non-UK sites (Logan/Edmonton/Eltopia/Chualar) have no monument in our set. NOTE: coords are approximate — verify `allington-cube-1999` before leaning on its distance.

### B8 — Vision LLM triage hook (local)
**Goal:** Use BAMBAM models via LM Studio.  
**Work:**
1. Document load steps for `Qwen2.5-VL-7B` / `GLM-4.6V-Flash` in `data/catalog/VISION_MODELS.md`.
2. Run `vision_probe.py` on Crabwood disc crop + Chilbolton + Chualar; save JSON under `outputs/vision/`.
3. Prompt must ask for countable geometry only (no alien claims).

**Acceptance:** ≥3 vision JSON outputs committed.

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

## D. Suggested delegation batches

| Agent / session | Tasks |
|-----------------|-------|
| **CV engineer** | B3, B4 |
| **Crypto / encoding** | B1, B2 |
| **Data wrangler** | B5 ✅, C2 partial (B7 ✅) — next: B6 or image tasks |
| **ML lite** | B6 |
| **Local vision** | B8 |
| **Captain (human)** | C1, C4, prioritize which READY next |

---

## E. Definition of “interesting information”

We treat a finding as interesting only if **one** of:

1. Independent bit recovery matches published plaintext with BER ≪ 0.25, **or**
2. Geometry ratios pass known-answer tests and replicate on rectified imagery, **or**
3. Lab metrics are transcribed with citations and survive CICAP-style methodology notes, **or**
4. A control (Chualar) cleanly separates on features while candidates do not look identical.

Otherwise: file under `outputs/` as negative / inconclusive — still valuable.

---

## F. Quick commands cheat sheet

```bash
cd /Users/perbrinell/Documents/TIN-STUDY/crop-circles
source .venv/bin/activate

python tools/forensics/tests/test_encoding.py
python tools/ccat/preprocess.py data/images/chualar_2013_nvidia_hoax.png --out outputs/chualar_mask.png
python tools/ccat/crabwood_bits.py data/images/crabwood_2002_tt_disc.jpg --out outputs/crabwood_bits.json
python tools/ccat/chilbolton_grid.py data/images/chilbolton_message_2001_tt.jpg --out outputs/chilbolton_grid.json
python tools/ccat/info_theory.py --synthetic-julia
python tools/ccat/blt_archive.py --out data/reports/blt_wayback
python tools/ccat/spatial_report.py
python tools/ccat/parse_blt_labs.py
```

When finishing a task: update the status line for that ID in this file, commit, push.

---

*Last updated: 2026-07-25 — B5 DONE + C2 partial (Levengood DOIs / Fe inventory). Open READY: B1–B4, B6, B8.*

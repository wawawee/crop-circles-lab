# Mission G18 — EAMENA ley-line null (ASSIGNED to Freebuff / DeepSeek v4 flash)

You are **Freebuff** on crop-circles-lab (ANOMALISTIK). Model: DeepSeek v4 flash. Stance: **structure ≠ meaning**. Measure → control → report. Honest prior = **no-signal** (chance-alignment FPR calibration).

**Context (leave alone):**
- G15 Cretan → PR #15
- G13 VASCO → PR #16 (Opencode)
- G14 Chankillo → PR #17 (your previous — do NOT reopen)

Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`
Brief: `docs/research_leads_kimi_2026-07-25.md` (G18) + board row G18.
Reuse: `tools/ccat/spatial_report.py`, Amazon Mode A / Gorafe spatial null patterns if present. GeoJSON subsets first — **not** full 338k dump day-one.

## Do NOT touch
G13/G14/G15 branches & PRs, Voynich, radio, BLC1, Amazon reopen, Meroitic, Linear Elamite.

## Git hygiene
1. `git fetch origin && git checkout main && git pull && git checkout -b feat/g18-eamena-ley-null`
2. Surgical board row for **G18 only**.
3. Rebase on `main` before PR. Cursor merges.

## Deliver
1. Ingest a **small** EAMENA GeoJSON subset (document provenance + license in `data/geo/eamena/README.md`). If bulk dump blocked: synthetic site cloud with known CSR geometry + honest BLOCKED note for full corpus.
2. Probe `tools/scripts/eamena_ley_null.py`: nearest-neighbor / alignment / “ley” line false-positive rate vs CSR / scrambled-coord nulls.
3. **Mandatory:** report chance-alignment FPR; if “leys” do not beat null → **NO_SIGNAL**.
4. Outputs: `outputs/eamena/{run.json,NOTES.md}`.
   Verdict: NO_SIGNAL | UNDERDETERMINED | STRUCTURE_SIGNAL (rare; must survive nulls).
5. Tests ≥12 under `tools/scripts/tests/test_eamena_ley_null.py`. Forbidden-phrase guard (no “ancient highways,” “ET corridors,” “proves ley network”).
6. Branch `feat/g18-eamena-ley-null`. Open PR → Cursor.

## Forbidden
Aliens, ley-line mysticism as truth, silent fabrication of EAMENA features, full 338k ingest without subset discipline.

Start now. Work until PR ready or honest BLOCKED in NOTES.md.

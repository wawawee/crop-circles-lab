# Mission G14 — Chankillo Thirteen Towers (ASSIGNED to Freebuff, same session)

You are **Freebuff** on crop-circles-lab (ANOMALISTIK). Stance: **structure ≠ meaning**. Measure → control → report.

**Context:** G15 Cretan is already in **PR #15** (`feat/g15-cretan-hieroglyphic`) — do NOT reopen it. This is your next ticket in the **same session**.

Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`
Brief: `docs/research_leads_anomalistics_2026-07-25.md` (G14).
Warm after N4++: reuse patterns from `tools/astro/astro_probe.py`, `tools/astro/archaeo_probe.py`, Gorafe/N4++ horizon logic where useful.
Cite: Ghezzi & Ruggles 2007 (Thirteen Towers solar/lunar).

## Do NOT touch
- G13 VASCO / PR #16 / `feat/g13-vasco` (Opencode)
- G15 Cretan / PR #15 (your previous — leave alone)
- Voynich, radio, BLC1, Amazon, Meroitic, Linear Elamite

## Git hygiene
1. Start from fresh `main`: `git fetch origin && git checkout main && git pull && git checkout -b feat/g14-chankillo`
2. Surgical board row only for **G14** (do not rewrite other agents' rows).
3. Rebase on `main` before PR. Author ≠ sole merger → Cursor merges.

## Deliver
1. Ingest tower coordinates / site geometry (+ DEM if obtainable): OpenTopography or Copernicus DEM ~30m → `data/astro/chankillo/` + README (attribution + license). If DEM blocked: honest BLOCKED/UNDERDETERMINED with synthetic ridge null still run.
2. Probe `tools/scripts/chankillo_probe.py`: horizon solar/lunar azimuths @ ~300 BCE (JPL Horizons / skyfield). Solstice structure expected; lunar = underdetermined prior.
3. **Mandatory null:** synthetic ridge / scrambled tower azimuths / random horizon control.
4. Outputs: `outputs/chankillo/{run.json,NOTES.md}`.
   Verdict vocab: ORIENTATION_STRUCTURE | NO_SIGNAL | UNDERDETERMINED | CONTROL_SEPARATED — never calendar-decipherment / ET.
5. Tests ≥12 under `tools/scripts/tests/test_chankillo_probe.py`.
6. Branch `feat/g14-chankillo`. Open PR → Cursor. Update **only** G14 board row when landed.

## Forbidden
Aliens, “proves solstice calendar of X culture” overclaim beyond measured azimuth structure, silent fake DEM.

Start now. Same session — stay focused on G14 until PR or honest BLOCKED in NOTES.md.

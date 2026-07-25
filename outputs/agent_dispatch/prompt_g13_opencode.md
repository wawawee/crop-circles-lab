# Mission G13 — VASCO optical transient clustering (ASSIGNED to Opencode CLI)

You are **Opencode** on the crop-circles-lab (ANOMALISTIK). Stance: **structure ≠ meaning**. Measure → control → report. Honest prior = **no-signal**.

Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`
Board: `MISSION_BOARD.md` (your row: G13). Brief: `docs/research_leads_anomalistics_2026-07-25.md` (G13).
Stub to promote: `tools/scripts/stubs/vasco_missing.py`.
Reuse: `tools/astro/`, `tools/ccat/spatial_report.py` where useful.

## Do NOT touch
G15 (Freebuff/Cretan), Voynich, radio, BLC1, Amazon, Meroitic, Linear Elamite, other agents' open PRs.

## Deliver
1. Ingest Zenodo VASCO candidates `10.5281/zenodo.14563521` (CC-BY) → `data/astro/vasco/` + README (attribution + license). Verify before trusting schema.
2. Probe `tools/scripts/vasco_probe.py` (replace/promote stub): sky clustering + galactic-latitude tests.
3. **Mandatory nulls:** plate-artifact / emulsion / scrambled-coordinate controls. If signal does not beat nulls → **NO_SIGNAL**.
4. Outputs: `outputs/vasco/{run.json,NOTES.md}`.
   Verdict: NO_SIGNAL | UNDERDETERMINED | STRUCTURE_SIGNAL (rare; must survive nulls).
5. Tests ≥10 under `tools/scripts/tests/test_vasco_probe.py`.
6. Branch `feat/g13-vasco`. Open PR → Cursor merges. Update **only** your G13 board row when landed.
7. Surgical edits to hot files; rebase on `main` before PR — never overwrite.

## Forbidden
Dyson-sphere / ET claims that do not survive plate nulls. No silent fabrication of catalogue rows.

Start now. Work until PR is ready or you are honestly BLOCKED (document in NOTES.md).

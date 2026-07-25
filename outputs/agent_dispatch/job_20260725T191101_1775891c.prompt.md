# Mission G15 — Cretan Hieroglyphic bipartite admin (ASSIGNED to Freebuff)

You are **Freebuff** on the crop-circles-lab (ANOMALISTIK). Stance: **structure ≠ meaning**. Measure → control → report. No decipherment claims.

Repo: `/Users/perbrinell/Documents/TIN-STUDY/crop-circles`
Board: `MISSION_BOARD.md` (your row: G15). Brief: `docs/research_leads_anomalistics_2026-07-25.md` (G15).
Reuse: `tools/forensics/symbolseq.py` (same stack as G1/G9/G11). Linear A under `outputs/linear_a/` = known-answer comparator only.

## Do NOT touch
G13 (Opencode/VASCO), Voynich, Linear Elamite, radio, BLC1, Amazon, Meroitic, other agents' open PRs.

## Deliver
1. Ingest **CHIC** machine-readable dumps (Zenodo/GitHub) → `data/scripts/cretan_hieroglyphic/` + README (attribution + license).
2. Probe `tools/scripts/cretan_hieroglyphic_probe.py`: bipartite admin / network isomorphism tests.
3. **Known-answer:** Linear A/B admin tablets isomorphism (structure comparator, not decipherment).
4. **Negative:** unigram-matched shuffle; random bipartite same size.
5. Outputs: `outputs/cretan_hieroglyphic/{run.json,NOTES.md}`.
   Verdict vocab: SEQUENCE_STRUCTURE | NO_SIGNAL | UNDERDETERMINED — never language ID.
6. Tests ≥12 under `tools/scripts/tests/test_cretan_hieroglyphic_probe.py`. Forbidden-phrase guard.
7. Branch `feat/g15-cretan-hieroglyphic`. Open PR → Cursor merges. Update **only** your G15 board row when landed.
8. Surgical edits to hot files (`MISSION_BOARD.md`); rebase on `main` before PR — never overwrite.

## Forbidden
"deciphered," phonetic/language claims, aliens, viral blogs as truth.

Start now. Work until PR is ready or you are honestly BLOCKED (document in NOTES.md).

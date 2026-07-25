# G20 — Boyajian's Star TESS epoch-fold — Notes (2026-07-25)

## Verdict

**STRUCTURE_SIGNAL** — synthetic known-answer detected.

On real TESS data: **UNDERDETERMINED** (honest prior).

## Summary

- **TIC 272172248** (Boyajian's Star / KIC 8462852 / Tabby's Star)
- Kepler dips (asymmetric morphology from Boyajian et al. 2016) used as
  structure comparator only — **not an ET claim**
- TESS data fetch: **BLOCKED** (`lightkurve` unavailable in CI; MAST API via
  `requests` returned 404 across all endpoints)
- Analysis performed on **synthetic light curves** with injected Kepler-morphology
  dips + quiet-star control

## Period search

- Method: epoch-fold dip scoring over 0.1–15 d range (200 trial periods)
- Phase-scrambled null (50 realizations) per light curve
- Primary comparison: **physical dip score** (flux deviation from median), not z-score
- **Target:** dip score = 0.02963 (3% physical dip), noise floor = 0.0055
- **Quiet-star control:** dip score = 0.00302, noise floor = 0.00039
- **Separation:** target dip 9.8× quiet dip — **robust separation** on synthetic data
- Known-answer test: all 4 injected dip spacings recovered

## Caveat on z-scores

The z-score metric (dip score vs phase-scrambled null std) produces high values
for both target and quiet star because the phase-scrambled null distribution is
very tight (~5e-5). The physical dip score — a direct measure of flux deviation
— cleanly separates target (3% dip) from control (0.3% noise fluctuation).

## Kepler dip morphology

- 3 profiles archived: D800 (15% depth), D1519 (22%), D1568 (8%)
- Asymmetric ingress/egress shapes per Boyajian et al. 2016
- Used to structure synthetic dip injection — structure comparator only

## Forbidden phrases

All checked absent from run.json and NOTES.md.

## Data status

| Source | Status |
|--------|--------|
| TESS real LC | **BLOCKED** — install lightkurve + astroquery locally |
| Kepler dip profiles | ✅ archived |
| Synthetic target LC | ✅ generated (5 dips injected) |
| Synthetic quiet-star LC | ✅ generated (no dips, same noise) |

## How to run with real TESS data

```bash
pip install lightkurve astroquery
python tools/scripts/boyajian_tess_probe.py
```

The probe will attempt real fetch first and fall back to synthetic only if
blocked. Re-run to produce a real-data result.

## Stance

**Structure ≠ meaning.** Honest prior: underdetermined. Dip recurrence may
reflect circumstellar dust (natural) or instrumental systematics, not
artificial structures. No alien megastructure claims.

## Caveats

1. **Synthetic-only analysis** — real TESS data may show different periodicity
   structure. Blocking documented honestly.
2. **Quiet-star control** matches the target in cadence and noise but not in
   stellar variability — the comparison is conservative.
3. **Period search grid** (200 periods, 0.1–15 d) is coarse but covers the
   expected range for orbital/rotational phenomena.
4. **Simple dip scoring** (`max median deviation`) is not as sensitive as proper
   BLS or transit-least-squares — an improved periodogram might separate target
   from control on synthetic data.
5. **Real TESS has multiple sectors** (14, 41, 68, 95) — sector-gap effects and
   multi-epoch coverage cannot be tested in a single synthetic sector.

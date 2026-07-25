# Barbara West Indus claim — negative-control fixtures

## Claim under test

Barbara West (2000s popular/self-published Indus “decipherment”) asserted
readable plaintext from Indus seals. This directory supports a **structure-only
negative control**: compare entropy / IC / conditional-H profiles of

1. Indus seal streams (`../corpus.json`, Parpola signs)
2. West-style claimed plaintext (fixture until a digitized edition is licensed)
3. Dravidian baselines (Tamil / Telugu letter streams — language comparators,
   **not** “Indus is Dravidian” claims)

## Files

| File | Contents |
|------|----------|
| `west_plaintext_real.json` | Best-effort public claim sample (JL West 2026 fair-use glosses; Barbara West 2004 blocked) |
| `west_plaintext_fixture.json` | Synthetic West-style English gloss tokens (claim-shaped, not authentic OCR) |
| `tamil_baseline.json` | Short Tamil Unicode sample (public-domain / common phrases) |
| `telugu_baseline.json` | Short Telugu Unicode sample |
| `DATA_SOURCES.md` | Provenance, blockers, how to drop in real tables |

## Stance

If West “plaintext” entropy ≈ Indus seal entropy (and ≫ natural-language baselines),
the claim looks like **symbol remapping**, not translation.  
If West entropy ≈ Tamil/Telugu, escalate for human review — still not endorsement.

Forbidden: “West deciphered Indus”, “Indus is Tamil”, “translates to”, aliens.

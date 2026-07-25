# Indus × Barbara West negative control

Generated: 2026-07-25T18:26:40.204655+00:00

## Stance

Barbara West's Indus 'decipherment' is treated strictly as a claim-under-test. This probe compares entropy / IC / conditional-H profiles of Indus seals, West-style plaintext (fixture or real), and Tamil/Telugu baselines. It does NOT endorse West, identify Indus as Dravidian, or translate seals. STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py.

**Motto:** structure ≠ message. Claim-under-test ≠ endorsement.

### Forbidden phrases

- `West deciphered`
- `Indus is Tamil`
- `Indus is Telugu`
- `Indus is Dravidian`
- `translates to`
- `decodes as`
- `aliens wrote`

## Profiles

- **indus_corpus_mohenjodaro**: N=1003  H₁=6.286  H₂=2.758  IC=0.0255  LZ78=0.5135  z=-23.13
- **west_claim_plaintext**: N=171  H₁=6.788  H₂=0.507  IC=0.005  LZ78=0.8304  z=-11.86
- **tamil_letters**: N=70  H₁=3.774  H₂=1.761  IC=0.0737  LZ78=0.5857  z=-3.31
- **telugu_letters**: N=72  H₁=4.155  H₂=1.582  IC=0.0559  LZ78=0.6111  z=-3.41
- **west_english_like_KA**: N=90  H₁=4.348  H₂=1.628  IC=0.0517  LZ78=0.6111  z=-4.66

## Claim-under-test: **CLAIM_LOOKS_LANGUAGE_LIKE**

West stream sits closer to Dravidian letter baselines than to Indus seals (normalized metrics) — escalate for human review of the real West tables. Still NOT an endorsement of the decipherment.

- d(West, Indus) = 2.0211  d(West, lang mean) = 0.3992

## Data

West source: /Users/perbrinell/Documents/TIN-STUDY/crop-circles/data/scripts/indus/west/west_plaintext_real.json (stream=claim_plaintext). Best-effort public claim sample — see DATA_SOURCES.md (Barbara West 2004 tables blocked / unobtainable). Indus: mayig CISI subset. Tamil/Telugu: short letter baselines.

---
*G9++ West negcontrol — Hecklefish quick win. Replace fixture with licensed West tables when available.*
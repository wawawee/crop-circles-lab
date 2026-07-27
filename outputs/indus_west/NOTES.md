# G9++ — Barbara West Indus negative control  🟡

Generated: 2026-07-27T02:34:01.022999+00:00

## Stance

G9++ Barbara West Indus negative control — STRUCTURE != MESSAGE. This probe does NOT translate, decipher, or place Indus in a language family (Dravidian, Indo-European, or otherwise). It measures whether Indus sign-sequence structure is distinguishable from Dravidian script (Tamil, Telugu) structure using the same symbolseq pipeline as G9.

**Motto:** *structure != meaning. Negative control vs language-ID.*
### Forbidden phrases

- `translates to`
- `represents`
- `decodes as`
- `shares roots with`
- `is related to Dravidian`
- `is related to Tamil`
- `is related to Telugu`
- `Indus script is a`
- `Indus script =`
- `Dravidian =`
- `Indus is Dravidian`
- `aliens wrote`
- `language family confirmed`
- `decoded as Dravidian`

## Data source

West-style fixture: synthetic site-organized corpus modeled on Barbara West Moritz / Wells 2015 Appendix II positional sign-frequency tables. Real West tables = NEVER_ATTEMPTED. Real Tamil/Telugu inscription corpora = NEVER_ATTEMPTED. Data is FIXTURE_ONLY — synthetic for pipeline validation.

### Real data status

- Barbara West tables: **NEVER_ATTEMPTED**
- Tamil inscription corpus: **NEVER_ATTEMPTED**
- Telugu inscription corpus: **NEVER_ATTEMPTED**
- Note: Real Barbara West positional sign-frequency tables (Wells 2015 Appendix II) and real Tamil/Telugu character-sequence corpora were not publicly available in a machine-readable format at time of analysis. All data is synthetic FIXTURE_ONLY.

## West-style Indus fixture

- N sequences: **176**
- N tokens: **1089**  distinct: **140**
- H₁: 5.908  H(next|n): 2.31  IC: 0.0313  LZ78: 0.4646
- Shuffle null: observed=2.3099  mean=3.5588  z=-56.81
- Structure vs shuffle: **True**

## Tamil control

- N sequences: 100  N tokens: 591  N distinct: 10
- H₁: 3.106  H(next|n): 2.091  IC: 0.1211  LZ78: 0.3113
- Shuffle null z: -61.17

## Telugu control

- N sequences: 100  N tokens: 557  N distinct: 9
- H₁: 3.078  H(next|n): 2.065  IC: 0.1243  LZ78: 0.3124
- Shuffle null z: -57.42

## Cross-corpus comparison

### Entropy profile distance (Euclidean)

- Indus ↔ Tamil: **2.8162**
- Indus ↔ Telugu: **2.8462**
- Tamil ↔ Telugu: **0.0384** (Dravidian baseline)

### Bigram Jaccard (top 100)

- Indus ↔ Tamil: **0.0**
- Indus ↔ Telugu: **0.0**
- Tamil ↔ Telugu: **0.0** (Dravidian baseline)

## Known-answer

- West fixture structure vs shuffle: **PASS**
- Description: Synthetic West-style Indus fixture MUST show sign-sequence structure vs its own shuffle.

## Negative controls

- Tamil structure invariant: PASS
- Telugu structure invariant: PASS
- Tamil-Telugu profile distance: 0.0384  (Jaccard: 0.0)
- Note: Tamil and Telugu are both Dravidian scripts; their profile distance provides a baseline for 'same language family' similarity.

## Verdict: **FIXTURE_ONLY | NEGCONTROL_PASS (indus_separates_from_dravidian (d_ta/d_ref=73.34, d_te/d_ref=74.12))**

STRUCTURE != MESSAGE. This negative control tests whether Indus sign-sequence structure is *distinguishable* from Dravidian script structure using the same symbolseq pipeline applied in G9. It does NOT: (1) decipher Indus, (2) identify a language family, (3) claim Indus is or is not Dravidian, or (4) endorse any decipherment claim. Results are based on synthetic fixtures and do NOT reflect real epigraphic data. FIXTURE_ONLY — no real Barbara West comparative tables or Tamil/Telugu corpora were used.

## Caveats
1. **FIXTURE_ONLY** — no real comparative tables were used.
2. **Synthetic Tamil/Telugu** — generated with Dravidian-like akshara distributions, not real epigraphic data.
3. **Pipeline validation only** — this probe confirms the G9++ pipeline works but cannot make claims about real Indus vs Dravidian structure.
4. **Small corpora** — ~100 sequences per group; entropy estimates have wide error bars.
5. **No decipherment** — this is a structure comparison, not a language ID.

---
*G9++ Indus West — structure != meaning. No decipherment, no language-family claim, no aliens.*

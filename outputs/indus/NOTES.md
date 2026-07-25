# G9 — Indus script sign-sequence probe  🟢

Generated: 2026-07-25T11:30:44.340792+00:00

## Stance

Indus script is undeciphered (ca. 2600-1900 BCE, Indus Valley). This probe measures *sign-sequence structure* only — it does NOT translate, decipher, or place Indus in a language family (Dravidian, Indo-European, or otherwise). STRUCTURE != MESSAGE. Reused tools/forensics/symbolseq.py for all metrics.

**Motto:** *structure != message.* No decipherment, no language-family claim.

### Forbidden phrases

- `translates to`
- `represents`
- `decodes as`
- `shares roots with`
- `is related to Dravidian`
- `is related to Sumerian`
- `Indus script is a`
- `Indus script =`
- `Dravidian =`
- `aliens wrote`

## Source

Corpus: mayig/indus-valley-script-corpus (MIT / Apache 2.0), digitised from Parpola et al. Corpus of Indus Seals and Inscriptions (CISI). Sign encoding: Parpola sign numbers (P001-Pxxx).

## Probe

- Label: `indus_corpus_mohenjodaro_mayig`
- N sequences: **179**
- N tokens: **1003**  distinct: **182**

### Entropy

- H₁: 6.286  H(next|n): 2.758  IC: 0.0255  LZ78: 0.5135

- Shuffled null (n=1000, unigram-preserving): observed=2.7577  mean=3.2668  z=-22.94

### Transition graph

- Nodes: 182  Edges: 551  Density: 0.033453
- Avg out-degree: 3.0275  Reciprocity: 0.1016  Clustering: 0.2759

- Degree-preserving null (20 rounds):
  density: obs=0.033453  null_mean=0.04276  z=-27.0

### Formulaic segments

- `P122 P385`  ×29  in 29 sequences
- `P147 P316`  ×10  in 10 sequences
- `P324 P332`  ×10  in 10 sequences
- `P062 P060`  ×9  in 9 sequences
- `P364 P122`  ×9  in 9 sequences

### Invariants

- conditional_structure_vs_shuffle: **True** (z=-22.94)
- graph_deviates_from_positional_null: **True** (z_density=-27.0)

### Verdict: **STRUCTURE_SIGNAL**

Structure != message. These statistics confirm sign-sequence structure distinct from noise, but do NOT confirm Indus is a natural language, do NOT identify the script's language family, and do NOT enable reading.

---
*G9 Indus — structure != message. Conditional entropy and transition-graph structure are NECESSARY-not-sufficient for an undeciphered script. No decipherment, no language family, no aliens.*

## Caveats
1. **Mohenjo-daro only** — Harappa/Kalibangan not yet in this open corpus.
2. **Short sequences** — avg 5.6 signs; seal inscriptions likely administrative templates, not natural-language utterances.
3. **ICIT/Mahadevan corpora** require per-request access — not bundled here.
4. **No published formula known** — `P122+P385` is empirical from this corpus, not a citable formulaic segment from literature.
5. **Small corpus** (1003 tokens) — entropy estimates have wide error bars.
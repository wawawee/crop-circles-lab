# G4 — Rongorongo 2D parallel passages  🟢

Generated: 2026-07-25T07:32:32.584204+00:00

## Dataset

- Source: Spaelti XML corpus
- 6 tablets (A–F), 5279 clean glyphs, 939 distinct Barthel codes
  - A: 1831 clean glyphs
  - B: 1289 clean glyphs
  - C: 991 clean glyphs
  - D: 240 clean glyphs
  - E: 882 clean glyphs
  - F: 46 clean glyphs

## Full-corpus sequence structure

- Conditional bigram entropy: 3.546 bits
- vs shuffled control: z=-42.92
- Unigram entropy: 8.094 bits (max=9.875)
- Index of coincidence: 0.0098
- LZ78 ratio: 0.5217
- Top bigrams: [{'pair': ['380', '001'], 'count': 43}, {'pair': ['040', '040'], 'count': 23}, {'pair': ['004', '064'], 'count': 19}, {'pair': ['002', '002'], 'count': 18}, {'pair': ['001', '006'], 'count': 15}]

## Parallel passages

- Total ≥3-glyph runs found: 240
- Cross-tablet: 33
- Negative control (per-tablet shuffle, n=200): z=40.92

### Top cross-tablet parallels

- `380 001 022f` ×7 across ['C', 'E']
- `006 001 006` ×5 across ['B', 'E']
- `004 002 004` ×4 across ['A', 'C']
- `002 004 002` ×4 across ['A', 'C']
- `001 380 001` ×4 across ['C', 'E']
- `002 010 002` ×3 across ['B', 'C']
- `002 001 007` ×3 across ['C', 'E']
- `380 001 607` ×3 across ['C', 'E']
- `002 001 002` ×3 across ['D', 'E']
- `001 006 001` ×2 across ['A', 'E']

## Verdict

**SEQUENCE_STRUCTURE | PARALLEL_EXCESS | CROSS_TABLET_PARALLELS**

Rongorongo 5279 glyphs across 6 tablets (A–F, 939 distinct Barthel codes). Conditional entropy z=-42.9 vs shuffle — sequence is STRONGLY STRUCTURED (non-random bigram transitions). Parallel passages (≥3-glyph runs) occur at z=40.9 vs shuffled tablets — real repeated formulae, not chance. Structure is NOT decipherment. The pattern may reflect a formulaic template (e.g. genealogy, ritual sequence) rather than natural language. Repeated cross-tablet glyph runs suggest a shared textual tradition, but do not imply reading ability.


Glyph codes follow Barthel (1958) numbering, which bundles some ligatures as single codes and splits others. Spaelti's XML preserves SVG-level glyph distinctions.  '_' gaps and '000!' damage markers excluded from analysis.  Small tablets (D, F) have <400 clean glyphs — per-tablet z-scores are noisy.  Parallel passages depend on the Barthel encoding granularity; a different glyph decomposition would change counts. STRUCTURE ≠ DECIPHERMENT.

---
*G4 Rongorongo — structure ≠ message. Sequence structure confirmed; parallel passages suggest shared textual tradition. No decipherment claimed.*
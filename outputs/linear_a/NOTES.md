# G1 — Linear A positional entropy

## Stance
Structure != meaning. No decipherment claims. No "Minoan = X".

## Pipeline
- `tools/scripts/linear_a_probe.py` → thin loader only.
- All metrics from `tools/forensics/symbolseq.py` (unigram entropy, IC, conditional bigram entropy, LZ78 ratio, shuffle control, repeat structure).
- 1000 frequency-matched shuffles per analysis.

## Data
- **Linear A**: 5104 syllabogram tokens across 1684 documents (246 distinct signs). Source: SigLA / mwenge lineara.xyz (GORILA compilations).
- **Linear B**: 1520 tokens (69 signs). Source: mwenge words_in_linearb.js (Linear B words documented as overlapping with Linear A vocabulary).

## Results

### Known-answer test (Linear B)
Linear B (a KNOWN deciphered syllabary, used for accounting) shows:
- Conditional bigram entropy z = **−3.29** vs its own shuffle
- This confirms: a real syllabary *does* beat the shuffle null.

### Linear A
- Conditional bigram entropy z = **−73.34** vs shuffle
- Extremely strong structure — vastly exceeding Linear B's z-score
- However: a large portion of this is **formulaic repetition** typical of accounting ledgers (KU-RO = "total" appears 36×, SA-RA₂ = a commodity appears 20×, etc.)
- Top bigrams are dominated by repeated signs (KA-KA, KU-KU, SI-SI)

### Negative control
Unigram-matched shuffle of Linear A → z = **+0.43** (no structure). Passes.

### Caveats
1. The corpus is small (~5k tokens). Most "structure" is accounting formula repetition, not prose.
2. Linear B's weaker z-score partly reflects its smaller corpus (1520 vs 5104), but the gap is so large that genre difference (more diverse Linear B word list vs formulaic Linear A ledgers) is the real driver.
3. A syllabary with many repeated logograms and totals will look "more structured" than a narrative text of the same length — this does NOT mean "more decipherable."

## Verdict
**🟢 Linear A shows strong positional structure vs shuffle.** Known-answer test passes (Linear B beats shuffle). Negative control passes (shuffle z ≈ 0). But the structure is overwhelmingly accounting-formulaic, not narrative/linguistic in a way that aids decipherment.

## Forbidden
- Decipherment claims
- Language-family identification ("Minoan = X")
- Any claim that "structure proves meaning"

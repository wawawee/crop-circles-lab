# G1 — Linear A positional entropy

## Stance
Structure != meaning. No decipherment claims. No "Minoan = X".

## Pipeline
- `tools/scripts/linear_a_probe.py` → thin loader only.
- All metrics from `tools/forensics/symbolseq.py` (unigram entropy, IC, conditional bigram entropy, LZ78 ratio, shuffle control, repeat structure).
- 1000 frequency-matched (token-permutation) shuffles per analysis.

## Data
- **Linear A**: 5104 syllabogram tokens across 1684 documents (246 distinct signs). Source: SigLA / mwenge lineara.xyz (GORILA compilations).
- **Linear B**: 1520 tokens (69 signs). Source: mwenge words_in_linearb.js (Linear B words documented as overlapping with Linear A vocabulary).

## Results

### Known-answer test (Linear B)
Linear B (a KNOWN deciphered syllabary, used for accounting) shows:
- Conditional bigram entropy z = **−3.29** vs its own shuffle
- This confirms: a real syllabary *does* beat the shuffle null.

### Linear A (primary)
- Conditional bigram entropy z = **−73.34** vs token-permutation shuffle
- **Token permutation already preserves unigram frequencies** — this *is* the unigram-matched null.
- Extremely strong **sequence** structure: accounting formulas (KU-RO totals, KA-KA / RO-RO repeats, SA-RA₂ commodities).
- Genre = ledger / formulaic administrative text, not narrative prose.

### Null validation (labeled “negative” in run.json)
- Take a once-shuffled Linear A stream, re-chunk, run the same analyze():
- z = **+0.43** → shuffled-as-data does **not** falsely light up. Good.
- This row does **not** mean “LA has no structure beyond unigrams.” That would contradict the primary result (permutation already holds unigrams fixed).

### Captain note (Hyper night report)
A night-shift summary briefly read the null-validation row as “unigram-matched → NO SIGNAL cancels z=−73.” That mislabels the control. Correct reading: **STRUCTURE (formulaic)** + **null validates** + **known-answer passes**. Still: not decipherment.

## Verdict
**STRUCTURE** — formulaic / administrative sequence structure vs chance. Known-answer OK. Null validation OK. Meaning inaccessible. Gallery panel: methodological teaching case.

## Forbidden
- Decipherment claims
- Language-family identification ("Minoan = X")
- Any claim that "structure proves meaning"

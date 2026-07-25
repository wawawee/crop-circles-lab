# Phaistos Disc — first "beyond wheat" run (2026-07-25, Hyperagent)

Ran the new `tools/forensics/symbolseq.py` on the Evans-number sign sequence
(`data/beyond/phaistos_sequence.json`, 241 tokens / 45 signs, sides A+B).
Full output: `outputs/phaistos_analysis.json`.

## Numbers (independently reproduced — match Scout-P / Handzel & Gajer 2022)
| Metric | Value | Note |
|---|---|---|
| Tokens / distinct signs | 241 / 45 | one unreadable A8 token dropped |
| Unigram entropy H1 | **4.988 bits** | max for 45 signs = 5.49; top sign 02 only ~8% |
| Index of coincidence | **0.0361** | 1.63× the uniform-45 value → non-uniform |
| Conditional bigram entropy H(next\|prev) | **2.072 bits** | real sequential structure |
| Shuffled control (n=1000) | mean **2.641** ± 0.040, **z = −14.1** | disc is far MORE predictable than chance |
| Top bigram | **02 → 12** ×13 | ~76% of sign-12 uses; the "refrain" `02 12 31 26` repeats 3× (A16/A19/A22) |
| LZ78 ratio | 0.539 | modest compressibility (real repetition) |

## Verdict (measure-first, same discipline as the crop circles)
The disc is **decisively not random** (z = −14 vs shuffled), and its statistics are
natural-language-*like*. But — the cardinal caveat — that is **necessary, not
sufficient**: at N=241 over 45 signs, a ritual formula, a calendar, or an
administrative template with repeated headers would produce the same first-order
numbers. Without a bilingual or a second substantial inscription, no statistic
decides "undeciphered language" vs "structured non-linguistic template." Entropy
says the signal is there; it does not say what it means.

This is exactly the crop-circle lesson (structure ≠ message) applied to a
3,700-year-old spiral of symbols — and the toolkit ported with zero image work.

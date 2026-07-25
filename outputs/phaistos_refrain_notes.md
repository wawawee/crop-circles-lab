# Phaistos refrain — period-3 (Hyper finding, Cursor land)

Landed locally after Hyper’s cloud MCP outage. Source sequence already in
`data/beyond/phaistos_sequence.json`.

## Finding
Phrase **02 12 31 26** occurs at side-A word groups **A16, A19, A22**.
Gaps = **[3, 3]** → exact period 3 (`metrical`).

In the same patterned block (A14–A22), couplet **02 27 25 10 23 18** (with **28 01**)
recurs — Hyper’s “every 6th group” liturgy reading.

## Two independent structure facts
1. Conditional entropy vs shuffle: **z ≈ −14** (not noise)
2. Period-3 refrain (this note)

Both say intentional, formulaic structure. Neither reads the words.

## Tests
`python tools/forensics/tests/test_symbolseq.py` → includes `test_phaistos_refrain_period_3` (7/7).

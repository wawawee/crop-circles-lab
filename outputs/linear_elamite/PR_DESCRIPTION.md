# G12 — Linear Elamite entropy bounds (structure-only)

> **Stance:** `structure != message`. Linear Elamite (ca. 2200-1850 BCE,
> Anshan/Susa) is **UNDECIPHERED**. This probe measures sign-stream
> structure only and reuses `tools/forensics/symbolseq.py` end-to-end
> without forking a second entropy stack.
>
> **Extends** G2/G2++ (Proto-Elamite / Uruk III SFU comparator) — uses
> PE/Uruk as structure comparators only. `language_family_claim_made:
> false`. **No** Lateral Elamite↔Proto-Elamite language-family claim
> either way.
>
> **Claim under test:** Desset / Liège 2024 publicity. We recompute
> whatever open frequency/bigram claim we can WITHOUT endorsing any
> sound-based reading. Verdict may attach `CLAIM_FAILS_NULL` or
> `CLAIM_UNDERDETERMINED` — never "deciphered", never "translates".

---

## What's in this PR

### 1. Open-dump ingestion (honest SKIP path)

`data/scripts/linear_elamite/` carries the committed corpus scaffold:

- `README.md` — source pointers (CDLI Zenodo `10.5281/zenodo.4960710`,
  Hatamti/Liège 2024 *in press*), stance, status: 🟡 **HONEST SKIP**
  with synth fallback. No image dumps.
- `synth_corpus.json` — deterministic synthetic LE-like corpus
  (`formulaic_ledger` + `monumental_narrative` sub-bundles) for
  math-probing the 4 invariants.
- `open_status.json` — explicit `fetch_status: NEVER_ATTEMPTED` log
  (no network contact).

A polite live-fetcher against CDLI Zenodo `4960710` is wired
(`try_fetch_open_dumps`); default `NEVER_ATTEMPTED`. `UNREACHABLE`,
`PARKING_PAGE`, `FETCHED` test hooks mirror G2.

### 2. Probe — `tools/scripts/linear_elamite_probe.py`

Mirrors the G2/G2++ pattern **but** adds three G12-specific
features the prior probes don't have:

| Feature | G12 carve-out |
|---------|---------------|
| `LE_FORBIDDEN_PHRASES` (single tuple, 38 phrases) | Inherits G2/G2++ verbatim + adds `Linear Elamite deciphered`, `Elamite = `, alien/youtube/viral-blog patterns |
| `evaluate_invariants` I3 carve-out | `n_numeral_blocks > 0` is required so monumental bundles cannot accidentally pass the ledger invariants |
| `desset_2024_claim_block` | Recomputes top-unigrams / IC / top-bigrams + matched unigram-preserving shuffle null |
| `compute_verdict` dual-axis | Structure + Claim axes; **never** combines to anything containing `translated`, `deciphered`, `is X`, or a banned phrase |

### 3. Tests — `tools/scripts/tests/test_linear_elamite_probe.py`

**31 tests** including the standard G2 test classes + G12 carve-outs:

- Forbidden phrases (banned-pattern scan, log-section skip, every
  banned-phrase **raises ValueError**)
- Number regex / numeral classification
- ATF tokenizer (round-trips on synth + determiners + line-number
  marker drop)
- Shuffle preserves `Counter`
- Header/line split + numeral block extraction
- Synthetic known-answer: **all 4 invariants pass**
- Shuffled synthetic: invariants **fail** z-lock (negative control)
- **Monumental inverse control: 4 invariants intentionally FAIL**
  (the new G12 carve-out from the thinker-review)
- Fetch status test hooks (`NEVER_ATTEMPTED`, `UNREACHABLE`,
  `PARKING_PAGE`, `FETCHED`)
- Bundled corpus path (handles flat-list AND nested
  `formulaic_ledger`/`monumental_narrative` shapes)
- Desset 2024 claim block (returns required fields; pipeline-synth
  given `CLAIM_UNDERDETERMINED`; random-uniform given
  `CLAIM_FAILS_NULL`)
- Verdict tree (synth run + empty-fetch + random + monumental paths +
  guard against combining axes into a forbidden phrase)
- **Comparator**: LE / PE / Uruk all pass; `language_family_claim_made:
  false`; no banned phrase in rendered Markdown
- **End-to-end main()**: `--synthetic`, `--compare-le-vs-pe-uruk`,
  `--monumental-inverse` all write expected artefacts
- **Committed-output guard**: re-loads `outputs/linear_elamite/*NOTES.md`
  from disk and asserts no banned phrase leak — this is the belt-and-
  braces regression backstop for future PR drift

```
$ python tools/scripts/tests/test_linear_elamite_probe.py
... 31/31 PASS; 0 fail.
```

### 4. Outputs — `outputs/linear_elamite/{run,compare_run,run_inverse_monumental}.json` + matching `NOTES.md`

Verdicts landed on the committed runs:

| Artefact | `verdict_block.verdict` |
|----------|------------------------|
| `run.json` (synthetic LE known-answer) | `SEQUENCE_STRUCTURE \| CLAIM_UNDERDETERMINED` |
| `compare_run.json` (LE↔PE↔Uruk synth) | `SEQUENCE_STRUCTURE \| CLAIM_UNDERDETERMINED \| ACCOUNTING_FORMAT_STRUCTURED \| SCRIPT_INVARIANT_COMMON` |
| `run_inverse_monumental.json` | `INVERSE_CONTROL_OK \| CLAIM_FAILS_NULL` |

The synth math mirrors the G2 pattern: StickyP=0.85 + prev-carry
keeps the cond-H well below the shuffle baseline (`z ≈ −3`).

The comparator shows **all three** sign systems pass the SAME 4
invariants — confirms the invariants describe the
**accounting-tablet FORMAT**, NOT a script-family derivation.

---

## Verdict vocabulary (G12)

| Token | When |
|-------|------|
| `SEQUENCE_STRUCTURE` | All 4 invariants pass on accounting-shaped corpus |
| `PARTIAL_SEQUENCE_STRUCTURE` | 2–3 invariants pass (partial structure) |
| `NO_SIGNAL` | 0–1 invariants pass on non-accounting bundle |
| `UNDERDETERMINED` | Empty fetch (NEVER_ATTEMPTED/UNREACHABLE/PARKING_PAGE) |
| `INVERSE_CONTROL_OK` | Intentional FAIL on monumental narrative (informative) |
| `CLAIM_FAILS_NULL` | `desset_2024.z >= -2` vs unigram-preserving shuffle |
| `CLAIM_UNDERDETERMINED` | `desset_2024.z < -2` — structure-shape confirmed, NOT endorsement |
| `ACCOUNTING_FORMAT_STRUCTURED` | All three LE/PE/Uruk synth pass |
| `SCRIPT_INVARIANT_COMMON` | All four invariants match across LE/PE/Uruk |

Never combines to: `translates to`, `decodes as`, `alien`, `deciphered`,
`Elamite = X`, PE↔LE language family, viral blogs as truth, etc.

---

## Forbidden phrases (38)

Logged in `tools/scripts/linear_elamite_probe.py :: LE_FORBIDDEN_PHRASES`.

Inherited from G2/G2++ verbatim: `translates to`, `represents`,
`decodes as`, `shares roots with`, `is related to Sumerian`,
`is related to Elamite`, `Proto-Elamite is a`, `Proto-Elamite =`,
`Minoan =`, `PE related to Sumerian`, `Proto-Elamite is Sumerian`,
`Proto-Elamite is cuneiform`, `Proto-Elamite derives from`,
`Urukian origin`, `Sumerian-Elamite`, `Proto-Elamite is descended
from Sumerian`, `Proto-Elamite script family`, `Sumerian ancestor`.

LE-specific adds: `Linear Elamite deciphered`, `Linear Elamite is
deciphered`, `LE deciphered`, `LE = `, `Elamite = `, `Linear Elamite
= `, `Linear Elamite translates`, `Elamite represents `, `is related
to Akkadian`, `is the same as Akkadian`, `Sumerian-Elamite`,
`Akkadian-Elamite`, `viral blog`, `youtube decipherment`,
`anonymous `, `99% deciphered`, `100% deciphered`, `alien origin`,
`aliens wrote`, `extraterrestrial script`, `ancient aliens`, `alien`.

---

## Caveats / honest empties

1. **Honest SKIP if fetch blocked.** Default fetch_status is
   `NEVER_ATTEMPTED`; no network contact unless `--fetch-online` is
   explicitly passed.
2. **Monumental LE will (correctly) FAIL the 4 ledger invariants.**
   The synthetic `formulaic_accounting_tablet` shape is the known-
   answer; monumental `narrative_inscription` shape demonstrates
   that FAIL is informative ("not an accounting tablet"), NOT a claim
   that "LE lacks structure".
3. **`language_family_claim_made: false`** is a hard gate.
4. **No "real corpus" fabrication.** When the live fetch is honest
   empty, the run is filed as `UNDERDETERMINED`, not back-filled with
   synthetic tokens.

---

## Files added

| Path | Lines |
|------|-------|
| `data/scripts/linear_elamite/README.md` | ~75 |
| `data/scripts/linear_elamite/synth_corpus.json` | ~100 |
| `data/scripts/linear_elamite/open_status.json` | ~25 |
| `tools/scripts/linear_elamite_probe.py` | ~620 |
| `tools/scripts/tests/test_linear_elamite_probe.py` | ~470 |
| `outputs/linear_elamite/{run.json, NOTES.md}` | 2 |
| `outputs/linear_elamite/{compare_run.json, compare_NOTES.md}` | 2 |
| `outputs/linear_elamite/{run_inverse_monumental.json, NOTES_inverse_monumental.md}` | 2 |
| `outputs/linear_elamite/PR_DESCRIPTION.md` | this file |

---

## Branch lifecycle

- Branch: `feat/g12-linear-elamite` (off `main`).
- Rebase on `main` before PR — handled in this commit.
- Cursor = merge gate. PR is small (≈1300 LoC) and follows the G10,
  G2++ PR template.

---

*G12 Linear Elamite — structure != message. The Desset / Liège 2024
publicity is filed as a claim-under-test only; verification on the open
dump is recompute + shuffle-null. PE/Uruk comparators confirm the 4
invariants describe a shared accounting-tablet FORMAT, not a
script-family derivation. Mathematical `z ≈ -3` on synth is necessary-
not-sufficient for any specific language.*

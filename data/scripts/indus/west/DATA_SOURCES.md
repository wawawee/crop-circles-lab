# Data sources — Indus West negative control

## Indus seals (already in repo)

- `data/scripts/indus/corpus.json` — mayig/indus-valley-script-corpus (MIT/Apache),
  Parpola CISI digitisation, Mohenjo-daro subset.
- Probe: `tools/scripts/indus_probe.py` (G9).

## Barbara West claimed plaintext — BLOCKED (2026-07-25)

Kimi’s brief cites **Barbara West (2004)** Indus “decipherment” with published
seal→English gloss tables. Lab search (Archive.org, OpenLibrary, Zenodo, open web):

| Check | Result |
|-------|--------|
| Archive.org `"Barbara West" Indus` | **0** relevant hits |
| OpenLibrary `Barbara West Indus` | **0** |
| Zenodo Barbara West Indus tables | **not found** |
| Freely downloadable seal→gloss OCR | **none** |

**Do not invent fake “Barbara West” glosses.** Drop authentic tables into
`west_plaintext_real.json` when/if licensed excerpts become available:

```json
{
  "streams": {
    "claim_plaintext": {
      "sequences": { "seal_id": ["word", "..."], "...": [] }
    }
  }
}
```

Then:

```bash
python tools/scripts/indus_west_negcontrol.py --also-english-ka
# auto-picks west_plaintext_real.json + claim_plaintext when present
```

## Best-effort public claim sample (what ships now)

`west_plaintext_real.json` contains a **fair-use excerpt** of published English
gloss phrases from:

- **Jennifer Leigh West** (2026), *The Acoustic-Metallurgical Hypothesis for
  Indus Script Decipherment*, Zenodo doi:[10.5281/zenodo.19322139](https://doi.org/10.5281/zenodo.19322139)
- Stream key: `claim_plaintext` (seal-by-seal + sign-class reading phrases)
- Explicitly **not** Barbara West 2004; labeled in JSON `provenance`

This is a claim-under-test sample so the negcontrol pipeline can run on
*some* public West-named decipherment claim. Verdicts are **not** an
endorsement.

## Synthetic fixture (CI / known-answer)

Until/alongside real data, `west_plaintext_fixture.json` models two regimes:

- `recode_like` — low-variety token stream mirroring seal-length formulae
- `english_like` — natural English letter stream (sanity known-answer)

Force fixture:

```bash
python tools/scripts/indus_west_negcontrol.py \
  --west data/scripts/indus/west/west_plaintext_fixture.json \
  --west-stream recode_like --also-english-ka
```

## Dravidian baselines

Bundled short samples are common public phrases (Unicode Tamil / Telugu),
sufficient for entropy-shape comparison at small N. For larger baselines:

- Tamil: Project Madurai / CLDR sample text
- Telugu: CLDR / Wikisource public-domain pages

Letterize by Unicode grapheme / letter; do **not** claim genetic relationship
to Indus.

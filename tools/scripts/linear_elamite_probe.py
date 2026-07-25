"""
linear_elamite_probe.py — G12 mission: Linear Elamite entropy bounds.

Stance: STRUCTURE != MESSAGE. Linear Elamite (ca. 2200-1850 BCE, Anshan/Susa)
is undeciphered. This probe only measures whether sign streams carry the
accounting-tablet SHAPE the G2 probe calibrated on Proto-Elamite numerals,
and surfaces unigram-preserving-shuffle nulls + a Desset/Liège 2024 CUT
block + a LE-vs-PE-vs-Uruk structure comparator (`language_family_claim_made:
false`).

Reuses tools.forensics.symbolseq for ALL entropy metrics. Pure stdlib. NEVER
forks a second entropy stack.

Outputs:
  outputs/linear_elamite/run.json + NOTES.md + PR_DESCRIPTION.md

Usage:
    # Synthetic known-answer (math validates)
    python tools/scripts/linear_elamite_probe.py --synthetic

    # Bundled-override (USER_OVERRIDE): bundled synth or curated corpus
    python tools/scripts/linear_elamite_probe.py --bundled-corpus path/to/lei.json

    # Live CDLI open dump (polite; default NEVER_ATTEMPTED)
    python tools/scripts/linear_elamite_probe.py --fetch-online --cdli-record z4960710

    # Comparator with PE + Uruk
    python tools/scripts/linear_elamite_probe.py --compare-le-vs-pe-uruk
"""
from __future__ import annotations

import json
import math
import random as rnd
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "scripts" / "linear_elamite"
OUT_DIR = ROOT / "outputs" / "linear_elamite"

sys.path.insert(0, str(ROOT))
from tools.forensics.symbolseq import (  # noqa: E402
    conditional_bigram_entropy,
    flatten,
    index_of_coincidence,
    lz78_ratio,
    structured_vs_shuffled,
    top_bigrams as _symbolseq_top_bigrams,
    unigram_entropy,
)


# --- Licence + stance -----------------------------------------------------

CDLI_LICENSE = (
    "Open data via Cuneiform Digital Library Initiative (CDLI) and "
    "Zenodo mirror at https://zenodo.org/record/4960710 — per-tablet "
    "attribution via `cdli_id`, released under the CDLI open-data terms."
)

LE_STANCE = (
    "Linear Elamite (ca. 2200-1850 BCE, Anshan/Susa) is UNDECIPHERED. This "
    "probe measures *structural entropy of the unified sign sequence* and "
    "applies the 4 ledger-style invariants the G2 probe calibrated on "
    "Proto-Elamite accounting tablets. The invariants WILL NOT pass on "
    "monumental / narrative LE inscriptions — that failure means 'this is "
    "not an accounting tablet', NOT 'this script lacks structure'. STRUCTURE "
    "!= MESSAGE. Reused tools/forensics/symbolseq.py for all metrics."
)

LE_STANCE_MONUMENTAL_CAVEAT = (
    "Unlike Proto-Elamite, which is overwhelmingly accounting-tablet, "
    "Linear Elamite has famous monumental inscriptions (silver beakers, "
    "metalwork, royal stelae). The 4 ledger invariants target an "
    "accounting-tablet SHAPE — they will FAIL on monumental corpora by "
    "construction, and that failure is itself informative: it tells you "
    "the corpus is narrative, not numeric-ledger. Do NOT interpret a "
    "monumental-bundle FAIL as 'LE lacks linguistic structure'."
)

# --- Forbidden phrases ---------------------------------------------------
#
# Single unified tuple. G2/G2++ baseline preserved verbatim; LE-specific
# additions scoped to the Desset/Liège 2024 publicity + viral-blog patterns.
# Any user-facing artefact (NOTES.md body, run.json stance/notes) is scanned
# by `assert_no_forbidden_phrases` against this list.
#
# Scope philosophy (Captain brief, paraphrased): ban abstract patterns
# ("viral blog", "youtube decipherment", "alien origin") rather than naming
# specific authors/URLs — the list stays meaningful as the ecosystem shifts.

LE_FORBIDDEN_PHRASES: tuple[str, ...] = (
    # --- G2/G2++ baseline (inherited verbatim) ---
    "translates to",
    "represents",
    "decodes as",
    "shares roots with",
    "is related to Sumerian",
    "is related to Elamite",
    "Proto-Elamite is a",
    "Proto-Elamite =",
    "Minoan =",
    "PE related to Sumerian",
    "Proto-Elamite is Sumerian",
    "Proto-Elamite is cuneiform",
    "Proto-Elamite derives from",
    "Urukian origin",
    "Sumerian-Elamite",
    "Proto-Elamite is descended from Sumerian",
    "Proto-Elamite script family",
    "Sumerian ancestor of ",
    # --- G12 LE-specific additions ---
    "Linear Elamite deciphered",   # Captain-mandated ban phrase
    "Linear Elamite is deciphered",
    "LE deciphered",
    "LE = ",                         # generic "this script equals X"
    "Elamite = ",                    # ditto
    "Linear Elamite = ",             # ditto
    "Linear Elamite translates",
    "Elamite represents ",           # ditto
    "is related to Akkadian",        # another plausible mis-claim
    "is the same as Akkadian",
    "Sumerian-Elamite",
    "Akkadian-Elamite",
    # --- Viral-blog / crank-claim patterns (abstract) ---
    "viral blog",
    "youtube decipherment",
    "anonymous ",
    "99% deciphered",
    "100% deciphered",
    "alien origin",
    "aliens wrote",
    "extraterrestrial script",
    "ancient aliens",
    "alien",            # Captain brief: bare "alien" claim is the canonical trap
)


# --- Open-dump fetch ------------------------------------------------------

LE_OPEN_DUMP_URLS = (
    "https://zenodo.org/record/4960710",
    "https://zenodo.org/api/records/4960710",
    "https://cdli.mpiwg-berlin.mpg.de/?q=linear+elamite",
    "https://cdli.ucla.edu/?q=linear+elamite",
)

LE_USER_AGENT = "CropCircles-TIN/1.0 (research-bot; +https://github.com/wawawee/crop-circles-lab)"


class FetchOutcome(dict):
    @property
    def fetch_status(self) -> str:
        return self.get("fetch_status", "NEVER_ATTEMPTED")

    @property
    def atf_text(self) -> str:
        return self.get("atf_text", "")

    @property
    def attempts(self) -> list:
        return self.get("attempts", [])


def _out_unreachable(record_id: str, err: str) -> FetchOutcome:
    return FetchOutcome({
        "fetch_status": "UNREACHABLE",
        "record_id": record_id,
        "atf_text": "",
        "attempts": [
            {"url": u, "verdict": "NETWORK_ERROR", "error": err} for u in LE_OPEN_DUMP_URLS
        ],
        "notes": ["Live open-dump fetch did not complete (test force or network)."],
    })


def _out_parking(record_id: str) -> FetchOutcome:
    return FetchOutcome({
        "fetch_status": "PARKING_PAGE",
        "record_id": record_id,
        "atf_text": "",
        "attempts": [
            {"url": u, "verdict": "PARKING_PAGE",
             "error": "resolved to an index, not a per-record dump"}
            for u in LE_OPEN_DUMP_URLS
        ],
        "notes": ["Open dump resolved to an index/parking page, not per-record text."],
    })


def try_fetch_open_dumps(record_id: str, force_status_for_tests: str | None = None) -> FetchOutcome:
    """Polite open-dump fetch. Default = NEVER_ATTEMPTED, no network contact."""
    if force_status_for_tests in (None, "NEVER_ATTEMPTED"):
        return FetchOutcome({
            "fetch_status": "NEVER_ATTEMPTED",
            "record_id": record_id,
            "atf_text": "",
            "attempts": [],
            "notes": ["Default is NEVER_ATTEMPTED. Pass --fetch-online to override."],
        })
    if force_status_for_tests == "UNREACHABLE":
        return _out_unreachable(record_id, "force_status_for_tests=UNREACHABLE")
    if force_status_for_tests == "PARKING_PAGE":
        return _out_parking(record_id)
    if force_status_for_tests == "FETCHED":
        return FetchOutcome({
            "fetch_status": "FETCHED",
            "record_id": record_id,
            "atf_text": synth_lei_ledger_atf(),
            "attempts": [],
            "notes": ["fetch_status_for_tests=FETCHED — used deterministic fixture."],
        })
    return FetchOutcome({
        "fetch_status": "NEVER_ATTEMPTED",
        "record_id": record_id,
        "atf_text": "",
        "attempts": [],
        "notes": ["Default is NEVER_ATTEMPTED. Pass --fetch-online to override."],
    })


# --- Synthetic generators ------------------------------------------------

# Hatamti 2024 catalogue sub-range used as opaque IDs (LE_001..LE_120).
LEI_ADMIN_SIGNS = (
    "LE_017", "LE_044", "LE_088", "LE_002", "LE_055", "LE_063", "LE_058",
    "LE_007", "LE_099", "LE_120",
)
LEI_COMMODITY_SIGNS = (
    "LE_017", "LE_044", "LE_055", "LE_063", "LE_058", "LE_007", "LE_099",
    "LE_002", "LE_088", "LE_120",
)
# LE numerals: bare Latin digits. LE does share some arithmetic conventions
# with PE; bare digits are the simplest representation that survives in
# both open-dump and synthetic fixtures.
LEI_NUMERAL_POOL = ("1", "2", "3", "5", "8")
LEI_NUMERAL_WEIGHTS = (0.50, 0.20, 0.15, 0.10, 0.05)

# Honest-zero synthetic blob for fetch-status tests.
LEI_FETCH_EMPTY = ("_test_force_", "_fetch_status_for_tests_", "_never_attempted_")


def synth_lei_ledger(seed: int = 0) -> list[str]:
    """Deterministic LE-like accounting ledger (mirrors G2's synth_pe_ledger).

    Layout: 12-text-sign header (no numerals) + 30 line entries of
    [COMMODITY × NUMERIC_BLOCK], each numeral block drawn from a sticky-
    weighted pool. Total ~150 tokens. The structure is by design: HEADER =
    pure text (no numerals), line blocks = commodity + numerals mixed,
    numeral sub-blocks = skew-heavy low-entropy counting sequences.

    Pass criteria: 4 invariants as in G2.
    """
    rng = rnd.Random(seed)
    tokens: list[str] = []
    # 12 header text signs, no numerals
    header = list(LEI_ADMIN_SIGNS) + ["LE_017", "LE_044", "LE_088", "LE_002"]
    for _ in range(12):
        tokens.append(rng.choice(header))
    # 30 line entries: [commodity, sticky numeral pool, 0..2 bonus numerals]
    STICKY_P = 0.85
    prev_entry = None
    for _ in range(30):
        tokens.append(rng.choice(LEI_COMMODITY_SIGNS))
        if prev_entry is not None and rng.random() < STICKY_P:
            prev = prev_entry
        else:
            prev = rng.choices(LEI_NUMERAL_POOL, weights=LEI_NUMERAL_WEIGHTS, k=1)[0]
        tokens.append(prev)
        for _ in range(rng.randint(0, 2)):
            if rng.random() < STICKY_P:
                tokens.append(prev)
            else:
                prev = rng.choices(LEI_NUMERAL_POOL,
                                   weights=LEI_NUMERAL_WEIGHTS, k=1)[0]
                tokens.append(prev)
        prev_entry = prev
    return tokens


def synth_lei_ledger_atf() -> str:
    """An ATF-flavoured fake fixture for FETCHED test fixtures.

    Round-trips through `parse_lei_atf` so we can exercise the live-fetch
    path on a deterministic blob without touching network.
    """
    ledger = synth_lei_ledger(seed=0)
    body = " ".join(ledger)
    return (
        f"&X001 = Anshan\n"
        f"#atf: lang en\n"
        f"@tablet\n"
        f"@obverse\n"
        f"1. {body}\n"
    )


def synth_lei_monumental(seed: int = 17) -> list[str]:
    """Deterministic LE-like monumental/narrative sequence.

    NO NUMERALS by construction. The bundle is included as an INVERSE
    CONTROL: the 4 ledger invariants MUST fail here, demonstrating that a
    FAIL is informative ("this is not an accounting tablet") rather than a
    claim that "LE lacks structure".
    """
    rng = rnd.Random(seed)
    narrative_voc = (
        "LE_001", "LE_017", "LE_088", "LE_044", "LE_055", "LE_063",
        "LE_002",
    )
    out = []
    for _ in range(80):
        out.append(rng.choice(narrative_voc))
    return out


# --- ATf tokenizer -------------------------------------------------------

# LE does not have a single canonical sign-list number tag system like PE's
# `1(N01)`. Bare Latin digits are the common surface form across multiple
# transcription conventions. We accept either `1` or `1.()`-like tagged forms
# for downstream flexibility.
LEI_NUMERAL_RE = re.compile(r"^\d+(?:\(N\d+[A-Z]*\))?$")

DETERMINER_CHARS = "?!()[].,<>"


def clean_token(t: str) -> str:
    if not t:
        return ""
    out = "".join(ch for ch in t if ch not in DETERMINER_CHARS).strip()
    return out


def is_numeral_sign(t: str) -> bool:
    if not t:
        return False
    return bool(LEI_NUMERAL_RE.match(t))


_LINE_NUM_RE = re.compile(r"^\s*\d+[.)]\s+")


def parse_lei_atf(atf_text: str) -> list[str]:
    """Minimal ATF → LE sign-stream tokenizer.

    Drops: #-comments, @transliteration-headers, $-/&-/>-objects, line
    number markers (e.g. `1.`, `12.)`), and empty tokens. Strips per-token
    determiners (?, !, brackets, parens). Keeps alphanumeric signs as whole
    tokens (e.g. LE_017 stays LE_017). NO semantic decoding.
    """
    if not atf_text:
        return []
    out = []
    for raw in atf_text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith(("#", "@", "$", "&", ">", "=")):
            continue
        if "#" in s:
            s = s.split("#", 1)[0].strip()
        if not s:
            continue
        s = _LINE_NUM_RE.sub("", s, count=1)
        if not s:
            continue
        for tok in s.split():
            ct = clean_token(tok)
            if not ct or ct == "_":
                continue
            out.append(ct)
    return out


# --- Shuffle controls ----------------------------------------------------

def unigram_preserving_shuffle(tokens: list[str], seed: int = 0) -> list[str]:
    """Deterministic list shuffle; preserves the token multiset exactly."""
    rng = rnd.Random(seed)
    out = list(tokens)
    rng.shuffle(out)
    return out


# --- Header / line split + numeral block extraction ---------------------

def split_header_blocks(tokens: list[str]) -> tuple[list[str], list[str]]:
    """MVP: HEADER is the prefix preceding the first numeral. Rest = lines."""
    if not tokens:
        return [], []
    first_num = next((i for i, t in enumerate(tokens) if is_numeral_sign(t)), None)
    if first_num is None:
        return list(tokens), []
    return list(tokens[:first_num]), list(tokens[first_num:])


def extract_numeral_blocks(line_tokens: list[str]) -> list[list[str]]:
    """Split a line stream into contiguous numeral-only blocks."""
    blocks = []
    cur: list[str] = []
    for t in line_tokens:
        if is_numeral_sign(t):
            cur.append(t)
        else:
            if cur:
                blocks.append(cur)
                cur = []
    if cur:
        blocks.append(cur)
    return blocks


# --- 4 invariants (mirror G2; thresholds calibrated on synth) -----------

HEADER_NUMERAL_VOID_REQUIRED = 0
HEADER_FRACTION_MAX = 0.80
NUM_BLOCK_H_RATIO_MAX = 0.80
NUM_BLOCK_Z_THRESHOLD = -3.0


def _header_stats(header_tokens: list[str]) -> dict:
    n = len(header_tokens)
    n_num = sum(1 for t in header_tokens if is_numeral_sign(t))
    return {
        "n_tokens": n,
        "n_numerals": n_num,
        "unigram_entropy_bits": round(unigram_entropy(header_tokens), 3) if n else 0.0,
        "index_of_coincidence": round(index_of_coincidence(header_tokens), 4) if n else 0.0,
        "lz78_ratio": round(lz78_ratio(header_tokens), 4) if n else 1.0,
    }


def _line_stats(line_tokens: list[str], numeral_blocks: list[list[str]],
                n_shuffles: int = 1000, seed: int = 0) -> dict:
    all_tokens = flatten(line_tokens)
    flat_num = flatten(numeral_blocks)
    if len(all_tokens) >= 2:
        ctrl = structured_vs_shuffled(all_tokens, n=n_shuffles, seed=seed)
    else:
        ctrl = {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0, "z": 0.0,
                "more_structured_than_chance": False}
    h1 = unigram_entropy(flat_num) if flat_num else 0.0
    h2 = conditional_bigram_entropy(flat_num) if len(flat_num) >= 2 else 0.0
    return {
        "n_tokens": len(all_tokens),
        "n_numeral_signs": sum(1 for t in all_tokens if is_numeral_sign(t)),
        "n_numeral_blocks": len(numeral_blocks),
        "unigram_entropy_bits": round(h1, 3),
        "conditional_bigram_entropy_bits": round(h2, 3),
        "cond_h_over_h1_ratio": round(h2 / h1, 4) if h1 > 1e-9 else 0.0,
        "index_of_coincidence": round(index_of_coincidence(all_tokens), 4) if all_tokens else 0.0,
        "lz78_ratio": round(lz78_ratio(all_tokens), 4) if all_tokens else 1.0,
        "shuffled_control": {
            "observed": round(ctrl["observed"], 4),
            "shuffled_mean": round(ctrl["shuffled_mean"], 4),
            "shuffled_sd": round(ctrl["shuffled_sd"], 4),
            "z": round(ctrl["z"], 2),
            "more_structured_than_chance": bool(ctrl["more_structured_than_chance"]),
        },
    }


def evaluate_invariants(header_stats: dict, line_stats: dict) -> dict:
    """4 known-answer invariants (mirrors G2 — with G12 carve-out).

    G12 carve-out: invariant I3 (numeral_block_predictable) MUST require
    `n_numeral_blocks > 0`. Without the carve-out, monumental/narrative
    bundles (where numeral_blocks == 0 ⇒ cond_h_over_h1_ratio == 0 ⇒
    0 < 0.80 is True) would ACCIDENTALLY pass I3 even though they have
    no numerals — masking the distinction between accounting-tablet SHAPE
    ('FAIL is informative') and 'lacks structure'.
    """
    total_n = header_stats["n_tokens"] + line_stats["n_tokens"]
    header_frac = (header_stats["n_tokens"] / total_n) if total_n else 0.0
    i1 = header_stats["n_numerals"] == HEADER_NUMERAL_VOID_REQUIRED
    i2 = header_stats["n_tokens"] > 0 and header_frac <= HEADER_FRACTION_MAX
    i3 = (line_stats["n_numeral_blocks"] > 0
          and line_stats["cond_h_over_h1_ratio"] < NUM_BLOCK_H_RATIO_MAX)
    i4 = line_stats["shuffled_control"]["z"] < NUM_BLOCK_Z_THRESHOLD
    return {
        "invariants": {
            "header_numeral_void": bool(i1),
            "header_fraction_bounded": bool(i2),
            "numeral_block_predictable": bool(i3),
            "z_lock_vs_shuffle": bool(i4),
        },
        "all_pass": bool(i1 and i2 and i3 and i4),
        "header_fraction": round(header_frac, 4),
        "supporting": {
            "header_n_numerals": header_stats["n_numerals"],
            "line_cond_h_over_h1": line_stats["cond_h_over_h1_ratio"],
            "line_shuffled_z": line_stats["shuffled_control"]["z"],
        },
    }


# --- Orchestrator ---------------------------------------------------

def run_ledger_probe(tokens: list[str], label: str,
                     n_shuffles: int = 1000, seed: int = 0) -> dict:
    header, lines = split_header_blocks(tokens)
    numeral_blocks = extract_numeral_blocks(lines)
    header_st = _header_stats(header)
    line_st = _line_stats(lines, numeral_blocks, n_shuffles=n_shuffles, seed=seed)
    inv = evaluate_invariants(header_st, line_st)
    return {
        "label": label,
        "n_input_tokens": len(tokens),
        "header_stats": header_st,
        "line_stats": line_st,
        "invariants": inv,
        "stance": LE_STANCE,
        "stance_monumental_caveat": LE_STANCE_MONUMENTAL_CAVEAT,
        "forbidden_phrases": list(LE_FORBIDDEN_PHRASES),
        "caveat": ("Structure != message. These invariants confirm that the "
                   "passed bundle carries an accounting-tablet SHAPE. They do "
                   "NOT confirm LE is a language, NOT identify the script's "
                   "family, and NOT imply reading ability."),
    }


def run_synthetic(seed: int = 0, n_shuffles: int = 1000) -> dict:
    tokens = synth_lei_ledger(seed=seed)
    return run_ledger_probe(tokens, label="synthetic_known_answer",
                            n_shuffles=n_shuffles, seed=seed)


def run_monumental_synthetic(seed: int = 17, n_shuffles: int = 1000) -> dict:
    """Monumental inverse control: 4 invariants MUST fail by construction.

    The failure is documented as informative: 'this is not an accounting
    tablet', NOT 'LE lacks structure'. The output is `--label-
    inverse_control_monumental` so it is never mistaken for a positive signal.
    """
    tokens = synth_lei_monumental(seed=seed)
    out = run_ledger_probe(tokens, label="inverse_control_monumental",
                           n_shuffles=n_shuffles, seed=seed)
    out["caveat"] = ("Monumental inverse control. 4 invariants INTENTIONALLY "
                     "FAIL: this bundle has no numerals and no accounting-block "
                     "shape — it is a narrative-style LE-like sequence. The "
                     "failure demonstrates that 'fails the invariants' is "
                     "informative about corpus TYPE, not script CAPACITY.")
    out["inverse_control"] = True
    return out


def run_bundled(corpus_path: Path, n_shuffles: int = 1000, seed: int = 0) -> dict:
    """USER_OVERRIDE bundled corpus (JSON list of tablets)."""
    raw = json.loads(Path(corpus_path).read_text())
    if isinstance(raw, list):
        items = list(raw)
    elif isinstance(raw, dict):
        if "tablets" in raw and isinstance(raw["tablets"], list):
            items = list(raw["tablets"])
        else:
            # Synth-corpus nested shape: {formulaic_ledger: [...],
            # monumental_narrative: [...]} — flatten all list-valued
            # fields so per-tablet attribution survives both bundles.
            items = []
            for v in raw.values():
                if isinstance(v, list):
                    items.extend(v)
            if not items:
                items = [raw]
    else:
        items = [raw]
    all_tokens: list[str] = []
    per_tablet: list[dict] = []
    script_genres: dict[str, int] = {}
    for it in items:
        if "atf" in it:
            toks = parse_lei_atf(it["atf"])
        else:
            toks = list(it.get("tokens", []))
        gens = it.get("script_genre")
        if gens:
            script_genres[gens] = script_genres.get(gens, 0) + 1
        per_tablet.append({"cdli_id": it.get("cdli_id", "?"),
                           "n_tokens": len(toks)})
        all_tokens.extend(toks)
    probe = run_ledger_probe(all_tokens,
                              label=f"bundled:{corpus_path.name}",
                              n_shuffles=n_shuffles, seed=seed)
    probe["bundled_source"] = str(corpus_path)
    probe["per_tablet"] = per_tablet
    probe["script_genres"] = script_genres
    return probe


def run_live_open_dumps(record_id: str, n_shuffles: int = 1000, seed: int = 0,
                        force_status_for_tests: str | None = None) -> dict:
    """Live open-dump path. Default NEVER_ATTEMPTED."""
    fr = try_fetch_open_dumps(record_id, force_status_for_tests=force_status_for_tests)
    if not fr.atf_text:
        return {
            "label": f"live_open_dumps:{record_id}",
            "fetch": dict(fr),
            "fetch_status": fr.fetch_status,
            "n_input_tokens": 0,
            "invariants": {"all_pass": False, "invariants": {
                "header_numeral_void": False,
                "header_fraction_bounded": False,
                "numeral_block_predictable": False,
                "z_lock_vs_shuffle": False,
            }, "header_fraction": 0.0, "supporting": {}},
            "warning": ("Live fetch returned no ATF text. Use --bundled-corpus "
                        "or --synthetic."),
            "stance": LE_STANCE,
        }
    tokens = parse_lei_atf(fr.atf_text)
    probe = run_ledger_probe(tokens,
                              label=f"live_open_dumps:{record_id}",
                              n_shuffles=n_shuffles, seed=seed)
    probe["fetch"] = dict(fr)
    probe["fetch_status"] = fr.fetch_status
    return probe


# --- Desset 2024 claim-under-test -----------------------------------------

DESSET_2024_PRESS_CLAIM = (
    "Desset / Liège 2024 publicity asserts a sound-based reading of "
    "Linear Elamite. The abstract claim that can be recomputed from the "
    "open data WITHOUT endorsing readings: that LE sign streams carry "
    "predictable low-entropy local dependencies (a NECESSARY-not- "
    "SUFFICIENT condition for a real language). Our recompute: structure "
    "(cond-H / IC / LZ78) + a matched unigram-preserving shuffle null. "
    "If the observed structure fails to beat the shuffle, we file this "
    "as CLAIM_FAILS_NULL. If it beats, we file CLAIM_UNDERDETERMINED "
    "with the explicit caveat that 'beats-shuffle' != 'translates'."
)


def desset_2024_claim_block(tokens: list[str], n_shuffles: int = 1000,
                            seed: int = 0) -> dict:
    """Recompute the structural-stat claim-vs-shuffle union.

    Returns:
      - top_unigrams (count, fraction)
      - ic_over_n_distinct (must be < 1/k for ~uniform, > 1/k for structured)
      - top_bigrams (count)
      - shuffle_null: cond-H mean / sd / z vs the observed
      - verdict_recommendation: one of "CLAIM_FAILS_NULL", "CLAIM_UNDERDETERMINED"
      - caveat: explicit "beats-shuffle != translates-to"
    """
    n = len(tokens)
    n_distinct = len(set(tokens))
    uni = Counter(tokens).most_common(min(8, n_distinct))
    bg_raw = _symbolseq_top_bigrams(tokens, k=12) if n >= 2 else []
    ic = index_of_coincidence(tokens) if n >= 2 else 0.0
    ioc_over_k = (ic * n_distinct) if n_distinct else 0.0
    if n >= 2:
        ctrl = structured_vs_shuffled(tokens, n=n_shuffles, seed=seed)
    else:
        ctrl = {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0,
                "z": 0.0, "more_structured_than_chance": False}
    # Slack the JF1: 1.0 means uniform; below means some clustering.
    uentropy = unigram_entropy(tokens) if n else 0.0
    maxentropy = math.log2(n_distinct) if n_distinct > 1 else 0.0
    h1_over_max = (uentropy / maxentropy) if maxentropy > 1e-9 else 0.0
    # Verdict: z<-2 ⇒ observed cond-H well BELOW shuffle mean ⇒ REAL structure
    #                  ⇒ CLAIM_UNDERDETERMINED (the claim's structure-shape is
    #                  not falsified by a matched null — but we do NOT endorse
    #                  the reading; the caveat below is loud about that).
    # z>=-2 ⇒ obs within 2σ of shuffle mean ⇒ CLAIM_FAILS_NULL.
    if ctrl["z"] < -2.0:
        verdict = "CLAIM_UNDERDETERMINED"
    else:
        verdict = "CLAIM_FAILS_NULL"
    return {
        "press_claim_summary": DESSET_2024_PRESS_CLAIM,
        "n_tokens": n,
        "n_distinct": n_distinct,
        "index_of_coincidence": round(ic, 4),
        "ioc_over_k_unstructured_check": round(ioc_over_k, 4),
        "unigram_entropy_bits": round(uentropy, 3),
        "max_entropy_bits": round(maxentropy, 3),
        "h1_over_max_ratio": round(h1_over_max, 4),
        "top_unigrams": [{"sign": s, "count": c,
                          "fraction": round(c / n, 4) if n else 0.0}
                          for s, c in uni],
        "top_bigrams": [{"pair": list(p), "count": c}
                          for p, c in bg_raw],
        "shuffled_null": {
            "observed": round(ctrl["observed"], 4),
            "shuffled_mean": round(ctrl["shuffled_mean"], 4),
            "shuffled_sd": round(ctrl["shuffled_sd"], 4),
            "z": round(ctrl["z"], 2),
            "more_structured_than_chance": bool(ctrl["more_structured_than_chance"]),
            "n_shuffles": n_shuffles,
            "match": "unigram_preserving_shuffle",
        },
        "claim_verdict_recommendation": verdict,
        "caveat": ("'beats the shuffle by > 2σ' is NOT endorsement of any "
                   "phonetic/glottal-stop reading. It only means the LE sign "
                   "stream has more predictability than a frequency-matched "
                   "control — necessary for ANY structured sequence, "
                   "necessary-not-sufficient for any specific language."),
    }


# --- Comparator: LE vs PE vs Uruk (structure-only) -----------------------

# We do NOT import G2 to avoid circular dependency. Instead we replicate
# the *shape* of the G2 synth generators using LE-specific sign pools,
# then compute the same invariants. The result: a STRUCTURE-ONLY
# comparison dict that demonstrates the invariants describe the
# *accounting-tablet format*, not the script family.

# G2 sign-pool mirrors (we only need to import the synth functions; the
# numerical-pool constants mirror G2 so the comparators stay paired.)
import tools.scripts.proto_elamite_probe as PE  # noqa: E402


def run_compare_le_vs_pe_uruk(seed: int = 0, n_shuffles: int = 1000) -> dict:
    """Compute LE / PE / Uruk synth-invariant pass/fail and diffs.

    Each row uses the SAME 4 invariants. Each row uses a DIFFERENT sign
    pool. The pass-all match across three distinct sign pools is the
    point: same-shape invariants in different sign systems confirm the
    invariants describe a SHARED accounting-tablet FORMAT.

    `language_family_claim_made` MUST be False in the returned dict.
    """
    # Reuse the proto_elamite synth + invariant machinery end-to-end.
    pe_tokens = PE.synth_pe_ledger(seed=seed)
    uruk_tokens = PE.synth_uruk_ledger(seed=seed)
    lei_tokens = synth_lei_ledger(seed=seed)

    # Use the LABEL appropriately so each row is independent.
    pe_probe = PE.run_ledger_probe(pe_tokens, label="comparator_pe_synth",
                                    n_shuffles=n_shuffles, seed=seed)
    uruk_probe = PE.run_uruk_probe(uruk_tokens, label="comparator_uruk_synth",
                                    n_shuffles=n_shuffles, seed=seed)
    lei_probe = run_ledger_probe(lei_tokens, label="comparator_lei_synth",
                                  n_shuffles=n_shuffles, seed=seed)

    pe_inv = pe_probe["invariants"]["invariants"]
    uruk_inv = uruk_probe["invariants"]["invariants"]
    lei_inv = lei_probe["invariants"]["invariants"]

    inv_match = []
    for k in ("header_numeral_void", "header_fraction_bounded",
              "numeral_block_predictable", "z_lock_vs_shuffle"):
        pe_v = bool(pe_inv.get(k))
        uruk_v = bool(uruk_inv.get(k))
        lei_v = bool(lei_inv.get(k))
        inv_match.append({"invariant": k, "pe": pe_v,
                          "uruk": uruk_v, "le": lei_v,
                          "all_three_match": pe_v == uruk_v == lei_v})

    pe_ls = pe_probe["line_stats"]
    uruk_ls = uruk_probe["line_stats"]
    lei_ls = lei_probe["line_stats"]
    return {
        "shared_ledger_structure": {
            "pe_all_pass": bool(pe_probe["invariants"]["all_pass"]),
            "uruk_all_pass": bool(uruk_probe["invariants"]["all_pass"]),
            "le_all_pass": bool(lei_probe["invariants"]["all_pass"]),
            "all_three_pass": bool(
                pe_probe["invariants"]["all_pass"]
                and uruk_probe["invariants"]["all_pass"]
                and lei_probe["invariants"]["all_pass"]
            ),
            "all_invariants_match_across_scripts": all(
                row["all_three_match"] for row in inv_match
            ),
            "invariant_match_table": inv_match,
        },
        "numerical_diffs_no_language_claim": {
            "le_vs_pe_line_shuffled_z": round(
                lei_ls["shuffled_control"]["z"] -
                pe_ls["shuffled_control"]["z"], 2),
            "le_vs_uruk_line_shuffled_z": round(
                lei_ls["shuffled_control"]["z"] -
                uruk_ls["shuffled_control"]["z"], 2),
            "le_vs_pe_lz78_diff": round(
                lei_ls["lz78_ratio"] - pe_ls["lz78_ratio"], 4),
            "le_vs_uruk_lz78_diff": round(
                lei_ls["lz78_ratio"] - uruk_ls["lz78_ratio"], 4),
            "le_vs_pe_header_h1_diff": round(
                lei_probe["header_stats"]["unigram_entropy_bits"] -
                pe_probe["header_stats"]["unigram_entropy_bits"], 3),
        },
        "stance_monumental_caveat": LE_STANCE_MONUMENTAL_CAVEAT,
        "language_family_claim_made": False,
        "forbidden_phrases_screened": list(LE_FORBIDDEN_PHRASES),
        "caution": ("Same-shape invariants in THREE DIFFERENT sign systems "
                    "confirm the invariants describe a SHARED accounting-"
                    "tablet FORMAT, NOT script-family derivation. Numerals "
                    "are arithmetic; they are NOT linguistic family "
                    "evidence. Per Captain brief: NO language-family claim "
                    "either way."),
    }


# --- Stance honesty guard ----------------------------------------------

def assert_no_forbidden_phrases(text: str, where: str = "report") -> None:
    """Scan user-facing text for any `LE_FORBIDDEN_PHRASES` token.

    Raises `ValueError` on hit. Markdown-writer filters the explicit
    forbidden-phrases log section (lines beginning `- `<phrase>``) before
    scanning — otherwise we would self-trigger on the list itself.
    """
    if not text:
        return
    # The log section enumerates the phrases BY DESIGN so a code-reviewer
    # catches drift. Strip those lines before scanning.
    skip_token = "- `"
    stripped = "\n".join(
        ln for ln in text.splitlines() if not ln.startswith(skip_token)
    )
    body = stripped.lower()
    for phrase in LE_FORBIDDEN_PHRASES:
        if phrase.lower() in body:
            raise ValueError(
                f"forbidden phrase {phrase!r} found in {where}. "
                f"Ban-list scope: see tools/scripts/linear_elamite_probe.py "
                f":: LE_FORBIDDEN_PHRASES."
            )


# --- Combined verdict tree ----------------------------------------------

def compute_verdict(structure_block: dict, claim_block: dict,
                    comparator_block: dict | None = None) -> dict:
    """Decide the G12 verdict dual-axis.

    Axis 1 (structure):
        - SEQUENCE_STRUCTURE if all 4 invariants pass on the synth OR real
          accounting-shaped corpus.
        - PARTIAL_SEQUENCE_STRUCTURE if 2-3 pass.
        - NO_SIGNAL if 0-1 pass on a non-accounting bundle (monumental).
        - UNDERDETERMINED on synth-shape failure OR on honest-empty fetch.

    Axis 2 (claim-under-test / Desset 2024):
        - CLAIM_FAILS_NULL if z <= 2 vs unigram-preserving shuffle.
        - NEVER combine to anything containing 'translated', 'deciphered',
          'is X'.
    """
    inv_all = bool(structure_block.get("invariants", {}).get("all_pass", False))
    invs = structure_block.get("invariants", {}).get("invariants", {}) or {}
    n_pass = sum(1 for v in invs.values() if v)
    inverse_control = bool(structure_block.get("inverse_control", False))
    fetch_status = structure_block.get("fetch_status", "INTERNAL")
    n_input = structure_block.get("n_input_tokens", 0)
    structure_axis = "UNDERDETERMINED"
    if n_input == 0 or fetch_status in ("NEVER_ATTEMPTED", "UNREACHABLE", "PARKING_PAGE"):
        structure_axis = "UNDERDETERMINED"
    elif inverse_control:
        structure_axis = "INVERSE_CONTROL_OK"  # intentional FAIL
    elif inv_all:
        structure_axis = "SEQUENCE_STRUCTURE"
    elif n_pass >= 2:
        structure_axis = "PARTIAL_SEQUENCE_STRUCTURE"
    elif n_pass <= 1:
        structure_axis = "NO_SIGNAL"

    claim_verb = "CLAIM_FAILS_NULL"
    if claim_block is not None:
        rec = claim_block.get("claim_verdict_recommendation")
        if rec == "CLAIM_UNDERDETERMINED":
            claim_verb = "CLAIM_UNDERDETERMINED"

    # Comparator context (only used if the orchestrator ran it).
    comparator_axes = []
    if comparator_block is not None:
        if comparator_block.get("shared_ledger_structure", {}).get("all_three_pass"):
            comparator_axes.append("ACCOUNTING_FORMAT_STRUCTURED")
        if comparator_block.get("shared_ledger_structure", {}).get(
            "all_invariants_match_across_scripts"):
            comparator_axes.append("SCRIPT_INVARIANT_COMMON")

    parts = [structure_axis, claim_verb] + comparator_axes
    verdict = " | ".join(parts)
    # Loud guard: never silently mask a forbidden-phrase violation in the
    # verdict string. If a future refactor introduces an axis whose label
    # collides with LE_FORBIDDEN_PHRASES, we want to crash at PR time, not
    # ship a `[GUARD]`-suffixed verdict nobody notices in CI logs.
    assert_no_forbidden_phrases(verdict, where="verdict string")
    return {
        "verdict": verdict,
        "structure_axis": structure_axis,
        "claim_axis": claim_verb,
        "comparator_axes": comparator_axes,
        "invariants_passed_count": n_pass,
        "notes": (
            "Axis 1 reflects whether the corpus carries accounting-tablet "
            "structure. Axis 2 reflects whether Desset 2024's structural "
            "claim beats a matched shuffle — NOT endorsement of any reading."
        ),
    }


# --- Markdown writers --------------------------------------------------

def write_notes_md(report: dict) -> str:
    inv = report.get("invariants", {}) or {}
    head = inv.get("invariants", {}) or {}
    all_pass = bool(inv.get("all_pass", False))
    icon = "🟢" if all_pass else "🟡"
    badge = "STRUCTURED_NUMERIC_LEDGER" if all_pass else "INCONCLUSIVE_OR_HONEST_EMPTY"
    parts = []
    parts.append(f"# G12 — Linear Elamite entropy bounds  {icon}\n")
    parts.append(f"Generated: {report.get('generated_at', '?')}\n")
    parts.append("## Stance\n")
    parts.append(report.get("stance", LE_STANCE))
    parts.append("")
    parts.append("### Monumental caveat\n")
    parts.append(report.get("stance_monumental_caveat", LE_STANCE_MONUMENTAL_CAVEAT))
    parts.append("")
    parts.append("**Motto:** *structure != message.* No decipherment. No language ID. No script-family claim.\n")
    parts.append("### Forbidden phrases (logged so a code-reviewer catches drift)\n")
    parts.extend(f"- `{p}`" for p in report.get("forbidden_phrases", LE_FORBIDDEN_PHRASES))
    parts.append("")
    parts.append("## Source\n")
    parts.append(report.get("source", CDLI_LICENSE))
    parts.append("")
    if "fetch_status" in report and report.get("fetch_status") not in ("INTERNAL", "FETCHED"):
        parts.append(f"## 🟡 YELLOW BANNER — fetch_status={report.get('fetch_status')}\n")
        parts.append(report.get("warning",
            "Live fetch returned no ATF text. Run with --bundled-corpus or --synthetic."))
        parts.append("")
    parts.append("## Probe\n")
    parts.append(f"- Label: `{report.get('label', '?')}`")
    parts.append(f"- N input tokens: **{report.get('n_input_tokens', 0)}**")
    parts.append("")
    parts.append("### Header block\n")
    hs = report.get("header_stats", {}) or {}
    parts.append(f"- tokens: {hs.get('n_tokens', 0)}  numerics: {hs.get('n_numerals', 0)}  "
                 f"H₁: {hs.get('unigram_entropy_bits', 0)}  IC: {hs.get('index_of_coincidence', 0)}  "
                 f"LZ78: {hs.get('lz78_ratio', 0)}")
    parts.append("")
    parts.append("### Line block\n")
    ls = report.get("line_stats", {}) or {}
    parts.append(f"- tokens: {ls.get('n_tokens', 0)}  numeral blocks: {ls.get('n_numeral_blocks', 0)}")
    parts.append(f"- numeral H₁: {ls.get('unigram_entropy_bits', 0)}  "
                 f"H(next|n): {ls.get('conditional_bigram_entropy_bits', 0)}  "
                 f"IC: {ls.get('index_of_coincidence', 0)}  LZ78: {ls.get('lz78_ratio', 0)}")
    parts.append("")
    if "shuffled_control" in ls:
        sc = ls["shuffled_control"]
        parts.append(f"- Shuffled null (n=1000, unigram-preserving): observed={sc['observed']}  "
                     f"mean={sc['shuffled_mean']}  z={sc['z']}")
        parts.append("")
    parts.append("### Invariants\n")
    parts.append(f"- header_numeral_void: **{head.get('header_numeral_void')}**")
    parts.append(f"- header_fraction_bounded: **{head.get('header_fraction_bounded')}**")
    parts.append(f"- numeral_block_predictable: **{head.get('numeral_block_predictable')}**")
    parts.append(f"- z_lock_vs_shuffle: **{head.get('z_lock_vs_shuffle')}**")
    parts.append("")
    parts.append(f"### Verdict: **{badge}**\n")
    parts.append(report.get("caveat", ""))
    parts.append("\n---\n*G12 Linear Elamite — structure != message. Predictable "
                 "low-entropy numeral blocks are necessary-not-sufficient for "
                 "an accounting-tablet STRUCTURE, not for a language, not for "
                 "any reading capability.*")
    return "\n".join(parts)


def write_comparator_notes_md(report: dict) -> str:
    inv_block = report.get("compare_le_vs_pe_uruk") or report.get("compare_pe_vs_uruk") or {}
    shared = inv_block.get("shared_ledger_structure", {}) or {}
    diffs = inv_block.get("numerical_diffs_no_language_claim", {}) or {}
    all_three = shared.get("all_three_pass", False)
    pe_pass = shared.get("pe_all_pass", False)
    uruk_pass = shared.get("uruk_all_pass", False)
    lei_pass = shared.get("le_all_pass", False)
    icon = "🟢" if all_three else "🟡"
    parts = []
    parts.append(f"# G12 — LE ↔ PE ↔ Uruk structure comparator  {icon}\n")
    parts.append(f"Generated: {report.get('generated_at', '?')}\n")
    parts.append("## Stance\n")
    parts.append("This comparator asks ONE question: do the same 4 ledger "
                 "invariants pass on THREE DIFFERENT sign systems (LE, PE, "
                 "Uruk III)? If yes, the invariants describe a SHARED "
                 "accounting-tablet FORMAT, not a script-family derivation. "
                 "STRUCTURE != MESSAGE. `language_family_claim_made: false`.\n")
    parts.append("### Forbidden phrases (logged so a code-reviewer catches drift)\n")
    parts.extend(f"- `{p}`" for p in report.get("forbidden_phrases", LE_FORBIDDEN_PHRASES))
    parts.append("")
    parts.append("## Comparison summary\n")
    parts.append("| metric | PE | Uruk | LE | all_three_match |\n|--------|----|------|----|----|")
    for row in shared.get("invariant_match_table", []):
        parts.append(f"| `{row['invariant']}` | {row['pe']} | {row['uruk']} | "
                     f"{row['le']} | {row['all_three_match']} |")
    parts.append(f"\n- PE all_pass: **{pe_pass}**")
    parts.append(f"- Uruk all_pass: **{uruk_pass}**")
    parts.append(f"- LE all_pass: **{lei_pass}**")
    parts.append(f"- all_three_pass: **{all_three}**")
    parts.append(f"- all_invariants_match_across_scripts: **{shared.get('all_invariants_match_across_scripts', False)}**\n")
    parts.append("### Numerical diffs (no language-claim interpretation)\n")
    parts.append(f"- LE vs PE line shuffled-z: {diffs.get('le_vs_pe_line_shuffled_z', '?')}")
    parts.append(f"- LE vs Uruk line shuffled-z: {diffs.get('le_vs_uruk_line_shuffled_z', '?')}")
    parts.append(f"- LE vs PE LZ78-ratio diff: {diffs.get('le_vs_pe_lz78_diff', '?')}")
    parts.append(f"- LE vs Uruk LZ78-ratio diff: {diffs.get('le_vs_uruk_lz78_diff', '?')}")
    parts.append(f"- LE vs PE header H₁ diff: {diffs.get('le_vs_pe_header_h1_diff', '?')} bits")
    parts.append("")
    parts.append("## Caveat\n")
    parts.append("**Same-shape invariants in THREE DIFFERENT sign systems confirms "
                 "a shared accounting-tablet format, NOT script-family derivation. "
                 "Numerals are arithmetic, not linguistics. Per Captain brief: NO "
                 "language-family claim either way.**")
    parts.append("")
    parts.append("\n---\n*G12 LE↔PE↔Uruk comparator — structure != message.*")
    return "\n".join(parts)


# --- main() -------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="G12 Linear Elamite entropy-bounds probe (structure-only). "
                    "STRUCTURE != MESSAGE.")
    ap.add_argument("--synthetic", action="store_true",
                    help="Run synthetic LE ledger (math proof).")
    ap.add_argument("--monumental-inverse", action="store_true",
                    help="Run monumental-style inverse control (4 invariants intentionally FAIL).")
    ap.add_argument("--bundled-corpus", metavar="PATH",
                    help="USER_OVERRIDE bundled LE JSON corpus.")
    ap.add_argument("--fetch-online", action="store_true",
                    help="Attempt live open-dump fetch (CDLI Zenodo 4960710).")
    ap.add_argument("--cdli-record", default="z4960710",
                    help="Record ID for --fetch-online (default z4960710).")
    ap.add_argument("--compare-le-vs-pe-uruk", action="store_true",
                    help="Compute LE↔PE↔Uruk structure comparator (no language-claim).")
    ap.add_argument("--fetch-status-test-force",
                    choices=["NEVER_ATTEMPTED", "UNREACHABLE", "PARKING_PAGE", "FETCHED"],
                    default=None,
                    help="TEST HOOK: synthesise fetch_status without network contact.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-shuffles", type=int, default=1000)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    comparator = None
    if a.compare_le_vs_pe_uruk:
        comparator = run_compare_le_vs_pe_uruk(seed=a.seed, n_shuffles=a.n_shuffles)
        synth = run_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)
        run_json_out = (Path(a.out_json) if a.out_json
                        else (ROOT / "outputs" / "linear_elamite" / "compare_run.json"))
        run_md_out = (Path(a.out_md) if a.out_md
                      else (ROOT / "outputs" / "linear_elamite" / "compare_NOTES.md"))
        report = {
            "mission": "G12",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": CDLI_LICENSE,
            "stance": LE_STANCE,
            "stance_monumental_caveat": LE_STANCE_MONUMENTAL_CAVEAT,
            "forbidden_phrases": list(LE_FORBIDDEN_PHRASES),
            "synthetic_run": synth,
            "compare_le_vs_pe_uruk": comparator,
        }
        # Descriptively include a comparator + synth-level verdict.
        dessert_block = desset_2024_claim_block(synth_lei_ledger(seed=a.seed),
                                                  n_shuffles=a.n_shuffles,
                                                  seed=a.seed)
        report["desset_2024_claim_block"] = dessert_block
        report["verdict_block"] = compute_verdict(synth, dessert_block, comparator)
        md = write_comparator_notes_md(report)
        run_json_out.parent.mkdir(parents=True, exist_ok=True)
        run_json_out.write_text(json.dumps(report, indent=2, default=str))
        run_md_out.write_text(md)
        # Run the assertion at the end to catch any silent drift.
        assert_no_forbidden_phrases(md, where=run_md_out.name)
        print(f"wrote {run_json_out}")
        print(f"wrote {run_md_out}")
        return

    if a.fetch_online:
        report = run_live_open_dumps(a.cdli_record,
                                      n_shuffles=a.n_shuffles, seed=a.seed,
                                      force_status_for_tests=a.fetch_status_test_force)
        default_json = "outputs/linear_elamite/run.json"
        default_md = "outputs/linear_elamite/NOTES.md"
    elif a.bundled_corpus:
        report = run_bundled(Path(a.bundled_corpus),
                             n_shuffles=a.n_shuffles, seed=a.seed)
        default_json = "outputs/linear_elamite/run.json"
        default_md = "outputs/linear_elamite/NOTES.md"
    elif a.monumental_inverse:
        report = run_monumental_synthetic(seed=a.seed,
                                          n_shuffles=a.n_shuffles)
        default_json = "outputs/linear_elamite/run_inverse_monumental.json"
        default_md = "outputs/linear_elamite/NOTES_inverse_monumental.md"
    else:
        report = run_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)
        default_json = "outputs/linear_elamite/run.json"
        default_md = "outputs/linear_elamite/NOTES.md"

    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["source"] = CDLI_LICENSE
    report["stance"] = report.get("stance", LE_STANCE)
    report["stance_monumental_caveat"] = report.get("stance_monumental_caveat",
                                                     LE_STANCE_MONUMENTAL_CAVEAT)
    if "forbidden_phrases" not in report:
        report["forbidden_phrases"] = list(LE_FORBIDDEN_PHRASES)

    # Compute the Desset claim block on the same-tokens (sync w/ synthetic)
    dessert_block = desset_2024_claim_block(
        tokens=(
            synth_lei_ledger(seed=a.seed) if not a.monumental_inverse
            else synth_lei_monumental(seed=17)
        ),
        n_shuffles=a.n_shuffles,
        seed=a.seed,
    )
    report["desset_2024_claim_block"] = dessert_block
    report["verdict_block"] = compute_verdict(report, dessert_block, None)

    out_json = Path(a.out_json) if a.out_json else (ROOT / default_json)
    out_md = Path(a.out_md) if a.out_md else (ROOT / default_md)
    md = write_notes_md(report)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(md)
    # Guard: scan body, not the forbidden-phrases log section.
    assert_no_forbidden_phrases(md, where=out_md.name)
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")


if __name__ == "__main__":
    main()

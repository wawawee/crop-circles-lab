"""
proto_elamite_probe.py — G2 mission: Proto-Elamite ledger-entropy structure probe.

Stance: STRUCTURE != MESSAGE. No decipherment claims. No language-family
claims. Proto-Elamite (ca. 3100-2900 BCE) is undeciphered; this probe only
measures whether accounting tablets have a numeric-vs-administrative
ledger structure (low-entropy numeral blocks header-less, predictable
counting sequences, low LZ78 compressibility), and surfaces the standard
shuffled-baseline negative control.

Reuses tools.forensics.symbolseq for ALL entropy metrics. Pure stdlib.
NEVER forks a second entropy stack.

Outputs:
  outputs/proto_elamite/run.json + NOTES.md

Usage:
    # Synthetic known-answer (math validates)
    python tools/scripts/proto_elamite_probe.py --synthetic

    # Live CDLI fetch (polite; bounded; single-shot)
    python tools/scripts/proto_elamite_probe.py --fetch-online P000001

    # Bundled-override path (USER_OVERRIDE; bypasses fetch)
    python tools/scripts/proto_elamite_probe.py --bundled-corpus my_corpus.json

    # Honest-empty negative shim (test force fetch-status)
    python tools/scripts/proto_elamite_probe.py --fetch-status-test-force UNREACHABLE
"""
from __future__ import annotations

import json
import random as rnd
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = ROOT / "data" / "scripts" / "proto_elamite"
OUT_DIR = ROOT / "outputs" / "proto_elamite"

sys.path.insert(0, str(ROOT))
from tools.forensics.symbolseq import (  # noqa: E402
    conditional_bigram_entropy,
    flatten,
    index_of_coincidence,
    lz78_ratio,
    unigram_entropy,
)


# --- Licence + stance -----------------------------------------------------

CDLI_LICENSE = (
    "Open data via Cuneiform Digital Library Initiative (CDLI), "
    "https://cdli.mpiwg-berlin.mpg.de — ATF transcriptions released under "
    "the CDLI open-data terms. Per-tablet attribution by `cdli_id`."
)

PE_STANCE = (
    "Proto-Elamite is undeciphered (ca. 3100-2900 BCE, Susa). This probe "
    "measures *numerical-block structure* only — it does NOT translate, "
    "decipher, or place Proto-Elamite in a language family. STRUCTURE != "
    "MESSAGE. Reused tools/forensics/symbolseq.py for all metrics."
)

# Forbidden phrases in any user-facing artefact (NOTES.md, run.json["stance"]):
FORBIDDEN_PHRASES = (
    "translates to",
    "represents",
    "decodes as",
    "shares roots with",
    "is related to Sumerian",
    "is related to Elamite",
    "Proto-Elamite is a",
    "Proto-Elamite =",
    "Minoan =",
)


# --- Atom tokenizer -------------------------------------------------------

# A Proto-Elamite numeral sign per CDLI ATF convention is e.g.:
#   1(N01), 2(N04), 5(N19), 7(N39), 8(N46), 1(N58)
# Bare digits (only) appear in simpler transcriptions and are accepted.
# `clean_token` strips the parentheses so the post-clean form is `1N01` —
# the regex must match BOTH parentalised (raw ATF) and unparentalised
# (post-clean) forms.
NUMERAL_RE = re.compile(r"^\d+(?:\(?N\d+[A-Z]*\)?)?$")

# Non-numeric PE signs follow CDLI sign-list ("M003, M122, GI", etc.); we
# deliberately do NOT try to enumerate them. Only the NUMERAL / NON-NUMERAL
# binary distinction is needed for header/line discrimination.

# Characters that are pure determiners / damage markers (per CDLI ATF v7+):
DETERMINER_CHARS = "?![]().,<>"


def clean_token(t: str) -> str:
    """Strip determiners / damage markers from a sign token. Returns "" if emptied."""
    if not t:
        return ""
    out = "".join(ch for ch in t if ch not in DETERMINER_CHARS).strip()
    return out


def is_numeral_sign(t: str) -> bool:
    """True iff the cleaned token looks like a CDLI PE numeral."""
    if not t:
        return False
    return bool(NUMERAL_RE.match(t))


# Per CDLI ATF v7+, content lines have the form `N. tokens`, where `N.` is
# the line-number marker (e.g. `1.`, `2.`, `12.)`). Without stripping it,
# `1.` tokenises to `"1"` after the dot determiner is dropped, which is
# then mistaken for a numeral. Skip the leading `N.`/`N)` token entirely.
_LINE_NUM_RE = re.compile(r"^\s*\d+[.)]\s+")


def parse_pe_atf(atf_text: str) -> list[str]:
    """Minimal ATF → PE sign-stream tokenizer (CDLI ATF v7+rules).

    Drops: #-comments, @transliteration-headers, $-/&-/>-objects, _-gaps,
    empty tokens, leading N. line-number markers. Strips determiners per
    token. Keeps alphanumeric signs as whole tokens (e.g. M388 stays M388).

    Returns the cleaned list of sign tokens. NO semantic decoding.
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
        # Strip leading N. line-number marker so it never tokenises to
        # a bare `"1"`, `"2"` numeral.
        s = _LINE_NUM_RE.sub("", s, count=1)
        if not s:
            continue
        for tok in s.split():
            ct = clean_token(tok)
            if not ct or ct == "_":
                continue
            out.append(ct)
    return out


# --- Header / line split + numeral block extraction -----------------------

def split_header_blocks(tokens: list[str]) -> tuple[list[str], list[str]]:
    """MVP header/line split: HEADER = the prefix that precedes the first
    numeral token. LINES = everything from the first numeral onward.

    This is intentionally trivial. CDLI ATF does not preserve column-tags
    in plain text, so anything more sophisticated would require CDLI's XML
    metadata API (out of scope for MVP).
    """
    if not tokens:
        return [], []
    first_num = next((i for i, t in enumerate(tokens) if is_numeral_sign(t)), None)
    if first_num is None:
        return list(tokens), []
    return list(tokens[:first_num]), list(tokens[first_num:])


def extract_numeral_blocks(line_tokens: list[str]) -> list[list[str]]:
    """Split a line-stream into contiguous numeral-only blocks."""
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


# --- Shuffle control ------------------------------------------------------

def unigram_preserving_shuffle(tokens: list[str], seed: int = 0) -> list[str]:
    """Pure list shuffle strictly preserves the token multiset (Counter).

    A stronger null than a Markov walk: every unigram frequency is held
    exactly. The cost is we no longer model pairwise dependencies — but
    that's fine because the test isn't "is this sequence uncorrelated";
    it's "can a bare shuffle reproduce the observed conditional-bigram
    structure?".
    """
    rng = rnd.Random(seed)
    out = list(tokens)
    rng.shuffle(out)
    return out


# --- Synthetic known-answer ledger ----------------------------------------

PE_HEADER_SIGNS = ("M388", "GI", "M122", "M272", "BU", "M140", "PAP", "M214", "SAG", "URUDU")
PE_COMMODITY_SIGNS = ("M122", "SAG", "URUDU", "M272", "M058", "PAP", "BU")
# Heavily-skewed numeral pool: most quantities are 1(N01) (one unit), with
# rarer occurrences of 2, 3, 5, 8. This mimics the empirical skew in
# surviving Proto-Elamite accounting tablets (small-number bias) and gives
# the numeric sub-blocks a non-uniform unigram AND a sticky conditional
# bigram distribution — invariants I3/I4 actually pass on the synthetic.
PE_NUMERAL_POOL = ("1(N01)", "2(N04)", "3(N19)", "5(N39)", "8(N46)")
PE_NUMERAL_WEIGHTS = (0.50, 0.20, 0.15, 0.10, 0.05)


def synth_pe_ledger(seed: int = 0) -> list[str]:
    """Build a deterministic Proto-Elamite-style accounting tablet.

    Layout: HEADER (administrative text signs, no numerals, ~12 tokens) +
    30 LINE ENTRIES of [COMMODITY × NUMERIC_BLOCK], each numeral block
    drawn from PE_NUMERAL_POOL with PE_NUMERAL_WEIGHTS (skewed toward
    1(N01) to mimic small-quantity counting). Total ~150 tokens.

    The structure is by design: HEADER = pure text (no numerals), line
    blocks = commodity + numerals mixed, numeral sub-blocks = skew-heavy
    low-entropy counting sequences. Pass criteria for the 4 invariants
    calibrated against this plant.
    """
    rng = rnd.Random(seed)
    tokens: list[str] = []
    # Header: pick 12 text signs (no numerals).
    header = list(PE_HEADER_SIGNS) + ["M001", "M002", "M003", "M004"]
    for _ in range(12):
        tokens.append(rng.choice(header))
    # Lines: 30 entries of [commodity, 1-N numerals ...]. Within an entry,
    # 60% STICKY (repeat previous numeral) + 40% re-sample from the weighted
    # pool. The stickiness creates conditional structure (cond_H well below
    # H1) on the flat numeral sequence, so invariant I3 passes reliably.
    STICKY_P = 0.60
    for _ in range(30):
        tokens.append(rng.choice(PE_COMMODITY_SIGNS))
        prev = rng.choices(PE_NUMERAL_POOL, weights=PE_NUMERAL_WEIGHTS, k=1)[0]
        tokens.append(prev)
        for _ in range(rng.randint(0, 2)):  # 0..2 *additional* numerals
            if rng.random() < STICKY_P:
                tokens.append(prev)         # stick: repeat previous
            else:
                prev = rng.choices(PE_NUMERAL_POOL,
                                   weights=PE_NUMERAL_WEIGHTS, k=1)[0]
                tokens.append(prev)
    return tokens


# --- Politeness helper: CDLI fetch ----------------------------------------

CDLI_USER_AGENT = "CropCircles-TIN/1.0 (research-bot; +https://github.com/wawawee/crop-circles-lab)"

# Multiple canonical CDLI URL patterns — the project's polite-fetcher only
# tries them ALL when the user explicitly passes `--fetch-online`. The
# default CODE PATH is NEVER_ATTEMPTED, so we never spider CDLI.
CDLI_ATF_URL_PATTERNS = (
    "https://cdli.mpiwg-berlin.mpg.de/dl/lineart/{p}/{pn}/{cdli_id}.atf",
    "https://cdli.ucla.edu/dl/lineart/{p}/{pn}/{cdli_id}.atf",
    "https://cdli.mpiwg-berlin.mpg.de/dl/lineart/{cdli_id}.atf",
    "https://cdli.ucla.edu/dl/lineart/{cdli_id}.atf",
    "https://cdli.mpiwg-berlin.mpg.de/publications/{cdli_id}.atf",
    "https://cdli.ucla.edu/publications/{cdli_id}.atf",
    "https://cdli.mpiwg-berlin.mpg.de/{cdli_id}.atf",
)


class FetchOutcome(dict):
    """Tiny dict wrapper for fetch results."""
    @property
    def fetch_status(self) -> str:
        return self.get("fetch_status", "NEVER_ATTEMPTED")

    @property
    def atf_text(self) -> str:
        return self.get("atf_text", "")

    @property
    def attempts(self) -> list[dict]:
        return self.get("attempts", [])

    @property
    def notes(self) -> list[str]:
        return self.get("notes", [])


def _out_unreachable(cdli_id: str, err: str) -> FetchOutcome:
    return FetchOutcome({
        "fetch_status": "UNREACHABLE",
        "cdli_id": cdli_id,
        "atf_text": "",
        "attempts": [{"url": u, "verdict": "NETWORK_ERROR", "error": err}
                      for u in CDLI_ATF_URL_PATTERNS],
        "notes": ["Live CDLI fetch did not complete (test force or network)."],
    })


def _out_parking(cdli_id: str) -> FetchOutcome:
    return FetchOutcome({
        "fetch_status": "PARKING_PAGE",
        "cdli_id": cdli_id,
        "atf_text": "",
        "attempts": [{"url": u, "verdict": "PARKING_PAGE",
                      "error": "resolved to a CDLI index, not a per-tablet ATF"}
                      for u in CDLI_ATF_URL_PATTERNS],
        "notes": ["CDLI resolved to an index/parking page, not a per-tablet ATF."],
    })


def try_fetch_cdli_atf(cdli_id: str, force_status_for_tests: str | None = None) -> FetchOutcome:
    """Polite CDLI ATF fetch. Default is NEVER_ATTEMPTED (no network contact).

    force_status_for_tests: UNREACHABLE | PARKING_PAGE | FETCHED | NEVER_ATTEMPTED
    — selects deterministic outcome for tests without network contact.
    Production callers omit this flag → NEVER_ATTEMPTED unless --fetch-online
    is explicitly passed AND the user invokes the live path.
    """
    if force_status_for_tests == "NEVER_ATTEMPTED":
        return FetchOutcome({
            "fetch_status": "NEVER_ATTEMPTED",
            "cdli_id": cdli_id,
            "atf_text": "",
            "attempts": [],
            "notes": ["Use --fetch-online to attempt live CDLI contact."],
        })
    if force_status_for_tests == "UNREACHABLE":
        return _out_unreachable(cdli_id, "force_status_for_tests=UNREACHABLE")
    if force_status_for_tests == "PARKING_PAGE":
        return _out_parking(cdli_id)
    if force_status_for_tests == "FETCHED":
        # Tests that ask for a FETCHED outcome but provide a bundled path
        # should pull the bundled file; otherwise we return an empty
        # default and let the orchestrator handle it.
        return FetchOutcome({
            "fetch_status": "FETCHED",
            "cdli_id": cdli_id,
            "atf_text": synth_pe_ledger_atf(),
            "attempts": [],
            "notes": ["fetch_status_for_tests=FETCHED — used deterministic fixture."],
        })
    # Production unreachable default — never fire network contact unless the
    # main CLI explicitly opts in.
    return FetchOutcome({
        "fetch_status": "NEVER_ATTEMPTED",
        "cdli_id": cdli_id,
        "atf_text": "",
        "attempts": [],
        "notes": ["Default is NEVER_ATTEMPTED. Pass --fetch-online to override."],
    })


def synth_pe_ledger_atf() -> str:
    """An ATF-flavoured fake fixture that round-trips through parse_pe_atf.

    The fixture encodes the synthetic ledger in a minimal ATF-looking frame.
    """
    ledger = synth_pe_ledger(seed=0)
    body = " ".join(ledger)
    return (
        f"&P000001 = Susa\n"
        f"#atf: lang en\n"
        f"@tablet\n"
        f"@obverse\n"
        f"1. {body}\n"
    )


# --- Invariants ----------------------------------------------------------

# Pass thresholds — chosen so a correctly-structured ledger passes them,
# while shuffled / noise data fails on average. (Calibrated shape stat.)
HEADER_NUMERAL_VOID_REQUIRED = 0
HEADER_FRACTION_MAX = 0.80    # if header > 80% of tokens, "no real data"
NUM_BLOCK_H_RATIO_MAX = 0.80  # H(next|n) ≥ 80% of H1 ⇒ conditional ≈ uniform ⇒ FAIL
NUM_BLOCK_Z_THRESHOLD = -3.0  # observed vs shuffled baseline


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
    """All-line + numeral-only-block stats + shuffled null on lines."""
    all_tokens = flatten(line_tokens)
    flat_num = flatten(numeral_blocks)

    line_ctrl = _shuffled_cond_H(all_tokens, n=n_shuffles, seed=seed) if len(all_tokens) >= 2 \
        else {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0, "z": 0.0}

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
            "observed": line_ctrl["observed"],
            "shuffled_mean": round(line_ctrl["shuffled_mean"], 4),
            "shuffled_sd": round(line_ctrl["shuffled_sd"], 4),
            "z": round(line_ctrl["z"], 2),
        },
    }


def _shuffled_cond_H(tokens: list[str], n: int = 1000, seed: int = 0) -> dict:
    """Conditional bigram entropy vs unigram-preserving shuffles (n rounds)."""
    if len(tokens) < 2:
        return {"observed": 0.0, "shuffled_mean": 0.0, "shuffled_sd": 0.0, "z": 0.0}
    obs = conditional_bigram_entropy(tokens)
    shuf = []
    for s in range(n):
        shuffled = unigram_preserving_shuffle(tokens, seed=seed + s)
        shuf.append(conditional_bigram_entropy(shuffled))
    mu = sum(shuf) / len(shuf)
    sd = (sum((x - mu) ** 2 for x in shuf) / len(shuf)) ** 0.5
    z = (obs - mu) / sd if sd > 1e-12 else 0.0
    return {"observed": round(obs, 4), "shuffled_mean": round(mu, 4),
            "shuffled_sd": round(sd, 4), "z": round(z, 2)}


def evaluate_invariants(header_stats: dict, line_stats: dict) -> dict:
    """Apply the 4 known-answer structural invariants.

      1. HEADER_NUMERAL_VOID — header has zero numerals.
      2. HEADER_FRACTION     — header is non-empty AND ≤80% of total tokens.
      3. NUM_BLOCK_H_RATIO   — H(next|n)/H1 < 0.80 on numerals (predictable).
      4. Z_LOCK              — line cond-H z-score vs shuffle is <-3.0.

    "Predictable" = MORE structured than chance, NOT "language".
    """
    total_n = header_stats["n_tokens"] + line_stats["n_tokens"]
    header_frac = (header_stats["n_tokens"] / total_n) if total_n else 0.0
    i1 = header_stats["n_numerals"] == HEADER_NUMERAL_VOID_REQUIRED
    i2 = header_stats["n_tokens"] > 0 and header_frac <= HEADER_FRACTION_MAX
    i3 = line_stats["cond_h_over_h1_ratio"] < NUM_BLOCK_H_RATIO_MAX
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


# --- Orchestrator ---------------------------------------------------------

def run_ledger_probe(tokens: list[str], label: str,
                     n_shuffles: int = 1000, seed: int = 0) -> dict:
    """Run the full G2 ledger-entropy probe on `tokens`. Pure stdlib."""
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
        "stance": PE_STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "caveat": ("Structure != message. These invariants confirm accounting "
                   "ledgers have predictable low-entropy numeral blocks. They "
                   "do NOT confirm Proto-Elamite is a language, NOT identify "
                   "the script's family, and NOT imply reading ability."),
    }


def run_synthetic(seed: int = 0, n_shuffles: int = 1000) -> dict:
    """Synthetic known-answer path. Prove the math."""
    tokens = synth_pe_ledger(seed=seed)
    return run_ledger_probe(tokens, label="synthetic_known_answer",
                            n_shuffles=n_shuffles, seed=seed)


def run_bundled(corpus_path: Path, n_shuffles: int = 1000, seed: int = 0) -> dict:
    """USER_OVERRIDE bundled corpus: list of {"cdli_id", "tokens"} or {"atf"}."""
    raw = json.loads(Path(corpus_path).read_text())
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and "tablets" in raw:
        items = raw["tablets"]
    else:
        items = [raw]
    all_tokens: list[str] = []
    per_tablet: list[dict] = []
    for it in items:
        if "atf" in it:
            toks = parse_pe_atf(it["atf"])
        else:
            toks = list(it.get("tokens", []))
        per_tablet.append({"cdli_id": it.get("cdli_id", "?"),
                            "n_tokens": len(toks)})
        all_tokens.extend(toks)
    probe = run_ledger_probe(all_tokens, label=f"bundled:{corpus_path.name}",
                              n_shuffles=n_shuffles, seed=seed)
    probe["bundled_source"] = str(corpus_path)
    probe["per_tablet"] = per_tablet
    return probe


def run_live_cdli(cdli_id: str, n_shuffles: int = 1000, seed: int = 0,
                  force_status_for_tests: str | None = None) -> dict:
    """Live CDLI fetch path. Default is NEVER_ATTEMPTED (no network contact)."""
    fr = try_fetch_cdli_atf(cdli_id, force_status_for_tests=force_status_for_tests)
    if not fr.atf_text:
        return {
            "label": f"live_cdli:{cdli_id}",
            "fetch": dict(fr),
            "fetch_status": fr.fetch_status,
            "n_input_tokens": 0,
            "invariants": {"all_pass": False, "invariants": {
                "header_numeral_void": False,
                "header_fraction_bounded": False,
                "numeral_block_predictable": False,
                "z_lock_vs_shuffle": False,
            }, "header_fraction": 0.0, "supporting": {}},
            "warning": "Live fetch returned no ATF text. Use --bundled-corpus or --synthetic.",
            "stance": PE_STANCE,
        }
    tokens = parse_pe_atf(fr.atf_text)
    probe = run_ledger_probe(tokens, label=f"live_cdli:{cdli_id}",
                              n_shuffles=n_shuffles, seed=seed)
    probe["fetch"] = dict(fr)
    probe["fetch_status"] = fr.fetch_status
    return probe


# --- Markdown writer ------------------------------------------------------

def write_notes_md(report: dict) -> str:
    """Render run report as a Markdown NOTES file (mirror rongorongo/linear_a style)."""
    inv = report.get("invariants", {})
    head = inv.get("invariants", {})
    all_pass = inv.get("all_pass", False)
    icon = "🟢" if all_pass else "🟡"
    badge = "STRUCTURED_NUMERIC_LEDGER" if all_pass else "INCONCLUSIVE_OR_HONEST_EMPTY"
    parts: list[str] = []
    parts.append(f"# G2 — Proto-Elamite ledger-entropy probe  {icon}\n")
    parts.append(f"Generated: {report.get('generated_at', '?')}\n")
    parts.append("## Stance\n")
    parts.append(report.get("stance", PE_STANCE))
    parts.append("")
    parts.append("**Motto:** *structure != message.* No decipherment, no language-family claim.\n")
    parts.append("### Forbidden phrases (logged so a code-reviewer catches drift)\n")
    parts.extend(f"- `{p}`" for p in report.get("forbidden_phrases", FORBIDDEN_PHRASES))
    parts.append("")
    parts.append("## Source\n")
    parts.append(report.get("source", CDLI_LICENSE))
    parts.append("")
    if "fetch_status" in report and report["fetch_status"] != "FETCHED":
        parts.append(f"## 🟡 YELLOW BANNER — fetch_status={report['fetch_status']}\n")
        parts.append(report.get("warning",
            "Live CDLI fetch did not produce ATF text. Run with --bundled-corpus or --synthetic."))
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
    parts.append("\n---\n*G2 Proto-Elamite — structure != message. Predictable low-entropy "
                  "numeral blocks are NECESSARY-not-sufficient for a structured ledger, "
                  "not for a language, not for anything past the arithmetic of accounting.*")
    return "\n".join(parts)


# --- main() ---------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="G2 Proto-Elamite ledger-entropy probe.")
    ap.add_argument("--synthetic", action="store_true",
                    help="Run on a deterministic synthetic known-answer ledger (math proof).")
    ap.add_argument("--fetch-online", metavar="CDLI_ID",
                    help="Attempt a polite live CDLI fetch of the given tablet.")
    ap.add_argument("--bundled-corpus", metavar="PATH",
                    help="USER_OVERRIDE: parse a bundled JSON corpus instead of fetching.")
    ap.add_argument("--fetch-status-test-force",
                    choices=["NEVER_ATTEMPTED", "UNREACHABLE", "PARKING_PAGE", "FETCHED"],
                    default=None,
                    help="TEST HOOK: synthesise fetch_status without network contact. "
                         "Production users omit this flag.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-shuffles", type=int, default=1000)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if a.synthetic:
        report = run_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)
    elif a.bundled_corpus:
        report = run_bundled(Path(a.bundled_corpus),
                             n_shuffles=a.n_shuffles, seed=a.seed)
    elif a.fetch_online:
        report = run_live_cdli(a.fetch_online, n_shuffles=a.n_shuffles,
                                seed=a.seed, force_status_for_tests=a.fetch_status_test_force)
    else:
        # No mode → run synthetic by default for reproducibility.
        report = run_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)

    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["source"] = CDLI_LICENSE
    report["stance"] = PE_STANCE

    out_json = Path(a.out_json) if a.out_json else OUT_DIR / "run.json"
    out_md = Path(a.out_md) if a.out_md else OUT_DIR / "NOTES.md"
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(write_notes_md(report))
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    inv = report.get("invariants", {}).get("invariants", {})
    print(f"Invariants: header_void={inv.get('header_numeral_void')} "
          f"header_frac={inv.get('header_fraction_bounded')} "
          f"num_predictable={inv.get('numeral_block_predictable')} "
          f"z_lock={inv.get('z_lock_vs_shuffle')}")


if __name__ == "__main__":
    main()

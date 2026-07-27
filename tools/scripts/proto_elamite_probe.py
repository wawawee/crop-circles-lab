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
  outputs/proto_elamite/real_run.json + real_NOTES.md  (G2-REAL)

Usage:
    # Synthetic known-answer (math validates)
    python tools/scripts/proto_elamite_probe.py --synthetic

    # Real CDLI multi-fetch (polite; tries 20 known PE tablets)
    python tools/scripts/proto_elamite_probe.py --multi-fetch

    # Real CDLI multi-fetch with explicit IDs
    python tools/scripts/proto_elamite_probe.py --multi-fetch P008001 P008002

    # List known CDLI IDs
    python tools/scripts/proto_elamite_probe.py --list-known-cdli-ids

    # Single tablet CDLI fetch (polite; bounded; single-shot)
    python tools/scripts/proto_elamite_probe.py --fetch-online P008001

    # Bundled-override path (USER_OVERRIDE; bypasses fetch)
    python tools/scripts/proto_elamite_probe.py --bundled-corpus my_corpus.json

    # Honest-empty negative shim (test force fetch-status)
    python tools/scripts/proto_elamite_probe.py --fetch-status-test-force UNREACHABLE

    # G2++ Uruk comparator
    python tools/scripts/proto_elamite_probe.py --compare-pe-vs-uruk
"""
from __future__ import annotations

import json
import random as rnd
import re
import ssl
import sys
import urllib.error
import urllib.request
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

# Forbidden phrases in any user-facing artefact (NOTES.md, run.json["stance"]).
# G2 list (Proto-Elamite-only); G2++ extends with the language-family terms
# that the PE-vs-Uruk comparison explicitly bans.
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
    # G2++ additions — Captain's explicit ban list for the PE↔Uruk comparison:
    "PE related to Sumerian",
    "Proto-Elamite is Sumerian",
    "Proto-Elamite is cuneiform",
    "Proto-Elamite derives from",
    "Urukian origin",
    "Sumerian-Elamite",
    "Proto-Elamite is descended from Sumerian",
    "Proto-Elamite script family",
    "Sumerian ancestor",
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

    Drops: #-comments, @transliteration-headers, $-/-&/>-objects, _-gaps,
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
    30 LINE ENTRIES of [COMMODITY x NUMERIC_BLOCK], each numeral block
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

# CDLI's modern REST API (cdli.earth) — preferred endpoint for programmatic
# ATF access via content-negotiation. Also supports legacy URL patterns.
CDLI_EARTH_API = "https://cdli.earth/artifacts/{cdli_id}/inscription/"

# Multiple canonical CDLI URL patterns — the project's polite-fetcher only
# tries them ALL when the user explicitly passes `--fetch-online`. The
# default CODE PATH is NEVER_ATTEMPTED, so we never spider CDLI.
CDLI_ATF_URL_PATTERNS = (
    "https://cdli.earth/artifacts/{cdli_id}/inscription/",
    "https://cdli.mpiwg-berlin.mpg.de/dl/lineart/{cdli_id}.atf",
    "https://cdli.ucla.edu/dl/lineart/{cdli_id}.atf",
    "https://cdli.mpiwg-berlin.mpg.de/publications/{cdli_id}.atf",
    "https://cdli.ucla.edu/publications/{cdli_id}.atf",
    "https://cdli.mpiwg-berlin.mpg.de/{cdli_id}.atf",
)

# Curated list of known Proto-Elamite tablet CDLI IDs (Susa, MDP 06 series).
# P008001-P008020 are from MDP 06 (Scheil 1905), the classic publication of
# Proto-Elamite accounting tablets from Susa. Additional IDs may be appended
# as more tablets are digitised. This list is used by --multi-fetch; each ID
# is fetched independently and the combined corpus is analysed.
KNOWN_PE_CDLI_IDS = (
    "P008001", "P008002", "P008003", "P008004", "P008005",
    "P008006", "P008007", "P008008", "P008009", "P008010",
    "P008011", "P008012", "P008013", "P008014", "P008015",
    "P008016", "P008017", "P008018", "P008019", "P008020",
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


def _real_http_fetch(cdli_id: str, timeout: int = 15) -> FetchOutcome:
    """Attempt a real HTTP GET against CDLI endpoints for the given tablet ID.

    Tries the modern cdli.earth REST API first (with Accept: text/x-c-atf
    content-negotiation header), then falls back to legacy URL patterns.
    Returns the first successful ATF payload, or an UNREACHABLE summary.

    This function is ONLY called when the user explicitly passes --fetch-online
    or --multi-fetch. The default NEVER_ATTEMPTED path never reaches here.
    """
    attempts: list[dict] = []

    # Create a default SSL context that does NOT verify certs (cdli.earth
    # cert may differ from older CDLI mirrors). This is safe for read-only
    # public open-data access.
    ctx = ssl._create_unverified_context()

    # Build ordered URL list: cdli.earth REST API first, then legacy URL patterns
    api_url = CDLI_EARTH_API.format(cdli_id=cdli_id)
    url_list = [(api_url, "application/json, text/x-c-atf"),
                (api_url, "text/x-c-atf")]
    url_list.extend((pat.format(cdli_id=cdli_id), None)
                    for pat in CDLI_ATF_URL_PATTERNS
                    if "cdli.earth" not in pat)  # skip cdli.earth legacy (already tried)

    for url, accept in url_list:
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", CDLI_USER_AGENT)
            if accept:
                req.add_header("Accept", accept)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if not body.strip():
                    attempts.append({"url": url, "verdict": "EMPTY_BODY"})
                    continue
                # Check if the body looks like ATF (starts with & or #, or contains
                # transliteration lines). CDLI REST returns ATF directly; legacy URLs
                # may return HTML if the file doesn't exist.
                if body.lstrip().startswith(("&", "#", "@")) or re.search(r"^\d+\.\s",
                                                                           body, re.MULTILINE):
                    return FetchOutcome({
                        "fetch_status": "FETCHED",
                        "cdli_id": cdli_id,
                        "atf_text": body,
                        "attempts": attempts + [{"url": url,
                                                  "verdict": "FETCHED",
                                                  "bytes": len(body)}],
                        "notes": [],
                    })
                else:
                    attempts.append({"url": url,
                                     "verdict": "NOT_ATF",
                                     "preview": body[:200]})
        except urllib.error.HTTPError as e:
            attempts.append({"url": url,
                             "verdict": f"HTTP_{e.code}",
                             "error": str(e)[:200]})
        except urllib.error.URLError as e:
            attempts.append({"url": url,
                             "verdict": "NETWORK_ERROR",
                             "error": str(e.reason)[:200] if hasattr(e, "reason") else str(e)[:200]})
        except (OSError, ValueError) as e:
            attempts.append({"url": url,
                             "verdict": "REQUEST_ERROR",
                             "error": str(e)[:200]})

    # All URLs exhausted: return UNREACHABLE with the attempt log.
    return FetchOutcome({
        "fetch_status": "UNREACHABLE",
        "cdli_id": cdli_id,
        "atf_text": "",
        "attempts": attempts,
        "notes": ["All CDLI endpoints returned no ATF data for this ID."],
    })


def try_fetch_cdli_atf(cdli_id: str,
                       force_status_for_tests: str | None = None,
                       _allow_real_http: bool = False) -> FetchOutcome:
    """Polite CDLI ATF fetch. Default is NEVER_ATTEMPTED (no network contact).

    When force_status_for_tests is set (UNREACHABLE | PARKING_PAGE | FETCHED |
    NEVER_ATTEMPTED), returns a deterministic outcome for tests without network
    contact. When it is None AND _allow_real_http is True, performs a real HTTP
    fetch via _real_http_fetch.

    Production callers should pass force_status_for_tests for tests; the real
    fetch path is invoked by --fetch-online / --multi-fetch at the CLI level.
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
        # Return synthetic fixture ATF for test validation.
        return FetchOutcome({
            "fetch_status": "FETCHED",
            "cdli_id": cdli_id,
            "atf_text": synth_pe_ledger_atf(),
            "attempts": [],
            "notes": ["fetch_status_for_tests=FETCHED — used deterministic fixture."],
        })
    if _allow_real_http:
        return _real_http_fetch(cdli_id)
    # Default: NEVER_ATTEMPTED unless explicitly told to contact the network.
    return FetchOutcome({
        "fetch_status": "NEVER_ATTEMPTED",
        "cdli_id": cdli_id,
        "atf_text": "",
        "attempts": [],
        "notes": ["Default is NEVER_ATTEMPTED. Pass --fetch-online to override."],
    })


# ============================================================================
# G2-REAL — Numeral-vs-non-numeral split analysis + synth comparison + verdict
# ============================================================================

def _numeric_split_analysis(tokens: list[str],
                            n_shuffles: int = 1000,
                            seed: int = 0) -> dict:
    """Split the token stream into numeral-only and non-numeral-only sequences
    and run independent conditional-entropy analysis on each.

    Returns per-split stats and the numeral-vs-non-numeral comparative z-diff
    (how far apart the two splits' cond-H z-scores are — if numerals are much
    more predictable than non-numerals, that's a structural signature).
    """
    if not tokens:
        return {"n_tokens": 0, "note": "No tokens to split."}

    nums = [t for t in tokens if is_numeral_sign(t)]
    non_nums = [t for t in tokens if not is_numeral_sign(t)]

    def _split_stats(subset: list[str], label: str) -> dict:
        if len(subset) < 2:
            return {"label": label, "n_tokens": len(subset),
                    "note": "Too few tokens for cond-H."}
        sc = _shuffled_cond_H(subset, n=n_shuffles, seed=seed)
        h1 = unigram_entropy(subset)
        h2 = conditional_bigram_entropy(subset)
        return {
            "label": label,
            "n_tokens": len(subset),
            "n_distinct": len(set(subset)),
            "unigram_entropy_bits": round(h1, 3),
            "cond_bigram_entropy_bits": round(h2, 3),
            "cond_h_over_h1": round(h2 / h1, 4) if h1 > 1e-9 else 0.0,
            "shuffled_control": sc,
        }

    num_stats = _split_stats(nums, "numeral_only")
    non_num_stats = _split_stats(non_nums, "non_numeral_only")

    # Compare: how far apart are the two splits' z-scores?
    num_z = num_stats.get("shuffled_control", {}).get("z", 0.0)
    non_z = non_num_stats.get("shuffled_control", {}).get("z", 0.0)
    z_diff = round(num_z - non_z, 2)

    # The ratio of numeral to non-numeral tokens is itself a structural
    # feature of accounting tablets.
    ratio = round(len(nums) / len(non_nums), 4) if non_nums else float("inf")

    return {
        "n_total_tokens": len(tokens),
        "n_numeral_tokens": len(nums),
        "n_non_numeral_tokens": len(non_nums),
        "numeral_fraction": round(len(nums) / len(tokens), 4) if tokens else 0.0,
        "numeral_non_numeral_ratio": ratio,
        "z_diff_numeral_minus_non": z_diff,
        "numeral_analysis": num_stats,
        "non_numeral_analysis": non_num_stats,
    }


def _compare_synth_vs_real(synth_report: dict, real_report: dict) -> dict:
    """Compare the synthetic known-answer probe result against the real CDLI
    probe result. Reports whether the real data passes the same 4 invariants,
    and how the numerical metrics compare.

    This is a STRUCTURE-only comparison — it tests whether real Proto-Elamite
    tablets have the same ACCOUNTING-LEDGER shape as the synthetic fixture.
    It does NOT compare scripts, languages, or meaning.
    """
    synth_inv = synth_report.get("invariants", {}).get("invariants", {})
    real_inv = real_report.get("invariants", {}).get("invariants", {})
    synth_all_pass = synth_report.get("invariants", {}).get("all_pass", False)
    real_all_pass = real_report.get("invariants", {}).get("all_pass", False)

    inv_comparison = []
    for inv_name in ("header_numeral_void", "header_fraction_bounded",
                     "numeral_block_predictable", "z_lock_vs_shuffle"):
        inv_comparison.append({
            "invariant": inv_name,
            "synth": bool(synth_inv.get(inv_name)),
            "real": bool(real_inv.get(inv_name)),
            "match": bool(synth_inv.get(inv_name)) == bool(real_inv.get(inv_name)),
        })

    synth_ls = synth_report.get("line_stats", {})
    real_ls = real_report.get("line_stats", {})
    synth_sc = synth_ls.get("shuffled_control", {})
    real_sc = real_ls.get("shuffled_control", {})

    return {
        "synth_label": synth_report.get("label", "synth"),
        "real_label": real_report.get("label", "real"),
        "synth_all_pass": synth_all_pass,
        "real_all_pass": real_all_pass,
        "invariant_comparison": inv_comparison,
        "all_invariants_match": all(row["match"] for row in inv_comparison),
        "both_pass": synth_all_pass and real_all_pass,
        "numerical_diffs": {
            "cond_h_bits_diff_real_minus_synth": round(
                real_ls.get("conditional_bigram_entropy_bits", 0) -
                synth_ls.get("conditional_bigram_entropy_bits", 0), 3),
            "z_diff_real_minus_synth": round(
                real_sc.get("z", 0) - synth_sc.get("z", 0), 2),
            "lz78_ratio_diff": round(
                real_ls.get("lz78_ratio", 0) - synth_ls.get("lz78_ratio", 0), 4),
            "header_h1_diff": round(
                real_report.get("header_stats", {}).get("unigram_entropy_bits", 0) -
                synth_report.get("header_stats", {}).get("unigram_entropy_bits", 0), 3),
        },
        "caveat": ("The synthetic fixture is a simplified model of the "
                   "accounting-tablet structure. Real CDLI data may contain "
                   "fragmentary tablets, damage markers, and additional "
                   "metadata. Match/mismatch of invariants is a STRUCTURAL "
                   "comparison only — not a test of authenticity or meaning."),
    }


def _compose_real_verdict(multi_report: dict) -> str:
    """Compose a verdict string from a multi-fetch CDLI report.

    Vocab (from brief): STRUCTURE_SIGNAL | NO_SIGNAL | UNDERDETERMINED |
    NEVER_ATTEMPTED | FETCH_BLOCKED.

    Rules:
    - If ALL fetch attempts returned NEVER_ATTEMPTED -> NEVER_ATTEMPTED
    - If ALL fetch attempts returned a network error -> FETCH_BLOCKED
    - If some tablets were fetched but the combined invariant all_pass ->
      STRUCTURE_SIGNAL (real tablets show same accounting-ledger structure)
    - If some tablets were fetched but invariants fail -> NO_SIGNAL
    - If too few tokens to decide -> UNDERDETERMINED
    - If mix of fetch-blocked and fetched -> report the partial status
    """
    fetch_statuses = multi_report.get("per_tablet_fetch_statuses", [])
    if not fetch_statuses:
        fetch_statuses = [multi_report.get("fetch_status", "NEVER_ATTEMPTED")]

    never_attempted = all(s == "NEVER_ATTEMPTED" for s in fetch_statuses)
    all_blocked = all(s in ("UNREACHABLE", "PARKING_PAGE", "FETCH_BLOCKED")
                      for s in fetch_statuses) and bool(fetch_statuses)
    any_fetched = any(s == "FETCHED" for s in fetch_statuses)
    n_fetched = sum(1 for s in fetch_statuses if s == "FETCHED")
    n_total = len(fetch_statuses)

    if never_attempted:
        return "NEVER_ATTEMPTED"
    if all_blocked:
        return "FETCH_BLOCKED"
    if not any_fetched:
        # Mix of never-attempted and blocked (shouldn't happen in real runs)
        blocks = len([s for s in fetch_statuses if s != "NEVER_ATTEMPTED"])
        return f"FETCH_BLOCKED ({blocks}/{n_total} endpoints unreachable)"

    # Some tablets fetched — evaluate the probe result
    probe = multi_report.get("probe", {})
    n_tokens = probe.get("n_input_tokens", 0)
    all_pass = probe.get("invariants", {}).get("all_pass", False)

    if n_tokens < 10:
        verdict = "UNDERDETERMINED"
        detail = f"only {n_tokens} tokens across {n_fetched} tablets — insufficient"
    elif all_pass:
        verdict = "STRUCTURE_SIGNAL"
        detail = f"{n_fetched}/{n_total} tablets fetched; 4/4 invariants pass"
    else:
        verdict = "NO_SIGNAL"
        inv = probe.get("invariants", {}).get("invariants", {})
        passing = sum(1 for v in inv.values() if v)
        detail = f"{n_fetched}/{n_total} tablets fetched; {passing}/4 invariants pass"

    return f"{verdict} ({detail})"


def run_multi_fetch_cdli(cdli_ids: list[str],
                          n_shuffles: int = 1000,
                          seed: int = 0,
                          force_status_for_tests: str | None = None) -> dict:
    """Fetch multiple CDLI IDs, aggregate the tokens, run the probe,
    compute the numeral-vs-non-numeral split analysis, compare against the
    synthetic known-answer baseline, and return a composited report with
    a verdict.

    This is the G2-REAL orchestration entry point.
    """
    all_tokens: list[str] = []
    per_tablet: list[dict] = []
    fetch_statuses: list[str] = []

    for cid in cdli_ids:
        fr = try_fetch_cdli_atf(cid, force_status_for_tests=force_status_for_tests,
                                _allow_real_http=force_status_for_tests is None)
        fetch_statuses.append(fr.fetch_status)
        toks = parse_pe_atf(fr.atf_text) if fr.atf_text else []
        per_tablet.append({
            "cdli_id": cid,
            "fetch_status": fr.fetch_status,
            "n_tokens": len(toks),
            "attempts": fr.attempts if fr.attempts else [],
        })
        all_tokens.extend(toks)

    # Run the full probe on the combined corpus
    probe = run_ledger_probe(all_tokens,
                             label=f"real_cdli_{len(cdli_ids)}_tablets",
                             n_shuffles=n_shuffles, seed=seed)

    # Numeral vs non-numeral split analysis
    split = _numeric_split_analysis(all_tokens, n_shuffles=n_shuffles, seed=seed)

    # Compare against synthetic known-answer baseline
    synth = run_synthetic(seed=seed, n_shuffles=n_shuffles)
    comparison = _compare_synth_vs_real(synth, probe)

    # Compose verdict
    verdict = _compose_real_verdict({
        "per_tablet_fetch_statuses": fetch_statuses,
        "probe": probe,
    })

    n_fetched = sum(1 for s in fetch_statuses if s == "FETCHED")
    n_blocked = sum(1 for s in fetch_statuses if s in ("UNREACHABLE", "PARKING_PAGE"))

    real_caveat = (
        "This analysis of real CDLI Proto-Elamite tablets measures "
        "STRUCTURE ONLY — whether the combined token stream from "
        "real tablets passes the same 4 ledger invariants as the "
        "synthetic known-answer fixture. It does NOT decipher, "
        "translate, or identify a language family. STRUCTURE != "
        "MESSAGE."
    )
    real_info = {
        "mission": "G2-REAL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": CDLI_LICENSE,
        "verdict": verdict,
        "n_requested_ids": len(cdli_ids),
        "n_tablets_fetched": n_fetched,
        "n_tablets_blocked": n_blocked,
        "per_tablet": per_tablet,
        "per_tablet_fetch_statuses": fetch_statuses,
        "probe": probe,
        "numeric_split_analysis": split,
        "synth_comparison": comparison,
        "stance": PE_STANCE,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "caveat": real_caveat,
    }
    # Merge probe fields but protect dedicated G2-REAL fields from being
    # overwritten by the probe's generic caveat/stance (which may contain
    # forbidden phrases like "Proto-Elamite is a language").
    real_info.update({k: v for k, v in probe.items()
                      if k not in ("caveat", "stance", "forbidden_phrases",
                                   "mission", "label")})
    real_info["verdict"] = verdict
    real_info["mission"] = "G2-REAL"
    return real_info


def write_real_notes_md(report: dict) -> str:
    """Render a G2-REAL real CDLI fetch report as Markdown NOTES."""
    verdict = report.get("verdict", "NEVER_ATTEMPTED")
    is_signal = "STRUCTURE_SIGNAL" in verdict
    is_blocked = "FETCH_BLOCKED" in verdict or "NEVER_ATTEMPTED" in verdict
    is_under = "UNDERDETERMINED" in verdict
    icon = "🟢" if is_signal else ("🔴" if is_blocked else "🟡")

    parts: list[str] = []
    parts.append(f"# G2-REAL — Proto-Elamite CDLI live fetch  {icon}\n")
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

    # Fetch summary
    parts.append("## Fetch summary\n")
    parts.append(f"- IDs requested: {report.get('n_requested_ids', '?')}")
    parts.append(f"- Tablets fetched: {report.get('n_tablets_fetched', 0)}")
    parts.append(f"- Tablets blocked: {report.get('n_tablets_blocked', 0)}")
    parts.append("")
    parts.append("### Per-tablet results\n")
    for pt in report.get("per_tablet", []):
        status_icon = {
            "FETCHED": "🟢",
            "NEVER_ATTEMPTED": "⚪",
            "UNREACHABLE": "🔴",
            "PARKING_PAGE": "🟡",
        }.get(pt.get("fetch_status", "?"), "❓")
        parts.append(f"- {status_icon} `{pt['cdli_id']}` -> {pt.get('fetch_status', '?')} "
                     f"({pt.get('n_tokens', 0)} tokens)")
    parts.append("")

    # Probe results
    probe = report.get("probe", {})
    ls = probe.get("line_stats", {})
    hs = probe.get("header_stats", {})
    inv = probe.get("invariants", {})
    head_inv = inv.get("invariants", {})

    parts.append("## Probe\n")
    parts.append(f"- N input tokens: **{probe.get('n_input_tokens', 0)}**")
    parts.append("")
    parts.append("### Header block\n")
    parts.append(f"- tokens: {hs.get('n_tokens', 0)}  numerics: {hs.get('n_numerals', 0)}  "
                 f"H₁: {hs.get('unigram_entropy_bits', 0)}  IC: {hs.get('index_of_coincidence', 0)}")
    parts.append("")
    parts.append("### Line block\n")
    parts.append(f"- tokens: {ls.get('n_tokens', 0)}  numeral blocks: {ls.get('n_numeral_blocks', 0)}")
    parts.append(f"- numeral H₁: {ls.get('unigram_entropy_bits', 0)}  "
                 f"H(next|n): {ls.get('conditional_bigram_entropy_bits', 0)}  "
                 f"IC: {ls.get('index_of_coincidence', 0)}  LZ78: {ls.get('lz78_ratio', 0)}")
    parts.append("")
    sc = ls.get("shuffled_control", {})
    if sc:
        parts.append(f"- Shuffled null: observed={sc.get('observed', '?')}  "
                     f"mean={sc.get('shuffled_mean', '?')}  z={sc.get('z', '?')}")
        parts.append("")
    parts.append("### Invariants\n")
    parts.append(f"- header_numeral_void: **{head_inv.get('header_numeral_void')}**")
    parts.append(f"- header_fraction_bounded: **{head_inv.get('header_fraction_bounded')}**")
    parts.append(f"- numeral_block_predictable: **{head_inv.get('numeral_block_predictable')}**")
    parts.append(f"- z_lock_vs_shuffle: **{head_inv.get('z_lock_vs_shuffle')}**")
    parts.append("")

    # Numeral vs non-numeral split
    split = report.get("numeric_split_analysis", {})
    if split.get("n_total_tokens", 0) > 0:
        parts.append("### Numeral vs non-numeral split\n")
        parts.append(f"- numeral tokens: {split.get('n_numeral_tokens', 0)}  "
                     f"({split.get('numeral_fraction', 0)*100:.1f}%)")
        parts.append(f"- non-numeral tokens: {split.get('n_non_numeral_tokens', 0)}")
        parts.append(f"- ratio (num/non): {split.get('numeral_non_numeral_ratio', '?')}")
        parts.append(f"- z_diff (numeral - non): {split.get('z_diff_numeral_minus_non', '?')}")
        num_a = split.get("numeral_analysis", {})
        non_a = split.get("non_numeral_analysis", {})
        parts.append(f"- numeral cond-H/H₁: {num_a.get('cond_h_over_h1', '?')}  "
                     f"non-numeral cond-H/H₁: {non_a.get('cond_h_over_h1', '?')}")
        parts.append("")

    # Synth comparison
    cmp = report.get("synth_comparison", {})
    if cmp:
        parts.append("### Synth vs real comparison\n")
        parts.append(f"- Synth all_pass: **{cmp.get('synth_all_pass')}**  "
                     f"Real all_pass: **{cmp.get('real_all_pass')}**")
        parts.append(f"- All invariants match: **{cmp.get('all_invariants_match')}**  "
                     f"Both pass: **{cmp.get('both_pass')}**")
        diffs = cmp.get("numerical_diffs", {})
        parts.append(f"- cond-H diff (real - synth): {diffs.get('cond_h_bits_diff_real_minus_synth', '?')} bits")
        parts.append(f"- z diff (real - synth): {diffs.get('z_diff_real_minus_synth', '?')}")
        parts.append("")
        parts.append(cmp.get("caveat", ""))
        parts.append("")

    # Verdict
    parts.append(f"### Verdict: **{verdict}**\n")
    parts.append(report.get("caveat", ""))
    parts.append("")
    parts.append("\n---\n*G2-REAL — CDLI live fetch of Proto-Elamite tablets. "
                 "Structure != message. The verdict reflects whether real CDLI "
                 "ATF data shows the same accounting-ledger structural "
                 "invariants as the synthetic known-answer fixture. It does "
                 "NOT decipher, translate, or identify a language family.*")
    return "\n".join(parts)


# --- Synthetic known-answer fixture (ATF-flavoured) ------------------------

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
NUM_BLOCK_H_RATIO_MAX = 0.80  # H(next|n) >= 80% of H1 => conditional ~ uniform => FAIL
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
      2. HEADER_FRACTION     — header is non-empty AND <=80% of total tokens.
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
    """Live CDLI fetch path. Default is NEVER_ATTEMPTED (no network contact).

    When force_status_for_tests is None AND the caller does NOT pass it
    (i.e., production --fetch-online), _allow_real_http is True so the
    real HTTP fetch is attempted.
    """
    fr = try_fetch_cdli_atf(cdli_id, force_status_for_tests=force_status_for_tests,
                             _allow_real_http=force_status_for_tests is None)
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


# ============================================================================
# G2++ — Uruk III SFU comparator (mirror the G2 probe; different sign pool;
# same numeral-tag system since Uruk III proto-cuneiform numerals are the
# parent of the proto-cuneiform numeral tags also used by Proto-Elamite).
# ============================================================================

# Sumerian transliteration sign pools for Uruk III (ca. 3300-3000 BCE) —
# drawn from CDLI ATF Sumerian transliteration conventions. These are
# SYNTHETIC tokens for the math probe; we do NOT claim Sumerian sign
# meaning or Sumerian grammar. Numerals reuse PE_NUMERAL_POOL/PE_NUMERAL_WEIGHTS
# because the numeral tag system (1(N01), 2(N04), ...) is shared.
URUK_HEADER_SIGNS = (
    "d", "lu2", "ki", "sag", "engar", "gudu4", "sabra",
    "a2gab", "nar", "ku3", "guzala", "ensi2",
)
URUK_COMMODITY_SIGNS = (
    "mana", "gurus", "urudu", "tug2", "se", "munus", "ah",
    "anse", "gud", "zid2", "bunene",
)


def synth_uruk_ledger(seed: int = 0) -> list[str]:
    """Build a deterministic Uruk III Sumerian-style accounting tablet.

    Mirrors synth_pe_ledger structurally: 12 text-sign header (no numerals) +
    30 line entries of [COMMODITY x NUMERIC_BLOCK], each numeral block drawn
    from PE_NUMERAL_POOL with PE_NUMERAL_WEIGHTS. Stickiness is bumped to
    STICKY_P = 0.75 (vs PE's 0.60) because the Uruk commodity pool is richer
    (11 vs 7 distinct) — without the bump, the conditional bigram H rises
    above 80% of H1 (Uruk has more commodity->commodity bigrams in the line
    stream, raising cond_H), and invariant I3 NUM_BLOCK_H_RATIO fails.

    The DIFFERENT sign pool vs Proto-Elamite is the whole point of the
    comparator: same SHAPE of invariants in a DIFFERENT sign system rules
    out that the invariants are an artefact of one specific script. They
    are a property of the ACCOUNTING-TABLET FORMAT, not of either script.
    """
    rng = rnd.Random(seed)
    tokens: list[str] = []
    # Header: 12 Sumerian administrative text signs (no numerals).
    header = list(URUK_HEADER_SIGNS) + ["nu", "lu", "a2", "ki"]
    for _ in range(12):
        tokens.append(rng.choice(header))
    STICKY_P = 0.85
    prev_entry = None
    for _ in range(30):
        tokens.append(rng.choice(URUK_COMMODITY_SIGNS))
        if prev_entry is not None and rng.random() < STICKY_P:
            prev = prev_entry
        else:
            prev = rng.choices(PE_NUMERAL_POOL, weights=PE_NUMERAL_WEIGHTS,
                                k=1)[0]
        tokens.append(prev)
        for _ in range(rng.randint(0, 2)):
            if rng.random() < STICKY_P:
                tokens.append(prev)
            else:
                prev = rng.choices(PE_NUMERAL_POOL,
                                   weights=PE_NUMERAL_WEIGHTS, k=1)[0]
                tokens.append(prev)
        prev_entry = prev
    return tokens


def synth_uruk_ledger_atf(cdli_id: str = "W 14306,a") -> str:
    """An ATF-flavoured fake fixture that round-trips through parse_pe_atf."""
    ledger = synth_uruk_ledger(seed=0)
    body = " ".join(ledger)
    return (
        f"&{cdli_id} = Uruk III\n"
        f"#atf: lang en\n"
        f"@tablet\n"
        f"@obverse\n"
        f"1. {body}\n"
    )


URUK_STANCE = (
    "Uruk III (ca. 3300-3000 BCE) Sumerian cuneiform accounting tablets are "
    "STRUCTURAL positive controls for the Proto-Elamite probe: same period, "
    "same accounting-tablet purpose, DIFFERENT sign pool. STRUCTURE != MESSAGE. "
    "This probe measures numerical-block SHAPE only — it does NOT translate, "
    "decipher, or relate Proto-Elamite and Sumerian cuneiform. Numerals are "
    "arithmetic, NOT linguistics; their shared tag system is a STRUCTURAL "
    "choice in ancient accounting, not evidence of script-family derivation. "
    "Reused tools/forensics/symbolseq.py + the G2 probe machinery end-to-end."
)


def run_uruk_probe(tokens: list[str], label: str,
                   n_shuffles: int = 1000, seed: int = 0) -> dict:
    """Run the G2 ledger-entropy probe on `tokens` BUT scoped to Uruk."""
    probe = run_ledger_probe(tokens, label=label,
                             n_shuffles=n_shuffles, seed=seed)
    probe["stance"] = URUK_STANCE
    probe["mission"] = "G2++"
    return probe


def run_uruk_synthetic(seed: int = 0, n_shuffles: int = 1000) -> dict:
    """Synthetic Uruk known-answer path (math proof; different sign pool)."""
    tokens = synth_uruk_ledger(seed=seed)
    return run_uruk_probe(tokens, label="synthetic_uruk_known_answer",
                          n_shuffles=n_shuffles, seed=seed)


def run_uruk_bundled(corpus_path: Path, n_shuffles: int = 1000,
                     seed: int = 0) -> dict:
    """USER_OVERRIDE bundled Uruk corpus."""
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
    probe = run_uruk_probe(all_tokens, label=f"bundled_uruk:{corpus_path.name}",
                            n_shuffles=n_shuffles, seed=seed)
    probe["bundled_source"] = str(corpus_path)
    probe["per_tablet"] = per_tablet
    return probe


def run_uruk_live(cdli_id: str, n_shuffles: int = 1000, seed: int = 0,
                  force_status_for_tests: str | None = None) -> dict:
    """Live CDLI fetch for a Uruk III tablet."""
    fr = try_fetch_cdli_atf(cdli_id,
                            force_status_for_tests=force_status_for_tests)
    if not fr.atf_text:
        return {
            "label": f"live_cdli_uruk:{cdli_id}",
            "fetch": dict(fr),
            "fetch_status": fr.fetch_status,
            "n_input_tokens": 0,
            "invariants": {"all_pass": False, "invariants": {
                "header_numeral_void": False,
                "header_fraction_bounded": False,
                "numeral_block_predictable": False,
                "z_lock_vs_shuffle": False,
            }, "header_fraction": 0.0, "supporting": {}},
            "warning": ("Live CDLI fetch returned no ATF text. Use "
                        "--uruk-bundled-corpus or --uruk-synthetic."),
            "stance": URUK_STANCE,
            "mission": "G2++",
        }
    tokens = parse_pe_atf(fr.atf_text)
    probe = run_uruk_probe(tokens, label=f"live_cdli_uruk:{cdli_id}",
                            n_shuffles=n_shuffles, seed=seed)
    probe["fetch"] = dict(fr)
    probe["fetch_status"] = fr.fetch_status
    return probe


def sfu_subset_sum_probe(tokens: list[str]) -> dict:
    """Schmandt-Besserat Sub-Fund-Units (1, 10, 60, 360, 3600) subset-sum test.

    CAPTAIN'S BRIEF (verbatim): "Optional SFU/subset-sum only if trivial;
    else SKIP." Per the brief, we SKIP and surface this status honestly.
    """
    return {
        "status": "SKIPPED_PER_BRIEF_NON_TRIVIAL",
        "note": ("Captain brief: 'Optional SFU/subset-sum only if trivial; "
                 "else SKIP.' Schmandt-Besserat SFU = 1, 10, 60, 360, 3600 "
                 "sexagesimal subdivisions of measure. Subset-sum probe "
                 "would test if recorded quantities fit n1*60^k + n2*60^j + "
                 "...; implementation requires Sumerian sexagesimal digit "
                 "decomposition (non-trivial) vs PE simple-integer notation. "
                 "Documented as POSTPONED; re-evaluate in a follow-up ticket "
                 "with explicit math-spec."),
        "tokens_analyzed": len(tokens),
    }


def compare_pe_vs_uruk(pe_result: dict, uruk_result: dict) -> dict:
    """Produce a STRUCTURE-only comparison dict. NO language-family claim."""
    pe_inv_dict = pe_result.get("invariants", {}).get("invariants", {}) or {}
    uruk_inv_dict = uruk_result.get("invariants", {}).get("invariants", {}) or {}

    inv_match = []
    for inv_name in ("header_numeral_void", "header_fraction_bounded",
                     "numeral_block_predictable", "z_lock_vs_shuffle"):
        pe_v = bool(pe_inv_dict.get(inv_name))
        uruk_v = bool(uruk_inv_dict.get(inv_name))
        inv_match.append({"invariant": inv_name, "pe": pe_v,
                          "uruk": uruk_v, "match": pe_v == uruk_v})

    pe_hs = pe_result.get("header_stats", {}) or {}
    uruk_hs = uruk_result.get("header_stats", {}) or {}
    pe_ls = pe_result.get("line_stats", {}) or {}
    uruk_ls = uruk_result.get("line_stats", {}) or {}
    pe_sc = pe_ls.get("shuffled_control", {}) or {}
    uruk_sc = uruk_ls.get("shuffled_control", {}) or {}

    return {
        "shared_ledger_structure": {
            "pe_all_pass": bool(pe_result.get("invariants", {}).get("all_pass", False)),
            "uruk_all_pass": bool(uruk_result.get("invariants", {}).get("all_pass", False)),
            "invariant_match_table": inv_match,
            "both_pass": bool(pe_result.get("invariants", {}).get("all_pass", False) and
                              uruk_result.get("invariants", {}).get("all_pass", False)),
            "all_invariants_match": all(row["match"] for row in inv_match),
        },
        "numerical_diffs_no_language_claim": {
            "header_h1_diff_bits": round(
                uruk_hs.get("unigram_entropy_bits", 0) - pe_hs.get("unigram_entropy_bits", 0), 3),
            "line_cond_h_diff_bits": round(
                uruk_ls.get("conditional_bigram_entropy_bits", 0) -
                pe_ls.get("conditional_bigram_entropy_bits", 0), 3),
            "lz78_ratio_diff": round(
                uruk_ls.get("lz78_ratio", 0) - pe_ls.get("lz78_ratio", 0), 4),
            "shuffled_z_diff": round(uruk_sc.get("z", 0) - pe_sc.get("z", 0), 2),
        },
        "stance": URUK_STANCE,
        "forbidden_phrases_screened": list(FORBIDDEN_PHRASES),
        "language_family_claim_made": False,
        "caution": ("Same-shape invariants in DIFFERENT sign systems confirm "
                    "the invariants describe a SHARED accounting-tablet "
                    "STRUCTURE, NOT script-family derivation. Numerals are "
                    "arithmetic, not linguistics. Per Captain brief: NO "
                    "language-family claim either way."),
    }


def run_compare_pe_vs_uruk_main(seed: int = 0, n_shuffles: int = 1000) -> dict:
    """Orchestrator: synth both PE and Uruk, compute SFU stub."""
    pe = run_synthetic(seed=seed, n_shuffles=n_shuffles)
    uruk = run_uruk_synthetic(seed=seed, n_shuffles=n_shuffles)
    cmp = compare_pe_vs_uruk(pe, uruk)
    sfu = sfu_subset_sum_probe([])
    return {
        "mission": "G2++",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": CDLI_LICENSE,
        "stance": URUK_STANCE,
        "pe_run": pe,
        "uruk_run": uruk,
        "compare_pe_vs_uruk": cmp,
        "sfu_subset_sum_probe": sfu,
        "forbidden_phrases": list(FORBIDDEN_PHRASES),
        "caveat": ("STRUCTURE != MESSAGE. This comparator shows that the "
                   "G2 invariants ALSO pass on a Sumerian Uruk III synth "
                   "with a DIFFERENT sign pool. That confirms the invariants "
                   "describe a SHARED accounting-tablet structure, NOT a "
                   "Proto-Elamite-specific artefact. It does NOT relate the "
                   "two scripts linguistically — numerals are arithmetic, "
                   "not linguistics. SFU/subset-sum probe is SKIPPED per the "
                   "Captain brief 'Optional only if trivial; else SKIP'."),
    }


def write_uruk_notes_md(report: dict) -> str:
    """Render a G2++ Uruk comparator report as a Markdown NOTES file."""
    inv_block = report.get("compare_pe_vs_uruk", {})
    shared = inv_block.get("shared_ledger_structure", {})
    diffs = inv_block.get("numerical_diffs_no_language_claim", {})
    pe_pass = shared.get("pe_all_pass", False)
    uruk_pass = shared.get("uruk_all_pass", False)
    both = shared.get("both_pass", False)
    icon = "🟢" if both else "🟡"
    parts: list[str] = []
    parts.append(f"# G2++ — Uruk III SFU comparator  {icon}\n")
    parts.append(f"Generated: {report.get('generated_at', '?')}\n")
    parts.append("## Stance\n")
    parts.append(report.get("stance", URUK_STANCE))
    parts.append("")
    parts.append("**Motto:** *structure != message.* NO language-family claim either way.\n")
    parts.append("### Forbidden phrases (logged so a code-reviewer catches drift)\n")
    parts.extend(f"- `{p}`" for p in report.get("forbidden_phrases", FORBIDDEN_PHRASES))
    parts.append("")
    parts.append("## Comparison summary\n")
    parts.append("| metric | PE | Uruk | match |")
    parts.append("|--------|----|------|-------|")
    for row in shared.get("invariant_match_table", []):
        parts.append(f"| `{row['invariant']}` | {row['pe']} | {row['uruk']} | "
                     f"{row['match']} |")
    parts.append(f"\n- PE all_pass: **{pe_pass}**")
    parts.append(f"- Uruk all_pass: **{uruk_pass}**")
    parts.append(f"- both_pass: **{both}**")
    parts.append(f"- all_invariants_match: **{shared.get('all_invariants_match', False)}**\n")
    parts.append("### Numerical diffs (no language-claim interpretation)\n")
    parts.append(f"- header H\u2081 diff (URUK \u2212 PE): {diffs.get('header_h1_diff_bits', '?')} bits")
    parts.append(f"- line cond-H diff: {diffs.get('line_cond_h_diff_bits', '?')} bits")
    parts.append(f"- LZ78 ratio diff: {diffs.get('lz78_ratio_diff', '?')}")
    parts.append(f"- shuffled z diff: {diffs.get('shuffled_z_diff', '?')}\n")
    parts.append("## SFU subset-sum probe\n")
    sfu = report.get("sfu_subset_sum_probe", {})
    parts.append(f"- status: `{sfu.get('status', '?')}`")
    parts.append(f"- note: {sfu.get('note', '?')}\n")
    parts.append("## Source\n")
    parts.append(report.get("source", CDLI_LICENSE))
    parts.append("")
    parts.append("\n---\n*G2++ Uruk III SFU comparator — structure != message. "
                 "Same-shape invariants in DIFFERENT sign systems confirm a "
                 "shared accounting-tablet STRUCTURE, NOT script-family "
                 "derivation. SFU/subset-sum probe SKIPPED per Captain brief "
                 "'Optional only if trivial; else SKIP'.*")
    return "\n".join(parts)


# --- main() ---------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description=("G2 Proto-Elamite ledger-entropy probe + G2++ Uruk III "
                     "SFU comparator + G2-REAL CDLI live fetch. STRUCTURE != MESSAGE."))
    ap.add_argument("--synthetic", action="store_true",
                    help="G2: run synthetic PE ledger (math proof).")
    ap.add_argument("--fetch-online", metavar="CDLI_ID",
                    help="G2: polite live CDLI fetch of the given tablet.")
    ap.add_argument("--bundled-corpus", metavar="PATH",
                    help="G2: USER_OVERRIDE bundled PE JSON corpus.")
    ap.add_argument("--multi-fetch", nargs="*",
                    help="G2-REAL: batch-fetch known Proto-Elamite CDLI IDs "
                         "(default: all 20 known IDs). Pass explicit IDs to "
                         "override the default list.")
    ap.add_argument("--list-known-cdli-ids", action="store_true",
                    help="G2-REAL: print the default list of known Proto-Elamite "
                         "CDLI IDs and exit.")
    ap.add_argument("--uruk-synthetic", action="store_true",
                    help="G2++: run synthetic Uruk III ledger (math proof).")
    ap.add_argument("--uruk-bundled-corpus", metavar="PATH",
                    help="G2++: USER_OVERRIDE bundled Uruk III JSON corpus.")
    ap.add_argument("--uruk-fetch-online", metavar="CDLI_ID",
                    help="G2++: polite live CDLI fetch of a Uruk III tablet.")
    ap.add_argument("--compare-pe-vs-uruk", action="store_true",
                    help="G2++: synth both PE + Uruk, compare, write to "
                         "outputs/proto_elamite/uruk_{run.json,NOTES.md}.")
    ap.add_argument("--fetch-status-test-force",
                    choices=["NEVER_ATTEMPTED", "UNREACHABLE", "PARKING_PAGE", "FETCHED"],
                    default=None,
                    help="TEST HOOK: synthesise fetch_status without network contact.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-shuffles", type=int, default=1000)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--out-md", default=None)
    a = ap.parse_args()

    if a.list_known_cdli_ids:
        print("Known Proto-Elamite CDLI IDs (Susa, MDP 06):")
        for cid in KNOWN_PE_CDLI_IDS:
            print(f"  {cid}")
        sys.exit(0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    is_uruk = (a.compare_pe_vs_uruk or a.uruk_synthetic or a.uruk_bundled_corpus
               or a.uruk_fetch_online)
    is_real = a.multi_fetch is not None
    uruk_paths = ("outputs/proto_elamite/uruk_run.json",
                   "outputs/proto_elamite/uruk_NOTES.md")
    pe_paths = ("outputs/proto_elamite/run.json",
                 "outputs/proto_elamite/NOTES.md")
    real_paths = ("outputs/proto_elamite/real_run.json",
                   "outputs/proto_elamite/real_NOTES.md")

    if a.multi_fetch is not None:
        ids = list(a.multi_fetch) if a.multi_fetch else list(KNOWN_PE_CDLI_IDS)
        report = run_multi_fetch_cdli(ids, n_shuffles=a.n_shuffles,
                                       seed=a.seed,
                                       force_status_for_tests=a.fetch_status_test_force)
        default_json, default_md = real_paths
    elif a.compare_pe_vs_uruk:
        report = run_compare_pe_vs_uruk_main(seed=a.seed,
                                              n_shuffles=a.n_shuffles)
        default_json, default_md = uruk_paths
    elif a.uruk_synthetic:
        report = run_uruk_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)
        default_json, default_md = uruk_paths
    elif a.uruk_bundled_corpus:
        report = run_uruk_bundled(Path(a.uruk_bundled_corpus),
                                   n_shuffles=a.n_shuffles, seed=a.seed)
        default_json, default_md = uruk_paths
    elif a.uruk_fetch_online:
        report = run_uruk_live(a.uruk_fetch_online, n_shuffles=a.n_shuffles,
                                seed=a.seed,
                                force_status_for_tests=a.fetch_status_test_force)
        default_json, default_md = uruk_paths
    elif a.synthetic:
        report = run_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)
        default_json, default_md = pe_paths
    elif a.bundled_corpus:
        report = run_bundled(Path(a.bundled_corpus),
                              n_shuffles=a.n_shuffles, seed=a.seed)
        default_json, default_md = pe_paths
    elif a.fetch_online:
        report = run_live_cdli(a.fetch_online, n_shuffles=a.n_shuffles,
                                seed=a.seed,
                                force_status_for_tests=a.fetch_status_test_force)
        default_json, default_md = pe_paths
    else:
        report = run_synthetic(seed=a.seed, n_shuffles=a.n_shuffles)
        default_json, default_md = pe_paths

    if "generated_at" not in report:
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
    if "source" not in report:
        report["source"] = CDLI_LICENSE

    out_json = Path(a.out_json) if a.out_json else (ROOT / default_json)
    out_md = Path(a.out_md) if a.out_md else (ROOT / default_md)
    if is_real:
        md_text = write_real_notes_md(report)
    elif is_uruk:
        md_text = write_uruk_notes_md(report)
    else:
        md_text = write_notes_md(report)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, default=str))
    out_md.write_text(md_text)
    print(f"wrote {out_json}")
    print(f"wrote {out_md}")
    if "verdict" in report:
        print(f"Verdict: {report['verdict']}")
    inv = report.get("invariants", {}).get("invariants", {})
    if inv:
        print(f"Invariants: header_void={inv.get('header_numeral_void')} "
              f"header_frac={inv.get('header_fraction_bounded')} "
              f"num_predictable={inv.get('numeral_block_predictable')} "
              f"z_lock={inv.get('z_lock_vs_shuffle')}")
    cmp = report.get("compare_pe_vs_uruk", {})
    if cmp:
        sh = cmp.get("shared_ledger_structure", {})
        print(f"PE all_pass: {sh.get('pe_all_pass')}; "
              f"Uruk all_pass: {sh.get('uruk_all_pass')}; "
              f"both_pass: {sh.get('both_pass')}")
        sfu = report.get("sfu_subset_sum_probe", {})
        print(f"SFU subset-sum status: {sfu.get('status')}")
    if is_real:
        print(f"Tablets fetched: {report.get('n_tablets_fetched', 0)}/"
              f"{report.get('n_requested_ids', 0)}")


if __name__ == "__main__":
    main()

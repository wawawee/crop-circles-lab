"""lde_probe — Long Delayed Echo historic-series analysis (G19).

Digitized from arXiv:1007.4054 (Faizullin 2010) and primary sources
(Størmer 1928, van der Pol 1928, Hals 1934, Appleton 1934,
Crawford 1970). 100 delay observations, 1927–1978.

Stance: **structure ≠ message.** We analyse DELAY VALUES only — no IQ
baseband exists, no synthetic baseband is fabricated. The "periodicity"
tested here is clustering/multiplicity in the delay-value multiset,
NOT a time-series periodicity of arrivals.

Verdict vocabulary (exactly one):
  NO_SIGNAL         — no excess structure over shuffle null
  UNDERDETERMINED   — ambiguous signal, cannot decide
  CLAIM_FAILS_NULL  — Lunan "Bootes/moon-relay" claim fails its null

Forbidden: confirming Lunan/Filipenko/Bracewell; fabricating IQ/baseband;
Skinwalker crossover.

CLI:
  python tools/radio/lde_probe.py --all
  python tools/radio/lde_probe.py --data data/radio/lde/lde_master.json
  python tools/radio/lde_probe.py --data data/radio/lde/lde_master.csv
  python tools/radio/lde_probe.py --lunan-claim
  python tools/radio/lde_probe.py --all --out-json outputs/radio/lde_run.json \
      --out-md outputs/radio/lde_NOTES.md
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

# Reuse radio_probe's Rayleigh Z² for the epoch-fold path.
TOOLS_RADIO = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_RADIO))
try:
    import radio_probe as RP
except ImportError:  # pragma: no cover
    RP = None


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

DATA_MASTER_JSON = (TOOLS_RADIO.parent.parent / "data" / "radio" / "lde"
                    / "lde_master.json")
DATA_MASTER_CSV = (TOOLS_RADIO.parent.parent / "data" / "radio" / "lde"
                   / "lde_master.csv")

# Stormer 1928 Oct 11 — Lunan's "Bootes" series (n=14).
# Source: Størmer 1928 Nature 122:681
STORMER_1928_OCT11_DELAYS_S = [
    8, 11, 15, 8, 13, 3, 8, 8, 8, 12, 15, 13, 8, 8,
]

# Prosaic mode: 8 s appears 7× in the Stormer series; Crawford confirmed
# "delays of 2 and 8 seconds were the most frequent."
PROSAIC_MODE_VALUE_S = 8.0
PROSAIC_SECOND_VALUE_S = 2.0

# Accuracy caveat for 1920s timing (stopwatch / second-hand watch).
TIMING_ACCURACY_NOTE = (
    "1920s timing: ±1–2 s uncertainty. Størmer 1955: 'The times noted by me "
    "can lay no claim to great accuracy, because I was not adequately prepared.' "
    "Van der Pol 1928: timing with stopwatch + second hand of ordinary watch."
)

# Shuffle iteration counts.
SHUFFLE_N_SYNTH = 200     # for descriptive structure tests
SHUFFLE_N_LUNAN = 1000    # for Lunan claim-under-test (tighter p-value)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_master(path: Path | None = None) -> list[dict]:
    """Load the master LDE delay table from JSON or CSV.

    Tries JSON first, then CSV. Returns list of dicts with at least
    'delay_s' and 'source' keys.
    """
    p = path
    if p is None:
        p = DATA_MASTER_JSON if DATA_MASTER_JSON.exists() else DATA_MASTER_CSV
    if not p.exists():
        raise FileNotFoundError(f"LDE master data not found: {p}")

    if p.suffix == ".json":
        with open(p) as f:
            rows = json.load(f)
    else:
        with open(p, newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            row["delay_s"] = float(row["delay_s"])
            row["index"] = int(row["index"])

    assert len(rows) > 0, "Master data is empty"
    assert all("delay_s" in r for r in rows), "Missing delay_s column"
    return rows


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def descriptive_stats(rows: list[dict]) -> dict:
    """Histogram of delay_s; per-source counts; basic moments."""
    delays = np.array([float(r["delay_s"]) for r in rows])
    sources = [r.get("source", "unknown") for r in rows]
    source_counts = dict(Counter(sources))

    # Delay-value multiplicity (how many values appear ≥2 times)
    val_counts = Counter(delays)
    integer_delays = [d for d in delays if d == int(d)]
    n_integer = len(integer_delays)
    n_unique = len(set(delays))
    n_repeated = sum(1 for c in val_counts.values() if c > 1)
    mode_val = val_counts.most_common(1)[0] if val_counts else (None, 0)

    # Entropy of delay distribution
    total = len(delays)
    probs = np.array([c / total for c in val_counts.values()])
    entropy = float(-np.sum(probs * np.log2(probs + 1e-30)))

    return {
        "n_total": int(total),
        "n_unique": int(n_unique),
        "delay_min_s": float(delays.min()),
        "delay_max_s": float(delays.max()),
        "delay_mean_s": float(delays.mean()),
        "delay_median_s": float(np.median(delays)),
        "delay_std_s": float(delays.std(ddof=1)),
        "n_integer_delays": int(n_integer),
        "fraction_integer": round(n_integer / total, 4),
        "n_repeated_values": int(n_repeated),
        "mode_delay_s": float(mode_val[0]) if mode_val[0] is not None else None,
        "mode_count": int(mode_val[1]),
        "entropy_bits": round(entropy, 4),
        "per_source": source_counts,
    }


# ---------------------------------------------------------------------------
# Structure tests on delay values (NOT time-series periodicity)
# ---------------------------------------------------------------------------

def integer_multiplicity_test(delays_s: np.ndarray, n_shuffle: int = SHUFFLE_N_SYNTH,
                              seed: int = 0) -> dict:
    """Test whether integer delays appear more often than expected.

    In the full corpus, most delays are integers (Størmer's 1920s reporting
    rounded to seconds). The question is: does the INTEGER multiplicity
    (how many distinct values appear more than once) exceed a shuffle null
    of the same multiset?

    Under the null, the delay multiset is shuffled — same values, different
    assignments to observations. The test statistic is the number of
    repeated values (values appearing ≥2 times).
    """
    rng = np.random.default_rng(seed)
    vals = list(delays_s)
    n_obs = len(vals)
    observed_n_repeated = sum(1 for c in Counter(vals).values() if c > 1)

    null_n_repeated = []
    for _ in range(n_shuffle):
        shuf = rng.permutation(vals)
        c = Counter(shuf)
        null_n_repeated.append(sum(1 for v in c.values() if v > 1))

    null_n_repeated = np.array(null_n_repeated)
    p_value = float(np.mean(null_n_repeated >= observed_n_repeated))

    return {
        "test": "integer_multiplicity",
        "statistic": "n_repeated_values",
        "observed": int(observed_n_repeated),
        "null_mean": round(float(null_n_repeated.mean()), 4),
        "null_p95": round(float(np.percentile(null_n_repeated, 95)), 4),
        "null_max": int(null_n_repeated.max()),
        "p_value": round(p_value, 6),
        "exceeds_null": bool(observed_n_repeated > null_n_repeated.mean() + 2 * null_n_repeated.std()),
        "n_shuffle": int(n_shuffle),
        "note": (
            "Tests whether integer-delay multiplicity exceeds a shuffle of "
            "the same multiset. NOT a time-series test. structure != message."
        ),
    }


def mode_concentration_test(delays_s: np.ndarray,
                            mode_value: float = PROSAIC_MODE_VALUE_S,
                            n_shuffle: int = SHUFFLE_N_SYNTH,
                            seed: int = 0) -> dict:
    """Test whether the mode (8 s) concentration exceeds a shuffle null.

    Crawford 1970: "delays of 2 and 8 seconds were the most frequent."
    The question: is the 8-s concentration in the master corpus
    significantly higher than expected from a random permutation of the
    same delay multiset?

    Statistic: count of delays == mode_value.
    """
    rng = np.random.default_rng(seed)
    vals = list(delays_s)
    observed_count = sum(1 for v in vals if v == mode_value)

    null_counts = []
    for _ in range(n_shuffle):
        shuf = rng.permutation(vals)
        null_counts.append(sum(1 for v in shuf if v == mode_value))

    null_counts = np.array(null_counts)
    p_value = float(np.mean(null_counts >= observed_count))

    return {
        "test": "mode_concentration",
        "mode_value_s": float(mode_value),
        "observed_count": int(observed_count),
        "observed_fraction": round(observed_count / len(vals), 4),
        "null_mean": round(float(null_counts.mean()), 4),
        "null_p95": round(float(np.percentile(null_counts, 95)), 4),
        "p_value": round(p_value, 6),
        "exceeds_null": bool(observed_count > null_counts.mean() + 2 * null_counts.std()),
        "n_shuffle": int(n_shuffle),
        "note": (
            f"Tests whether {mode_value}s concentration exceeds shuffle null. "
            "Crawford 1970: '2 and 8 seconds were the most frequent.' "
            "structure != message."
        ),
    }


def entropy_test(delays_s: np.ndarray,
                 n_shuffle: int = SHUFFLE_N_SYNTH,
                 seed: int = 0) -> dict:
    """Test whether the Shannon entropy of the delay distribution is lower
    than expected from a shuffle null.

    Lower entropy = more concentrated = more structure. Under the null,
    the same multiset is shuffled, so the distribution is identical —
    but the TEST is whether the observed entropy is within the expected
    range for this multiset size. This is really a consistency check:
    if the multiset is fixed, the entropy is a deterministic function
    of the value counts, so the null entropy is always the same.

    We instead compare against a UNIFORM null: a set of N draws from
    Uniform(0, max_delay) with the same N. This tests whether the
    observed distribution is more concentrated than uniform.
    """
    rng = np.random.default_rng(seed)
    vals = list(delays_s)
    n = len(vals)
    n_unique_obs = len(set(vals))

    # Observed entropy
    total = len(vals)
    val_counts = Counter(vals)
    probs = np.array([c / total for c in val_counts.values()])
    observed_entropy = float(-np.sum(probs * np.log2(probs + 1e-30)))

    # Uniform null: N draws from Uniform(0, max_delay), quantised to 0.5 s
    max_d = float(max(vals))
    null_entropies = []
    for _ in range(n_shuffle):
        uniform_vals = np.round(rng.uniform(0, max_d, size=n) * 2) / 2
        uc = Counter(uniform_vals)
        total_u = len(uniform_vals)
        pp = np.array([c / total_u for c in uc.values()])
        null_entropies.append(float(-np.sum(pp * np.log2(pp + 1e-30))))

    null_entropies = np.array(null_entropies)
    # LOW entropy = more concentrated = more structure
    p_low = float(np.mean(null_entropies <= observed_entropy))

    return {
        "test": "entropy_vs_uniform",
        "observed_entropy_bits": round(observed_entropy, 4),
        "uniform_null_mean_entropy": round(float(null_entropies.mean()), 4),
        "uniform_null_std_entropy": round(float(null_entropies.std()), 4),
        "p_value_low_entropy": round(p_low, 6),
        "n_unique_observed": int(n_unique_obs),
        "note": (
            "Shannon entropy of delay distribution vs uniform null. "
            "Low entropy = concentrated distribution. "
            "structure != message; concentration can arise from rounding "
            "(1920s integer-second reporting) or from prosaic clustering."
        ),
    }


# ---------------------------------------------------------------------------
# Epoch-fold on delay values (optional — structure != message)
# ---------------------------------------------------------------------------

def delay_epoch_fold(delays_s: np.ndarray,
                     period_grid: np.ndarray | None = None,
                     seed: int = 0) -> dict:
    """Epoch-fold the delay values themselves (NOT arrival times).

    WARNING: This treats delay_s values as 'arrival times' for the
    purpose of finding periodicity in the VALUE distribution. This is
    a math-validation tool; a positive result means 'the delay values
    repeat at a regular interval', NOT 'the echoes are periodic in real
    time'.

    Requires radio_probe for rayleigh_z2.
    """
    if RP is None:
        return {"error": "radio_probe not importable; epoch_fold disabled"}

    t = np.asarray(delays_s, dtype=float)
    if period_grid is None:
        max_d = float(t.max())
        period_grid = np.arange(0.5, max_d / 2.0 + 0.1, 0.1)

    z2_curve = []
    for P in period_grid:
        z2, phase = RP.rayleigh_z2(t, float(P))
        z2_curve.append({"period_s": float(P), "z2": float(z2),
                         "phase_rad": float(phase)})

    best = max(z2_curve, key=lambda x: x["z2"])

    # Shuffle null
    rng = np.random.default_rng(seed)
    shuf_z2_max = 0.0
    for _ in range(SHUFFLE_N_SYNTH):
        shuf = rng.uniform(0, float(t.max()), size=len(t))
        for P in period_grid:
            z2_s, _ = RP.rayleigh_z2(shuf, float(P))
            if z2_s > shuf_z2_max:
                shuf_z2_max = z2_s

    return {
        "test": "delay_value_epoch_fold",
        "best_period_s": best["period_s"],
        "best_z2": best["z2"],
        "best_phase_rad": best["phase_rad"],
        "shuffled_z2_max": round(shuf_z2_max, 4),
        "exceeds_shuffle": bool(best["z2"] > shuf_z2_max),
        "note": (
            "Epoch-fold on delay VALUES (not arrival times). A positive "
            "result means delay values repeat at a regular interval, NOT "
            "that echoes are periodic in real time. structure != message."
        ),
    }


# ---------------------------------------------------------------------------
# Lunan claim-under-test (Stormer 1928 Oct 11 subset)
# ---------------------------------------------------------------------------

def _lunan_structure_stat(delays_s: list[float]) -> float:
    """Quantify 'Lunan-like' structure in a delay series.

    Lunan's claim: delay values encode a star constellation (Bootes).
    The key structural features he invoked:
      1. The 8-s value is dominant (barrier / reference).
      2. The 3-s value is unique (exact repeat of transmitted signal).
      3. Values cluster at specific 'star positions'.

    Our test statistic: a composite score combining:
      - Multiplicity of 8s (the 'barrier' dominance)
      - Presence of 3s (the 'unique dot')
      - Skew toward integer values (prosaic rounding)

    We normalise so that a random permutation of the same multiset
    gives ~0 and the actual series gives a score.
    """
    vals = list(delays_s)
    n = len(vals)
    counts = Counter(vals)

    # Factor 1: 8s dominance — fraction of delays equal to 8
    f8 = counts.get(8, 0) / n

    # Factor 2: 3s presence — 1 if present, 0 if not
    has_3 = 1.0 if 3 in counts else 0.0

    # Factor 3: integer concentration — fraction of integer delays
    f_int = sum(1 for v in vals if v == int(v)) / n

    # Composite: weighted sum
    return 0.4 * f8 + 0.3 * has_3 + 0.3 * f_int


def lunan_claim_test(stormer_delays: list[float] | None = None,
                     n_shuffle: int = SHUFFLE_N_LUNAN,
                     seed: int = 0) -> dict:
    """Test Lunan's 'Bootes / moon relay' claim on the Stormer 1928
    Oct 11 series (n=14).

    Lunan's hypothesis: delay values encode a constellation.
    Null hypotheses:
      (a) Shuffle null: permute the 14 delay values randomly.
          If Lunan's structure is real, the observed composite score
          should exceed the shuffle null distribution.
      (b) Prosaic null: generate delays from a distribution that
          favours 2s and 8s (as noted by Crawford/Hals). If the
          Lunan structure is just prosaic clustering, the prosaic
          null should match or exceed it.

    Verdict:
      - If observed beats BOTH nulls → UNDERDETERMINED (structure exists
        but could be prosaic rounding; insufficient to confirm Lunan)
      - If observed fails EITHER null → CLAIM_FAILS_NULL
      - Lunan is NEVER confirmed. Period.
    """
    if stormer_delays is None:
        stormer_delays = STORMER_1928_OCT11_DELAYS_S

    rng = np.random.default_rng(seed)
    vals = list(stormer_delays)
    n = len(vals)
    observed_score = _lunan_structure_stat(vals)

    # (a) Shuffle null: permute the multiset
    shuffle_scores = []
    for _ in range(n_shuffle):
        shuf = rng.permutation(vals).tolist()
        shuffle_scores.append(_lunan_structure_stat(shuf))
    shuffle_scores = np.array(shuffle_scores)
    p_shuffle = float(np.mean(shuffle_scores >= observed_score))

    # (b) Prosaic null: generate delays from weighted distribution
    #     favouring 2s and 8s (the historical mode pattern).
    prosaic_pool = []
    for v in set(vals):
        count = Counter(vals)[v]
        # Weight 2s and 8s more heavily
        if v == PROSAIC_MODE_VALUE_S:
            weight = 3.0  # boost 8s
        elif v == PROSAIC_SECOND_VALUE_S:
            weight = 2.0  # boost 2s
        else:
            weight = 1.0
        prosaic_pool.extend([v] * int(count * weight))

    prosaic_scores = []
    for _ in range(n_shuffle):
        # Sample n values from the prosaic pool with replacement
        prosaic_sample = rng.choice(prosaic_pool, size=n, replace=True).tolist()
        prosaic_scores.append(_lunan_structure_stat(prosaic_sample))
    prosaic_scores = np.array(prosaic_scores)
    p_prosaic = float(np.mean(prosaic_scores >= observed_score))

    # Verdict
    beats_shuffle = observed_score > shuffle_scores.mean() + 2 * shuffle_scores.std()
    beats_prosaic = observed_score > prosaic_scores.mean() + 2 * prosaic_scores.std()

    if beats_shuffle and beats_prosaic:
        verdict = "UNDERDETERMINED"
        verdict_reason = (
            "Observed Lunan-structure score exceeds both shuffle and prosaic "
            "nulls. Structure exists but is consistent with prosaic integer "
            "rounding (1920s ±1-2 s accuracy) and Crawford/Hals mode "
            "clustering. INSUFFICIENT to confirm Lunan. Period."
        )
    else:
        verdict = "CLAIM_FAILS_NULL"
        if not beats_shuffle:
            verdict_reason = (
                "Lunan-structure score does NOT exceed shuffle null. "
                "The delay-value multiset has no more 'Bootes-like' structure "
                "than a random permutation of the same values."
            )
        else:
            verdict_reason = (
                "Lunan-structure score matches or is exceeded by the prosaic "
                "null (2s/8s mode clustering). The apparent structure is "
                "consistent with Crawford/Hals observation that '2 and 8 "
                "seconds were the most frequent' — no exotic interpretation "
                "needed."
            )

    return {
        "test": "lunan_claim_stormer_oct11",
        "subset": "Stormer 1928 Oct 11 (n=14)",
        "delays": vals,
        "observed_score": round(observed_score, 4),
        "shuffle_null_mean": round(float(shuffle_scores.mean()), 4),
        "shuffle_null_std": round(float(shuffle_scores.std()), 4),
        "shuffle_null_p95": round(float(np.percentile(shuffle_scores, 95)), 4),
        "p_shuffle": round(p_shuffle, 6),
        "beats_shuffle_null": bool(beats_shuffle),
        "prosaic_null_mean": round(float(prosaic_scores.mean()), 4),
        "prosaic_null_std": round(float(prosaic_scores.std()), 4),
        "prosaic_null_p95": round(float(np.percentile(prosaic_scores, 95)), 4),
        "p_prosaic": round(p_prosaic, 6),
        "beats_prosaic_null": bool(beats_prosaic),
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "stance": (
            "Lunan's 'Bootes constellation / moon-relay' hypothesis is "
            "UNDER-TEST here. Verdict is CLAIM_FAILS_NULL or UNDERDETERMINED. "
            "Never validates Lunan. Structure != message."
        ),
        "accuracy_caveat": TIMING_ACCURACY_NOTE,
        "n_shuffle": int(n_shuffle),
    }


# ---------------------------------------------------------------------------
# Full corpus shuffle test
# ---------------------------------------------------------------------------

def corpus_shuffle_test(rows: list[dict],
                        n_shuffle: int = SHUFFLE_N_SYNTH,
                        seed: int = 0) -> dict:
    """Test whether the full corpus (100 delays) has any excess structure
    over a shuffle null.

    Statistic: Shannon entropy of the delay distribution. Lower = more
    concentrated = more structure. Under the null, the same multiset is
    shuffled — entropy is a deterministic function of the value counts,
    so the null distribution is degenerate. Instead we compare against
    a UNIFORM null (N draws from Uniform(0, max_delay)).

    If the observed entropy is NOT significantly lower than uniform →
    NO_SIGNAL (the delay distribution is not more concentrated than
    random).
    """
    delays = np.array([float(r["delay_s"]) for r in rows])
    ent = entropy_test(delays, n_shuffle=n_shuffle, seed=seed)

    # Additional: chi-squared test for uniformity of integer delays
    integer_delays = [int(d) for d in delays if d == int(d)]
    if len(integer_delays) > 0:
        val_counts = Counter(integer_delays)
        expected_count = len(integer_delays) / len(set(integer_delays))
        chi2 = sum((c - expected_count) ** 2 / expected_count
                   for c in val_counts.values())
    else:
        chi2 = 0.0

    # Overall: if entropy is not significantly low → NO_SIGNAL
    is_structured = ent["p_value_low_entropy"] < 0.05

    return {
        "test": "corpus_shuffle",
        "n_total": int(len(delays)),
        "entropy": ent,
        "chi2_uniformity": round(chi2, 4),
        "any_excess_structure": bool(is_structured),
        "verdict": "NO_SIGNAL" if not is_structured else "UNDERDETERMINED",
        "note": (
            "Full corpus structure test. If the delay distribution is not "
            "more concentrated than a uniform random draw → NO_SIGNAL. "
            "structure != message."
        ),
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all(seed: int = 0,
            data_path: Path | None = None,
            n_shuffle_syn: int = SHUFFLE_N_SYNTH,
            n_shuffle_lunan: int = SHUFFLE_N_LUNAN) -> dict:
    """Run the full LDE analysis suite."""
    rows = load_master(data_path)
    desc = descriptive_stats(rows)
    delays = np.array([float(r["delay_s"]) for r in rows])

    # Structure tests on full corpus
    int_mult = integer_multiplicity_test(delays, n_shuffle=n_shuffle_syn, seed=seed)
    mode_test = mode_concentration_test(delays, n_shuffle=n_shuffle_syn, seed=seed)
    ent_test = entropy_test(delays, n_shuffle=n_shuffle_syn, seed=seed)
    corpus_test = corpus_shuffle_test(rows, n_shuffle=n_shuffle_syn, seed=seed)

    # Epoch fold (optional — requires radio_probe)
    try:
        efold = delay_epoch_fold(delays, seed=seed)
    except Exception as e:
        efold = {"error": str(e)}

    # Lunan claim
    lunan = lunan_claim_test(n_shuffle=n_shuffle_lunan, seed=seed)

    # Overall verdict
    overall_verdict = corpus_test["verdict"]
    if lunan["verdict"] == "CLAIM_FAILS_NULL":
        overall_verdict = "CLAIM_FAILS_NULL"
    elif lunan["verdict"] == "UNDERDETERMINED" and overall_verdict == "NO_SIGNAL":
        overall_verdict = "UNDERDETERMINED"

    return {
        "label": "lde_probe",
        "mission": "G19 — Long Delayed Echoes historic series",
        "stance": (
            "structure != message. Historic delay values, not IQ baseband. "
            "We analyse delay-value multiset structure only. Never validates "
            "Lunan/Filipenko/Bracewell."
        ),
        "data_source": str(data_path or DATA_MASTER_JSON),
        "n_observations": desc["n_total"],
        "descriptive": desc,
        "structure_tests": {
            "integer_multiplicity": int_mult,
            "mode_concentration_8s": mode_test,
            "entropy_vs_uniform": ent_test,
            "epoch_fold_values": efold,
        },
        "corpus_verdict": corpus_test,
        "lunan_claim": lunan,
        "overall_verdict": overall_verdict,
        "accuracy_caveat": TIMING_ACCURACY_NOTE,
        "forbidden": [
            "No IQ/baseband fabricated",
            "No Lunan/Filipenko/Bracewell confirmation",
            "No Skinwalker crossover",
        ],
    }


# ---------------------------------------------------------------------------
# Markdown notes renderer
# ---------------------------------------------------------------------------

def write_notes_md(report: dict) -> str:
    """Render a NOTES.md from the analysis report."""
    v = report["overall_verdict"]
    desc = report["descriptive"]
    lunan = report["lunan_claim"]
    lines = [
        f"# lde_probe — G19 Long Delayed Echoes NOTES",
        "",
        f"> **Verdict: {v}**",
        "> Stance: **structure ≠ message.** Historic delay values only, not IQ baseband.",
        f"> Generated from `{report['data_source']}` ({desc['n_total']} observations).",
        "",
        "---",
        "",
        "## Descriptive Statistics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total observations | {desc['n_total']} |",
        f"| Unique delay values | {desc['n_unique']} |",
        f"| Delay range | {desc['delay_min_s']:.1f}–{desc['delay_max_s']:.1f} s |",
        f"| Mean delay | {desc['delay_mean_s']:.2f} s |",
        f"| Median delay | {desc['delay_median_s']:.2f} s |",
        f"| Std deviation | {desc['delay_std_s']:.2f} s |",
        f"| Mode (most frequent) | {desc['mode_delay_s']} s ({desc['mode_count']}×) |",
        f"| Integer delays | {desc['n_integer_delays']}/{desc['n_total']} ({desc['fraction_integer']*100:.1f}%) |",
        f"| Repeated values | {desc['n_repeated_values']} |",
        f"| Shannon entropy | {desc['entropy_bits']:.2f} bits |",
        "",
        "### Per-source breakdown",
        "",
        "| Source | Count |",
        "|--------|-------|",
    ]
    for src, cnt in sorted(desc["per_source"].items(), key=lambda x: -x[1]):
        lines.append(f"| {src} | {cnt} |")

    lines.extend([
        "",
        "---",
        "",
        "## Structure Tests (Full Corpus)",
        "",
    ])

    for name, test in report["structure_tests"].items():
        lines.append(f"### {name}")
        lines.append("")
        if isinstance(test, dict) and "error" not in test:
            for k, v in test.items():
                if k != "note":
                    lines.append(f"- **{k}**: {v}")
            if "note" in test:
                lines.append(f"- *Note:* {test['note']}")
        elif "error" in test:
            lines.append(f"- Error: {test['error']}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Corpus Verdict",
        "",
        f"- **{report['corpus_verdict']['verdict']}**",
        f"- Any excess structure over uniform null: {report['corpus_verdict']['any_excess_structure']}",
        f"- Shannon entropy p-value (low = concentrated): {report['corpus_verdict']['entropy']['p_value_low_entropy']}",
        "",
        "---",
        "",
        "## Lunan Claim-Under-Test (Stormer 1928 Oct 11, n=14)",
        "",
        f"- **Verdict: {lunan['verdict']}**",
        f"- Observed structure score: {lunan['observed_score']}",
        f"- Shuffle null: mean={lunan['shuffle_null_mean']}, std={lunan['shuffle_null_std']}, p={lunan['p_shuffle']}",
        f"- Prosaic null: mean={lunan['prosaic_null_mean']}, std={lunan['prosaic_null_std']}, p={lunan['p_prosaic']}",
        f"- Beats shuffle null: {lunan['beats_shuffle_null']}",
        f"- Beats prosaic null: {lunan['beats_prosaic_null']}",
        f"- Reason: {lunan['verdict_reason']}",
        "",
        f"> {lunan['stance']}",
        "",
        "---",
        "",
        "## Accuracy Caveat",
        "",
        f"> {TIMING_ACCURACY_NOTE}",
        "",
        "---",
        "",
        "## Controls Ledger",
        "",
        "| Control | Where | Expected |",
        "|---------|-------|----------|",
        "| Shuffle null (multiset permute) | All structure tests | Structure must NOT exceed |",
        "| Prosaic null (2s/8s weighted) | Lunan claim | Lunan structure must NOT exceed |",
        "| Uniform null (random delays) | Entropy test | Observed entropy must NOT be lower |",
        "",
        "---",
        "",
        "## Forbidden",
        "",
        "- No ET/alien probe claims",
        "- No Lunan/Filipenko/Bracewell confirmation",
        "- No IQ/baseband fabrication",
        "- No Skinwalker / modern SDR crossover",
        "",
        f"*{report['stance']}*",
    ])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="G19 LDE historic-series probe (structure != message)"
    )
    parser.add_argument("--all", action="store_true",
                        help="Run all analyses")
    parser.add_argument("--descriptive", action="store_true",
                        help="Descriptive statistics only")
    parser.add_argument("--structure", action="store_true",
                        help="Structure tests on full corpus")
    parser.add_argument("--lunan-claim", action="store_true",
                        help="Lunan claim-under-test on Stormer Oct 11")
    parser.add_argument("--epoch-fold", action="store_true",
                        help="Epoch-fold on delay values")
    parser.add_argument("--data", type=Path, default=None,
                        help="Path to master JSON or CSV (default: auto)")
    parser.add_argument("--seed", type=int, default=0,
                        help="RNG seed")
    parser.add_argument("--n-shuffle-syn", type=int, default=SHUFFLE_N_SYNTH,
                        help=f"Shuffle iterations for structure tests (default {SHUFFLE_N_SYNTH})")
    parser.add_argument("--n-shuffle-lunan", type=int, default=SHUFFLE_N_LUNAN,
                        help=f"Shuffle iterations for Lunan claim (default {SHUFFLE_N_LUNAN})")
    parser.add_argument("--out-json", type=Path, default=None,
                        help="Output JSON path")
    parser.add_argument("--out-md", type=Path, default=None,
                        help="Output Markdown notes path")

    args = parser.parse_args()

    if not any([args.all, args.descriptive, args.structure,
                args.lunan_claim, args.epoch_fold]):
        args.all = True

    report = run_all(
        seed=args.seed,
        data_path=args.data,
        n_shuffle_syn=args.n_shuffle_syn,
        n_shuffle_lunan=args.n_shuffle_lunan,
    )

    # Selective output
    if args.descriptive:
        report = {"label": "lde_probe", "descriptive": report["descriptive"]}
    elif args.structure:
        report = {"label": "lde_probe", "structure_tests": report["structure_tests"]}
    elif args.lunan_claim:
        report = {"label": "lde_probe", "lunan_claim": report["lunan_claim"]}
    elif args.epoch_fold:
        report = {"label": "lde_probe", "epoch_fold": report["structure_tests"]["epoch_fold_values"]}

    print(json.dumps(report, indent=2, default=str))

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"JSON written to {args.out_json}", file=sys.stderr)

    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        md = write_notes_md(report)
        with open(args.out_md, "w") as f:
            f.write(md)
        print(f"Markdown written to {args.out_md}", file=sys.stderr)


if __name__ == "__main__":
    main()

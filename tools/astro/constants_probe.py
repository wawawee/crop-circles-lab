"""
constants_probe.py -- Hermes mission N3: Dimensionless constants pattern hunt.

Computes pairwise ratios of canonical dimensionless physical constants, then
asks Gerald S. Hawkins' question with a 2026 twist:

    \"Are the dimensionless ratios that govern the universe small-whole-number
     'diatonic' ratios -- the way Hawkins reported for crop-circle pitches?\"

We:

  (1) Build a table of canonical dimensionless constants (CODATA / PDG / Planck)
      and recover the famous coincidences -- m_p/m_e, the lepton ladder, the
      cosmic coincidence Omega_m ~ Omega_Lambda, the alpha_G ~ 1/alpha Dirac
      Large Number Hypothesis, etc.
  (2) Compute all n(n-1)/2 pairwise ratios. For each ratio we apply the same
      Hawkins-style diatonic fold (ratios.py::nearest_diatonic) and a cents
      error, plus log10 of the raw ratio so the order-of-magnitude is visible.
  (3) Write outputs/constants/feature_table.csv -- the deliverable listed on the
      MISSION_BOARD N3 row.
  (4) Run TWO negative controls (mandatory per ROADMAP_BEYOND_WHEAT.md):
        (a) log-uniform-within-decade -- replaces every real constant with a
            random value in its own order of magnitude (preserves rough 'this
            constant lives in decade X' structure, randomises exact value);
        (b) pair-permutation null -- keeps the values fixed and randomly
            pairs which two constants are compared. THIS answers 'are these
            specific pair cells special?', which (a) does not.
      A 'diatonic hit' means within `tol_cents` of a just-intonation note.

Honest framing (crop-circle lab motto: structure != message):

    A 'diatonic hit within 20 cents' on a ratio of two physical constants is
    necessary, not sufficient evidence of design. Selection bias, look-elsewhere
    effect, and the fact that small-integer ratios are dense in real space all
    inflate apparent signal. The watchlist below tags the famous coincidences
    (Dirac LNH, Eddington, cosmic coincidence, lepton ladder). Hit totals are
    reported WITH and WITHOUT the watchlist to make the selection effect
    explicit. Derived ratios (e.g. alpha/alpha_G) are tagged `derived=True` and
    EXCLUDED from hit counts -- they would triple-count the LNH pair.

CLI:
    python tools/astro/constants_probe.py --out outputs/constants/
    python tools/astro/constants_probe.py --trials 2000 --csv
    python tools/astro/constants_probe.py --constant-set large   # adds Dirac LNH
    python tools/astro/constants_probe.py --small-control        # N=50 trials (fast)

Dependencies: numpy + the repo's forensics/ratios.py. Pure standard library.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "forensics"))
import ratios as R  # noqa: E402


# ---------------------------------------------------------------------------
# Canonical dimensionless constants table
# Sources: CODATA 2018 (https://physics.nist.gov/cuu/Constants), PDG 2022,
# Planck 2018 (arXiv:1807.06209). Values frozen at CI; uncertainty omitted
# because we are hunting whole-number ratios, not propagating error budgets.
# `derived=True` flags rows that are DERIVED ratii of the others -- they are
# excluded from hit counts to avoid double-counting (e.g. Dirac LNH).
# ---------------------------------------------------------------------------
CONSTANTS_CORE = [
    {"name": "alpha",           "symbol": "α",          "value": 7.2973525643e-3,
     "category": "coupling", "source": "CODATA 2018 fine-structure constant"},
    {"name": "alpha_s_MZ",      "symbol": "α_s(M_Z)",   "value": 0.1179,
     "category": "coupling", "source": "PDG 2022 strong coupling at M_Z"},
    {"name": "sin2_thetaW",     "symbol": "sin²θ_W",    "value": 0.23121,
     "category": "coupling", "source": "PDG 2022 weak mixing angle (on-shell)"},
    {"name": "mp_me",           "symbol": "m_p/m_e",    "value": 1836.15267343,
     "category": "mass",     "source": "CODATA 2018 proton/electron mass"},
    {"name": "Omega_matter",    "symbol": "Ω_m",        "value": 0.3153,
     "category": "cosmo",    "source": "Planck 2018 (TT,TE,EE+lowE+BAO)"},
    {"name": "Omega_Lambda",    "symbol": "Ω_Λ",        "value": 0.6847,
     "category": "cosmo",    "source": "Planck 2018 dark energy density"},
    {"name": "Omega_baryon",    "symbol": "Ω_b",        "value": 0.0493,
     "category": "cosmo",    "source": "Planck 2018 baryon density"},
    {"name": "n_s",             "symbol": "n_s",        "value": 0.9649,
     "category": "cosmo",    "source": "Planck 2018 scalar spectral index"},
    {"name": "electron_g-2",    "symbol": "(g-2)/2",    "value": 1.159652181e-3,
     "category": "anomaly",  "source": "CODATA 2018 electron magnetic moment anomaly"},
    {"name": "mn_mp",           "symbol": "m_n/m_p",    "value": 1.00137841931,
     "category": "mass",     "source": "CODATA 2018"},
    {"name": "m_mu_me",         "symbol": "m_μ/m_e",    "value": 206.7682830,
     "category": "mass",     "source": "CODATA 2018 muon/electron mass"},
    {"name": "m_tau_me",        "symbol": "m_τ/m_e",    "value": 3477.15,
     "category": "mass",     "source": "PDG 2022 tau/electron mass"},
    {"name": "m_tau_mmu",       "symbol": "m_τ/m_μ",    "value": 16.8170,
     "category": "mass",     "source": "PDG 2022 tau/muon mass"},
    {"name": "CMB_dT_T",        "symbol": "ΔT/T",       "value": 5.0e-5,
     "category": "cosmo",    "source": "Planck 2018 quadrupole anisotropy ~ 1e-5"},
    {"name": "epsilon_K_CP",    "symbol": "ε_K",        "value": 2.228e-3,
     "category": "anomaly",  "source": "PDG 2022 indirect CP violation in K_L decay"},
]


# "large" set adds Dirac Large Number candidates. alpha_G(proton) is an
# INDEPENDENT constant (no pair of others derives it). The two `derived=True`
# rows below are included for *narrative* completeness only -- the analysis
# filters them before counting hits.
CONSTANTS_LARGE_EXTRA = [
    {"name": "alpha_G_proton", "symbol": "α_G",         "value": 5.906e-39,
     "category": "dirac",   "derived": False,
     "source": "G m_p² / (ℏ c); Dirac LNH -- fundamental"},
    {"name": "ratio_LNDirac",  "symbol": "α/α_G",       "value": 1.236e36,
     "category": "dirac",   "derived": True,
     "source": "alpha / alpha_G -- DERIVED, excluded from hit counts (triple-counts LNH)"},
    {"name": "N_Hubble_particles", "symbol": "N_H",     "value": 1.0e80,
     "category": "dirac",   "derived": False,
     "source": "N ~ (c/H_0)^3 / cm^3 ~ 10^80 (Dirac uses ~10^78)"},
    {"name": "ratio_age_Hubble","symbol": "1/(H_0 t_P)", "value": 4.35e60,
     "category": "dirac",   "derived": True,
     "source": "1/(H_0 t_Planck) -- DERIVED, excluded from hit counts"},
]


def get_table(set_name: str = "core") -> list[dict]:
    """Return constant table. 'core' (default) -- 15 fundamental dimensionless
    constants, NO Dirac LNH. 'large' -- core + alpha_G, N_H, plus derived
    ratios kept for narrative only. 'large' excludes the derived rows from
    the hit-count denominator automatically.

    The split exists so a CI run of `--set core` is a clean apples-to-apples
    probe of the standard model fundamental constants, and `--set large` is
    an explicit 'turn on Dirac' mode where the derived rows are visible but
    neutralised.
    """
    name = (set_name or "core").lower()
    if name in ("core", "default"):
        return list(CONSTANTS_CORE)
    if name in ("large", "dirac", "dirac_lnh"):
        # Mark core rows as not-derived
        out = [dict(c, derived=False) for c in CONSTANTS_CORE]
        out.extend(CONSTANTS_LARGE_EXTRA)
        return out
    raise ValueError(f"unknown constant-set: {set_name!r} (use 'core' or 'large')")


# Famous coincidences / watchlist pairs -- tagged for human-readable narrative.
# Hit totals are reported BOTH including and excluding these so the
# selection-bias loop ('we found what we looked for') is visible to the reader.
WATCHLIST = [
    ("alpha_G_proton", "alpha",              "Dirac LNH: gravitational vs EM coupling (~10^36)"),
    ("mp_me",          "alpha",              "Eddington coincidence (m_p/m_e ~ 6*(1/alpha) ~ 6*137)"),
    ("Omega_matter",   "Omega_Lambda",       "Cosmic coincidence (matter-Lambda crossover)"),
    ("mp_me",          "m_mu_me",            "Proton vs muon mass (factor ~ 8.9)"),
    ("m_tau_mmu",      "m_mu_me",            "Lepton mass ratio chain"),
    ("n_s",            "alpha",              "Harrison-Zel'dovich / scalar index vs fine-structure"),
    ("m_tau_me",       "mp_me",              "Tau vs proton mass (~ 1.9)"),
    ("epsilon_K_CP",   "alpha_s_MZ",         "Kaon CP violation vs strong coupling"),
]

# Visually bold small-integer matches in the markdown when pct error below this.
INT_RATIO_BOLD_PCT = 2.0


@dataclass
class PairwiseRatio:
    i: int
    j: int
    a_name: str
    b_name: str
    a_symbol: str
    b_symbol: str
    ratio: float
    log10_abs: float
    folded_to_octave: float
    diatonic_note: str
    diatonic_target: float
    cents_error: float
    within_tol: bool
    integer_ratio: str
    integer_pct_error: float
    on_watchlist: bool
    watchlist_reason: str


def pairwise_ratios(constants: list[dict], tol_cents: float = 20.0) -> list[PairwiseRatio]:
    """All n(n-1)/2 pairwise ratios, Hawkins-style fold + cents error.

    Uses the canonical record format `a` (smaller index) over `b` (larger
    index); if a < b mathematically the ratio is inverted so large_small
    is reported (>= 1.0). This keeps the watchlist tagger consistent: we
    treat pair (alpha, mp_me) and pair (mp_me, alpha) as the same entry.
    """
    n = len(constants)
    if n < 2:
        return []
    pairs: list[PairwiseRatio] = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = constants[i], constants[j]
            va, vb = float(a["value"]), float(b["value"])
            if vb == 0 or not math.isfinite(va / vb):
                continue
            # We always report large / small so r >= 1.0, label the bigger one
            # 'a' for symmetry with the watchlist tagger.
            if va >= vb:
                ra_name, rb_name = a["name"], b["name"]
                ra_sym, rb_sym = a["symbol"], b["symbol"]
                ratio = va / vb
            else:
                ra_name, rb_name = b["name"], a["name"]
                ra_sym, rb_sym = b["symbol"], a["symbol"]
                ratio = vb / va
            folded = R.reduce_to_octave(ratio)
            m = R.nearest_diatonic(ratio, tol_cents=tol_cents)
            ir = R.nearest_small_integer_ratio(ratio, max_denominator=20)
            on_wl, reason = _tag_watch(ra_name, rb_name)
            pairs.append(PairwiseRatio(
                i=i, j=j,
                a_name=ra_name, b_name=rb_name,
                a_symbol=ra_sym, b_symbol=rb_sym,
                ratio=float(ratio),
                log10_abs=float(math.log10(abs(ratio))),
                folded_to_octave=float(folded),
                diatonic_note=m.note,
                diatonic_target=float(m.target),
                cents_error=float(m.cents_error),
                within_tol=bool(m.within_tol),
                integer_ratio=str(ir.fraction),
                integer_pct_error=float(ir.pct_error),
                on_watchlist=on_wl,
                watchlist_reason=reason,
            ))
    return pairs


def _tag_watch(a_name: str, b_name: str) -> tuple[bool, str]:
    for n1, n2, why in WATCHLIST:
        if {n1, n2} == {a_name, b_name}:
            return True, why
    return False, ""


def log10_signed_matrix(constants: list[dict]) -> tuple[np.ndarray, list[str]]:
    """signed log10 ratio matrix M[i,j] = log10(constant_i / constant_j)."""
    names = [c["name"] for c in constants]
    logs = np.array([math.log10(float(c["value"])) for c in constants], dtype=float)
    M = logs[:, None] - logs[None, :]
    return M, names


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------
def random_constants_control(constants: list[dict], n_trials: int = 1000,
                             tol_cents: float = 20.0,
                             seed: int | None = 20260725) -> np.ndarray:
    """Null A: log-uniform-within-decade.

    For each trial, replace every constant with a value sampled LOG-UNIFORMLY
    within its own order of magnitude (uniform in [10^floor(log10), 10^ceil]).
    Preserves rough 'this constant lives in decade X' structure, randomises
    exact value. Hit counts above this bar's 95th percentile are noteworthy;
    below it are consistent with naive random expectation.

    Constants flagged `derived=True` are sampled like the others but their
    hits are NOT counted by the caller's analysis -- see filter_for_hits.
    """
    rng = np.random.default_rng(seed)
    reuse = []
    for c in constants:
        v = float(c["value"])
        if v <= 0 or not math.isfinite(math.log10(v)):
            continue
        lo = math.floor(math.log10(v))
        reuse.append({**c, "_log10_lo": float(lo),
                              "_log10_hi": float(lo) + 1.0})
    hits = np.empty(n_trials, dtype=int)
    for t in range(n_trials):
        sampled = [{**c, "value": 10.0 ** rng.uniform(c["_log10_lo"], c["_log10_hi"])}
                   for c in reuse]
        # Filter out derived rows so the null matches the filtered real analysis.
        sampled = [s for s in sampled if not s.get("derived", False)]
        pairs = pairwise_ratios(sampled, tol_cents)
        hits[t] = _count_countable_hits(pairs)
    return hits


def pair_permutation_control(constants: list[dict], n_trials: int = 1000,
                             tol_cents: float = 20.0,
                             seed: int | None = 20260725) -> np.ndarray:
    """Null B: reciprocal-arrangement (pair-permutation).

    For each trial: keep the named slots fixed, scramble which real constant's
    VALUE is assigned to each NAME. Recompute pairwise ratios over the
    shuffled table and count diatonic hits. This answers the question the
    decade-null does NOT: 'are these specific PAIRINGS (alpha vs mp_me,
    Omega_m vs Omega_Lambda) special compared to random arrangements?' If the
    real hit count beats the permutation null, the SPECIFIC pair-cells are
    doing the work; if not, the apparent structure is an arrangement effect.

    Operator note: this permutes which value is assigned to each named slot,
    NOT which pair-indices are visited. The two operators are different and
    'permute pair indices' is the weaker null. We use the stronger one.

    This is the gold-standard reciprocal-arrangement null in tandem-massed
    spectrometry (e.g. charge-state correlation tests).
    """
    rng = np.random.default_rng(seed)
    real = [c for c in constants if not c.get("derived", False)]
    vals = np.array([float(c["value"]) for c in real], dtype=float)
    n = len(real)
    hits = np.empty(n_trials, dtype=int)
    for t in range(n_trials):
        perm = rng.permutation(n)
        shuffled = [{**real[i], "value": float(vals[perm[i]])} for i in range(n)]
        pairs = pairwise_ratios(shuffled, tol_cents)
        hits[t] = _count_countable_hits(pairs)
    return hits


def filter_for_hits(pairs: list[PairwiseRatio], constants: list[dict]) -> list[PairwiseRatio]:
    """Hide watchlist + derived rows from hit counts.

    `derived=True` rows (e.g. ratio_LNDirac) are present in the CSV for
    narrative but their pair-ratios against any other constant are dropped
    here to avoid double-counting. Watchlist rows are kept OPTIONALLY
    excluded -- the caller decides.
    """
    derived_names = {c["name"] for c in constants if c.get("derived", False)}
    out = []
    for p in pairs:
        if p.a_name in derived_names or p.b_name in derived_names:
            continue
        out.append(p)
    return out


def _count_countable_hits(pairs: list[PairwiseRatio]) -> int:
    return sum(1 for p in pairs if p.within_tol)


def hit_rate(pairs: list[PairwiseRatio]) -> float:
    if not pairs:
        return 0.0
    return _count_countable_hits(pairs) / len(pairs)


def interpret(real_all_pairs: list[PairwiseRatio],
              filtered_pairs: list[PairwiseRatio],
              null_decade: np.ndarray,
              null_perm: np.ndarray,
              tol_cents: float) -> list[str]:
    """Honest framing. NEVER ends with 'therefore X'. Always qty+control+qty."""
    n_all = len(real_all_pairs)
    n_filt = len(filtered_pairs)
    hits_all = _count_countable_hits(real_all_pairs)
    hits_filt = _count_countable_hits(filtered_pairs)
    rate_all = hits_all / max(n_all, 1)
    rate_filt = hits_filt / max(n_filt, 1)

    notes: list[str] = [
        f"Real constants -- all pairs: {hits_all}/{n_all} diatonic hits within "
        f"{tol_cents:.0f} cents ({rate_all*100:.2f}%).",
        f"Real constants -- excluding watchlist (Dirac/Eddington/cosmic/lepton ladder): "
        f"{hits_filt}/{n_filt} hits ({rate_filt*100:.2f}%). "
        f"This is the bar the p-values below are judged against -- the watchlist is "
        f"what motivated the search, so hits there are biased to inflate.",
        "",
        f"Null A (log-uniform-within-decade, {len(null_decade)} trials): "
        f"mean {null_decade.mean():.2f} std {null_decade.std():.2f} "
        f"50th {np.percentile(null_decade, 50):.1f} "
        f"95th {np.percentile(null_decade, 95):.1f} "
        f"99th {np.percentile(null_decade, 99):.1f} "
        f"max {null_decade.max()}.",
        f"Null B (pair-permutation, {len(null_perm)} trials): "
        f"mean {null_perm.mean():.2f} std {null_perm.std():.2f} "
        f"50th {np.percentile(null_perm, 50):.1f} "
        f"95th {np.percentile(null_perm, 95):.1f} "
        f"99th {np.percentile(null_perm, 99):.1f} "
        f"max {null_perm.max()}.",
        f"p(decade-null >= filtered-real) = "
        f"{(null_decade >= hits_filt).mean():.4f}.",
        f"p(permutation-null >= filtered-real) = "
        f"{(null_perm >= hits_filt).mean():.4f}.",
        "",
        "INTERPRETATION -- necessary, not sufficient:",
        "  * 'Within 20 cents' is a Hawkins bar, not a sigma bar. Selection bias "
        "    (we hand-picked constants known to have notable ratios) and the "
        "    look-elsewhere effect inflate apparent signal.",
        "  * Small-integer ratios are dense in real space -- many 'almost-perfect' "
        "    hits will be produced by random draws of similar-magnitude numbers.",
        "  * The watchlist test is the strictest bar -- excluded from the hit "
        "    total so the score reflects UN-biased pair-cell structure.",
        "  * Null A tests magnitude structure; Null B tests pairing structure. "
        "    Both must clear for a defensible 'signal above noise' claim.",
        "  * A pass on this probe is a DIRECTION, not a finding.",
    ]
    if hits_filt >= max(np.percentile(null_decade, 95), np.percentile(null_perm, 95)):
        notes.append(
            "  -> Filtered hit rate exceeds the 95th percentile of BOTH nulls. "
            "Reportable as 'above null-model confidence'. INSIDE the lab only, "
            "not as a global claim."
        )
    elif hits_filt >= np.percentile(null_perm, 95):
        notes.append(
            "  -> Filtered hit rate exceeds the permutation null 95th percentile "
            "(specific pair-cells matter) but not the decade null. The pattern "
            "may be a sampling artefact of magnitude structure."
        )
    elif hits_filt >= max(np.percentile(null_decade, 50), np.percentile(null_perm, 50)):
        notes.append(
            "  -> Filtered hit rate sits above the medians of both nulls -- "
            "modest excess at best. Worth a manual review of the top pairs."
        )
    else:
        notes.append(
            "  -> Filtered hit rate is BELOW both null medians. Real pair-cell "
            "diatonic density is BELOW random expectation. Consistent with the "
            "constants being deliberately spread across orders of magnitude."
        )
    return notes


def tol_column_name(tol_cents: float) -> str:
    return f"within_tol_cents_{int(round(tol_cents))}"


def write_feature_table_csv(pairs: list[PairwiseRatio], path: Path,
                             tol_cents: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "a_name", "b_name", "a_symbol", "b_symbol",
        "ratio", "log10_abs", "folded_to_octave",
        "diatonic_note", "diatonic_target", "cents_error",
        tol_column_name(tol_cents),
        "integer_ratio", "integer_pct_error",
        "on_watchlist", "watchlist_reason",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in pairs:
            w.writerow({
                "a_name": p.a_name,
                "b_name": p.b_name,
                "a_symbol": p.a_symbol,
                "b_symbol": p.b_symbol,
                "ratio": f"{p.ratio:.6e}",
                "log10_abs": f"{p.log10_abs:.5f}",
                "folded_to_octave": f"{p.folded_to_octave:.6f}",
                "diatonic_note": p.diatonic_note,
                "diatonic_target": f"{p.diatonic_target:.6f}",
                "cents_error": f"{p.cents_error:.4f}",
                tol_column_name(tol_cents): p.within_tol,
                "integer_ratio": p.integer_ratio,
                "integer_pct_error": f"{p.integer_pct_error:.4f}",
                "on_watchlist": p.on_watchlist,
                "watchlist_reason": p.watchlist_reason,
            })


def _pair_to_dict(p: PairwiseRatio) -> dict:
    return {
        "i": p.i, "j": p.j,
        "a_name": p.a_name, "b_name": p.b_name,
        "a_symbol": p.a_symbol, "b_symbol": p.b_symbol,
        "ratio": p.ratio,
        "log10_abs": round(p.log10_abs, 5),
        "folded_to_octave": round(p.folded_to_octave, 6),
        "diatonic_note": p.diatonic_note,
        "diatonic_target": p.diatonic_target,
        "cents_error": round(p.cents_error, 4),
        "within_tol": p.within_tol,
        "integer_ratio": p.integer_ratio,
        "integer_pct_error": round(p.integer_pct_error, 4),
        "on_watchlist": p.on_watchlist,
        "watchlist_reason": p.watchlist_reason,
    }


def _safe_relpath(p: Path, root: Path) -> str:
    """Like Path.relative_to but works even when one is a partial match."""
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", default="core", help="constant set: core | large")
    ap.add_argument("--trials", type=int, default=1000,
                    help="trials per null model (default 1000)")
    ap.add_argument("--small-control", action="store_true",
                    help="fast iteration: pin n_trials=50 (default 1000) for BOTH nulls")
    ap.add_argument("--tol-cents", type=float, default=20.0,
                    help="diatonic tolerance in cents (default 20.0)")
    ap.add_argument("--seed", type=int, default=20260725, help="RNG seed")
    ap.add_argument("--out", type=Path,
                    default=Path("outputs/constants"),
                    help="output directory (default outputs/constants)")
    args = ap.parse_args()

    if args.small_control:
        args.trials = 50

    constants = get_table(args.set)
    pairs = pairwise_ratios(constants, tol_cents=args.tol_cents)
    filtered = filter_for_hits(pairs, constants)
    M, names = log10_signed_matrix(constants)

    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "feature_table.csv"
    write_feature_table_csv(pairs, csv_path, tol_cents=args.tol_cents)

    null_decade = random_constants_control(
        constants, n_trials=args.trials, tol_cents=args.tol_cents, seed=args.seed
    )
    null_perm = pair_permutation_control(
        constants, n_trials=args.trials, tol_cents=args.tol_cents,
        seed=args.seed + 1
    )

    report = {
        "constant_set": args.set,
        "n_constants_total": len(constants),
        "n_constants_for_hits": len(constants_for_filter(filtered)) if filtered else 0,
        "n_pairs_all": len(pairs),
        "n_pairs_for_hits": len(filtered),
        "tol_cents": args.tol_cents,
        "n_trials": args.trials,
        "seed": args.seed,
        "used_small_control": args.small_control,
        "constants": constants,
        "log10_signed_ratio_matrix": {
            "names": names,
            "matrix": M.round(5).tolist(),
        },
        "top_pairs_by_cents_error": [
            _pair_to_dict(p) for p in sorted(pairs, key=lambda p: abs(p.cents_error))[:8]
        ],
        "all_watchlist_hits": [
            _pair_to_dict(p) for p in pairs if p.on_watchlist
        ],
        "null_decade": {
            "n_trials": int(args.trials),
            "seed": int(args.seed),
            "null_description": (
                "Each constant replaced by a log-uniform sample within its own "
                "order of magnitude (preserves decade, randomises exact value)."
            ),
            "hits_mean": float(null_decade.mean()),
            "hits_std": float(null_decade.std()),
            "hits_p50": float(np.percentile(null_decade, 50)),
            "hits_p95": float(np.percentile(null_decade, 95)),
            "hits_p99": float(np.percentile(null_decade, 99)),
            "hits_max": int(null_decade.max()),
        },
        "null_permutation": {
            "n_trials": int(args.trials),
            "seed": int(args.seed) + 1,
            "null_description": (
                "Real values preserved, identities randomly permuted (reciprocal-"
                "arrangement null). Tests whether the SPECIFIC pair cells matter."
            ),
            "hits_mean": float(null_perm.mean()),
            "hits_std": float(null_perm.std()),
            "hits_p50": float(np.percentile(null_perm, 50)),
            "hits_p95": float(np.percentile(null_perm, 95)),
            "hits_p99": float(np.percentile(null_perm, 99)),
            "hits_max": int(null_perm.max()),
        },
        "interpretation": interpret(pairs, filtered, null_decade, null_perm, args.tol_cents),
    }
    json_path = args.out / "constants_analysis.json"
    json_path.write_text(json.dumps(report, indent=2, default=float))
    md_path = args.out / "constants_notes.md"
    md_path.write_text(_render_markdown(report))

    print(f"Wrote {_safe_relpath(csv_path, ROOT)}  ({len(pairs)} pairs, {len(filtered)} countable)")
    print(f"Wrote {_safe_relpath(json_path, ROOT)}")
    print(f"Wrote {_safe_relpath(md_path, ROOT)}")
    print()
    print(f"Real (all):       {sum(1 for p in pairs if p.within_tol)}/{len(pairs)} diatonic hits within {args.tol_cents:.0f} cents")
    print(f"Real (excl. watch): {sum(1 for p in filtered if p.within_tol)}/{len(filtered)} diatonic hits")
    nd = report["null_decade"]; np_ = report["null_permutation"]
    print(f"Null A (decade):   mean {nd['hits_mean']:.2f}  95p {nd['hits_p95']:.1f}  99p {nd['hits_p99']:.1f}  max {nd['hits_max']}")
    print(f"Null B (perm):     mean {np_['hits_mean']:.2f}  95p {np_['hits_p95']:.1f}  99p {np_['hits_p99']:.1f}  max {np_['hits_max']}")
    return 0


def constants_for_filter(filtered_pairs: list[PairwiseRatio]) -> list[str]:
    """Names of constants actually used by the filtered pair list."""
    out: list[str] = []
    seen: set[str] = set()
    for p in filtered_pairs:
        for nm in (p.a_name, p.b_name):
            if nm not in seen:
                seen.add(nm); out.append(nm)
    return out


def _render_markdown(report: dict) -> str:
    lines = [
        "# Hermes / N3 -- Dimensionless Constants Pattern Hunt",
        "",
        f"Constant set: `{report['constant_set']}` "
        f"({report['n_constants_total']} total constants, "
        f"{report['n_constants_for_hits']} after dropping derived rows, "
        f"{report['n_pairs_for_hits']}/{report['n_pairs_all']} hit-countable pairs)  ",
        f"Diatonic tolerance: +/- {report['tol_cents']:.0f} cents (Hawkins bar)  ",
        f"Trials per null: **{report['n_trials']}**  "
        f"Seed: {report['seed']}  "
        f"{'(small-control=ON)' if report.get('used_small_control') else ''}",
        "",
        "## Top 8 pairs by |cents error|",
        "",
        "| a | b | ratio | log10 | nearest diatonic | cents | hit? | int ratio |",
        "|---|---|------:|------:|------------------|------:|:----:|-----------|",
    ]
    for p in report["top_pairs_by_cents_error"]:
        hit = "YES" if p["within_tol"] else "."
        int_r = p["integer_ratio"]
        if p["integer_pct_error"] and abs(p["integer_pct_error"]) < INT_RATIO_BOLD_PCT:
            int_r = f"**{int_r}**"
        lines.append(
            f"| {p['a_symbol']} | {p['b_symbol']} | {p['ratio']:.4g} | "
            f"{p['log10_abs']:.3f} | {p['diatonic_note']} | {p['cents_error']:+.2f} | "
            f"{hit} | {int_r} |"
        )
    if report["all_watchlist_hits"]:
        lines += ["", "## Famous coincidences (watchlist -- TAINTED by selection bias)",
                  "",
                  "These pairs are the famous coincidences Dirac / Eddington / cosmic / "
                  "lepton ladder. They are EXCLUDED from the headline hit-total so the "
                  "p-value below is not a self-fulfilling score.", ""]
        for p in report["all_watchlist_hits"]:
            hit = "YES" if p["within_tol"] else "."
            lines.append(
                f"- **{p['a_symbol']} / {p['b_symbol']}**: {p['watchlist_reason']}  "
                f"`ratio={p['ratio']:.4g}` `log10={p['log10_abs']:.3f}` "
                f"`cents={p['cents_error']:+.2f}` `{hit}`"
            )
    lines += [
        "",
        "## Negative controls (mandatory per ROADMAP_BEYOND_WHEAT.md)",
        "",
        "Two nulls, two different questions:",
        "",
    ]
    for key, label in (
        ("null_decade", "Null A -- log-uniform within decade"),
        ("null_permutation", "Null B -- pair-permutation (reciprocal-arrangement)"),
    ):
        rc = report[key]
        lines += [
            f"**{label}**",
            f"- Trials: **{rc['n_trials']}** (seed {rc['seed']})",
            f"- {rc['null_description']}",
            f"- Hits per random trial -- mean `{rc['hits_mean']:.2f}` std `{rc['hits_std']:.2f}` "
            f"50th `{rc['hits_p50']:.1f}` 95th `{rc['hits_p95']:.1f}` 99th `{rc['hits_p99']:.1f}` "
            f"max `{rc['hits_max']}`",
            "",
        ]
    if report["interpretation"]:
        lines += ["## Interpretation", ""]
        for n in report["interpretation"]:
            lines.append(n if n else "")
    lines += [
        "",
        "---",
        "",
        "*Generated by `tools/astro/constants_probe.py` -- Hermes mission N3.*  ",
        "*Stance: structure is not a message. A 20-cent hit is necessary, not sufficient.*",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

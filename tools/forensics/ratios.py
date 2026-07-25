"""
ratios.py -- Diatonic-scale and Hawkins-theorem ratio analysis for crop formations.

Computational recreation of Gerald S. Hawkins' crop-circle work (Science News, 1996;
The Mathematics Teacher, 1995). Hawkins measured the diameters and areas of circles and
rings in multi-circle formations and reported that:

  * In 11 of 18 patterns the ratios matched small-whole-number "diatonic" ratios --
    the frequency ratios of the notes of the diatonic (white-key) musical scale.
  * Several patterns embodied four Euclidean theorems (plus a general fifth) relating
    the areas of a regular polygon's circumscribed and inscribed circles -- theorems
    Hawkins could not locate in Euclid or any modern text.

Measurement conventions (per Hawkins / cropcirclesecrets.org):
  * Two "spaced" / satellite circles  -> ratio of interest = large_diameter / small_diameter
  * Two concentric circles            -> ratio of interest = outer_area / inner_area
                                          ( = (outer_diameter / inner_diameter) ** 2 )

Pure standard library -- no third-party dependencies. Validated in tests/test_ratios.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import log2, pi, sqrt

# --- Diatonic just-intonation major scale, one octave [1, 2] --------------------
#     do        re         mi        fa         sol       la        ti          do
DIATONIC = {
    "unison (1:1)":      Fraction(1, 1),
    "major 2nd (9:8)":   Fraction(9, 8),
    "major 3rd (5:4)":   Fraction(5, 4),
    "perfect 4th (4:3)": Fraction(4, 3),
    "perfect 5th (3:2)": Fraction(3, 2),
    "major 6th (5:3)":   Fraction(5, 3),
    "major 7th (15:8)":  Fraction(15, 8),
    "octave (2:1)":      Fraction(2, 1),
}

# Hawkins polygon AREA-ratio theorems: circumscribed_area / inscribed_area.
# Thm II triangle 4:1, Thm III square 2:1, Thm IV hexagon 4:3.
# Note each is itself a diatonic interval: 4:1 = two octaves, 2:1 = octave,
# 4:3 = perfect fourth -- which is precisely why Hawkins linked geometry to music.
HAWKINS_AREA_RATIOS = {
    "triangle (Thm II, 4:1)": 4.0,
    "square (Thm III, 2:1)":  2.0,
    "hexagon (Thm IV, 4:3)":  4.0 / 3.0,
}

# Thm I: for three equal circles centred on the corners of an equilateral triangle,
# the diameter of the circle through those three centres : corner-circle diameter = 4:3.
HAWKINS_THEOREM_I_DIAM_RATIO = 4.0 / 3.0

# Irrational constants for the "beyond-diatonic" hunt the Captain asked for.
CONSTANTS = {
    "phi (golden ratio)": (1 + sqrt(5)) / 2,
    "sqrt(2)": sqrt(2),
    "sqrt(3)": sqrt(3),
    "pi": pi,
    "pi/2": pi / 2,
    "e": 2.718281828459045,
}


def cents(r_measured: float, r_target: float) -> float:
    """Interval error in cents (1200 cents == one octave)."""
    return 1200.0 * log2(r_measured / r_target)


def reduce_to_octave(r: float) -> float:
    """Fold a positive ratio into the pitch-class range [1, 2)."""
    if r <= 0:
        raise ValueError("ratio must be positive")
    while r >= 2.0:
        r /= 2.0
    while r < 1.0:
        r *= 2.0
    return r


@dataclass
class DiatonicMatch:
    measured: float
    folded: float
    note: str
    target: float
    cents_error: float
    within_tol: bool


def nearest_diatonic(ratio: float, tol_cents: float = 20.0) -> DiatonicMatch:
    """Fold `ratio` into an octave and return the closest diatonic note.

    tol_cents ~= 20 (about 1.2 %) is a sane field-measurement bar: a semitone is
    100 cents, so 20 cents means "this genuinely is that interval," not a coincidence.
    """
    folded = reduce_to_octave(ratio)
    name, frac = min(DIATONIC.items(),
                     key=lambda kv: abs(cents(folded, float(kv[1]))))
    err = cents(folded, float(frac))
    return DiatonicMatch(ratio, folded, name, float(frac), err, abs(err) <= tol_cents)


@dataclass
class IntegerRatioMatch:
    measured: float
    fraction: Fraction
    approx: float
    pct_error: float


def nearest_small_integer_ratio(ratio: float, max_denominator: int = 12) -> IntegerRatioMatch:
    """Closest small whole-number ratio p:q (Hawkins emphasised small integers)."""
    fr = Fraction(ratio).limit_denominator(max_denominator)
    approx = float(fr)
    pct = 100.0 * (ratio - approx) / approx if approx else float("inf")
    return IntegerRatioMatch(ratio, fr, approx, pct)


def classify_polygon_area_ratio(area_ratio: float, tol_pct: float = 3.0):
    """Test a circumscribed:inscribed AREA ratio against Hawkins' polygon theorems.

    Returns a list of (name, target, pct_error, within_tol) sorted best-first.
    """
    out = []
    for name, target in HAWKINS_AREA_RATIOS.items():
        pct = 100.0 * abs(area_ratio - target) / target
        out.append((name, target, pct, pct <= tol_pct))
    out.sort(key=lambda t: t[2])
    return out


def hunt_constants(ratio: float, tol_pct: float = 2.0):
    """Compare a ratio against phi, sqrt(2), sqrt(3), pi, ... Returns sorted matches."""
    results = []
    for name, val in CONSTANTS.items():
        pct = 100.0 * abs(ratio - val) / val
        results.append((name, val, pct, pct <= tol_pct))
    results.sort(key=lambda t: t[2])
    return results


def analyze_pair(large: float, small: float, kind: str = "diameter",
                 tol_cents: float = 20.0) -> dict:
    """Full analysis of a circle pair.

    kind='diameter' for spaced/satellite circles (ratio = large/small diameter);
    kind='area'     for concentric circles     (ratio = outer/inner area).
    """
    if kind not in ("diameter", "area"):
        raise ValueError("kind must be 'diameter' or 'area'")
    ratio = large / small
    result = {
        "kind": kind,
        "ratio": ratio,
        "diatonic": nearest_diatonic(ratio, tol_cents),
        "integer_ratio": nearest_small_integer_ratio(ratio),
        "constants": hunt_constants(ratio),
    }
    if kind == "area":
        result["polygon_theorem"] = classify_polygon_area_ratio(ratio)
    return result


if __name__ == "__main__":
    demo = [
        ("Perfect fourth 4:3 (Hawkins Thm I diam ratio)", 4 / 3, "diameter"),
        ("Perfect fifth 3:2", 3 / 2, "diameter"),
        ("Two octaves folded (8:3)", 8 / 3, "diameter"),
        ("Equilateral triangle circ:insc area (Thm II)", 4.0, "area"),
        ("Square circ:insc area (Thm III)", 2.0, "area"),
        ("Hexagon circ:insc area (Thm IV)", 4 / 3, "area"),
        ("Golden ratio", 1.6180339, "diameter"),
    ]
    for label, r, kind in demo:
        res = analyze_pair(r, 1.0, kind=kind)
        d = res["diatonic"]
        print(f"\n{label}: ratio={r:.5f} ({kind})")
        print(f"  diatonic -> {d.note:20s} err {d.cents_error:+6.1f} cents"
              f" [{'MATCH' if d.within_tol else 'no'}]")
        ir = res["integer_ratio"]
        print(f"  integer  -> {ir.fraction} ({ir.pct_error:+.2f} %)")
        if kind == "area":
            top = res["polygon_theorem"][0]
            print(f"  Hawkins  -> {top[0]} ({top[2]:.2f} %) [{'MATCH' if top[3] else 'no'}]")

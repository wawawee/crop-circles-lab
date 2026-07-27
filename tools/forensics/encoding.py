"""
encoding.py -- decoders / verifiers for the "message" crop formations.
Thin wrapper over bitstream.py for shared bit primitives.

Ground-truth compiled from primary sources (Wikipedia Arecibo message; Paul Vigay's
Chilbolton analysis; plus.maths.org and the Gazette & Herald on Barbury pi;
Skeptical Inquirer / Rod Dickinson on the Stonehenge Julia Set; Red Collie /
cropcircleconnector on Crabwood).

IMPORTANT scope note: we do NOT re-read the field pixels here (that needs the aerial
image + preprocess/geometry). Instead we implement the *decoding logic* and the
*arithmetic verifiers*, and reproduce the published decodes so each is runnable and
self-checking. Every disputed reading is surfaced explicitly, not smoothed over.

Validated in tests/test_encoding.py.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

try:
    from .bitstream import text_to_bits as _bs_text_to_bits, bits_to_text as _bs_bits_to_text
    from .bitstream import semiprime_dims as _bs_semiprime_dims
except ImportError:
    from bitstream import text_to_bits as _bs_text_to_bits, bits_to_text as _bs_bits_to_text
    from bitstream import semiprime_dims as _bs_semiprime_dims


# =============================================================================
# 1. BARBURY CASTLE "PI"  (Wiltshire, 1 June 2008)
# =============================================================================
# A ratcheted spiral divided into ten 36-degree sectors. Reading from the centre
# outward, each arc spans a whole number of sectors = one digit; a small circle
# after the first digit marks the decimal point. Decoded by Michael Reed.
BARBURY_PI_SECTORS = [3, 1, 4, 1, 5, 9, 2, 6, 5, 4]
PI_10_SIG_FIGURES = "3.141592654"   # note the 10th digit is *rounded up* from ...653589


def decode_pi_spiral(sector_counts, decimal_after: int = 1) -> str:
    """Reconstruct the encoded number from successive 36-degree sector counts.
    A decimal point follows `decimal_after` digits (the central dot)."""
    digits = [str(int(d)) for d in sector_counts]
    return "".join(digits[:decimal_after]) + "." + "".join(digits[decimal_after:])


def verify_barbury_pi() -> dict:
    decoded = decode_pi_spiral(BARBURY_PI_SECTORS)          # "3.141592654"
    value = float(decoded)
    pi_rounded_9dp = round(math.pi, 9)                      # 3.141592654
    pi_truncated_9dp = math.floor(math.pi * 1e9) / 1e9      # 3.141592653
    return {
        "decoded": decoded,
        "value": value,
        "matches_pi_rounded": value == pi_rounded_9dp,
        "tenth_digit_rounded_up": value == pi_rounded_9dp and value != pi_truncated_9dp,
        "decoder": "Michael Reed (retired astrophysicist), 2008",
    }


# =============================================================================
# 2. CRABWOOD "ALIEN FACE + DISC"  (near Winchester, 15 Aug 2002)
# =============================================================================
# The disc encodes text in 8-bit ASCII, spiralling counter-clockwise from the
# centre outward, ~151 characters. We implement a general codec and reproduce the
# published decode; the field bitstream itself requires the aerial image to read.
CRABWOOD_REDCOLLIE = ("Beware the bearers of FALSE gifts & their BROKEN PROMISES. "
                      "Much PAIN but still time. BELIEVE. There is GOOD out there. "
                      "We OPpose DECEPTION. COnduit CLOSING\\")
CRABWOOD_VIGAY = ("Beware the bearers of FALSE gifts & their BROKEN PROMISES. "
                  "Much PAIN but still time. EELRIJUE. There is GOOD out there. "
                  "We oppose DECEPTION. Conduit CLOSING (bell)")

CRABWOOD_AMBIGUITIES = {
    "disputed_word": {
        "vigay_1st_decode": "EELRIJUE",
        "red_collie_redecode": "BELIEVE",
        "note": "physically corrupted / bit-inserted region; both cited in primary literature",
    },
    "terminal_char": {
        "red_collie": r"\ (0x5C backslash)",
        "vigay": "bell sound (ASCII BEL 0x07)",
        "gver": "final period 0x2E (argues the 'bell' is a mis-decoded full stop)",
    },
    "false_capitalisation": "e.g. OPpose, COnduit -- deliberate high-bit flips (011x->010x); "
                            "Red Collie argues a second hidden layer",
    "read_direction": "counter-clockwise from centre outward (like a CD), 8 bits/char",
}


def text_to_bits(text: str, msb_first: bool = True) -> str:
    return _bs_text_to_bits(text, nbits=8, msb_first=msb_first)


def bits_to_text(bits: str, msb_first: bool = True) -> str:
    return _bs_bits_to_text(bits, nbits=8, msb_first=msb_first)


def decode_crabwood(variant: str = "red_collie") -> dict:
    text = CRABWOOD_REDCOLLIE if variant == "red_collie" else CRABWOOD_VIGAY
    return {
        "text": text,
        "char_count": len(text),
        "bit_count_8bit": len(text) * 8,
        "ambiguities": CRABWOOD_AMBIGUITIES,
    }


# =============================================================================
# 3. ARECIBO 1974 + CHILBOLTON "REPLY" 2001
# =============================================================================
ARECIBO_ROWS, ARECIBO_COLS = 73, 23
ARECIBO_BITS = 1679                                   # semiprime 23 x 73
ARECIBO_FREQ_HZ = 2.380e9                             # transmit frequency
# canonical first rows (reference/documentation only -- not pixel-verified here)
ARECIBO_FIRST_ROWS = [
    "00000010101010000000000",
    "00101000001010000000100",
    "10001000100010010110010",
    "10101010101010100100100",
    "00000000000000000000001",
]
DNA_ELEMENTS = {"H": 1, "C": 6, "N": 7, "O": 8, "P": 15}
CHILBOLTON_ADDED_ELEMENT = {"Si": 14}                 # silicon inserted in the reply


def wavelength_cm() -> float:
    """Message length unit = transmit wavelength = c / f."""
    return 3.0e8 / ARECIBO_FREQ_HZ * 100.0            # ~12.605 cm


def decode_length_units(units: int) -> dict:
    cm = units * wavelength_cm()
    return {"units": units, "cm": cm, "m": cm / 100.0, "feet": cm / 30.48}


def verify_arecibo_semiprime() -> dict:
    dims = _bs_semiprime_dims(ARECIBO_BITS)
    both_prime = any(r == ARECIBO_COLS and c == ARECIBO_ROWS and p for r, c, p in dims)
    return {
        "bits": ARECIBO_BITS,
        "factors": (ARECIBO_COLS, ARECIBO_ROWS),
        "product_ok": ARECIBO_COLS * ARECIBO_ROWS == ARECIBO_BITS,
        "both_prime": both_prime,
    }


CHILBOLTON_DIFF = {
    "grid": "73 x 23 = 1679 bits (unchanged)",
    "numbers_1_to_10": "unchanged",
    "elements": {"original": ["H(1)", "C(6)", "N(7)", "O(8)", "P(15)"],
                 "reply_adds": "Si(14)"},
    "helix": {"original": "double", "reply": "triple"},
    "figure_height_units": {"original": 14, "reply": 8},
    "population": {"original": "~4.29 billion", "reply": "~21.3 billion"},
    "solar_system": {"original": "Earth (3rd planet) offset",
                     "reply": "planets 3, 4 and 5 flagged; 5th emphasised"},
    "transmitter": {"original": "Arecibo dish (2430 units ~ 1000 ft)",
                    "reply": "depiction of the 2000 Chilbolton 'nested rings' formation"},
    "figure": {"original": "human stick figure", "reply": "large-headed 'grey' figure"},
}


def verify_chilbolton_reply() -> dict:
    return {
        "silicon_atomic_number": CHILBOLTON_ADDED_ELEMENT["Si"],
        "helix_change": "double -> triple",
        "height_original": decode_length_units(14),      # ~176 cm
        "height_reply": decode_length_units(8),          # ~101 cm
        "telescope_diameter": decode_length_units(2430), # ~1000 ft
        "diff": CHILBOLTON_DIFF,
    }


# =============================================================================
# 4. 1996 STONEHENGE "JULIA SET" -- true fractal, or spiral of circles?
# =============================================================================
def generate_log_spiral_circles(n: int = 150, r0: float = 100.0, shrink: float = 0.975,
                                a: float = 2.0, b: float = 0.16, dtheta: float = 0.45):
    """Synthetic model of the 1996 formation: ~150 circles whose radii shrink
    geometrically, centres marching along a logarithmic spiral."""
    circles, r, theta = [], r0, 0.0
    for _ in range(n):
        rc = a * math.exp(b * theta)
        circles.append((rc * math.cos(theta), rc * math.sin(theta), r))
        r *= shrink
        theta += dtheta
    return circles


def is_true_julia_set(circles, cv_threshold: float = 0.15) -> dict:
    """Classify a finite set of (x, y, radius) circles.

    A true Julia set {z : iterating z->z^2+c stays bounded} is an infinitely
    detailed fractal boundary, NOT a finite set of discs -- so any finite circle
    list is, by definition, at most an *approximation*. We additionally report
    whether the radii shrink like a single-resolution logarithmic spiral.
    """
    radii = [c[2] for c in circles]
    ratios = [radii[i + 1] / radii[i] for i in range(len(radii) - 1) if radii[i] > 0]
    mean = statistics.fmean(ratios) if ratios else float("nan")
    cv = (statistics.pstdev(ratios) / mean) if ratios and mean else float("inf")
    log_spiral = (cv < cv_threshold) and (mean < 1.0)
    return {
        "n_circles": len(circles),
        "radius_ratio_mean": mean,
        "radius_ratio_cv": cv,
        "is_true_julia_set": False,
        "classification": ("julia-set-inspired log-spiral (single-resolution)"
                           if log_spiral else "irregular finite circle set"),
        "reason": ("A finite set of flattened circles cannot be a true z^2+c Julia set "
                   "(an infinitely detailed fractal boundary). The 1996 Stonehenge "
                   "formation is ~149-151 circles whose radii shrink geometrically along "
                   "a logarithmic spiral -- a human-constructable visual approximation "
                   "(Rod Dickinson confessed to making it overnight in ~2h45m)."),
    }


if __name__ == "__main__":
    print("=== Barbury Castle Pi (2008) ===")
    print(" ", verify_barbury_pi())
    print("\n=== Crabwood disc (2002) ===")
    cw = decode_crabwood()
    print("  text:", cw["text"])
    print("  chars:", cw["char_count"], " bits:", cw["bit_count_8bit"])
    print("  disputed word:", cw["ambiguities"]["disputed_word"])
    print("\n=== Arecibo / Chilbolton ===")
    print(" ", verify_arecibo_semiprime())
    ch = verify_chilbolton_reply()
    print("  height original: %.1f cm  reply: %.1f cm  telescope: %.0f ft"
          % (ch["height_original"]["cm"], ch["height_reply"]["cm"],
             ch["telescope_diameter"]["feet"]))
    print("\n=== 1996 Stonehenge 'Julia Set' ===")
    js = is_true_julia_set(generate_log_spiral_circles())
    print("  is_true_julia_set:", js["is_true_julia_set"],
          "| classification:", js["classification"],
          "| ratio cv: %.3f" % js["radius_ratio_cv"])

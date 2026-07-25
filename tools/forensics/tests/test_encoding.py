"""Validation for encoding.py -- run: python3 tools/forensics/tests/test_encoding.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import encoding as E  # noqa: E402


# --- Barbury Pi ---------------------------------------------------------------
def test_pi_decoder():
    assert E.decode_pi_spiral([3, 1, 4, 1, 5, 9, 2, 6, 5, 4]) == "3.141592654"


def test_barbury_pi_rounding():
    v = E.verify_barbury_pi()
    assert v["decoded"] == "3.141592654"
    assert v["value"] == round(math.pi, 9)
    assert v["tenth_digit_rounded_up"] is True


# --- Crabwood ASCII -----------------------------------------------------------
def test_ascii_single_byte():
    assert E.bits_to_text("01000010") == "B"
    assert E.bits_to_text("00100110") == "&"


def test_ascii_roundtrip():
    sample = "Beware the bearers of FALSE gifts & their BROKEN PROMISES."
    assert E.bits_to_text(E.text_to_bits(sample)) == sample


def test_crabwood_message_roundtrip():
    # full canonical decode survives encode->decode (incl. caps, punctuation, backslash)
    assert E.bits_to_text(E.text_to_bits(E.CRABWOOD_REDCOLLIE)) == E.CRABWOOD_REDCOLLIE


def test_crabwood_ambiguities_present():
    a = E.decode_crabwood()["ambiguities"]
    assert a["disputed_word"]["vigay_1st_decode"] == "EELRIJUE"
    assert a["disputed_word"]["red_collie_redecode"] == "BELIEVE"


# --- Arecibo / Chilbolton -----------------------------------------------------
def test_arecibo_semiprime():
    v = E.verify_arecibo_semiprime()
    assert v["product_ok"] and v["both_prime"]
    assert 23 * 73 == 1679


def test_arecibo_height_units():
    assert abs(E.decode_length_units(14)["cm"] - 176.5) < 1.0
    assert abs(E.decode_length_units(8)["cm"] - 100.8) < 1.0


def test_arecibo_telescope_diameter():
    assert abs(E.decode_length_units(2430)["feet"] - 1000.0) < 10.0


def test_chilbolton_diff():
    v = E.verify_chilbolton_reply()
    assert v["silicon_atomic_number"] == 14
    assert v["diff"]["helix"]["reply"] == "triple"
    assert v["diff"]["figure_height_units"]["reply"] == 8


# --- Julia set ----------------------------------------------------------------
def test_julia_not_true():
    js = E.is_true_julia_set(E.generate_log_spiral_circles(n=150))
    assert js["is_true_julia_set"] is False
    assert "log-spiral" in js["classification"]
    assert js["radius_ratio_cv"] < 0.15


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); ok += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} passed")
    sys.exit(0 if ok == len(fns) else 1)

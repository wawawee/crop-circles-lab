"""Known-answer tests for tools/forensics/bitstream.py.
Run: python tools/forensics/tests/test_bitstream.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bitstream as B  # noqa: E402


def test_text_bits_roundtrip_8():
    for msb in (True, False):
        s = "Beware the FALSE gifts."
        assert B.bits_to_text(B.text_to_bits(s, 8, msb), 8, msb) == s


def test_text_bits_roundtrip_7():
    s = "PI=3.14"
    assert B.bits_to_text(B.text_to_bits(s, 7, True), 7, True) == s


def test_flatten_row():
    g = [[0, 1, 2], [3, 4, 5]]
    assert B.flatten(g, "row") == [0, 1, 2, 3, 4, 5]
    assert B.flatten(g, "col") == [0, 3, 1, 4, 2, 5]
    assert B.flatten(g, "boustrophedon") == [0, 1, 2, 5, 4, 3]


def test_spiral_cw():
    g = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    assert B.flatten(g, "spiral_cw") == [0, 1, 2, 5, 8, 7, 6, 3, 4]


def test_spiral_ccw_is_permutation():
    g = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    assert sorted(B.flatten(g, "spiral_ccw")) == list(range(9))
    assert B.flatten(g, "spiral_ccw")[0] == 0  # starts top-left


def test_ber():
    assert B.ber("0000", "0000") == 0.0
    assert B.ber("0000", "1111") == 1.0
    assert B.ber("0011", "0101") == 0.5


def test_semiprime_1679():
    dims = B.semiprime_dims(1679)
    assert (23, 73, True) in dims          # the Arecibo grid, both prime
    assert all(r > 1 for (r, _, _) in dims)


def test_ioc():
    assert B.index_of_coincidence("aaaaaa") == 1.0
    assert B.index_of_coincidence("abcdefghij") < 0.15   # all distinct -> low


def test_scan_recovers_hidden_message():
    msg = "HELLO WORLD"
    bits = B.text_to_bits(msg, 8, True)
    cols = 8
    grid = [[int(b) for b in bits[i:i + cols]] for i in range(0, len(bits), cols)]
    best = B.scan(grid, reference_text=msg)[0]
    assert best["ber"] == 0.0
    assert best["order"] == "row" and best["nbits"] == 8 and best["msb_first"]
    assert msg in best["preview"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    ok = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}"); ok += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{ok}/{len(fns)} passed")
    sys.exit(0 if ok == len(fns) else 1)

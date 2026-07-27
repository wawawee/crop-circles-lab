"""Known-answer tests for tools/signal (multiplex heritage)."""

from __future__ import annotations

from tools.signal.bitstream_probe import (
    MULTIPLEX_L20,
    analyze,
    shannon_entropy_bits,
    bit_balance,
    lz76_count,
)


def test_all_zeros_low_entropy():
    h = shannon_entropy_bits("0" * 64)
    assert h == 0.0


def test_alternating_maxish():
    bits = "01" * 64
    h = shannon_entropy_bits(bits)
    assert h > 0.99
    assert bit_balance(bits) < 0.01


def test_multiplex_l20_near_max_entropy():
    """Reproduces the Dec 2025 Weeks finding: entropy ≈ 1, balance tight."""
    m = analyze(MULTIPLEX_L20)
    assert m["n_bits"] == 87
    assert m["shannon_entropy"] > 0.95
    assert m["bit_balance_abs"] < 0.08
    assert any("entropy" in line.lower() or "balance" in line.lower() for line in m["interpretation"])


def test_lz_repeats_fewer_phrases_than_random():
    rep = ("01" * 8) * 8  # highly periodic
    rnd = "10010110011010100101101001100101101001011010010110010110"
    assert lz76_count(rep) < lz76_count(rnd)


def test_ascii_hello():
    # "Hi" = 01001000 01101001
    bits = "0100100001101001"
    m = analyze(bits)
    assert "Hi" in m["ascii_msb"]["preview"]


def main() -> None:
    tests = [
        test_all_zeros_low_entropy,
        test_alternating_maxish,
        test_multiplex_l20_near_max_entropy,
        test_lz_repeats_fewer_phrases_than_random,
        test_ascii_hello,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(failed)


if __name__ == "__main__":
    main()

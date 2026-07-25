"""Known-answer tests for tools/forensics/messages.py.
Run: python tools/forensics/tests/test_messages.py

These verify CODEC correctness + reference well-formedness, NOT that field pixels
decode to these strings (they don't, at web resolution — see crabwood_b1_notes).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import messages as M  # noqa: E402


def test_pi_from_sectors():
    assert M.pi_from_sectors() == "3.141592654"


def test_all_ascii_entries_roundtrip():
    for k, e in M.REGISTRY.items():
        if e["ascii"]:
            assert M.codec_roundtrip_ok(e["plaintext"]), k


def test_all_ascii_entries_are_pure_ascii():
    for k, e in M.REGISTRY.items():
        if e["ascii"]:
            assert M.is_pure_ascii(e["plaintext"]), k


def test_registry_has_confidence_and_source():
    for k, e in M.REGISTRY.items():
        assert e.get("confidence") and e.get("source"), k


def test_expected_random_ber_near_half():
    ber = M.expected_random_ber(M.REGISTRY["crabwood-2002"]["plaintext"])
    assert 0.42 <= ber <= 0.58, ber   # random vs plaintext ~ 0.5 (the honest floor)


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

"""
messages.py — reference registry + codec verifiers for the "message" formations.

IMPORTANT honesty boundary: this module verifies that OUR codec round-trips the
PUBLISHED / REPORTED plaintexts (i.e. our bit<->text is correct and the reference
strings are well-formed ASCII). It does NOT claim the field pixels decode to these
strings. Independent field decode is a separate, resolution-limited problem — e.g.
the Crabwood web-res disc bottoms out at BER ~= 0.50 vs the plaintext, which is
statistically indistinguishable from noise (see outputs/crabwood_b1_notes.md).

Each entry carries an explicit `confidence` and `source`. Uses tools/forensics/
bitstream.py for all bit work. Validated in tools/forensics/tests/test_messages.py.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bitstream as bs  # noqa: E402


# Reported / published decodes. confidence: verified > published > reported > uncertain.
REGISTRY = {
    "barbury-pi-2008": {
        "scheme": "pi ratchet-spiral, 10 x 36-degree sectors -> digits",
        "plaintext": "3.141592654",
        "ascii": False,
        "confidence": "verified",
        "source": "Michael Reed; plus.maths.org (2008)",
    },
    "crabwood-2002": {
        "scheme": "8-bit ASCII, spiral CCW from centre",
        "plaintext": ("Beware the bearers of FALSE gifts & their BROKEN PROMISES. "
                      "Much PAIN but still time. BELIEVE. There is GOOD out there. "
                      "We OPpose DECEPTION. COnduit CLOSING\\"),
        "ascii": True,
        "confidence": "published (Vigay / Red Collie); disputed word (EELRIJUE/BELIEVE) + terminal",
        "source": "Paul Vigay 2002; Red Collie / cropcircleconnector",
    },
    "wilton-windmill-2010": {
        "scheme": "8-bit ASCII around a 12-segment ring",
        "plaintext": "e^(i*pi)+1=0",
        "ascii": True,
        "confidence": "reported; a debated 'h'/Planck-looking glyph; exact field bytes UNVERIFIED",
        "source": "widely reported 2010; ASCII reading of the ring",
    },
    "poirino-2011": {
        "scheme": "8-bit ASCII around a heptagram ring",
        "plaintext": "Ea Enki",
        "ascii": True,
        "confidence": "reported",
        "source": "Poirino/Turin 2011 coverage",
    },
    "poirino-2010": {
        "scheme": "ASCII (decimal/8-bit as reported)",
        "plaintext": "E=mc2",
        "ascii": True,
        "confidence": "reported / uncertain (sources vary on exact string)",
        "source": "Poirino/Turin 2010 coverage",
    },
}

PI_SECTORS = [3, 1, 4, 1, 5, 9, 2, 6, 5, 4]


def pi_from_sectors(sectors=PI_SECTORS, decimal_after=1):
    d = [str(int(x)) for x in sectors]
    return "".join(d[:decimal_after]) + "." + "".join(d[decimal_after:])


def codec_roundtrip_ok(text, nbits=8, msb_first=True):
    """Our bit<->text codec must reproduce the text exactly (codec correctness)."""
    return bs.bits_to_text(bs.text_to_bits(text, nbits, msb_first), nbits, msb_first) == text


def is_pure_ascii(text):
    return all(ord(c) < 128 for c in text)


def expected_random_ber(text, seed=0, nbits=8):
    """BER of a seeded random bitstream vs the plaintext bits — should sit ~0.5.

    This is the honest yardstick for a failed field decode: the Crabwood web-res
    disc lands at ~0.50 vs this plaintext, i.e. no better than random noise.
    """
    import random
    ref = bs.text_to_bits(text, nbits, True)
    rng = random.Random(seed)
    rnd = "".join(rng.choice("01") for _ in range(len(ref)))
    return bs.ber(rnd, ref)


def verify_registry():
    out = {}
    for k, e in REGISTRY.items():
        row = {"confidence": e["confidence"]}
        if e["ascii"]:
            row["codec_roundtrip"] = codec_roundtrip_ok(e["plaintext"])
            row["pure_ascii"] = is_pure_ascii(e["plaintext"])
            row["n_chars"] = len(e["plaintext"])
            row["n_bits_8"] = len(e["plaintext"]) * 8
        else:
            row["note"] = "non-ASCII scheme (digits/geometry)"
        out[k] = row
    return out


if __name__ == "__main__":
    import json
    print("pi from sectors:", pi_from_sectors())
    print(json.dumps(verify_registry(), indent=2))
    print("Crabwood expected random-vs-plaintext BER: %.3f (web-res disc measured ~0.50)"
          % expected_random_ber(REGISTRY["crabwood-2002"]["plaintext"]))

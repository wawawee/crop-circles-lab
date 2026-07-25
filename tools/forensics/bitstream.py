"""
bitstream.py — reusable bit-grid / bitstream primitives for the message formations.

The formation-specific samplers (tools/ccat/crabwood_bits.py, chilbolton_grid.py)
each reinvent reading-order + BER + decode logic. This module centralises the
*pure* primitives so there is ONE tested implementation to call:

  * flatten / read_bits    — grid -> ordered cells in a chosen reading order
                             (row, col, boustrophedon/snake, spiral CW/CCW)
  * text_to_bits / bits_to_text  — n-bit ASCII either bit order
  * ber                    — bit error rate between two bitstrings
  * semiprime_dims         — factor a bit-count into candidate grid shapes
                             (the Arecibo 1679 = 23x73 insight, generalised)
  * index_of_coincidence   — classic IC, for cipher/структure screening
  * scan                   — try every (order x n-bit x MSB/LSB x polarity),
                             score by printable fraction or BER vs a reference.
                             Honest sweep: on a real formation we EXPECT it to
                             fail to find plaintext — that failure is the result.

Pure standard library; numpy accepted but not required. "Beyond wheat": works on
any binary grid / bitstream. Validated in tools/forensics/tests/test_bitstream.py.
"""
from __future__ import annotations

from collections import Counter

READING_ORDERS = ("row", "row_rev", "col", "col_rev", "boustrophedon",
                  "spiral_cw", "spiral_ccw")


# --- grid normalisation ---------------------------------------------------------
def _as_rows(grid):
    """Accept list-of-lists or a 2D numpy array -> list of lists of ints."""
    try:
        import numpy as np
        if isinstance(grid, np.ndarray):
            return [[int(v) for v in row] for row in grid.tolist()]
    except Exception:
        pass
    return [[int(v) for v in row] for row in grid]


# --- reading orders -------------------------------------------------------------
def _spiral_indices(r, c, cw=True):
    top, bottom, left, right = 0, r - 1, 0, c - 1
    out = []
    if cw:
        while top <= bottom and left <= right:
            for j in range(left, right + 1): out.append((top, j))
            top += 1
            for i in range(top, bottom + 1): out.append((i, right))
            right -= 1
            if top <= bottom:
                for j in range(right, left - 1, -1): out.append((bottom, j))
                bottom -= 1
            if left <= right:
                for i in range(bottom, top - 1, -1): out.append((i, left))
                left += 1
    else:  # counter-clockwise, start top-left going down
        while top <= bottom and left <= right:
            for i in range(top, bottom + 1): out.append((i, left))
            left += 1
            for j in range(left, right + 1): out.append((bottom, j))
            bottom -= 1
            if left <= right:
                for i in range(bottom, top - 1, -1): out.append((i, right))
                right -= 1
            if top <= bottom:
                for j in range(right, left - 1, -1): out.append((top, j))
                top += 1
    return out


def flatten(grid, order="row"):
    """Return grid cell values as a flat list in the given reading order."""
    rows = _as_rows(grid)
    r, c = len(rows), len(rows[0]) if rows else 0
    if order == "row":
        return [rows[i][j] for i in range(r) for j in range(c)]
    if order == "row_rev":
        return [rows[i][j] for i in range(r) for j in range(c - 1, -1, -1)]
    if order == "col":
        return [rows[i][j] for j in range(c) for i in range(r)]
    if order == "col_rev":
        return [rows[i][j] for j in range(c) for i in range(r - 1, -1, -1)]
    if order == "boustrophedon":
        out = []
        for i in range(r):
            cols = range(c) if i % 2 == 0 else range(c - 1, -1, -1)
            out.extend(rows[i][j] for j in cols)
        return out
    if order in ("spiral_cw", "spiral_ccw"):
        idx = _spiral_indices(r, c, cw=(order == "spiral_cw"))
        return [rows[i][j] for (i, j) in idx]
    raise ValueError(f"unknown order: {order}")


def read_bits(grid, order="row"):
    return "".join("1" if v else "0" for v in flatten(grid, order))


# --- bit <-> text ---------------------------------------------------------------
def text_to_bits(text, nbits=8, msb_first=True):
    out = []
    for ch in text:
        b = format(ord(ch) & ((1 << nbits) - 1), f"0{nbits}b")
        out.append(b if msb_first else b[::-1])
    return "".join(out)


def bits_to_text(bits, nbits=8, msb_first=True):
    bits = "".join(str(bits).split())
    chars = []
    for i in range(0, (len(bits) // nbits) * nbits, nbits):
        chunk = bits[i:i + nbits]
        if not msb_first:
            chunk = chunk[::-1]
        chars.append(chr(int(chunk, 2)))
    return "".join(chars)


def printable_fraction(text):
    if not text:
        return 0.0
    ok = sum(1 for ch in text if 32 <= ord(ch) < 127 or ch in "\n\t")
    return ok / len(text)


# --- metrics --------------------------------------------------------------------
def ber(a, b):
    """Bit error rate over the overlapping length (raises if either empty)."""
    a = "".join(str(a).split()); b = "".join(str(b).split())
    n = min(len(a), len(b))
    if n == 0:
        raise ValueError("empty bitstring")
    diff = sum(1 for i in range(n) if a[i] != b[i])
    return diff / n


def semiprime_dims(n, max_pairs=64):
    """Factor n into candidate grid shapes (r, c, both_prime) with 1 < r <= c.

    The Arecibo message is 1679 bits = 23 x 73 (a semiprime), which is *why* the
    grid shape is unambiguous. This generalises that: given a bit-count, what
    rectangular arrangements are possible, and is any a clean semiprime?
    """
    def _isprime(k):
        if k < 2:
            return False
        i = 2
        while i * i <= k:
            if k % i == 0:
                return False
            i += 1
        return True

    out = []
    r = 2
    while r * r <= n and len(out) < max_pairs:
        if n % r == 0:
            c = n // r
            out.append((r, c, _isprime(r) and _isprime(c)))
        r += 1
    return out


def index_of_coincidence(symbols):
    """Classic IC: probability two random picks are equal. ~1/alphabet for
    uniform noise; ~0.066 for English; 1.0 for a single repeated symbol."""
    s = list(symbols)
    N = len(s)
    if N < 2:
        return 0.0
    counts = Counter(s)
    return sum(v * (v - 1) for v in counts.values()) / (N * (N - 1))


# --- honest multi-order sweep ---------------------------------------------------
def scan(grid_or_bits, reference_text=None, nbits_options=(7, 8),
         orders=READING_ORDERS, msb_options=(True, False), try_polarity=True,
         top=8):
    """Try every (order x n-bit x MSB/LSB x polarity), decode to text, and rank.

    If reference_text is given, rank ascending by BER vs the reference's bits
    (same n-bit/order used to encode the reference); else rank descending by
    printable fraction. Returns the top candidates. Expectation on real
    formation data: nothing lands near a real message — that is the finding.
    """
    if isinstance(grid_or_bits, str):
        base_variants = {"asis": grid_or_bits}
        grid = None
    else:
        grid = grid_or_bits
        base_variants = None

    results = []
    order_list = orders if grid is not None else ("asis",)
    for order in order_list:
        bits0 = base_variants["asis"] if grid is None else read_bits(grid, order)
        polarities = {"normal": bits0}
        if try_polarity:
            polarities["inverted"] = "".join("1" if b == "0" else "0" for b in bits0)
        for pol, bits in polarities.items():
            for nbits in nbits_options:
                for msb in msb_options:
                    text = bits_to_text(bits, nbits=nbits, msb_first=msb)
                    entry = {
                        "order": order, "polarity": pol, "nbits": nbits,
                        "msb_first": msb, "printable": round(printable_fraction(text), 3),
                        "ioc": round(index_of_coincidence(text), 4),
                        "preview": text[:48],
                    }
                    if reference_text is not None:
                        ref_bits = text_to_bits(reference_text, nbits=nbits, msb_first=msb)
                        try:
                            entry["ber"] = round(ber(bits, ref_bits), 4)
                        except ValueError:
                            entry["ber"] = 1.0
                    results.append(entry)

    if reference_text is not None:
        results.sort(key=lambda e: e["ber"])
    else:
        results.sort(key=lambda e: e["printable"], reverse=True)
    return results[:top]


if __name__ == "__main__":
    import json
    # demo: hide "HELLO WORLD" row-major 8-bit, then let scan find it
    msg = "HELLO WORLD"
    bits = text_to_bits(msg, 8, True)
    cols = 8
    rows = [[int(b) for b in bits[i:i + cols]] for i in range(0, len(bits), cols)]
    best = scan(rows, reference_text=msg)[0]
    print("hidden-message recovery demo:", json.dumps(best))
    print("Arecibo bit-count 1679 ->", semiprime_dims(1679))

"""Signal / stego / bitstream probes — message hunting, not crop-or-aliens.

Ported and slimmed from the Jeremy Weeks multiplex lab (Dec 2025) and the
covid19-genomic-dsp Shannon/FFT toolkit. Use on:
  - recovered bitstrings (Crabwood, Chilbolton, puzzle dumps)
  - image LSB planes / bitplanes
  - any suspected encoded payload (human or otherwise)

Stance: high entropy + perfect balance often means crypto/compression/test
pattern — interesting either way. Report metrics; don't claim authors.
"""

from __future__ import annotations

__all__ = ["bitstream_probe", "lsb_probe", "window_entropy"]

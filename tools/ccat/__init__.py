"""CCAT — Crop Circle Analysis Toolkit (local foil-hat lab).

Optional dependency imports (sklearn, matplotlib) are wrapped in try/except
so the package loads when they are not installed. Other submodules use
only stdlib / numpy (available) and raise a clean ModuleNotFoundError if
something is truly missing.
"""

from .ccat import analyze_image, batch_analyze

try:
    from .circle_cluster import cluster_circles
except ModuleNotFoundError:
    cluster_circles = None  # needs scikit-learn

try:
    from .dashboard import render_dashboard
except ModuleNotFoundError:
    render_dashboard = None  # needs matplotlib

from .exif_probe import extract_exiftool, exiftool_available
from .julia_compare import PRESETS, julia_set, save_preset
from .swirl import dominant_swirl

__all__ = [
    "analyze_image",
    "batch_analyze",
    "cluster_circles",
    "render_dashboard",
    "extract_exiftool",
    "exiftool_available",
    "julia_set",
    "save_preset",
    "PRESETS",
    "dominant_swirl",
]

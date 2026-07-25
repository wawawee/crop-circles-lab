"""CCAT — Crop Circle Analysis Toolkit (local foil-hat lab)."""

from .ccat import analyze_image, batch_analyze
from .circle_cluster import cluster_circles
from .dashboard import render_dashboard
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

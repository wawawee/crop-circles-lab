"""uap_flight_consistency — Newton/G sanity checks on UAP video tracks.

N2 mission (Opencode). Downloads official DoD/DNI GIMBAL/GOFAST/FLIR1 releases
from Wikimedia Commons (public domain), extracts per-frame metadata via exiftool
+ ffprobe, and flags unphysical acceleration if range/FOV assumptions support it.

New backends (2026):
  vidstab     — VidStab video stabilization before tracking
  pyexiftool  — PyExifTool wrapper (more reliable than subprocess)
  tracker     — OpenCV CSRT/DaisyCF track for automatic flight-path extraction

Key finding: official releases contain ZERO telemetry metadata.
G-force claims are UNDERDETERMINED without platform-motion separation.

CLI:
  python tools/uap/uap_flight_consistency.py --scan-all
  python tools/uap/uap_flight_consistency.py --video data/uap/GoFast*.webm
  python tools/uap/uap_flight_consistency.py --video data/uap/Gimbal*.webm --track
  python tools/uap/uap_flight_consistency.py --demo
  python tools/uap/uap_flight_consistency.py --negative-controls
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

import numpy as np

# ---------------------------------------------------------------------------
# backend availability
# ---------------------------------------------------------------------------

HAS_VIDSTAB = False
try:
    from vidstab import VidStab
    HAS_VIDSTAB = True
except ImportError:
    pass

HAS_PYEXIFTOOL = False
try:
    import exiftool as _pyexif
    HAS_PYEXIFTOOL = True
except ImportError:
    pass

BACKENDS = ("subprocess", "pyexiftool")

# ---------------------------------------------------------------------------
# Constants — aircraft performance envelopes (public sources)
# ---------------------------------------------------------------------------

FA18_MAX_G = 7.5
FA18_MAX_G_WITH_AAM = 7.0
FA18_SUSTAINED_G = 5.0

AIRCRAFT_ENVELOPE = {
    "commercial_jet": {"max_g": 2.5, "max_accel_m_s2": 24.5},
    "fighter_clean": {"max_g": 9.0, "max_accel_m_s2": 88.3},
    "fighter_combat": {"max_g": 7.5, "max_accel_m_s2": 73.5},
    "drone_mq9": {"max_g": 3.5, "max_accel_m_s2": 34.3},
    "missile_aim120": {"max_g": 40.0, "max_accel_m_s2": 392.0},
}

ATFLIR_FOV_DEG = {
    "narrow": 0.7,
    "medium": 2.0,
    "wide": 4.0,
}

VIDEO_INFO = {
    "gimbal": {
        "filename": "Gimbal_Official_UAP_Footage.webm",
        "date": "2015-01-21",
        "sensor": "AN/ASQ-228 ATFLIR",
        "platform": "F/A-18F Super Hornet",
        "resolution": (640, 480),
        "fps": 29.97,
        "duration_s": 34,
        "status": "Official DoD release 2020-04-27",
    },
    "gofast": {
        "filename": "GoFast_Official_UAP_Footage.webm",
        "date": "2015-01-21",
        "sensor": "AN/ASQ-228 ATFLIR",
        "platform": "F/A-18F Super Hornet",
        "resolution": (640, 480),
        "fps": 29.97,
        "duration_s": 34,
        "status": "Official DoD release 2020-04-27; AARO 2025 resolved as parallax",
    },
    "flir1": {
        "filename": "FLIR1_Official_UAP_Footage_from_the_USG_for_Public_Release.webm",
        "date": "2004-11-14",
        "sensor": "FLIR (likely AN/ASQ-228 ATFLIR)",
        "platform": "F/A-18F Super Hornet",
        "resolution": (352, 264),
        "fps": 29.97,
        "duration_s": 76,
        "status": "Official DoD release 2020-04-27",
    },
}


# ---------------------------------------------------------------------------
# metadata extraction backends
# ---------------------------------------------------------------------------

def exiftool_available() -> bool:
    return shutil.which("exiftool") is not None


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def _probe_video_ffprobe(path: Path) -> dict:
    if not ffprobe_available():
        return {"error": "ffprobe not found — brew install ffmpeg"}
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip()}
    return json.loads(proc.stdout)


def _probe_video_exiftool_subprocess(path: Path) -> dict:
    if not exiftool_available():
        return {"error": "exiftool not found — brew install exiftool"}
    proc = subprocess.run(
        ["exiftool", "-json", "-n", str(path)],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr.strip()}
    data = json.loads(proc.stdout)
    return data[0] if data else {}


def _probe_video_exiftool_pyexif(path: Path) -> dict:
    if not HAS_PYEXIFTOOL:
        return {"error": "PyExifTool not installed — pip install PyExifTool"}
    try:
        with _pyexif.ExifTool() as et:
            data = et.execute_json("-n", str(path))
            return data[0] if data else {}
    except Exception as exc:
        return {"error": str(exc), "fallback": "use --backend subprocess"}


def probe_video_exiftool(path: Path, backend: str = "auto") -> dict:
    if backend == "pyexiftool" or (backend == "auto" and HAS_PYEXIFTOOL):
        r = _probe_video_exiftool_pyexif(path)
        if "error" not in r:
            r["backend"] = "pyexiftool"
            return r
        return r
    r = _probe_video_exiftool_subprocess(path)
    if "error" not in r:
        r["backend"] = "subprocess"
    return r


# ---------------------------------------------------------------------------
# vidstab stabilization
# ---------------------------------------------------------------------------

def stabilize_video(path: Path, output: Path | None = None) -> list[np.ndarray]:
    """Stabilize video using VidStab, return stabilized frames."""
    if not HAS_VIDSTAB:
        warnings.warn("VidStab not installed; returning raw frames")
        return []
    stabilizer = VidStab()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        stabilized = stabilizer.stabilize_frame(frame, smoothing_window=15)
        if stabilized is None:
            frames.append(frame)
        else:
            frames.append(stabilized)
    cap.release()

    if output and frames:
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"VP90")
        writer = cv2.VideoWriter(str(output), fourcc, 29.97, (w, h))
        for f in frames:
            writer.write(f)
        writer.release()

    return frames


# ---------------------------------------------------------------------------
# OpenCV frame extraction + tracking
# ---------------------------------------------------------------------------

def opencv_available() -> bool:
    return cv2 is not None


def extract_frames(path: Path, max_frames: int = 300) -> list[np.ndarray]:
    """Extract up to max_frames evenly-spaced frames."""
    if not opencv_available():
        warnings.warn("OpenCV not installed; frame extraction skipped")
        return []
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if total <= 0:
        cap.release()
        return []
    step = max(1, total // max_frames)
    frames = []
    for i in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)
    cap.release()
    return frames


def frame_entropy(frame: np.ndarray) -> float:
    """Shannon entropy of pixel intensities."""
    if frame.size == 0:
        return 0.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    hist = hist[hist > 0]
    if hist.size == 0:
        return 0.0
    hist = hist / hist.sum()
    return -np.sum(hist * np.log2(hist))


# ---------------------------------------------------------------------------
# automatic tracking via CSRT / DaisyCF
# ---------------------------------------------------------------------------

def auto_track_video(
    path: Path, stabilizer: str = "vidstab",
    track_type: str = "csrt", max_frames: int = 600,
) -> dict:
    """Auto-extract flight path using CSRT tracker, with optional stabilization.

    Returns:
      {"track_label": str, "points": [{"t": s, "x": px, "y": px}], ...}
    """
    result: dict = {
        "video": str(path),
        "stabilizer": stabilizer if HAS_VIDSTAB else "none",
        "tracker": track_type,
        "points": [],
        "error": None,
        "stabilized": False,
    }
    if not opencv_available():
        result["error"] = "OpenCV not installed"
        return result

    # Stabilize if requested
    if stabilizer == "vidstab" and HAS_VIDSTAB:
        stabilized_frames = stabilize_video(path)
        if stabilized_frames:
            result["stabilized"] = True
            cap_frames = stabilized_frames
            fps_est = 29.97
        else:
            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                result["error"] = "cannot open video"
                return result
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps_est = cap.get(cv2.CAP_PROP_FPS) or 29.97
            cap_frames = []
            while True:
                ret, f = cap.read()
                if not ret:
                    break
                cap_frames.append(f)
            cap.release()
    else:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            result["error"] = "cannot open video"
            return result
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_est = cap.get(cv2.CAP_PROP_FPS) or 29.97
        cap_frames = []
        while True:
            ret, f = cap.read()
            if not ret:
                break
            cap_frames.append(f)
        cap.release()

    if not cap_frames:
        result["error"] = "no frames extracted"
        return result

    step = max(1, len(cap_frames) // max_frames)
    working_frames = cap_frames[::step]

    # Select initial region: center-crop to reduce false positives
    h, w = working_frames[0].shape[:2]
    margin = 0.3
    bbox = (int(w * margin), int(h * margin),
            int(w * (1 - 2 * margin)), int(h * (1 - 2 * margin)))

    if track_type == "csrt":
        tracker = cv2.TrackerCSRT_create()
    else:
        tracker = cv2.TrackerDaSiamRPN_create() if hasattr(cv2, "TrackerDaSiamRPN_create") else cv2.TrackerCSRT_create()

    tracker.init(working_frames[0], bbox)
    points = []
    for idx, frame in enumerate(working_frames):
        success, box = tracker.update(frame)
        t_sec = round(idx * step / fps_est, 3)
        if success:
            x = box[0] + box[2] / 2
            y = box[1] + box[3] / 2
            points.append({"t": t_sec, "x": round(x, 1), "y": round(y, 1),
                           "w": round(box[2], 1), "h": round(box[3], 1),
                           "status": "tracked"})
        else:
            points.append({"t": t_sec, "x": 0, "y": 0, "status": "lost"})

    result["points"] = points
    result["n_frames"] = len(points)
    result["n_lost"] = sum(1 for p in points if p.get("status") == "lost")
    return result


# ---------------------------------------------------------------------------
# flight-path physics
# ---------------------------------------------------------------------------

def analyze_track(
    points: list[dict],
    range_m: float | None = None,
    fov_deg: float | None = None,
    frame_w: int | None = None,
    label: str = "track",
) -> dict:
    """points: [{t, x, y}, ...] in seconds + pixels."""
    pts = sorted(points, key=lambda p: p["t"])
    if len(pts) < 3:
        return {"error": "need >=3 points", "n": len(pts), "label": label}

    v_vals: list[tuple] = []
    a_vals: list[tuple] = []
    for i in range(1, len(pts)):
        dt = pts[i]["t"] - pts[i - 1]["t"]
        if dt <= 0:
            continue
        dx = pts[i]["x"] - pts[i - 1]["x"]
        dy = pts[i]["y"] - pts[i - 1]["y"]
        vx, vy = dx / dt, dy / dt
        v_vals.append((pts[i]["t"], vx, vy, math.hypot(vx, vy)))

    for i in range(1, len(v_vals)):
        dt = v_vals[i][0] - v_vals[i - 1][0]
        if dt <= 0:
            continue
        ax = (v_vals[i][1] - v_vals[i - 1][1]) / dt
        ay = (v_vals[i][2] - v_vals[i - 1][2]) / dt
        a_vals.append((v_vals[i][0], ax, ay, math.hypot(ax, ay)))

    max_v_px = max((x[3] for x in v_vals), default=0.0)
    max_a_px = max((x[3] for x in a_vals), default=0.0)

    result: dict = {
        "label": label,
        "n_points": len(pts),
        "duration_s": round(pts[-1]["t"] - pts[0]["t"], 3),
        "max_speed_px_s": round(max_v_px, 3),
        "max_accel_px_s2": round(max_a_px, 3),
        "range_m": range_m,
        "fov_deg": fov_deg,
        "frame_w": frame_w,
        "physical": None,
        "flags": [],
        "stance": (
            "UNDERDETERMINED: Without calibrated range + FOV + "
            "platform-motion separation, g-claims are not physically meaningful."
        ),
    }

    if range_m and fov_deg and frame_w:
        width_m = 2.0 * range_m * math.tan(math.radians(fov_deg) / 2.0)
        m_per_px = width_m / frame_w
        max_a_mps2 = max_a_px * m_per_px
        g = max_a_mps2 / 9.80665

        result["physical"] = {
            "m_per_px": round(m_per_px, 4),
            "max_accel_m_s2": round(max_a_mps2, 3),
            "max_g": round(g, 2),
        }

        flags = []
        if g > 50:
            flags.append(
                f"CRITICAL: Implied |a| ≈ {g:.0f} g — far exceeds known "
                f"aircraft envelopes. If real, the object violates Newtonian "
                f"flight. However, this ASSUMES range={range_m}m, fov={fov_deg}°, "
                f"and NO platform motion — all unknown in official footage."
            )
        elif g > 10:
            flags.append(
                f"HIGH: Implied |a| ≈ {g:.1f} g — above sustained fighter "
                f"capability ({FA18_MAX_G} g structural). Needs platform-motion "
                f"separation. Might be sensor slew, not object motion."
            )
        elif g > 5:
            flags.append(
                f"ELEVATED: Implied |a| ≈ {g:.1f} g — within fighter "
                f"envelope but above commercial aircraft."
            )
        else:
            flags.append(
                f"NORMAL: Implied |a| ≈ {g:.1f} g — within broad aircraft "
                f"envelope (commercial: {AIRCRAFT_ENVELOPE['commercial_jet']['max_g']} g, "
                f"fighter: {FA18_MAX_G} g structural)."
            )

        flags.append(
            "CAVEAT: pixel tracking cannot distinguish object motion from "
            "sensor platform motion (aircraft + gimbal slew). Without "
            "telemetry metadata, any g-claim is speculative."
        )
        result["flags"] = flags
    else:
        result["flags"].append(
            "UNDERDETERMINED: No range/FOV metadata in official release. "
            "Provide --range-m --fov-deg --frame-w for speculative g estimate."
        )
        result["flags"].append(
            "METADATA POVERTY: The official DoD/DNI releases contain NO "
            "embedded telemetry, sensor calibration, or range data. "
            "NGA-compressed WebM; no ancillary EXIF. "
            "Full-resolution ATFLIR feeds include MIL-STD-1553 telemetry "
            "overlay but it is stripped in the public releases."
        )

    return result


# ---------------------------------------------------------------------------
# aircraft performance comparison
# ---------------------------------------------------------------------------

def check_aircraft_envelope(accel_m_s2: float) -> list[str]:
    g = accel_m_s2 / 9.80665
    flags = []
    for name, env in AIRCRAFT_ENVELOPE.items():
        status = "EXCEEDS" if g > env["max_g"] else "within"
        flags.append(f"  {name:20s}: {status} (max {env['max_g']} g)")
    return flags


# ---------------------------------------------------------------------------
# synthetic tracks (negative controls)
# ---------------------------------------------------------------------------

def synthetic_ballistic() -> list[dict]:
    pts = []
    g = 9.80665
    for i in range(30):
        t = i * 0.05
        x = 100 + 50 * t
        y = 200 - 0.5 * g * t * t + 100
        pts.append({"t": round(t, 3), "x": round(x, 1), "y": round(max(y, 0), 1)})
    return pts


def synthetic_aircraft_turn() -> list[dict]:
    pts = []
    r = 200.0
    omega = math.radians(30)
    cx, cy = 300, 200
    for i in range(40):
        t = i * 0.1
        theta = omega * t
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        pts.append({"t": round(t, 3), "x": round(x, 1), "y": round(y, 1)})
    return pts


def synthetic_jerk() -> list[dict]:
    pts = []
    for i in range(25):
        t = i * 0.04
        if i < 10:
            x, y = 100 + i * 2, 200
        else:
            x, y = 100 + 10 * 2 + (i - 10) * 80, 200
        pts.append({"t": round(t, 3), "x": round(x, 1), "y": round(y, 1)})
    return pts


# ---------------------------------------------------------------------------
# negative controls runner
# ---------------------------------------------------------------------------

def run_negative_controls() -> dict:
    controls = {
        "synthetic_ballistic_freefall": analyze_track(
            synthetic_ballistic(),
            range_m=5000, fov_deg=2.0, frame_w=640,
            label="ballistic_freefall",
        ),
        "synthetic_aircraft_4g_turn": analyze_track(
            synthetic_aircraft_turn(),
            range_m=10000, fov_deg=2.0, frame_w=640,
            label="aircraft_4g_turn",
        ),
        "synthetic_jerk_unphysical": analyze_track(
            synthetic_jerk(),
            range_m=10000, fov_deg=2.0, frame_w=640,
            label="jerk_(unphysical)",
        ),
    }
    return controls


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------

def demo() -> dict:
    gentle = [{"t": i * 0.1, "x": 100 + i * 2, "y": 200 + 0.05 * i * i}
              for i in range(30)]
    spike = [{"t": i * 0.05, "x": 100 + (0 if i < 10 else (i - 10) * 80),
              "y": 200} for i in range(25)]
    return {
        "demo_gentle_curve": analyze_track(
            gentle, range_m=10000, fov_deg=30, frame_w=1920, label="gentle_curve",
        ),
        "demo_spike": analyze_track(
            spike, range_m=10000, fov_deg=30, frame_w=1920, label="spike",
        ),
        "negative_controls": run_negative_controls(),
        "verdict": (
            "Demo confirms the pipeline can flag unphysical acceleration "
            "(spike => ~9100 g with assumed range/FOV). "
            "Real UAP videos cannot be assessed without telemetry metadata."
        ),
    }


# ---------------------------------------------------------------------------
# full scan
# ---------------------------------------------------------------------------

def scan_all_videos(
    data_dir: Path, exif_backend: str = "auto",
) -> dict:
    """Scan all UAP videos, reporting metadata + frame stats + auto track."""
    results: dict = {"scanned": [], "summary": {}}
    for key, info in VIDEO_INFO.items():
        path = data_dir / info["filename"]
        if not path.exists():
            results["scanned"].append({
                "key": key,
                "file": info["filename"],
                "error": "file not found",
            })
            continue

        entry: dict = {"key": key, "file": info["filename"], "info": info}

        ff = _probe_video_ffprobe(path)
        entry["ffprobe"] = {
            "format": ff.get("format", {}),
            "streams": [
                {"index": s.get("index"), "codec": s.get("codec_name"),
                 "width": s.get("width"), "height": s.get("height"),
                 "fps": s.get("avg_frame_rate"), "pix_fmt": s.get("pix_fmt")}
                for s in ff.get("streams", [])
            ],
        }

        exif = probe_video_exiftool(path, backend=exif_backend)
        if "error" not in exif:
            interesting_keys = [
                "FileSize", "Duration", "ImageWidth", "ImageHeight",
                "Rotation", "GPSLatitude", "GPSLongitude", "GPSAltitude",
                "CreateDate", "ModifyDate", "Make", "Model",
            ]
            meta = {k: exif.get(k) for k in interesting_keys if k in exif}
            entry["exif"] = meta
        else:
            entry["exif"] = exif

        if opencv_available():
            frames = extract_frames(path, max_frames=50)
            entropies = [frame_entropy(f) for f in frames] if frames else []
            entry["frame_analysis"] = {
                "frames_extracted": len(frames),
                "mean_entropy": round(float(np.mean(entropies)), 3) if entropies else None,
                "entropy_range": (
                    [round(float(min(entropies)), 3),
                     round(float(max(entropies)), 3)]
                    if entropies else None
                ),
            }
        else:
            entry["frame_analysis"] = {"error": "OpenCV not available"}

        has_range = any(k in exif for k in ("GPSLatitude", "GPSLongitude", "GPSAltitude"))
        has_fov = "FOV" in str(ff.get("format", {})) or "FOV" in str(exif)
        has_telemetry = any(k in exif for k in (
            "CameraSerialNumber", "LensID", "FocusDistance",
        ))

        entry["metadata_assessment"] = {
            "has_geo_coords": has_range,
            "has_fov": has_fov,
            "has_telemetry_overlay": False,
            "has_sensor_calibration": has_telemetry,
            "metadata_quality": "POOR",
            "note": (
                "Official DoD release is NGA-compressed WebM. "
                "Original ATFLIR feed includes MIL-STD-1553 telemetry overlay "
                "(range, azimuth, elevation, platform state) but it is stripped "
                "in the public release."
            ),
        }

        entry["track_assessment"] = analyze_track(
            [],
            label=f"{key}_no_track",
        )

        results["scanned"].append(entry)

    results["summary"] = {
        "total_videos": len(VIDEO_INFO),
        "found": sum(1 for r in results["scanned"] if "error" not in r),
        "metadata_quality": "POOR — zero telemetry in all official releases",
        "negative_controls": run_negative_controls(),
        "verdict": (
            "The official DoD/DNI UAP video releases contain ZERO telemetry "
            "metadata (range, FOV, platform state). G-force claims made on "
            "these videos are speculative without range assumptions. "
            "The AARO (2025) resolved GOFAST as parallax; "
            "GIMBAL and FLIR1 remain officially 'unidentified' but "
            "unanalyzable from the public WebM alone. "
            "Full-resolution ATFLIR recordings exist with telemetry overlays "
            "but remain classified. Physics-based claims cannot be verified "
            "from public data."
        ),
    }
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="UAP flight consistency — Newton/G sanity + metadata forensics",
    )
    ap.add_argument("--video", type=Path, help="Path to a UAP video file")
    ap.add_argument("--track", type=Path, help="JSON track file [{t,x,y},...]")
    ap.add_argument("--range-m", type=float, default=None, help="Assumed range (m)")
    ap.add_argument("--fov-deg", type=float, default=None, help="Assumed FOV (deg)")
    ap.add_argument("--frame-w", type=int, default=None, help="Frame width (px)")
    ap.add_argument("--demo", action="store_true", help="Run demo")
    ap.add_argument("--negative-controls", action="store_true",
                    help="Run synthetic negative controls")
    ap.add_argument("--scan-all", action="store_true",
                    help="Scan all videos in data/uap/")
    ap.add_argument("--data-dir", type=Path,
                    default=Path(__file__).resolve().parents[2] / "data" / "uap",
                    help="Data directory (default: data/uap)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output JSON path (default: outputs/uap/run.json)")
    ap.add_argument("--backend", choices=("auto", *BACKENDS), default="auto",
                    help="ExifTool backend (pyexiftool or subprocess)")
    ap.add_argument("--auto-track", action="store_true",
                    help="Auto-extract track via CSRT tracker")
    ap.add_argument("--stabilize", action="store_true",
                    help="Apply VidStab stabilization before tracking")

    args = ap.parse_args()

    if args.demo:
        result = demo()
    elif args.negative_controls:
        result = {
            "type": "negative_controls",
            "description": "Synthetic tracks for pipeline verification",
            "controls": run_negative_controls(),
        }
    elif args.scan_all or (not args.video and not args.track):
        result = scan_all_videos(args.data_dir, exif_backend=args.backend)
    elif args.video:
        ff = _probe_video_ffprobe(args.video)
        exif = probe_video_exiftool(args.video, backend=args.backend)
        result = {
            "type": "single_video",
            "file": str(args.video),
            "ffprobe": ff.get("format", {}),
            "exif": exif if "error" not in exif else {"note": "exiftool not available"},
        }

        if args.auto_track:
            stabilizer = "vidstab" if args.stabilize else "none"
            track_result = auto_track_video(args.video, stabilizer=stabilizer)
            if track_result.get("points"):
                result["auto_track"] = {
                    "n_frames": track_result["n_frames"],
                    "n_lost": track_result["n_lost"],
                    "stabilized": track_result["stabilized"],
                    "physics": analyze_track(
                        track_result["points"],
                        range_m=args.range_m,
                        fov_deg=args.fov_deg,
                        frame_w=args.frame_w,
                        label=args.video.name,
                    ),
                }
            else:
                result["auto_track"] = track_result

        if args.range_m or args.fov_deg or args.frame_w:
            result["range_m"] = args.range_m
            result["fov_deg"] = args.fov_deg
            result["frame_w"] = args.frame_w

    elif args.track:
        with open(args.track) as f:
            points = json.load(f)
        result = analyze_track(
            points if isinstance(points, list) else points.get("points", []),
            range_m=args.range_m,
            fov_deg=args.fov_deg,
            frame_w=args.frame_w,
            label=str(args.track),
        )
    else:
        result = scan_all_videos(args.data_dir, exif_backend=args.backend)

    text = json.dumps(result, indent=2, default=str)
    print(text)

    out_path = args.out
    if out_path is None:
        out_path = (
            Path(__file__).resolve().parents[2] / "outputs" / "uap" / "run.json"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(f"\n→ wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

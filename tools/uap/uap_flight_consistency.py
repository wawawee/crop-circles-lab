"""uap_flight_consistency — Newton/G sanity checks on tracked image points.

N2 mission (Opencode owns official video acquisition). Scaffold:
  * ingest a CSV of (t_sec, x_px, y_px) or JSON track
  * estimate pixel-accel; flag if implied g >> aircraft regime when range known
  * without range/metadata → report "underdetermined"

CLI:
  python tools/uap/uap_flight_consistency.py --demo
  python tools/uap/uap_flight_consistency.py track.json --range-m 10000 --out outputs/uap/run.json

Does NOT claim aliens. Physics flags only.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def load_track(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "points" in data:
        return data["points"]
    return data


def analyze_track(
    points: list[dict],
    range_m: float | None = None,
    fov_deg: float | None = None,
    frame_w: int | None = None,
) -> dict:
    """points: [{t, x, y}, ...] in seconds + pixels."""
    pts = sorted(points, key=lambda p: p["t"])
    if len(pts) < 3:
        return {"error": "need >=3 points", "n": len(pts)}

    # pixel velocities / accelerations
    v, a = [], []
    for i in range(1, len(pts)):
        dt = pts[i]["t"] - pts[i - 1]["t"]
        if dt <= 0:
            continue
        dx = pts[i]["x"] - pts[i - 1]["x"]
        dy = pts[i]["y"] - pts[i - 1]["y"]
        vx, vy = dx / dt, dy / dt
        v.append((pts[i]["t"], vx, vy, math.hypot(vx, vy)))
    for i in range(1, len(v)):
        dt = v[i][0] - v[i - 1][0]
        if dt <= 0:
            continue
        ax = (v[i][1] - v[i - 1][1]) / dt
        ay = (v[i][2] - v[i - 1][2]) / dt
        a.append((v[i][0], ax, ay, math.hypot(ax, ay)))

    max_a_px = max((x[3] for x in a), default=0.0)
    result = {
        "n_points": len(pts),
        "duration_s": pts[-1]["t"] - pts[0]["t"],
        "max_speed_px_s": round(max((x[3] for x in v), default=0.0), 3),
        "max_accel_px_s2": round(max_a_px, 3),
        "range_m": range_m,
        "fov_deg": fov_deg,
        "physical": None,
        "flags": [],
        "stance": "Without calibrated range + FOV + platform motion, g-claims are underdetermined.",
    }

    if range_m and fov_deg and frame_w:
        # approx m/px at range: width at range spanned by FOV
        width_m = 2 * range_m * math.tan(math.radians(fov_deg) / 2)
        m_per_px = width_m / frame_w
        max_a_mps2 = max_a_px * m_per_px
        g = max_a_mps2 / 9.80665
        result["physical"] = {
            "m_per_px": round(m_per_px, 4),
            "max_accel_m_s2": round(max_a_mps2, 3),
            "max_g": round(g, 2),
        }
        if g > 50:
            result["flags"].append(f"Implied |a| ≈ {g:.0f} g with ASSUMED range/FOV — check platform motion / bad range.")
        elif g > 10:
            result["flags"].append(f"Implied |a| ≈ {g:.1f} g — high for manned craft; still assumption-bound.")
        else:
            result["flags"].append(f"Implied |a| ≈ {g:.1f} g — within broad aircraft envelope under these assumptions.")
    else:
        result["flags"].append("UNDERDETERMINED: provide --range-m --fov-deg --frame-w for g estimate.")

    return result


def demo() -> dict:
    # synthetic: gentle curve (aircraft-like) vs spike
    gentle = [{"t": i * 0.1, "x": 100 + i * 2, "y": 200 + 0.05 * i * i} for i in range(30)]
    spike = [{"t": i * 0.05, "x": 100 + (0 if i < 10 else (i - 10) * 80), "y": 200} for i in range(25)]
    return {
        "gentle_assumed_10km": analyze_track(gentle, range_m=10000, fov_deg=30, frame_w=1920),
        "spike_assumed_10km": analyze_track(spike, range_m=10000, fov_deg=30, frame_w=1920),
        "negative_control": "Compare official UAP track to known jet clip + synthetic ballistic; metadata poverty → no claim.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("track", nargs="?", type=Path)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--range-m", type=float, default=None)
    ap.add_argument("--fov-deg", type=float, default=None)
    ap.add_argument("--frame-w", type=int, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.demo or not args.track:
        result = demo()
    else:
        result = analyze_track(
            load_track(args.track),
            range_m=args.range_m,
            fov_deg=args.fov_deg,
            frame_w=args.frame_w,
        )
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()

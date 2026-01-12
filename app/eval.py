from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import cv2
import numpy as np

from app.main import PrismEngine, PrismConfig


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline PRISM evaluation runner")
    p.add_argument("--video", required=True, help="Path to input video (mp4/avi/etc)")
    p.add_argument(
        "--fps",
        type=float,
        default=None,
        help="Override FPS if video metadata is wrong",
    )
    p.add_argument(
        "--stimulus",
        choices=["none", "cycle"],
        default="cycle",
        help="Stimulus source: cycle colors or none",
    )
    p.add_argument(
        "--hold-seconds",
        type=float,
        default=2.0,
        help="Stimulus hold seconds when using cycle",
    )
    p.add_argument(
        "--out",
        default="eval_results.csv",
        help="Output CSV path",
    )
    p.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Stop after N seconds of video",
    )
    return p.parse_args()


def _bgr_for_screen_color(screen_color: str) -> tuple[int, int, int]:
    c = (screen_color or "").upper()
    if c == "RED":
        return (0, 0, 255)
    if c == "BLUE":
        return (255, 0, 0)
    if c == "GREEN":
        return (0, 255, 0)
    return (255, 255, 255)


def _next_screen_color(screen_color: str) -> str:
    order = ["RED", "BLUE", "GREEN", "WHITE"]
    c = (screen_color or "RED").upper()
    try:
        i = order.index(c)
    except ValueError:
        i = 0
    return order[(i + 1) % len(order)]


def _fallback_forehead(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    fw = int(w * 0.33)
    fh = int(h * 0.20)
    fx = int((w - fw) / 2)
    fy = int(h * 0.30)
    return frame[fy : fy + fh, fx : fx + fw]


def _iter_frames(
    cap: cv2.VideoCapture, max_seconds: Optional[float], fps: float
) -> Iterable[tuple[int, np.ndarray]]:
    idx = 0
    start = time.time()
    while True:
        if max_seconds is not None and (idx / fps) >= max_seconds:
            return
        ok, frame = cap.read()
        if not ok or frame is None:
            return
        yield idx, frame
        idx += 1
        if time.time() - start > 60 * 60:
            return


def _flatten_details(details: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in details.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


def main() -> int:
    args = _parse_args()
    video_path = Path(args.video)
    if not video_path.exists():
        raise SystemExit(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")

    fps = float(args.fps) if args.fps else float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    if fps <= 1.0:
        fps = 30.0

    config = PrismConfig(fps=int(round(fps)))
    engine = PrismEngine(config=config)

    screen_color = "RED"
    last_change_ts = 0.0

    out_path = Path(args.out)

    # Prime headers after first result
    writer: Optional[csv.DictWriter] = None
    out_f = out_path.open("w", newline="")

    try:
        for idx, frame in _iter_frames(cap, args.max_seconds, fps):
            now_ms = (idx / fps) * 1000.0

            if args.stimulus == "cycle":
                if (idx / fps) - last_change_ts >= args.hold_seconds:
                    screen_color = _next_screen_color(screen_color)
                    last_change_ts = idx / fps

            forehead = _fallback_forehead(frame)
            face_img = frame

            result = engine.process_frame(
                forehead_roi=forehead,
                face_img=face_img,
                screen_color=screen_color,
                timestamp_ms=now_ms,
            )

            row: Dict[str, Any] = {
                "frame": idx,
                "t_sec": round(idx / fps, 3),
                "screen_color": screen_color,
                "is_human": result.is_human,
                "confidence": result.confidence,
                "bpm": result.bpm,
                "signal_quality": result.signal_quality,
                "hrv_score": result.hrv_score,
            }
            row.update(_flatten_details(result.details))

            if writer is None:
                fieldnames = list(row.keys())
                writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                writer.writeheader()

            assert writer is not None
            writer.writerow(row)

    finally:
        out_f.close()
        cap.release()

    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

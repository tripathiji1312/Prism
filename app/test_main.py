from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
import os
from typing import Optional, Tuple

import cv2
import numpy as np

try:
    # Works when executed as a module (preferred)
    from app.main import PrismEngine  # type: ignore
except Exception:
    # Works when executed as a script: `uv run app/test_main.py`
    from main import PrismEngine


@dataclass
class TestState:
    screen_color: str = "RED"
    auto_cycle: bool = True
    hold_seconds: float = 2.0
    last_change_ts: float = 0.0
    stimulus_fullscreen: bool = False
    camera_index: int = 0
    video_path: Optional[str] = None


def _bgr_for_screen_color(screen_color: str) -> Tuple[int, int, int]:
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


def _largest_face_rect(faces) -> Optional[Tuple[int, int, int, int]]:
    if faces is None or len(faces) == 0:
        return None
    # faces is usually an ndarray of (x, y, w, h)
    x, y, w, h = max(faces, key=lambda r: int(r[2]) * int(r[3]))
    return int(x), int(y), int(w), int(h)


def _clip_rect(
    x: int, y: int, w: int, h: int, max_w: int, max_h: int
) -> Tuple[int, int, int, int]:
    x = max(0, min(x, max_w - 1))
    y = max(0, min(y, max_h - 1))
    w = max(1, min(w, max_w - x))
    h = max(1, min(h, max_h - y))
    return x, y, w, h


def _forehead_from_face(
    face_rect: Tuple[int, int, int, int], frame_w: int, frame_h: int
) -> Tuple[int, int, int, int]:
    x, y, w, h = face_rect
    # Forehead is roughly the upper-middle band of the face box.
    fx = x + int(0.20 * w)
    fw = int(0.60 * w)
    fy = y + int(0.10 * h)
    fh = int(0.22 * h)
    return _clip_rect(fx, fy, fw, fh, frame_w, frame_h)


def _fallback_forehead(frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
    # Center crop fallback (kept from the original test, but as a rect).
    fw = int(frame_w * 0.33)
    fh = int(frame_h * 0.20)
    fx = int((frame_w - fw) / 2)
    fy = int(frame_h * 0.30)
    return _clip_rect(fx, fy, fw, fh, frame_w, frame_h)


def _draw_label(
    img, text: str, org: Tuple[int, int], color: Tuple[int, int, int]
) -> None:
    cv2.putText(
        img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA
    )
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1, cv2.LINE_AA)


def _paste_letterboxed(
    dst: np.ndarray, src: np.ndarray, x: int, y: int, w: int, h: int
) -> Tuple[int, int, int, int]:
    """Paste src into dst[x:x+w, y:y+h] keeping aspect ratio (letterboxed)."""
    if w <= 0 or h <= 0:
        return x, y, 0, 0
    sh, sw = src.shape[:2]
    if sh <= 0 or sw <= 0:
        return x, y, 0, 0
    scale = min(w / sw, h / sh)
    new_w = max(1, int(sw * scale))
    new_h = max(1, int(sh * scale))
    resized = cv2.resize(src, (new_w, new_h), interpolation=cv2.INTER_AREA)
    ox = x + (w - new_w) // 2
    oy = y + (h - new_h) // 2
    dst[oy : oy + new_h, ox : ox + new_w] = resized
    return ox, oy, new_w, new_h


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PRISM live test harness")
    p.add_argument(
        "--video",
        default=None,
        help="Optional path to a video file to use as input instead of a webcam",
    )
    p.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="Webcam index to use when --video is not provided",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    engine = PrismEngine()
    state = TestState(
        last_change_ts=time.time(),
        camera_index=int(args.camera_index),
        video_path=str(args.video) if args.video else None,
    )

    cascade_path = os.path.join(
        os.path.dirname(cv2.__file__), "data", "haarcascade_frontalface_default.xml"
    )
    face_cascade = cv2.CascadeClassifier(cascade_path)
    eye_cascade_path = os.path.join(
        os.path.dirname(cv2.__file__), "data", "haarcascade_eye.xml"
    )
    eye_cascade = cv2.CascadeClassifier(eye_cascade_path)

    if state.video_path:
        cap = cv2.VideoCapture(state.video_path)
        source_label = f"VIDEO:{os.path.basename(state.video_path)}"
    else:
        cap = cv2.VideoCapture(state.camera_index)
        source_label = f"CAM:{state.camera_index}"

    if not cap.isOpened():
        if state.video_path:
            print(f"Could not open video: {state.video_path}")
        else:
            print(f"Could not open webcam at index {state.camera_index}.")
        return 2

    cv2.namedWindow("Prism Debug", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Prism Debug", 1280, 720)

    print(
        "PRISM Test Harness\n"
        "Keys: q quit | c cycle color | 1 RED | 2 BLUE | 3 GREEN | 4 WHITE | space toggle auto-cycle\n"
        "      f toggle fullscreen | s reset engine buffers\n"
        "HUD: shows rPPG method, quality gate, temporal xcorr\n"
    )

    try:
        fps_last = time.time()
        fps_value = 0.0
        while True:
            now = time.time()

            # Simple FPS estimate
            dt = now - fps_last
            if dt > 0:
                fps_value = 0.9 * fps_value + 0.1 * (1.0 / dt)
            fps_last = now

            # Auto-cycle the stimulus color
            if state.auto_cycle and (now - state.last_change_ts) >= state.hold_seconds:
                state.screen_color = _next_screen_color(state.screen_color)
                state.last_change_ts = now

            ret, frame = cap.read()
            if not ret or frame is None:
                break

            h, w = frame.shape[:2]

            # Face detection -> forehead ROI
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(120, 120)
            )
            face_rect = _largest_face_rect(faces)
            if face_rect is not None:
                x, y, fw, fh = face_rect
                cv2.rectangle(frame, (x, y), (x + fw, y + fh), (120, 255, 120), 2)
                fx, fy, fww, fhh = _forehead_from_face(face_rect, w, h)

                # Eye detection inside face ROI (upper half is usually enough)
                face_gray = gray[y : y + fh, x : x + fw]
                upper = face_gray[0 : max(1, int(0.65 * fh)), :]
                eyes = eye_cascade.detectMultiScale(
                    upper, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )
                for ex, ey, ew, eh in eyes[:4]:
                    cv2.rectangle(
                        frame,
                        (x + ex, y + ey),
                        (x + ex + ew, y + ey + eh),
                        (255, 180, 0),
                        2,
                    )
            else:
                fx, fy, fww, fhh = _fallback_forehead(w, h)
                eyes = []

            cv2.rectangle(frame, (fx, fy), (fx + fww, fy + fhh), (0, 255, 255), 2)
            forehead = frame[fy : fy + fhh, fx : fx + fww]

            # Run the engine with the *current* screen color.
            # IMPORTANT: pass a tight face crop (not the full frame) so anti-screen
            # texture checks don’t get polluted by background regions.
            if face_rect is not None:
                x, y, fw, fh = face_rect
                face_img = frame[y : y + fh, x : x + fw]
            else:
                face_img = frame

            result = engine.process_frame(
                forehead, face_img, state.screen_color, timestamp_ms=now * 1000.0
            )

            # Compose a larger single window with stimulus as the FULL background.
            # This maximizes colored light hitting the face.
            out_h, out_w = 720, 1280
            display = np.zeros((out_h, out_w, 3), dtype=np.uint8)
            display[:] = _bgr_for_screen_color(state.screen_color)

            # Inset camera feed on top of the colored background (letterboxed).
            margin = 18
            cam_x = margin
            cam_y = margin
            cam_w = int(out_w * 0.68)
            cam_h = out_h - 2 * margin
            cv2.rectangle(
                display,
                (cam_x - 2, cam_y - 2),
                (cam_x + cam_w + 2, cam_y + cam_h + 2),
                (30, 30, 30),
                2,
            )
            _paste_letterboxed(display, frame, cam_x, cam_y, cam_w, cam_h)

            # Forehead ROI thumbnail in the bottom-right corner
            roi_h = 220
            roi_w = int(out_w * 0.26)
            roi_x = out_w - roi_w - margin
            roi_y = out_h - roi_h - margin
            cv2.rectangle(
                display,
                (roi_x - 2, roi_y - 2),
                (roi_x + roi_w + 2, roi_y + roi_h + 2),
                (30, 30, 30),
                2,
            )
            if forehead.size > 0:
                roi_thumb = cv2.resize(
                    forehead, (roi_w, roi_h), interpolation=cv2.INTER_AREA
                )
                display[roi_y : roi_y + roi_h, roi_x : roi_x + roi_w] = roi_thumb
            _draw_label(
                display, "FOREHEAD ROI", (roi_x + 8, roi_y + 28), (255, 255, 255)
            )

            # Stimulus label (top-right)
            stim_text_color = (
                (0, 0, 0) if state.screen_color == "WHITE" else (255, 255, 255)
            )
            _draw_label(
                display,
                f"STIMULUS: {state.screen_color}",
                (out_w - int(out_w * 0.30), 48),
                stim_text_color,
            )

            # Overlay metrics
            ok_color = (80, 220, 80)
            bad_color = (40, 40, 255)
            human_color = ok_color if result.is_human else bad_color
            chroma_passed = bool(result.details.get("chroma_passed", False))
            physics_passed = bool(result.details.get("physics_passed", False))
            is_static = bool(result.details.get("is_static_image", True))
            moire = bool(result.details.get("moire_detected", False))
            screen_texture = bool(result.details.get("screen_texture_detected", False))
            texture_score = result.details.get("texture_uniformity", 0)
            bpm_std = result.details.get("bpm_stability_std", 0)
            rppg_method = result.details.get("rppg_method", "GREEN")
            q_gate = result.details.get("quality_gate", True)
            q_reason = result.details.get("quality_gate_reason", "")
            xcorr_delay = result.details.get("temporal_xcorr_delay_ms", 0)
            xcorr_strength = result.details.get("temporal_xcorr_strength", 0)
            xcorr_passed = result.details.get("temporal_xcorr_passed", False)
            eyes_count = 0 if face_rect is None else int(len(eyes))

            _draw_label(
                display,
                f"Src: {source_label} | ScreenColor: {state.screen_color} | Auto: {state.auto_cycle} | Hold: {state.hold_seconds:.1f}s | FPS: {fps_value:.1f}",
                (20, 35),
                (255, 255, 255),
            )
            _draw_label(
                display,
                f"Human: {result.is_human} ({result.confidence}%)",
                (20, 65),
                human_color,
            )
            _draw_label(
                display,
                f"BPM: {result.bpm} | Q: {result.signal_quality:.2f} | HRV Ent: {result.hrv_score:.3f} | BPM_std: {bpm_std}",
                (20, 95),
                (255, 220, 120),
            )
            forced_reason = result.details.get("forced_false_reason", "")
            lighting_unstable = bool(result.details.get("lighting_unstable", False))
            screen_flicker = bool(result.details.get("screen_flicker_detected", False))
            flicker_ratio = result.details.get("screen_flicker_ratio", 0)
            _draw_label(
                display,
                f"Chroma: {chroma_passed} | SSS: {physics_passed} | Moire: {moire} | Static: {is_static} | ScreenTex: {screen_texture} | Flicker: {screen_flicker}",
                (20, 125),
                (200, 200, 200),
            )
            if forced_reason:
                _draw_label(
                    display,
                    f"FORCED FALSE: {forced_reason}",
                    (20, 245),
                    (80, 80, 255),
                )
            _draw_label(
                display,
                f"SSS: {result.details.get('sss_ratio', 0):.3f} | Var%: {result.details.get('signal_variance', 0):.3f} | Texture: {texture_score} | FlickRatio: {flicker_ratio:.2f} | Eyes: {eyes_count}",
                (20, 155),
                (200, 200, 200),
            )
            _draw_label(
                display,
                f"rPPG: {rppg_method} | QGate: {q_gate} ({q_reason}) | XCorr: {xcorr_passed} {xcorr_delay}ms {xcorr_strength}",
                (20, 215),
                (180, 180, 255),
            )

            # Buffer warmup indicator
            buf_len = len(getattr(engine, "green_signal_buffer", []))
            buf_need = getattr(getattr(engine, "config", None), "buffer_size", 150)
            warmup = "WARMUP" if buf_len < buf_need else "READY"
            _draw_label(
                display,
                f"rPPG buffer: {buf_len}/{buf_need} ({warmup})",
                (20, 185),
                (180, 180, 255),
            )

            cv2.imshow("Prism Debug", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("c"):
                state.screen_color = _next_screen_color(state.screen_color)
                state.last_change_ts = time.time()
            if key == ord("1"):
                state.screen_color = "RED"
                state.last_change_ts = time.time()
            if key == ord("2"):
                state.screen_color = "BLUE"
                state.last_change_ts = time.time()
            if key == ord("3"):
                state.screen_color = "GREEN"
                state.last_change_ts = time.time()
            if key == ord("4"):
                state.screen_color = "WHITE"
                state.last_change_ts = time.time()
            if key == ord(" "):
                state.auto_cycle = not state.auto_cycle
                state.last_change_ts = time.time()
            if key == ord("s"):
                engine.reset()
            if key == ord("f"):
                state.stimulus_fullscreen = not state.stimulus_fullscreen
                cv2.setWindowProperty(
                    "Prism Debug",
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN
                    if state.stimulus_fullscreen
                    else cv2.WINDOW_NORMAL,
                )

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

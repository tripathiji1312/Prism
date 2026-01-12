from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.main import PrismConfig, PrismEngine


@dataclass
class SanityResult:
    label: str
    bpm: int
    signal_quality: float
    is_human: bool
    confidence: float
    details: dict


def _make_synthetic_forehead(
    t: float,
    base: tuple[float, float, float],
    amp: float,
    bpm: float,
    stimulus_rgb: tuple[float, float, float],
) -> np.ndarray:
    """Create a solid-color ROI with a weak pulsatile component.

    We model camera BGR values as:
      base + rppg(sine) + stimulus_crosstalk
    """
    pulse = math.sin(2.0 * math.pi * (bpm / 60.0) * t)
    r, g, b = base

    # pulse mostly in green, a bit in red/blue
    r += amp * 0.35 * pulse
    g += amp * 1.00 * pulse
    b += amp * 0.25 * pulse

    # stimulus adds to all channels depending on color
    sr, sg, sb = stimulus_rgb
    r += 18.0 * sr
    g += 18.0 * sg
    b += 18.0 * sb

    rgb = np.clip([r, g, b], 0.0, 255.0).astype(np.uint8)
    roi = np.zeros((80, 120, 3), dtype=np.uint8)
    # ROI is BGR in OpenCV.
    roi[:, :, 0] = rgb[2]
    roi[:, :, 1] = rgb[1]
    roi[:, :, 2] = rgb[0]
    return roi


def _run_case(method: str, enable_gate: bool) -> SanityResult:
    config = PrismConfig(
        fps=30,
        buffer_size=150,
        rppg_method=method,
        enable_quality_gate=enable_gate,
        # Make the gate permissive for synthetic inputs
        max_motion_score=9999.0,
        min_blur_var_laplacian=0.0,
        max_exposure_clip_pct=1.0,
        min_roi_size=10,
        enable_temporal_xcorr=True,
        temporal_xcorr_min_corr=0.05,
        temporal_xcorr_min_lag_ms=50.0,
        temporal_xcorr_max_lag_ms=500.0,
        min_signal_quality=0.10,
        rppg_min_window_seconds=8.0,
    )
    engine = PrismEngine(config=config)

    # 10 seconds synthetic stream.
    bpm_true = 78.0
    base = (120.0, 95.0, 85.0)
    amp = 4.0

    screen_color = "RED"
    for i in range(int(10 * config.fps)):
        t = i / float(config.fps)
        ts_ms = t * 1000.0

        # Color cycle: abrupt switches, 2s hold.
        if i % int(2 * config.fps) == 0:
            screen_color = {
                "RED": "BLUE",
                "BLUE": "GREEN",
                "GREEN": "WHITE",
                "WHITE": "RED",
            }[screen_color]

        stimulus_rgb = engine._rgb_from_screen_color(screen_color)
        roi = _make_synthetic_forehead(t, base, amp, bpm_true, stimulus_rgb)

        # face_img not used heavily in this synthetic run; keep as ROI.
        engine.process_frame(
            forehead_roi=roi,
            face_img=roi,
            screen_color=screen_color,
            timestamp_ms=ts_ms,
        )

    result = engine.process_frame(
        forehead_roi=roi,
        face_img=roi,
        screen_color=screen_color,
        timestamp_ms=(10.0 * 1000.0),
    )

    return SanityResult(
        label=f"method={method} gate={enable_gate}",
        bpm=result.bpm,
        signal_quality=result.signal_quality,
        is_human=result.is_human,
        confidence=result.confidence,
        details=result.details,
    )


def main() -> int:
    print("Running PRISM synthetic sanity checks...")
    for method in ["GREEN", "CHROM", "POS"]:
        for gate in [False, True]:
            res = _run_case(method, gate)
            xcorr = {
                "xcorr_passed": res.details.get("temporal_xcorr_passed"),
                "xcorr_strength": res.details.get("temporal_xcorr_strength"),
                "xcorr_delay_ms": res.details.get("temporal_xcorr_delay_ms"),
            }
            qgate = {
                "passed": res.details.get("roi_quality_gate_passed"),
                "reason": res.details.get("roi_quality_gate_reason"),
            }
            print(
                f"{res.label}: bpm={res.bpm} quality={res.signal_quality} "
                f"is_human={res.is_human} conf={res.confidence} qgate={qgate} xcorr={xcorr}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

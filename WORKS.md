# PRISM Engine v2.x - WORKS / Implementation Notes

**Updated:** Jan 12, 2026

This file captures what changed in the PRISM liveness engine during the latest iteration. It is intended as a practical, engineering-facing changelog for the team.

---

## Summary of Major Changes

- Upgraded rPPG extraction from legacy "mean green" to classical robust methods (`POS` default, plus `CHROM`).
- Added ROI quality gating (motion/blur/exposure) so rPPG/HRV aren’t computed from garbage frames.
- Added temporal cross-correlation (“xcorr”) to validate stimulus→response timing more reliably.
- Added offline evaluation runner (`app/eval.py`) for CSV logging and threshold tuning.
- Updated debug harness (`app/test_main.py`) HUD to show new diagnostics and block reasons.
- Added explicit defenses for phone/screen attacks:
  - **Screen texture hard gate** (forces `is_human=False`).
  - **Screen flicker / refresh detection** in the signal frequency domain.
- Added support to test harness for feeding a **video file as the camera stream** (`--video`).

---

## rPPG (POS/CHROM)

### What changed

- New config: `PrismConfig.rppg_method` with values `GREEN | CHROM | POS`.
- Default is now `POS` (more robust under illumination changes).
- Engine maintains a per-frame mean RGB buffer from the forehead ROI (`rgb_signal_buffer`).

### Why

- Mean-green is prone to illumination artifacts.
- POS/CHROM are proven classical rPPG methods that are substantially more stable for webcams.

### Where

- `app/main.py`
  - `PrismConfig.rppg_method`
  - `PrismEngine._extract_bvp_from_rgb()`
  - `PrismEngine._get_heart_rate()`

---

## ROI Quality Gating

### What changed

- New rule-based gate that computes quick quality features from the forehead ROI:
  - motion score (frame diff)
  - blur variance (Laplacian)
  - exposure clipping fraction
  - ROI size check

- If the gate fails, the engine suppresses rPPG updates for that window.

### Why

- Prevent false BPM/HRV readings from blur/motion/exposure issues.

### Where

- `app/main.py`
  - `PrismEngine._compute_quality_features()`
  - `PrismEngine._quality_gate()`

---

## Temporal Response: XCorr

### What changed

- Added a temporal buffer of stimulus scalar vs. observed response.
- Added cross-correlation scan across lags to estimate:
  - `temporal_xcorr_delay_ms`
  - `temporal_xcorr_strength`
  - `temporal_xcorr_passed`

### Why

- Threshold-crossing temporal delay is brittle; xcorr is more stable and gives a strength metric.

### Where

- `app/main.py`
  - `PrismEngine._check_temporal_response()`

---

## Offline Evaluation Runner

### What changed

- Added `app/eval.py` to run PRISM on a video file and write per-frame results to CSV.

### Why

- Lets us tune thresholds and prove improvements with repeatable data.

### Usage

- `python app/eval.py --video some_clip.mp4 --out eval_results.csv`

---

## Anti-Spoofing: Phone/Screen Replay Fixes

### Problem observed

- AI-generated photos/videos shown on a phone can create strong refresh/flicker artifacts that look like pulse to naive signal processing.

### What changed

1) **Screen texture detection is now a hard gate**
- Texture uniformity check is used as a decisive “screen-like” classifier.
- If `screen_texture_detected=True`, the engine forces `is_human=False`.

2) **Screen flicker detection**
- New check computes frequency-domain ratio of high-frequency power (>5Hz) vs heart-band power (0.75–3Hz).
- Screens tend to spike high-frequency energy due to refresh.

### Where

- `app/main.py`
  - `PrismEngine._check_screen_texture()`
  - `PrismEngine._check_screen_flicker()`
  - Fusion section: forced false when screen texture is detected

---

## Static Image Detection

### What changed

- Static detection is now primarily **low-variance detection**.
- High variance is treated as a separate `lighting_unstable` flag (penalty), not “definitely fake”.

### Why

- Active stimulus + auto-exposure can create large variance on real humans; blocking on that caused false negatives.

---

## Fusion Scoring Updates

### What changed

- More permissive defaults to reduce false negatives in real-world indoor conditions.
- Partial credits / warmup bonuses introduced.
- Decision threshold adjusted to avoid “almost human” cases.

### Important note

- Fusion rules changed meaningfully; if you need a stricter production setting, we should introduce a `mode` (e.g., `"strict"` vs `"demo"`) rather than only changing defaults.

---

## Test Harness Improvements

### What changed

- HUD shows:
  - rPPG method and quality gate status
  - temporal xcorr delay/strength
  - lighting instability
  - screen flicker ratio
  - forced-false reason (when a hard gate trips)

### New input option

- Run test harness with video input:
  - `uv run app/test_main.py --video ai.mp4`

- Or with webcam:
  - `uv run app/test_main.py --camera-index 0`

---

## API / Pipeline (Engineering)

This section describes a practical API-style contract for feeding frames into the engine and receiving results.

### Engine Call (In-Process)

The engine is in-process Python:

- `app/main.py` → `PrismEngine.process_frame(forehead_roi, face_img, screen_color, timestamp_ms)`

Inputs are OpenCV images (`np.ndarray` in BGR) plus the current stimulus color.

### How to Build Engine Inputs

1) Acquire a frame from camera/video (`frame_bgr`).
2) Detect face and compute a forehead ROI (recommended: face mesh landmarks; fallback: face box heuristic).
3) Pass:
- `face_img = frame_bgr`
- `forehead_roi = frame_bgr[y:y+h, x:x+w]`
- `screen_color = "RED" | "GREEN" | "BLUE" | "WHITE"`
- `timestamp_ms = time.time() * 1000.0`

### JSON: Frame Request (Suggested)

If you’re calling PRISM over HTTP/WebSocket, frames must be serialized. Recommended options:
- `image_jpeg_base64` (easy)
- `image_bytes` (binary body)

Example payload:

```json
{
  "session_id": "abc123",
  "timestamp_ms": 1736700000000,
  "screen_color": "RED",
  "image_jpeg_base64": "...",
  "roi": {
    "forehead": {"x": 240, "y": 120, "w": 160, "h": 80},
    "face": {"x": 180, "y": 60, "w": 300, "h": 340}
  },
  "client": {
    "fps": 30,
    "device": "web",
    "camera_facing": "front"
  }
}
```

Server-side conversion:
- Decode `image_jpeg_base64` → `frame_bgr`
- Crop ROIs using the provided coordinates
- Call `PrismEngine.process_frame()`

### JSON: Liveness Response

Top-level schema is stable; new signals are added under `details`.

```json
{
  "is_human": true,
  "confidence": 82.5,
  "bpm": 78,
  "signal_quality": 0.62,
  "hrv_score": 0.91,
  "details": {
    "rppg_method": "POS",
    "quality_gate": true,
    "quality_gate_reason": "pass",

    "bpm_signal_quality": 0.62,
    "hrv_entropy": 0.91,

    "chroma_passed": true,
    "physics_passed": true,
    "sss_ratio": 0.92,

    "temporal_xcorr_passed": true,
    "temporal_xcorr_strength": 0.31,
    "temporal_xcorr_delay_ms": 220.0,

    "is_static_image": false,
    "signal_variance": 1.2,
    "lighting_unstable": false,

    "screen_texture_detected": false,
    "texture_uniformity": 9.4,

    "screen_flicker_detected": false,
    "screen_flicker_ratio": 0.7,

    "forced_false_reason": ""
  }
}
```

### Suggested Endpoints

If a pipeline engineer wraps PRISM as a service:

- `POST /v1/sessions` → create session, return `session_id`
- `POST /v1/sessions/{session_id}/frame` → submit frame payload, return `LivenessResult`
- `POST /v1/sessions/{session_id}/reset` → resets engine buffers
- `GET /v1/sessions/{session_id}/status` → optional debug/status

Notes:
- Keep one `PrismEngine` instance per session.
- Call `.reset()` between users.

---

## Output Compatibility

- Top-level `LivenessResult` schema is unchanged.
- All new diagnostics are **schema-additive** under `result.details`.

---

## Next Recommended Work

- Add an explicit `PrismConfig.mode = "strict" | "demo"` and tune thresholds per mode.
- Add unit tests for:
  - POS/CHROM extraction sanity
  - screen texture/flicker gating
  - temporal xcorr outputs on synthetic signals
- Improve ROI selection using stable landmarks (face mesh) instead of Haar heuristics.

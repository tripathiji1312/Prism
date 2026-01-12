"""
PRISM Core Engine - ML & Signal Processing Module
Author: Swarnim
Version: 2.0.0

Advanced physics-based liveness detection using:
- rPPG (Remote Photoplethysmography) with Welch's method
- HRV (Heart Rate Variability) for biological chaos detection
- Subsurface Scattering Spectroscopy
- Temporal Frequency Response Analysis
- Moiré Pattern Detection (anti-screen-replay)
- Multi-Modal Fusion Scoring
"""

from __future__ import annotations

import numpy as np
import cv2
import scipy.signal as signal
import scipy.fftpack as fft
from scipy.stats import entropy as scipy_entropy
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PRISM_CORE")


# =============================================================================
# CONFIGURATION & DATA MODELS
# =============================================================================


class ScreenColor(str, Enum):
    """Screen colors used in chroma challenge."""

    RED = "RED"
    BLUE = "BLUE"
    WHITE = "WHITE"
    GREEN = "GREEN"


@dataclass
class PrismConfig:
    """Configuration for the PRISM engine. Tune these for different environments."""

    # Core settings
    fps: int = 30
    buffer_size: int = 90  # 3 seconds at 30fps (faster warmup)

    # rPPG settings
    # "POS" is the recommended default for webcam robustness.
    rppg_method: str = "POS"  # "GREEN" | "CHROM" | "POS"
    rppg_min_window_seconds: float = 3.0  # faster BPM detection

    # Quality gating (rules-first; compatible with ML training later)
    enable_quality_gate: bool = True
    max_motion_score: float = 20.0  # more permissive for movement
    min_blur_var_laplacian: float = 15.0  # more permissive for blur
    max_exposure_clip_pct: float = 0.35  # more permissive for exposure
    min_roi_size: int = 20  # smaller ROI OK

    # Temporal xcorr
    enable_temporal_xcorr: bool = True
    temporal_xcorr_min_corr: float = 0.05  # lower threshold
    temporal_xcorr_min_lag_ms: float = 0.0
    temporal_xcorr_max_lag_ms: float = 800.0

    # rPPG thresholds
    min_bpm: int = 40
    max_bpm: int = 200
    min_signal_quality: float = 0.10  # much more permissive

    # SSS (Subsurface Scattering) thresholds
    # Lowered significantly for indoor/variable lighting
    sss_ratio_threshold: float = 0.75

    # Chroma thresholds
    chroma_sensitivity: float = 0.9  # more permissive

    # Temporal response thresholds (milliseconds)
    temporal_delay_min_ms: float = 0  # allow instant response
    temporal_delay_max_ms: float = 600  # wider window

    # HRV thresholds
    hrv_min_rmssd: float = 3.0  # much lower for noisy signals
    hrv_entropy_threshold: float = 0.10  # much lower

    # Moiré detection (higher = less aggressive, fewer false positives)
    moire_threshold: float = 0.08  # raised to reduce false screen detection

    # BPM stability (anti-photo attack)
    bpm_stability_threshold: float = 20.0  # more permissive

    # Static image detection (THE KEY ANTI-PHOTO DEFENSE)
    min_signal_variance: float = 0.4  # lower threshold for real faces

    # Screen replay detection (additional layer)
    screen_color_uniformity_threshold: float = 0.15

    # Fusion model weights (rebalanced for real-world webcam conditions)
    weight_physics_sss: int = 10  # reduced - SSS unreliable indoors
    weight_chroma: int = 25  # chroma is reliable
    weight_rppg: int = 25  # rPPG important but needs time
    weight_hrv: int = 10  # HRV hard to get in short windows
    weight_temporal: int = 20  # temporal xcorr is working well
    weight_moire: int = 5


@dataclass
class HRVMetrics:
    """Heart Rate Variability metrics for biological liveness."""

    rmssd: float = 0.0  # Root Mean Square of Successive Differences
    sdnn: float = 0.0  # Standard Deviation of NN intervals
    entropy: float = 0.0  # Shannon entropy of RR intervals
    is_biologically_valid: bool = False


@dataclass
class RPPGResult:
    """Results from rPPG heart rate analysis."""

    bpm: int = 0
    signal_quality: float = 0.0  # SNR-based quality score (0-1)
    raw_confidence: float = 0.0
    is_valid: bool = False
    hrv: HRVMetrics = field(default_factory=HRVMetrics)


@dataclass
class PhysicsResult:
    """Results from physics-based checks."""

    sss_passed: bool = False
    sss_ratio: float = 0.0
    red_variance: float = 0.0
    blue_variance: float = 0.0


@dataclass
class TemporalResult:
    """Results from temporal frequency response analysis."""

    delay_ms: float = 0.0
    is_biological: bool = False
    response_detected: bool = False
    # Cross-correlation-based temporal estimate
    xcorr_delay_ms: float = 0.0
    xcorr_strength: float = 0.0
    xcorr_passed: bool = False


@dataclass
class MoireResult:
    """Results from Moiré pattern detection."""

    is_screen: bool = False
    moire_score: float = 0.0


@dataclass
class StaticImageResult:
    """Results from static image detection."""

    is_static: bool = True  # Default to static until proven otherwise
    signal_variance: float = 0.0
    is_alive: bool = False


@dataclass
class LivenessResult:
    """Final liveness detection result. This is what Sohini's API consumes."""

    is_human: bool = False
    confidence: float = 0.0  # 0-100
    bpm: int = 0
    hrv_score: float = 0.0  # Biological chaos metric
    signal_quality: float = 0.0
    details: dict = field(default_factory=dict)


# =============================================================================
# PRISM ENGINE
# =============================================================================


class PrismEngine:
    """
    PRISM Physics-Based Liveness Detection Engine.

    Implements multi-modal fusion of:
    1. rPPG (Remote Photoplethysmography) - Heart rate from face color
    2. HRV (Heart Rate Variability) - Biological chaos signature
    3. SSS (Subsurface Scattering) - Light penetration through skin
    4. Temporal Response - Biological delay to stimuli
    5. Moiré Detection - Screen replay attack defense
    6. Chroma Sync - Color reflection verification

    Usage:
        engine = PrismEngine()
        result = engine.process_frame(forehead_roi, face_img, "RED")
    """

    def __init__(self, config: Optional[PrismConfig] = None):
        """
        Initialize the PRISM engine.

        Args:
            config: Configuration object. Uses defaults if None.
        """
        self.config = config or PrismConfig()

        # Signal buffers
        # Keep legacy green buffer for backward compatibility and static-image detection.
        self.green_signal_buffer: deque = deque(maxlen=self.config.buffer_size)

        # RGB mean buffer used for robust rPPG (POS/CHROM).
        self.rgb_signal_buffer: deque = deque(maxlen=self.config.buffer_size)

        # Time-synced buffers for temporal cross-correlation
        self.temporal_buffer: deque = deque(maxlen=120)  # ~4 seconds at 30fps
        self.color_change_timestamps: List[Tuple[str, float]] = []

        # Backward-compatible luminance buffer (used by legacy temporal method)
        self.luminance_buffer: deque = deque(maxlen=60)  # 2 seconds for temporal

        # State tracking
        self.last_bpm = 0
        self.bpm_history: deque = deque(maxlen=10)
        self.last_screen_color: Optional[str] = None
        self.last_color_change_time: float = 0.0

        # RR interval buffer for HRV
        self.rr_intervals: deque = deque(maxlen=30)

        # BPM stability tracking (anti-photo attack)
        self.raw_bpm_history: deque = deque(maxlen=30)  # Track BPM over time

        logger.info(
            f"PRISM Engine initialized with buffer_size={self.config.buffer_size}"
        )

    # =========================================================================
    # 1. ENHANCED rPPG (Heart Rate Detection)
    # =========================================================================

    def _rgb_from_screen_color(self, screen_color: str) -> Tuple[float, float, float]:
        c = (screen_color or "").upper()
        if c == "RED":
            return 1.0, 0.0, 0.0
        if c == "GREEN":
            return 0.0, 1.0, 0.0
        if c == "BLUE":
            return 0.0, 0.0, 1.0
        # WHITE/unknown
        return 1.0, 1.0, 1.0

    def _extract_bvp_from_rgb(self, rgb_window: np.ndarray) -> np.ndarray:
        """Return a 1D BVP signal from RGB mean window.

        Implements lightweight classical rPPG methods (GREEN/CHROM/POS).
        rgb_window is shape (N, 3) in RGB channel order.
        """
        method = (self.config.rppg_method or "GREEN").upper()
        # Normalize by per-channel mean to reduce illumination variation
        mean_rgb = np.mean(rgb_window, axis=0)
        mean_rgb = np.where(mean_rgb <= 1e-6, 1.0, mean_rgb)
        C = (rgb_window / mean_rgb) - 1.0
        r, g, b = C[:, 0], C[:, 1], C[:, 2]

        if method == "GREEN":
            return g

        if method == "CHROM":
            # de Haan & Jeanne (2013): chrominance-based rPPG
            x = 3.0 * r - 2.0 * g
            y = 1.5 * r + g - 1.5 * b
            # Robust scaling
            std_y = np.std(y)
            alpha = (np.std(x) / (std_y + 1e-10)) if std_y > 0 else 1.0
            return x - alpha * y

        # POS (recommended default)
        # Wang et al. (2017): Plane-Orthogonal-to-Skin
        x = g - b
        y = -2.0 * r + g + b
        std_y = np.std(y)
        alpha = (np.std(x) / (std_y + 1e-10)) if std_y > 0 else 1.0
        return x + alpha * y

    def _get_heart_rate(self) -> RPPGResult:
        """
        Advanced rPPG using Welch's method for robust frequency estimation.

        Improvements over v1:
        - Welch's method instead of raw FFT (reduces noise)
        - Hamming window for spectral leakage reduction
        - SNR-based signal quality metric
        - Peak detection for RR interval extraction

        Returns:
            RPPGResult with BPM, signal quality, and validity flag.
        """
        result = RPPGResult()

        # Choose signal source based on configured rPPG method
        method = (self.config.rppg_method or "GREEN").upper()
        if method == "GREEN":
            if len(self.green_signal_buffer) < self.config.buffer_size:
                return result  # Not enough data yet (warming up)
            raw_signal = np.array(self.green_signal_buffer, dtype=np.float32)
        else:
            if len(self.rgb_signal_buffer) < self.config.buffer_size:
                return result
            rgb_window = np.array(self.rgb_signal_buffer, dtype=np.float32)
            raw_signal = self._extract_bvp_from_rgb(rgb_window).astype(np.float32)

        # Ensure we have enough effective duration for BPM
        window_seconds = len(raw_signal) / float(self.config.fps)
        if window_seconds < self.config.rppg_min_window_seconds:
            return result

        # 1. Detrending (remove slow DC drift from lighting changes)
        detrended = signal.detrend(raw_signal)

        # 2. Z-score normalization
        std = np.std(detrended)
        if std == 0:
            return result
        normalized = (detrended - np.mean(detrended)) / std

        # 3. Butterworth Bandpass Filter [0.75Hz - 3.0Hz] = [45 - 180 BPM]
        nyquist = 0.5 * self.config.fps
        low = 0.75 / nyquist
        high = 3.0 / nyquist

        # Clamp to valid range
        low = max(0.01, min(low, 0.99))
        high = max(low + 0.01, min(high, 0.99))

        b_coeffs, a_coeffs = signal.butter(
            3, [low, high], btype="bandpass", output="ba"
        )

        filtered_signal = signal.filtfilt(
            b_coeffs, a_coeffs, normalized
        )  # filtfilt for zero phase

        # 4. Welch's method for power spectral density (more robust than FFT)
        nperseg = min(len(filtered_signal), 128)
        freqs, psd = signal.welch(
            filtered_signal,
            fs=self.config.fps,
            nperseg=nperseg,
            noverlap=nperseg // 2,
            window="hamming",
        )

        # 5. Find peak in valid HR range
        valid_mask = (freqs >= 0.75) & (freqs <= 3.0)
        valid_freqs = freqs[valid_mask]
        valid_psd = psd[valid_mask]

        if len(valid_psd) == 0:
            return result

        # Find dominant frequency
        peak_idx = np.argmax(valid_psd)
        peak_freq = valid_freqs[peak_idx]
        peak_power = valid_psd[peak_idx]

        # 6. Calculate Signal Quality (SNR: peak power / mean of rest)
        noise_mask = np.ones(len(valid_psd), dtype=bool)
        noise_mask[max(0, peak_idx - 2) : min(len(valid_psd), peak_idx + 3)] = False
        noise_power = (
            np.mean(valid_psd[noise_mask]) if np.sum(noise_mask) > 0 else 1e-10
        )
        snr = peak_power / (noise_power + 1e-10)
        signal_quality = min(1.0, snr / 10.0)  # Normalize to 0-1

        # 7. Convert to BPM
        current_bpm = peak_freq * 60

        # 8. Temporal smoothing with quality weighting
        self.bpm_history.append((current_bpm, signal_quality))
        if len(self.bpm_history) > 0:
            # Weighted average by signal quality
            weighted_sum = sum(bpm * q for bpm, q in self.bpm_history)
            weight_sum = sum(q for _, q in self.bpm_history)
            smoothed_bpm = weighted_sum / (weight_sum + 1e-10)
        else:
            smoothed_bpm = current_bpm

        self.last_bpm = int(smoothed_bpm)

        # Track raw BPM for stability analysis (anti-photo attack)
        self.raw_bpm_history.append(current_bpm)

        # 9. Extract RR intervals for HRV (using peak detection on filtered signal)
        hrv_metrics = self._extract_hrv(filtered_signal)

        # Validate result
        is_valid = (
            self.config.min_bpm <= self.last_bpm <= self.config.max_bpm
            and signal_quality >= self.config.min_signal_quality
        )

        result.bpm = self.last_bpm
        result.signal_quality = float(round(float(signal_quality), 3))
        result.raw_confidence = float(round(float(peak_power), 3))
        result.is_valid = bool(is_valid)
        result.hrv = hrv_metrics

        return result

    # =========================================================================
    # 2. HRV (Heart Rate Variability) Extraction
    # =========================================================================

    def _extract_hrv(self, bvp_signal: np.ndarray) -> HRVMetrics:
        """
        Extract Heart Rate Variability metrics from BVP waveform.

        HRV is a key liveness indicator because:
        - Living hearts have natural variability (chaos)
        - Synthetic/static signals lack this biological randomness

        Metrics:
        - RMSSD: Root Mean Square of Successive Differences
        - SDNN: Standard Deviation of NN intervals
        - Entropy: Shannon entropy (higher = more biological chaos)

        Args:
            bvp_signal: Blood Volume Pulse signal (filtered green channel)

        Returns:
            HRVMetrics with computed values and validity flag.
        """
        result = HRVMetrics()

        if len(bvp_signal) < 30:
            return result

        # Find peaks (heartbeats) in the BVP signal
        # Use prominence to filter noise
        peaks, properties = signal.find_peaks(
            bvp_signal,
            distance=int(self.config.fps * 0.4),  # Min 0.4s between beats (150 BPM max)
            prominence=0.3 * np.std(bvp_signal),
        )

        if len(peaks) < 3:
            return result

        # Calculate RR intervals (time between peaks) in milliseconds
        rr_intervals = np.diff(peaks) * (1000 / self.config.fps)

        # Filter physiologically implausible intervals
        valid_mask = (rr_intervals > 333) & (rr_intervals < 1500)  # 40-180 BPM
        rr_intervals = rr_intervals[valid_mask]

        if len(rr_intervals) < 2:
            return result

        # RMSSD: Root Mean Square of Successive Differences
        successive_diffs = np.diff(rr_intervals)
        rmssd = np.sqrt(np.mean(successive_diffs**2))

        # SDNN: Standard Deviation of NN intervals
        sdnn = np.std(rr_intervals)

        # Shannon Entropy of RR intervals (binned)
        hist, _ = np.histogram(rr_intervals, bins=10, density=True)
        hist = hist[hist > 0]  # Remove zeros for log
        hrv_entropy = scipy_entropy(hist)

        # Determine biological validity
        is_valid = (
            rmssd >= self.config.hrv_min_rmssd
            and hrv_entropy >= self.config.hrv_entropy_threshold
        )

        result.rmssd = float(round(float(rmssd), 2))
        result.sdnn = float(round(float(sdnn), 2))
        result.entropy = float(round(float(hrv_entropy), 3))
        result.is_biologically_valid = bool(is_valid)

        return result

    # =========================================================================
    # 3. PHYSICS CHECK (Subsurface Scattering Spectroscopy)
    # =========================================================================

    def _check_physics_sss(self, face_img: np.ndarray) -> PhysicsResult:
        """
        Subsurface Scattering Spectroscopy analysis.

        Real skin physics:
        - Blue light reflects off surface (high sharpness, captures pores)
        - Red light penetrates ~1-3mm, scatters internally (blurry)

        Screens/photos:
        - Both channels have identical sharpness (flat surface)

        Args:
            face_img: BGR face image from Jai's CV pipeline.

        Returns:
            PhysicsResult with SSS ratio and pass/fail status.
        """
        result = PhysicsResult()

        if face_img is None or face_img.size == 0:
            return result

        # Split channels (OpenCV = BGR)
        b, g, r = cv2.split(face_img)

        # Apply Gaussian blur to reduce noise before Laplacian
        b_blur = cv2.GaussianBlur(b, (3, 3), 0)
        r_blur = cv2.GaussianBlur(r, (3, 3), 0)

        # Calculate Laplacian variance (sharpness) for each channel
        lap_b = cv2.Laplacian(b_blur, cv2.CV_64F)
        lap_r = cv2.Laplacian(r_blur, cv2.CV_64F)

        var_b = lap_b.var()
        var_r = lap_r.var()

        # Avoid division by zero
        if var_r < 0.001:
            var_r = 0.001

        # SSS Ratio: Blue sharpness / Red sharpness
        # Real skin: ratio > 1.05 (blue is sharper)
        # Screen: ratio ≈ 1.0 (both equal)
        ratio = var_b / var_r

        result.sss_ratio = round(ratio, 4)
        result.blue_variance = round(var_b, 2)
        result.red_variance = round(var_r, 2)
        result.sss_passed = ratio > self.config.sss_ratio_threshold

        return result

    # =========================================================================
    # 4. TEMPORAL FREQUENCY RESPONSE
    # =========================================================================

    def _check_temporal_response(
        self,
        face_img: np.ndarray,
        screen_color: str,
        timestamp_ms: Optional[float] = None,
    ) -> TemporalResult:
        """
        Temporal frequency response analysis.

        Biological response timing:
        - Human skin has 100-300ms delay to light stimulus
        - Pre-recorded video: response already baked in (0ms delay)
        - Real-time deepfake: processing lag in wrong direction

        Args:
            face_img: BGR face image
            screen_color: Current screen color from frontend
            timestamp_ms: Optional timestamp for precise timing

        Returns:
            TemporalResult with delay measurement and validity.
        """
        result = TemporalResult()

        if face_img is None or face_img.size == 0:
            return result

        current_time = timestamp_ms or (time.time() * 1000)

        # Calculate current face luminance
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        luminance = np.mean(gray)

        self.luminance_buffer.append((current_time, luminance, screen_color))

        # Buffer for cross-correlation temporal check
        stim_r, stim_g, stim_b = self._rgb_from_screen_color(screen_color)
        # Use mean face luminance as response (works even when colors vary)
        self.temporal_buffer.append(
            (float(current_time), float(luminance), float(stim_r + stim_g + stim_b))
        )

        # Detect color change
        if (
            screen_color != self.last_screen_color
            and self.last_screen_color is not None
        ):
            self.last_color_change_time = current_time
            self.color_change_timestamps.append((screen_color, current_time))

            # Keep only recent changes
            if len(self.color_change_timestamps) > 10:
                self.color_change_timestamps.pop(0)

        self.last_screen_color = screen_color

        # Analyze response if we have enough data
        if len(self.luminance_buffer) >= 30 and self.last_color_change_time > 0:
            # Find luminance change after color flash
            pre_flash = [
                lum
                for t, lum, _ in self.luminance_buffer
                if t < self.last_color_change_time
            ]
            post_flash = [
                (t, lum)
                for t, lum, _ in self.luminance_buffer
                if t >= self.last_color_change_time
            ]

            if len(pre_flash) >= 5 and len(post_flash) >= 5:
                baseline = np.mean(pre_flash[-5:])

                # Find when luminance changed significantly (>5% deviation)
                for t, lum in post_flash:
                    if abs(lum - baseline) > 0.05 * baseline:
                        delay = t - self.last_color_change_time
                        result.delay_ms = float(delay)
                        result.response_detected = True
                        result.is_biological = bool(
                            self.config.temporal_delay_min_ms
                            <= delay
                            <= self.config.temporal_delay_max_ms
                        )
                        break

        # Cross-correlation temporal check (more stable than threshold crossing)
        if self.config.enable_temporal_xcorr and len(self.temporal_buffer) >= 45:
            resp = np.array([r for _, r, _ in self.temporal_buffer], dtype=np.float64)
            stim = np.array([s for _, _, s in self.temporal_buffer], dtype=np.float64)

            # Normalize
            resp = resp - np.mean(resp)
            stim = stim - np.mean(stim)
            resp_std = float(np.std(resp))
            stim_std = float(np.std(stim))
            if resp_std > 1e-6 and stim_std > 1e-6:
                resp = resp / resp_std
                stim = stim / stim_std

                dt_ms = 1000.0 / float(self.config.fps)
                min_lag = int(self.config.temporal_xcorr_min_lag_ms / dt_ms)
                max_lag = int(self.config.temporal_xcorr_max_lag_ms / dt_ms)
                min_lag = max(0, min_lag)
                max_lag = max(min_lag + 1, max_lag)

                best_corr = -1.0
                best_lag = 0
                # Correlate stim(t) with resp(t+lag)
                for lag in range(min_lag, min(max_lag, len(resp) - 1)):
                    a = stim[: len(resp) - lag]
                    b = resp[lag:]
                    if len(a) < 10:
                        break
                    corr = float(np.mean(a * b))
                    if corr > best_corr:
                        best_corr = corr
                        best_lag = lag

                result.xcorr_strength = float(round(best_corr, 3))
                result.xcorr_delay_ms = float(round(best_lag * dt_ms, 1))
                result.xcorr_passed = bool(
                    best_corr >= self.config.temporal_xcorr_min_corr
                    and self.config.temporal_xcorr_min_lag_ms
                    <= result.xcorr_delay_ms
                    <= self.config.temporal_xcorr_max_lag_ms
                )

        return result

    # =========================================================================
    # 5. MOIRÉ PATTERN DETECTION
    # =========================================================================

    def _check_moire_pattern(self, face_img: np.ndarray) -> MoireResult:
        """
        Detect Moiré patterns indicating screen replay attack.

        When a camera films a screen, interference patterns appear
        in the frequency domain due to screen pixel grid interaction
        with camera sensor.

        Args:
            face_img: BGR face image

        Returns:
            MoireResult with screen detection status and score.
        """
        result = MoireResult()

        if face_img is None or face_img.size == 0:
            return result

        # Convert to grayscale
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY).astype(np.float32)

        # Apply 2D FFT
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)

        # Log transform for visualization
        log_magnitude = np.log1p(magnitude)

        # Normalize
        denom = float(np.max(log_magnitude))
        if denom <= 1e-10:
            return result
        log_magnitude = log_magnitude / denom

        # Look for periodic peaks that indicate screen pixels
        # Real faces have smooth frequency distribution
        # Screens have sharp peaks at regular intervals

        h, w = log_magnitude.shape
        center_h, center_w = h // 2, w // 2

        # Exclude DC component (center) and low frequencies
        mask = np.zeros_like(log_magnitude)
        mask[center_h - 10 : center_h + 10, center_w - 10 : center_w + 10] = 1
        masked_mag = log_magnitude * (1 - mask)

        # Calculate ratio of peak values to mean
        peak_value = np.max(masked_mag)
        mean_value = np.mean(masked_mag[masked_mag > 0])

        moire_score = peak_value / (mean_value + 1e-10)

        # High score indicates periodic pattern (screen)
        result.moire_score = float(round(float(moire_score), 3))
        result.is_screen = bool(moire_score > (1 / self.config.moire_threshold))

        return result

    # =========================================================================
    # 6. CHROMA SYNC CHECK
    # =========================================================================

    def _check_chroma(self, face_img: np.ndarray, screen_color: str) -> bool:
        """
        Verify face reflection matches screen color.

        Physics: Real faces in real rooms reflect screen light.
        Pre-recorded video: Lighting doesn't match current screen.

        Args:
            face_img: BGR face image
            screen_color: Current screen color ("RED", "BLUE", "WHITE", "GREEN")

        Returns:
            True if reflection matches expected physics.
        """
        if face_img is None or face_img.size == 0:
            return False

        # Get average color of face (BGR)
        avg_color = np.mean(face_img, axis=(0, 1))
        blue_val, green_val, red_val = avg_color

        sensitivity = self.config.chroma_sensitivity

        if screen_color == "RED":
            return red_val > (blue_val * sensitivity)

        elif screen_color == "BLUE":
            # Lower threshold for blue due to skin absorption
            return blue_val > (red_val * 0.8)

        elif screen_color == "GREEN":
            return green_val > (red_val * 0.9) and green_val > (blue_val * 0.9)

        elif screen_color == "WHITE":
            # All channels should be relatively balanced and elevated
            return True

        return True

    # =========================================================================
    # 7. STATIC IMAGE DETECTION (THE KEY ANTI-PHOTO DEFENSE)
    # =========================================================================

    def _check_static_image(self) -> StaticImageResult:
        """
        Detect static images (photos) by analyzing temporal variance.

        THIS IS THE MOST IMPORTANT ANTI-PHOTO DEFENSE.

        Real faces: Green channel fluctuates due to blood volume pulse (~0.1-1%)
                   Variance over 5 seconds should be > 2.0

        Photos:    Green channel is STATIC (only camera sensor noise)
                   Variance over 5 seconds should be < 0.5

        AI images: Also static - no temporal variance at all

        Returns:
            StaticImageResult with variance and is_alive flag
        """
        result = StaticImageResult()

        if len(self.green_signal_buffer) < 60:  # Need at least 2 seconds
            return result

        # Get recent green channel values
        recent_signal = np.array(list(self.green_signal_buffer)[-90:])  # Last 3 seconds

        # Calculate variance (normalized by mean to handle different lighting)
        mean_val = np.mean(recent_signal)
        if mean_val < 1:
            mean_val = 1

        # Coefficient of variation (CV) - normalized variance
        variance = float(np.std(recent_signal) / mean_val * 100)  # As percentage

        result.signal_variance = float(round(variance, 3))

        # Static-image detection should primarily catch "too stable" signals.
        # High variance is common with stimulus/exposure pumping and should not
        # force a false negative; treat it as a "lighting unstable" flag instead.
        too_stable = variance < self.config.min_signal_variance

        # Flag unusually high variance, but do not mark as static.
        lighting_unstable = variance > 25.0

        result.is_static = bool(too_stable)
        result.is_alive = bool(not result.is_static)

        # Extra diagnostics are computed again in fusion.
        self._lighting_unstable = bool(lighting_unstable)

        return result

    def _check_screen_texture(self, face_img: np.ndarray) -> Tuple[bool, float]:
        """
        Detect screen replay by analyzing texture uniformity.

        Screens displaying images have unnaturally uniform color patches
        because of pixel rendering. Real skin has micro-texture variation.

        Returns:
            (is_screen_like, uniformity_score)
        """
        if face_img is None or face_img.size == 0:
            return False, 0.0

        # Convert to grayscale
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY).astype(np.float32)

        # Calculate local standard deviation using a small window
        # Real skin: high local variation due to pores, texture
        # Screen: low local variation (smooth pixel rendering)
        kernel_size = 5
        mean_local = cv2.blur(gray, (kernel_size, kernel_size))
        sqr_mean = cv2.blur(gray**2, (kernel_size, kernel_size))
        local_std = np.sqrt(np.maximum(sqr_mean - mean_local**2, 0))

        avg_local_std = float(np.mean(local_std))

        # Real skin typically has local_std > 8-12
        # Screens/AI images typically have local_std < 7
        # Your phone showed 5.97 - clearly a screen
        is_screen_like = bool(avg_local_std < 7.5)

        return is_screen_like, float(round(avg_local_std, 2))

    def _check_screen_flicker(self) -> Tuple[bool, float]:
        """
        Detect screen flicker patterns in the signal.

        Screens refresh at fixed rates (60Hz, 120Hz) which creates
        a characteristic high-frequency pattern different from blood flow.
        Real rPPG is 0.75-3Hz, screen flicker is much higher frequency.

        Returns:
            (is_screen_flicker, flicker_score)
        """
        if len(self.green_signal_buffer) < 60:
            return False, 0.0

        sig = np.array(list(self.green_signal_buffer)[-60:], dtype=np.float64)
        sig = sig - np.mean(sig)

        # FFT to find frequency content
        fft_vals = np.abs(np.fft.rfft(sig))
        freqs = np.fft.rfftfreq(len(sig), d=1.0 / self.config.fps)

        # rPPG band: 0.75-3Hz (heart rate)
        rppg_mask = (freqs >= 0.75) & (freqs <= 3.0)
        # High freq band: >5Hz (screen flicker, noise)
        high_mask = freqs > 5.0

        rppg_power = np.sum(fft_vals[rppg_mask]) if np.any(rppg_mask) else 0.001
        high_power = np.sum(fft_vals[high_mask]) if np.any(high_mask) else 0.0

        # Ratio of high-freq to rPPG power
        # Real faces: mostly rPPG band, ratio < 1
        # Screens: lots of high-freq flicker, ratio > 2
        ratio = high_power / (rppg_power + 1e-6)

        is_flicker = ratio > 1.5
        return is_flicker, float(round(ratio, 3))

    # =========================================================================
    # 7. MULTI-MODAL FUSION
    # =========================================================================

    def _compute_fusion_score(
        self,
        rppg: RPPGResult,
        physics: PhysicsResult,
        chroma_passed: bool,
        temporal: TemporalResult,
        moire: MoireResult,
    ) -> Tuple[bool, float, dict]:
        """
        Multi-modal fusion scoring with weighted confidence.

        Combines all detection layers into final liveness decision.
        Uses weighted scoring with anomaly detection for inconsistencies.

        Args:
            rppg: rPPG heart rate results
            physics: Subsurface scattering results
            chroma_passed: Chroma sync check result
            temporal: Temporal response results
            moire: Moiré detection results

        Returns:
            Tuple of (is_human, confidence_score, details_dict)
        """
        cfg = self.config
        score = 0.0
        max_score = 100.0

        details = {
            "bpm": rppg.bpm,
            "bpm_signal_quality": rppg.signal_quality,
            "hrv_rmssd": rppg.hrv.rmssd,
            "hrv_entropy": rppg.hrv.entropy,
            "physics_passed": physics.sss_passed,
            "sss_ratio": physics.sss_ratio,
            "chroma_passed": chroma_passed,
            "temporal_delay_ms": temporal.delay_ms,
            "temporal_biological": temporal.is_biological,
            "temporal_xcorr_delay_ms": temporal.xcorr_delay_ms,
            "temporal_xcorr_strength": temporal.xcorr_strength,
            "temporal_xcorr_passed": temporal.xcorr_passed,
            "moire_detected": moire.is_screen,
            "moire_score": moire.moire_score,
        }

        # 1. rPPG Score (weighted by signal quality)
        if rppg.is_valid:
            rppg_score = cfg.weight_rppg * rppg.signal_quality
            score += rppg_score
            details["rppg_contribution"] = round(rppg_score, 1)
        else:
            # Give partial credit if buffer is filling (warming up)
            if len(self.rgb_signal_buffer) > 30:
                warmup_bonus = 5
                score += warmup_bonus
                details["rppg_warmup_bonus"] = warmup_bonus

        # 2. HRV Score (biological chaos)
        if rppg.hrv.is_biologically_valid:
            hrv_score = cfg.weight_hrv
            score += hrv_score
            details["hrv_contribution"] = hrv_score

        # 3. Physics SSS Score - more lenient
        if physics.sss_passed:
            # Scale by how much ratio exceeds threshold
            sss_confidence = min(
                1.0, (physics.sss_ratio - cfg.sss_ratio_threshold) / 0.15
            )
            sss_confidence = max(0.5, sss_confidence)  # Minimum 50% if passed
            physics_score = cfg.weight_physics_sss * sss_confidence
            score += physics_score
            details["physics_contribution"] = round(physics_score, 1)
        else:
            # Give partial credit if SSS is close to threshold
            if physics.sss_ratio > cfg.sss_ratio_threshold - 0.15:
                partial_sss = cfg.weight_physics_sss * 0.3
                score += partial_sss
                details["physics_partial"] = round(partial_sss, 1)

        # 4. Chroma Score
        if chroma_passed:
            score += cfg.weight_chroma
            details["chroma_contribution"] = cfg.weight_chroma

        # 5. Temporal Score - give full credit if xcorr passed
        temporal_passed = (temporal.response_detected and temporal.is_biological) or (
            temporal.xcorr_passed
        )
        if temporal_passed:
            # Boost temporal score based on xcorr strength
            xcorr_bonus = min(10, temporal.xcorr_strength * 15)
            score += cfg.weight_temporal + xcorr_bonus
            details["temporal_contribution"] = cfg.weight_temporal + xcorr_bonus

        # 6. Moiré Penalty (negative if screen detected)
        if moire.is_screen:
            score -= cfg.weight_moire * 3  # reduced penalty
            details["moire_penalty"] = -cfg.weight_moire * 3
        else:
            score += cfg.weight_moire
            details["moire_contribution"] = cfg.weight_moire

        # 7. BPM Stability Check - only penalize if we have enough data
        bpm_stability_penalty = 0
        if len(self.raw_bpm_history) >= 15:  # need more samples
            bpm_std = np.std(list(self.raw_bpm_history))
            details["bpm_stability_std"] = round(bpm_std, 1)

            if bpm_std > cfg.bpm_stability_threshold:
                bpm_stability_penalty = min(
                    30, (bpm_std - cfg.bpm_stability_threshold) * 1.5
                )  # reduced penalty
                score -= bpm_stability_penalty
                details["bpm_stability_penalty"] = round(-bpm_stability_penalty, 1)

        # 8. STATIC IMAGE CHECK (THE MOST IMPORTANT ANTI-PHOTO DEFENSE)
        static_result = self._check_static_image()
        details["signal_variance"] = static_result.signal_variance
        details["is_static_image"] = static_result.is_static

        # Track high-variance lighting separately to avoid false negatives.
        lighting_unstable = bool(getattr(self, "_lighting_unstable", False))
        details["lighting_unstable"] = lighting_unstable
        if lighting_unstable:
            score -= 10
            details["lighting_penalty"] = -10

        if static_result.is_static:
            # CRITICAL: Static image = definitely not alive (low variance)
            score -= 50  # reduced from 70
            details["static_image_penalty"] = -50
        elif static_result.is_alive:
            score += 15  # increased alive bonus
            details["alive_bonus"] = 15

        # 9. SCREEN TEXTURE CHECK (catches AI images on screens)
        # This is CRITICAL for blocking phone/screen attacks
        is_screen_texture = False
        texture_score = 0.0
        if hasattr(self, "_last_face_img") and self._last_face_img is not None:
            is_screen_texture, texture_score = self._check_screen_texture(
                self._last_face_img
            )
            details["texture_uniformity"] = texture_score
            details["screen_texture_detected"] = is_screen_texture
            if is_screen_texture:
                # HEAVY penalty for screen-like texture
                score -= 60
                details["screen_texture_penalty"] = -60

        # 10. SCREEN FLICKER CHECK (catches phone/monitor refresh patterns)
        is_flicker, flicker_ratio = self._check_screen_flicker()
        details["screen_flicker_detected"] = is_flicker
        details["screen_flicker_ratio"] = flicker_ratio
        if is_flicker:
            score -= 40
            details["screen_flicker_penalty"] = -40

        # Normalize to 0-100
        confidence = max(0, min(100, score))

        # Final decision threshold
        is_human = confidence >= 40

        # CRITICAL GATE: If static image detected, FORCE False regardless of score
        if static_result.is_static and len(self.green_signal_buffer) >= 60:
            is_human = False
            details["forced_false_reason"] = "static_image_low_variance"

        # CRITICAL GATE: If screen texture detected, FORCE False
        if is_screen_texture and len(self.green_signal_buffer) >= 30:
            is_human = False
            details["forced_false_reason"] = "screen_texture_detected"

        # Anomaly detection: removed to reduce false negatives
        # Real humans can have inconsistent signals in bad lighting

        return bool(is_human), float(round(float(confidence), 1)), details

    # =========================================================================
    # MAIN PIPELINE
    # =========================================================================

    def _compute_quality_features(self, roi_bgr: np.ndarray) -> Dict[str, float]:
        if roi_bgr is None or roi_bgr.size == 0:
            return {
                "motion_score": 0.0,
                "blur_var": 0.0,
                "exposure_clip_pct": 1.0,
                "roi_min_dim": 0.0,
            }

        gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Exposure clipping (too dark or too bright)
        low_clip = float(np.mean(gray <= 5))
        high_clip = float(np.mean(gray >= 250))
        exposure_clip_pct = low_clip + high_clip

        # Motion score from ROI frame differencing
        if (
            getattr(self, "_prev_roi_gray", None) is None
            or self._prev_roi_gray.shape != gray.shape
        ):
            motion_score = 0.0
        else:
            diff = cv2.absdiff(self._prev_roi_gray, gray)
            motion_score = float(np.mean(diff))
        self._prev_roi_gray = gray

        h, w = gray.shape[:2]
        return {
            "motion_score": motion_score,
            "blur_var": blur_var,
            "exposure_clip_pct": float(exposure_clip_pct),
            "roi_min_dim": float(min(h, w)),
        }

    def _quality_gate(self, features: Dict[str, float]) -> Tuple[bool, str]:
        cfg = self.config
        if not cfg.enable_quality_gate:
            return True, "disabled"

        if features.get("roi_min_dim", 0.0) < float(cfg.min_roi_size):
            return False, "roi_too_small"
        if features.get("blur_var", 0.0) < cfg.min_blur_var_laplacian:
            return False, "too_blurry"
        if features.get("exposure_clip_pct", 1.0) > cfg.max_exposure_clip_pct:
            return False, "bad_exposure"
        if features.get("motion_score", 0.0) > cfg.max_motion_score:
            return False, "too_much_motion"

        return True, "pass"

    def process_frame(
        self,
        forehead_roi: Optional[np.ndarray],
        face_img: Optional[np.ndarray],
        screen_color: str,
        timestamp_ms: Optional[float] = None,
    ) -> LivenessResult:
        """
        Main processing pipeline. Called by Sohini's FastAPI backend.

        Processes a single frame through all detection layers and
        returns a fused liveness result.

        Args:
            forehead_roi: Cropped forehead region from Jai's CV pipeline.
                         Used for rPPG heart rate detection.
            face_img: Full face BGR image from Jai's CV pipeline.
                     Used for physics and chroma checks.
            screen_color: Current screen color ("RED", "BLUE", "WHITE", "GREEN").
                         From Srijan's frontend via Sohini's API.
            timestamp_ms: Optional timestamp for temporal analysis.

        Returns:
            LivenessResult with is_human, confidence, BPM, HRV score, and details.
        """
        result = LivenessResult()

        # Store face_img for texture analysis in fusion scoring
        self._last_face_img = face_img

        # 1. Update rPPG buffers
        quality_features: Dict[str, float] = {}
        quality_passed = True
        quality_reason = "pass"

        if forehead_roi is not None and forehead_roi.size > 0:
            try:
                # Legacy green buffer (used by static-image check)
                mean_green = float(np.mean(forehead_roi[:, :, 1]))
                self.green_signal_buffer.append(mean_green)

                # Robust POS/CHROM buffer: per-frame mean RGB
                roi_rgb = cv2.cvtColor(forehead_roi, cv2.COLOR_BGR2RGB)
                mean_rgb = np.mean(roi_rgb.reshape(-1, 3), axis=0)
                self.rgb_signal_buffer.append(
                    (float(mean_rgb[0]), float(mean_rgb[1]), float(mean_rgb[2]))
                )

                # Quality features + gating
                quality_features = self._compute_quality_features(forehead_roi)
                quality_passed, quality_reason = self._quality_gate(quality_features)
            except (IndexError, ValueError) as e:
                logger.warning(f"Error extracting rPPG features: {e}")
                quality_passed, quality_reason = False, "roi_error"
        else:
            quality_passed, quality_reason = False, "roi_missing"

        # 2. Run all detection algorithms
        rppg_result = self._get_heart_rate() if quality_passed else RPPGResult()
        rppg_details: Dict[str, Any] = {
            "rppg_method": (self.config.rppg_method or "GREEN").upper(),
            "quality_gate": bool(quality_passed),
            "quality_gate_reason": quality_reason,
        }
        if quality_features:
            rppg_details.update({k: float(v) for k, v in quality_features.items()})
        safe_face_img = (
            face_img if face_img is not None else np.empty((0, 0, 3), dtype=np.uint8)
        )
        physics_result = self._check_physics_sss(safe_face_img)
        chroma_passed = self._check_chroma(safe_face_img, screen_color)
        temporal_result = self._check_temporal_response(
            safe_face_img, screen_color, timestamp_ms
        )
        moire_result = self._check_moire_pattern(safe_face_img)

        # 3. Multi-modal fusion
        is_human, confidence, details = self._compute_fusion_score(
            rppg_result, physics_result, chroma_passed, temporal_result, moire_result
        )

        # 4. Build final result
        result.is_human = is_human
        result.confidence = confidence
        result.bpm = rppg_result.bpm
        result.hrv_score = rppg_result.hrv.entropy
        result.signal_quality = rppg_result.signal_quality
        details.update(rppg_details)
        result.details = details

        return result

    def reset(self) -> None:
        """Reset all buffers. Call when starting a new verification session."""
        self.green_signal_buffer.clear()
        self.luminance_buffer.clear()
        self.bpm_history.clear()
        self.rr_intervals.clear()
        self.color_change_timestamps.clear()
        self.last_bpm = 0
        self.last_screen_color = None
        self.last_color_change_time = 0.0
        logger.info("PRISM Engine buffers reset")


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Maintain backward compatibility with existing test_main.py
# The old API returned dict, new API returns dataclass
# This wrapper ensures both work


def _result_to_dict(result: LivenessResult) -> dict:
    """Convert LivenessResult to dict for legacy compatibility."""
    return {
        "is_human": result.is_human,
        "confidence": result.confidence,
        "details": {
            "bpm": result.bpm,
            "bpm_signal_strength": result.signal_quality,
            "physics_passed": result.details.get("physics_passed", False),
            "chroma_passed": result.details.get("chroma_passed", False),
            "sss_ratio": result.details.get("sss_ratio", 0),
            "hrv_entropy": result.hrv_score,
        },
    }

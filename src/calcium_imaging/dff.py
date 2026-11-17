"""Baseline estimation and dF/F."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d, percentile_filter, uniform_filter1d


def rolling_baseline(
    traces: np.ndarray,
    fps: float,
    window_s: float = 60.0,
    percentile: float = 8.0,
    smooth_s: float = 1.0,
) -> np.ndarray:
    """F0 as a running low percentile, then smoothed over the same window.

    A low percentile tracks the resting fluorescence under the transients and
    follows slow drift (bleaching, focus changes) without following activity.
    The trace is Gaussian-smoothed (``smooth_s`` seconds) first; otherwise a
    low percentile of a noisy trace sits below the true resting level and
    biases dF/F upwards.
    """
    traces = np.atleast_2d(traces)
    if smooth_s > 0:
        traces = gaussian_filter1d(traces, smooth_s * fps, axis=1, mode="nearest")
    n = traces.shape[1]
    win = int(round(window_s * fps)) | 1  # odd
    win = max(3, min(win, n if n % 2 else n - 1))
    f0 = percentile_filter(traces, percentile, size=(1, win), mode="nearest")
    return uniform_filter1d(f0, size=win, axis=1, mode="nearest")


def compute_dff(
    traces: np.ndarray, fps: float, window_s: float = 60.0, percentile: float = 8.0
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(dff, f0)`` with ``dff = (F - F0) / F0`` for (n_rois, T) traces."""
    traces = np.atleast_2d(np.asarray(traces, dtype=np.float64))
    f0 = rolling_baseline(traces, fps, window_s, percentile)
    # A non-positive baseline (possible after neuropil subtraction) makes the
    # ratio meaningless; mark those samples rather than emit huge values.
    safe = np.where(f0 > 0, f0, np.nan)
    return (traces - f0) / safe, f0

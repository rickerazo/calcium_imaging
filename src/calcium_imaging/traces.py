"""Fluorescence extraction from ROI masks."""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def neuropil_masks(
    labels: np.ndarray, inner_gap: int = 2, width: int = 6, min_pixels: int = 20
) -> list[np.ndarray]:
    """Ring around each ROI, excluding every ROI (plus a small margin).

    Returns one boolean mask per label, in label order. A ring with fewer
    than ``min_pixels`` pixels is widened until it has enough.
    """
    n = int(labels.max())
    any_roi = ndi.binary_dilation(labels > 0, iterations=inner_gap)
    masks = []
    for lab in range(1, n + 1):
        roi = labels == lab
        w = width
        while True:
            ring = ndi.binary_dilation(roi, iterations=inner_gap + w) & ~any_roi
            if ring.sum() >= min_pixels or w > 4 * width:
                break
            w += 2
        masks.append(ring)
    return masks


def extract_traces(
    movie: np.ndarray, labels: np.ndarray, neuropil_coeff: float = 0.7
) -> dict[str, np.ndarray]:
    """Mean fluorescence per ROI and its neuropil-corrected version.

    Returns arrays of shape (n_rois, T): ``raw``, ``neuropil`` and
    ``corrected = raw - coeff * (neuropil - median(neuropil))``.

    Only the *fluctuations* of the neuropil are removed; its median level is
    left in. Subtracting the full neuropil would leave dim cells with a
    resting level near zero, and dF/F divides by that level.
    """
    n = int(labels.max())
    t = movie.shape[0]
    flat = movie.reshape(t, -1)
    lab_flat = labels.ravel()

    raw = np.empty((n, t), dtype=np.float32)
    neu = np.zeros((n, t), dtype=np.float32)
    rings = neuropil_masks(labels)
    for i in range(n):
        raw[i] = flat[:, lab_flat == i + 1].mean(axis=1)
        ring = rings[i].ravel()
        if ring.any():
            neu[i] = flat[:, ring].mean(axis=1)

    corrected = raw - neuropil_coeff * (neu - np.median(neu, axis=1, keepdims=True))
    return {"raw": raw, "neuropil": neu, "corrected": corrected}

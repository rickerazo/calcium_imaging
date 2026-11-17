"""Rigid motion correction by phase correlation against a template."""

from __future__ import annotations

import cv2
import numpy as np
from skimage.registration import phase_cross_correlation


def _smooth(img: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return img
    return cv2.GaussianBlur(img, (0, 0), sigma)


def make_template(movie: np.ndarray, n_candidates: int = 200, n_keep: int = 40) -> np.ndarray:
    """Mean of the frames that agree best with each other.

    Evenly spaced candidate frames are correlated pairwise; the ones with the
    highest mean correlation to the rest are, in practice, the frames where
    the brain sat in its most common position.
    """
    n_candidates = min(n_candidates, len(movie))
    idx = np.linspace(0, len(movie) - 1, n_candidates).astype(int)
    frames = movie[idx]
    flat = frames.reshape(len(frames), -1)
    cc = np.corrcoef(flat)
    score = cc.mean(axis=1)
    best = np.argsort(score)[-min(n_keep, len(frames)):]
    return frames[best].mean(axis=0)


def estimate_shifts(
    movie: np.ndarray,
    template: np.ndarray,
    upsample: int = 10,
    sigma: float = 1.0,
    max_shift: float | None = None,
) -> np.ndarray:
    """Per-frame (dy, dx) shift that aligns each frame onto the template."""
    ref = _smooth(template.astype(np.float32), sigma)
    shifts = np.zeros((len(movie), 2), dtype=np.float32)
    for t, frame in enumerate(movie):
        shift, _, _ = phase_cross_correlation(
            ref, _smooth(frame, sigma), upsample_factor=upsample, normalization=None
        )
        shifts[t] = shift
    if max_shift is not None:
        np.clip(shifts, -max_shift, max_shift, out=shifts)
    return shifts


def apply_shifts(movie: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """Translate every frame by its (dy, dx) shift (bilinear, edge-replicated)."""
    out = np.empty_like(movie)
    h, w = movie.shape[1:]
    for t, (dy, dx) in enumerate(shifts):
        m = np.float32([[1, 0, dx], [0, 1, dy]])
        out[t] = cv2.warpAffine(
            movie[t], m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )
    return out


def correct_motion(
    movie: np.ndarray,
    n_iter: int = 2,
    upsample: int = 10,
    sigma: float = 1.0,
    max_shift: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rigidly register a movie.

    Returns ``(corrected, shifts, template)`` where ``shifts[t] = (dy, dx)`` is
    the translation applied to frame ``t``. The template is refined from the
    corrected movie on each iteration; shifts are always estimated from the
    original frames so interpolation is applied only once.
    """
    if max_shift is None:
        max_shift = 0.15 * min(movie.shape[1:])
    template = make_template(movie)
    corrected, shifts = movie, np.zeros((len(movie), 2), np.float32)
    for _ in range(n_iter):
        shifts = estimate_shifts(movie, template, upsample, sigma, max_shift)
        corrected = apply_shifts(movie, shifts)
        template = corrected.mean(axis=0)
    return corrected, shifts, template

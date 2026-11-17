"""ROI detection from summary images."""

from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.measure import regionprops
from skimage.segmentation import relabel_sequential, watershed


def temporal_bin(movie: np.ndarray, factor: int) -> np.ndarray:
    """Average consecutive groups of ``factor`` frames (drops the remainder)."""
    if factor <= 1:
        return movie
    n = (len(movie) // factor) * factor
    return movie[:n].reshape(-1, factor, *movie.shape[1:]).mean(axis=1)


def correlation_image(movie: np.ndarray) -> np.ndarray:
    """Mean temporal correlation of each pixel with its 8 neighbours.

    Pixels inside an active cell rise and fall together, so they score high;
    static structures and shot noise score near zero regardless of brightness.
    """
    z = movie - movie.mean(axis=0)
    std = z.std(axis=0)
    std[std == 0] = 1.0
    z = z / std

    kernel = np.ones((3, 3), dtype=np.float32)
    kernel[1, 1] = 0
    acc = np.zeros(movie.shape[1:], dtype=np.float64)
    for frame in z:
        acc += frame * ndi.convolve(frame, kernel, mode="constant")
    n_neighbours = ndi.convolve(
        np.ones(movie.shape[1:], np.float32), kernel, mode="constant"
    )
    return (acc / (len(z) * n_neighbours)).astype(np.float32)


def detect_rois(
    image: np.ndarray,
    diameter: float = 10.0,
    threshold: float = 2.0,
    min_circularity: float = 0.4,
    border: int = 2,
) -> np.ndarray:
    """Segment roughly round, cell-sized blobs in a summary image.

    Steps: band-pass at the cell scale (difference of Gaussians), threshold at
    ``median + threshold * robust_sd``, split touching cells with a
    marker-based watershed seeded at local maxima, then keep regions whose
    area and shape are plausible for a soma of the given ``diameter`` (pixels).

    Returns an int32 label image (0 = background, 1..N = ROIs).
    """
    r = diameter / 2.0
    img = image.astype(np.float32)
    band = ndi.gaussian_filter(img, r / 2.0) - ndi.gaussian_filter(img, 2.0 * r)

    med = np.median(band)
    robust_sd = 1.4826 * np.median(np.abs(band - med))
    mask = band > med + threshold * robust_sd
    mask = ndi.binary_opening(mask, iterations=1)

    peaks = peak_local_max(
        band, min_distance=max(1, int(round(r))), labels=mask.astype(np.uint8)
    )
    markers = np.zeros(img.shape, dtype=np.int32)
    markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    labels = watershed(-band, markers, mask=mask)

    cell_area = np.pi * r**2
    h, w = img.shape
    for p in regionprops(labels):
        y0, x0, y1, x1 = p.bbox
        circularity = 4 * np.pi * p.area / (p.perimeter**2) if p.perimeter > 0 else 0
        touches_border = (
            y0 < border or x0 < border or y1 > h - border or x1 > w - border
        )
        if (
            p.area < 0.3 * cell_area
            or p.area > 3.0 * cell_area
            or min(circularity, 1.0) < min_circularity
            or touches_border
        ):
            labels[labels == p.label] = 0

    labels, _, _ = relabel_sequential(labels)
    return labels.astype(np.int32)


def segment_movie(
    movie: np.ndarray,
    diameter: float = 10.0,
    threshold: float = 2.0,
    bin_frames: int = 5,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Detect ROIs in a motion-corrected movie.

    Returns ``(labels, images)`` where ``images`` holds the ``mean`` and
    ``correlation`` summary images.
    """
    corr = correlation_image(temporal_bin(movie, bin_frames))
    labels = detect_rois(corr, diameter=diameter, threshold=threshold)
    return labels, {"mean": movie.mean(axis=0), "correlation": corr}

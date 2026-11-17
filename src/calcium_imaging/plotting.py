"""Figures for quality control and results."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from skimage.segmentation import find_boundaries

INK = "#1f2933"
MUTED = "#6b7785"
GRID = "#e3e7ec"
SERIES = "#2a6fb0"
SERIES_2 = "#c2571a"
OUTLINE = "#ffb000"

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "figure.facecolor": "white",
    }
)


def _stretch(img: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(img, 1)), float(np.percentile(img, 99.5))


def plot_rois(images: dict[str, np.ndarray], labels: np.ndarray, path: Path) -> None:
    """Mean and correlation images with ROI outlines and numbers."""
    edges = find_boundaries(labels, mode="outer")
    overlay = np.ma.masked_where(~edges, edges)
    outline_cmap = matplotlib.colors.ListedColormap([OUTLINE])

    n = int(labels.max())
    fig, axes = plt.subplots(2, 2, figsize=(12, 12.4))
    axes = axes.ravel()
    panels = [
        ("Mean image", images["mean"], False),
        ("Local correlation image", images["correlation"], False),
        (f"ROIs on mean image (n = {n})", images["mean"], True),
        (f"ROIs on correlation image (n = {n})", images["correlation"], True),
    ]
    for ax, (title, img, with_rois) in zip(axes, panels):
        lo, hi = _stretch(img)
        ax.imshow(img, cmap="gray", vmin=lo, vmax=hi, interpolation="nearest")
        if with_rois:
            ax.imshow(overlay, cmap=outline_cmap, interpolation="nearest")
            for lab in range(1, int(labels.max()) + 1):
                ys, xs = np.nonzero(labels == lab)
                ax.text(
                    xs.mean(), ys.mean(), str(lab), color="white", fontsize=6,
                    ha="center", va="center",
                )
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    fig.savefig(path)
    plt.close(fig)


def plot_traces(
    dff: np.ndarray, fps: float, path: Path, roi_ids: np.ndarray, max_rois: int = 20
) -> None:
    """Stacked dF/F traces for the given ROIs (already ordered)."""
    roi_ids = roi_ids[:max_rois]
    t = np.arange(dff.shape[1]) / fps
    traces = dff[roi_ids]
    step = max(1.0, float(np.nanpercentile(traces, 99.5)))

    fig, ax = plt.subplots(figsize=(11, 0.36 * len(roi_ids) + 1.6))
    for row, (rid, tr) in enumerate(zip(roi_ids, traces)):
        offset = (len(roi_ids) - 1 - row) * step
        ax.plot(t, tr + offset, color=SERIES, lw=0.8)
        ax.text(
            -0.01, offset, f"ROI {rid + 1}", transform=ax.get_yaxis_transform(),
            ha="right", va="center", color=MUTED, fontsize=7,
        )
    # Scale bar instead of a y-axis: offsets make absolute tick values meaningless.
    x_bar = t[-1] * 1.015
    ax.plot([x_bar, x_bar], [0, 1.0], color=INK, lw=1.5, clip_on=False)
    ax.text(x_bar * 1.008, 0.5, "1.0 ΔF/F\n(100%)", va="center", fontsize=7, color=INK)

    ax.set_xlim(0, t[-1])
    top = max(len(roi_ids) * step, (len(roi_ids) - 1) * step + float(np.nanmax(traces[0])))
    ax.set_ylim(-0.6 * step, top + 0.3 * step)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Time (s)")
    ax.set_title(f"ΔF/F over time, {len(roi_ids)} most active ROIs")
    fig.savefig(path)
    plt.close(fig)


def plot_heatmap(dff: np.ndarray, fps: float, path: Path, order: np.ndarray) -> None:
    """All ROIs x time, one sequential hue."""
    data = dff[order]
    vmax = float(np.nanpercentile(data, 99.5))
    fig, ax = plt.subplots(figsize=(11, max(2.5, 0.09 * len(order) + 1.5)))
    im = ax.imshow(
        data, aspect="auto", cmap="Blues", vmin=0, vmax=vmax,
        extent=(0, dff.shape[1] / fps, len(order), 0), interpolation="nearest",
    )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("ROI (sorted by activity)")
    ax.set_title(f"ΔF/F, all {len(order)} ROIs")
    cb = fig.colorbar(im, ax=ax, pad=0.015)
    cb.set_label("ΔF/F")
    cb.outline.set_visible(False)
    fig.savefig(path)
    plt.close(fig)


def plot_motion(shifts: np.ndarray, fps: float, path: Path) -> None:
    """Estimated rigid shift per frame; x and y in separate panels."""
    t = np.arange(len(shifts)) / fps
    fig, axes = plt.subplots(2, 1, figsize=(11, 3.6), sharex=True, sharey=True)
    for ax, col, name, color in [
        (axes[0], 1, "x shift (px)", SERIES),
        (axes[1], 0, "y shift (px)", SERIES_2),
    ]:
        ax.plot(t, shifts[:, col], color=color, lw=0.8)
        ax.axhline(0, color=GRID, lw=0.8, zorder=0)
        ax.set_ylabel(name)
    axes[0].set_title("Rigid motion correction: estimated frame shifts")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_xlim(0, t[-1])
    fig.savefig(path)
    plt.close(fig)

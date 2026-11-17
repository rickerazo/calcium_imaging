"""Command line entry point: ``calcium-dff``."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import download as dl
from .dff import compute_dff
from .io import load_movie
from .motion import correct_motion
from .segment import segment_movie
from .traces import extract_traces


def run_pipeline(
    movie_path: str | Path,
    out_dir: str | Path = "outputs",
    fps: float = dl.DATASET_FPS,
    diameter: float = 10.0,
    threshold: float = 2.0,
    neuropil_coeff: float = 0.7,
    baseline_window_s: float = 60.0,
    baseline_percentile: float = 8.0,
    dark_offset: float | None = None,
    skip_motion: bool = False,
    make_plots: bool = True,
) -> dict:
    """Run every stage on one movie and write results to ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)

    movie = load_movie(movie_path)
    n_frames, h, w = movie.shape
    log(f"Loaded {movie_path}: {n_frames} frames, {h}x{w} px, {n_frames / fps:.1f} s at {fps:g} Hz")

    # dF/F is a ratio, so it is only meaningful if zero fluorescence maps to a
    # pixel value of zero. Many acquisition systems add an arbitrary (even
    # negative) offset; by default take the darkest pixel as the zero level.
    if dark_offset is None:
        dark_offset = float(movie.min())
    movie = movie - np.float32(dark_offset)
    log(f"Subtracted dark offset of {dark_offset:g}")

    if skip_motion:
        shifts = np.zeros((n_frames, 2), np.float32)
    else:
        movie, shifts, _ = correct_motion(movie)
        log(
            "Motion corrected: max |shift| "
            f"y={np.abs(shifts[:, 0]).max():.2f} px, x={np.abs(shifts[:, 1]).max():.2f} px"
        )

    labels, images = segment_movie(movie, diameter=diameter, threshold=threshold)
    n_rois = int(labels.max())
    log(f"Detected {n_rois} ROIs")
    if n_rois == 0:
        raise SystemExit("No ROIs found; try a lower --threshold or a different --diameter.")

    tr = extract_traces(movie, labels, neuropil_coeff=neuropil_coeff)
    dff, f0 = compute_dff(
        tr["corrected"], fps, window_s=baseline_window_s, percentile=baseline_percentile
    )
    n_bad = int(np.isnan(dff).any(axis=1).sum())
    log(f"Computed dF/F ({n_bad} ROIs with a non-positive baseline)")

    t = np.arange(n_frames) / fps
    df = pd.DataFrame(dff.T, columns=[f"roi_{i + 1}" for i in range(n_rois)])
    df.insert(0, "time_s", t)
    df.to_csv(out_dir / "dff.csv", index=False, float_format="%.5f")
    np.savez_compressed(
        out_dir / "dff.npz",
        dff=dff.astype(np.float32),
        f0=f0.astype(np.float32),
        f_raw=tr["raw"],
        f_neuropil=tr["neuropil"],
        f_corrected=tr["corrected"],
        time_s=t,
        fps=fps,
        dark_offset=dark_offset,
        labels=labels,
        shifts_yx=shifts,
        mean_image=images["mean"],
        correlation_image=images["correlation"],
    )

    # Rank by robust signal-to-noise: peak dF/F over the noise estimated from
    # frame-to-frame differences.
    valid = ~np.isnan(dff).any(axis=1)
    snr = np.full(n_rois, -np.inf)
    noise = 1.4826 * np.median(np.abs(np.diff(dff[valid], axis=1)), axis=1) / np.sqrt(2)
    snr[valid] = np.percentile(dff[valid], 99.5, axis=1) / np.maximum(noise, 1e-12)
    order = np.argsort(-snr)

    if make_plots:
        from . import plotting

        plotting.plot_rois(images, labels, out_dir / "rois.png")
        plotting.plot_traces(dff, fps, out_dir / "dff_traces.png", order)
        plotting.plot_heatmap(dff, fps, out_dir / "dff_heatmap.png", order)
        plotting.plot_motion(shifts, fps, out_dir / "motion.png")
    log(f"Wrote results to {out_dir}/")

    return {"dff": dff, "f0": f0, "labels": labels, "shifts": shifts, "order": order}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="calcium-dff", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_dl = sub.add_parser("download", help="download the public demo movie")
    p_dl.add_argument("--dest", default="data/raw")

    p_run = sub.add_parser("run", help="movie -> dF/F traces and figures")
    p_run.add_argument("movie", help="path to a (T, Y, X) TIFF stack")
    p_run.add_argument("--out", default="outputs")
    p_run.add_argument("--fps", type=float, default=dl.DATASET_FPS, help="frame rate in Hz")
    p_run.add_argument("--diameter", type=float, default=10.0, help="cell diameter in pixels")
    p_run.add_argument(
        "--threshold", type=float, default=2.0,
        help="detection threshold in robust SDs above the image median",
    )
    p_run.add_argument("--neuropil-coeff", type=float, default=0.7)
    p_run.add_argument("--baseline-window", type=float, default=60.0, help="seconds")
    p_run.add_argument("--baseline-percentile", type=float, default=8.0)
    p_run.add_argument(
        "--dark-offset", type=float, default=None,
        help="pixel value that corresponds to zero light (default: movie minimum)",
    )
    p_run.add_argument("--skip-motion", action="store_true")
    p_run.add_argument("--no-plots", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "download":
        dl.download(args.dest)
    else:
        run_pipeline(
            args.movie,
            out_dir=args.out,
            fps=args.fps,
            diameter=args.diameter,
            threshold=args.threshold,
            neuropil_coeff=args.neuropil_coeff,
            baseline_window_s=args.baseline_window,
            baseline_percentile=args.baseline_percentile,
            dark_offset=args.dark_offset,
            skip_motion=args.skip_motion,
            make_plots=not args.no_plots,
        )


if __name__ == "__main__":
    main()

# calcium-imaging

Computer-vision pipeline that turns a raw calcium imaging movie into ΔF/F traces over time.

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

## Usage

```bash
.venv/bin/calcium-dff download                                   # 347 MB into data/raw/
.venv/bin/calcium-dff run data/raw/Sue_2x_3000_40_-46.tif --fps 30
.venv/bin/python -m pytest                                       # synthetic-data tests
```

Results land in `outputs/`:

| File | Contents |
|---|---|
| `dff.csv` | `time_s` plus one ΔF/F column per ROI |
| `dff.npz` | ΔF/F, F0, raw / neuropil / corrected fluorescence, ROI label mask, motion shifts, summary images |
| `dff_traces.png` | ΔF/F vs time for the most active ROIs |
| `dff_heatmap.png` | ΔF/F for every ROI |
| `rois.png` | mean image, correlation image, ROI outlines |
| `motion.png` | estimated x/y shift per frame |

## Dataset

`Sue_2x_3000_40_-46.tif`: two-photon GCaMP6f recording from mouse cortex, 3000 frames at
~30 Hz, distributed with [CaImAn](https://github.com/flatironinstitute/CaImAn)
(Giovannucci et al., eLife 2019). `data/` is not tracked by git.

## Method

| Stage | Module | What it does |
|---|---|---|
| Load | `io.py` | TIFF stack to float32 `(T, Y, X)` |
| Dark offset | `cli.py` | Subtract the pixel value of zero light (default: movie minimum; this dataset bottoms out at -296) |
| Motion correction | `motion.py` | Rigid: sub-pixel phase correlation of each frame against a template, two passes |
| Segmentation | `segment.py` | Local-correlation image, difference-of-Gaussians band-pass, robust threshold, watershed split, size and shape filter |
| Traces | `traces.py` | Mean fluorescence per ROI; neuropil from a surrounding ring that excludes other ROIs; `F = F_roi - 0.7 * (F_neuropil - median(F_neuropil))` |
| ΔF/F | `dff.py` | `F0` = running 8th percentile over 60 s of the 1 s-smoothed trace; `ΔF/F = (F - F0) / F0` |

Main knobs (`calcium-dff run --help`): `--diameter` (cell size in pixels), `--threshold`
(detection strictness), `--neuropil-coeff`, `--dark-offset`, `--baseline-window`, `--baseline-percentile`.

## Limitations

- ΔF/F magnitudes depend on two conventions: the dark offset and the neuropil correction.
  The default offset (movie minimum) is an estimate; pass `--dark-offset` if the true value is
  known. Neuropil fluctuations are subtracted but its median level is kept, which gives
  smaller ΔF/F than subtracting the full neuropil signal.
- Motion correction is rigid only; no piecewise (non-rigid) correction.
- ROIs are non-overlapping masks; signals from overlapping cells are not demixed.
- Detection relies on activity, so cells that stay silent during the recording are missed.
- The percentile baseline lags fast drift by about half a window; shorten `--baseline-window`
  for recordings with strong bleaching.

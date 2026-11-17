# Usage

## Installation

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

This installs the package in editable mode (changes to `src/` take effect immediately), its
dependencies, `pytest`, and the `calcium-dff` command at `.venv/bin/calcium-dff`.

Either call tools by path (`.venv/bin/calcium-dff`) or activate the environment first
(`source .venv/bin/activate`) and drop the prefix. The examples below use the path form.

## Command line

### `calcium-dff download`

Downloads the demo movie (347 MB).

```bash
.venv/bin/calcium-dff download [--dest data/raw]
```

- Skips the download if a complete copy is already present.
- Downloads to a `.part` file and renames it only after the size matches, so an interrupted
  download never leaves a truncated movie in place.

### `calcium-dff run`

Runs the whole pipeline on one movie.

```bash
.venv/bin/calcium-dff run MOVIE [options]
```

| Option | Default | Meaning |
|---|---|---|
| `MOVIE` | required | Path to a single-channel TIFF stack, frames × height × width |
| `--out` | `outputs` | Folder for results (created if missing; existing files are overwritten) |
| `--fps` | `30` | Frame rate in Hz. Sets the time axis and converts the baseline window to frames |
| `--diameter` | `10` | Expected cell body diameter in pixels |
| `--threshold` | `2.0` | Detection strictness, in robust standard deviations above the image median. Lower finds more (and fainter) cells |
| `--neuropil-coeff` | `0.7` | Fraction of the neuropil fluctuation subtracted from each cell. `0` disables neuropil correction |
| `--dark-offset` | movie minimum | Pixel value that corresponds to zero light |
| `--baseline-window` | `60` | Length in seconds of the running window used for the baseline F0 |
| `--baseline-percentile` | `8` | Percentile of the window taken as F0 |
| `--skip-motion` | off | Skip motion correction (for movies that are already registered) |
| `--no-plots` | off | Write only `dff.csv` and `dff.npz` |

Progress is printed with elapsed time:

```
[   0.1s] Loaded data/raw/Sue_2x_3000_40_-46.tif: 3000 frames, 170x170 px, 100.0 s at 30 Hz
[   0.2s] Subtracted dark offset of -296
[   3.2s] Motion corrected: max |shift| y=2.30 px, x=3.00 px
[   3.4s] Detected 31 ROIs
[   3.8s] Computed dF/F (0 ROIs with a non-positive baseline)
[   4.4s] Wrote results to outputs/
```

If no cells are found the command exits with a message suggesting a lower `--threshold` or a
different `--diameter`.

## Running on your own movie

1. **Format.** Save the recording as one single-channel TIFF stack. Multi-channel or
   multi-plane files must be split first; the loader rejects anything that is not 3-D after
   removing singleton dimensions.
2. **Memory.** The whole movie is loaded into RAM as 32-bit floats, and motion correction
   makes a second copy. Budget roughly `2 × frames × height × width × 4` bytes, plus working
   space (about 1 GB for the demo movie).
3. **Frame rate.** Pass the true `--fps`. A wrong value shifts the time axis and changes the
   effective baseline window.
4. **Cell size.** Measure a typical cell body in pixels and pass it as `--diameter`.
5. **Dark offset.** If you know your detector's offset, pass `--dark-offset`. See
   [pipeline.md](pipeline.md#2-dark-offset) for why this matters.

```bash
.venv/bin/calcium-dff run my_recording.tif --fps 15.5 --diameter 14 --out outputs/my_recording
```

## Tuning

Always start from `rois.png`: the bottom-right panel shows the outlines on the correlation
image, which is what detection actually sees.

| Symptom | Try |
|---|---|
| Visible cells are not outlined | Lower `--threshold` (e.g. `1.5`) |
| Outlines on noise or on neuropil | Raise `--threshold` (e.g. `3`) |
| One outline covers two cells | Lower `--diameter` |
| One cell is split into pieces | Raise `--diameter` |
| Cells look smeared in the mean image; `motion.png` shows shifts pinned at a flat limit | Motion exceeds the 15 % clamp or is non-rigid; this pipeline cannot fix it |
| Traces slope up or down between events | Shorten `--baseline-window` (e.g. `30`) |
| Long bursts are flattened or the trace dips below 0 around them | Lengthen `--baseline-window`, or lower `--baseline-percentile` |
| Log reports ROIs "with a non-positive baseline" | The dark offset is too high; pass a lower `--dark-offset` |

## Python API

Every stage is an ordinary function that takes and returns NumPy arrays, so stages can be
run, inspected and swapped individually.

### Whole pipeline

```python
from calcium_imaging.cli import run_pipeline

result = run_pipeline(
    "data/raw/Sue_2x_3000_40_-46.tif",
    out_dir="outputs",
    fps=30.0,
    diameter=10.0,
)
result["dff"]      # (n_cells, n_frames) ΔF/F
result["f0"]       # (n_cells, n_frames) baseline
result["labels"]   # (height, width) int mask, 0 = background, k = cell k
result["shifts"]   # (n_frames, 2) applied motion shift as (dy, dx)
result["order"]    # cell indices sorted from most to least active
```

`run_pipeline` accepts the same settings as the command line (`threshold`, `neuropil_coeff`,
`baseline_window_s`, `baseline_percentile`, `dark_offset`, `skip_motion`, `make_plots`).

### Stage by stage

```python
import numpy as np
from calcium_imaging.io import load_movie
from calcium_imaging.motion import correct_motion
from calcium_imaging.segment import segment_movie
from calcium_imaging.traces import extract_traces
from calcium_imaging.dff import compute_dff

fps = 30.0
movie = load_movie("data/raw/Sue_2x_3000_40_-46.tif")   # (T, Y, X) float32
movie -= movie.min()                                     # dark offset

corrected, shifts, template = correct_motion(movie)
labels, images = segment_movie(corrected, diameter=10, threshold=2.0)
traces = extract_traces(corrected, labels, neuropil_coeff=0.7)
dff, f0 = compute_dff(traces["corrected"], fps, window_s=60, percentile=8)

t = np.arange(dff.shape[1]) / fps    # seconds
```

### Function reference

| Function | Input | Returns |
|---|---|---|
| `download.download(dest_dir, url)` | folder | `Path` of the saved movie |
| `io.load_movie(path)` | TIFF path | `(T, Y, X)` float32 array |
| `motion.correct_motion(movie, n_iter, upsample, sigma, max_shift)` | movie | `(corrected, shifts, template)` |
| `motion.make_template(movie)` | movie | `(Y, X)` reference image |
| `motion.estimate_shifts(movie, template, …)` | movie, template | `(T, 2)` shifts as `(dy, dx)` |
| `motion.apply_shifts(movie, shifts)` | movie, shifts | translated movie |
| `segment.segment_movie(movie, diameter, threshold, bin_frames)` | registered movie | `(labels, {"mean", "correlation"})` |
| `segment.correlation_image(movie)` | movie | `(Y, X)` local-correlation image |
| `segment.detect_rois(image, diameter, threshold, min_circularity, border)` | any summary image | `(Y, X)` int32 label mask |
| `traces.extract_traces(movie, labels, neuropil_coeff)` | movie, labels | dict of `raw`, `neuropil`, `corrected`, each `(n_cells, T)` |
| `traces.neuropil_masks(labels, inner_gap, width, min_pixels)` | labels | list of boolean ring masks |
| `dff.compute_dff(traces, fps, window_s, percentile)` | `(n_cells, T)` traces | `(dff, f0)` |
| `dff.rolling_baseline(traces, fps, window_s, percentile, smooth_s)` | traces | `f0` |
| `plotting.plot_rois / plot_traces / plot_heatmap / plot_motion` | results, output path | writes a PNG |

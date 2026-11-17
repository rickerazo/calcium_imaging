# Output files

`calcium-dff run` writes six files to the output folder (default `outputs/`). Existing files
with the same names are overwritten.

## Cell numbering

Cells are numbered from 1 in the order detection produced them. The numbering has no
meaning beyond identification, but it is consistent everywhere:

| Where | Cell *k* appears as |
|---|---|
| `dff.csv` | column `roi_k` |
| `dff.npz` trace arrays | row `k − 1` (arrays are zero-indexed) |
| `dff.npz` `labels` | pixels with value `k` |
| `rois.png` | the number `k` printed on the outline |
| `dff_traces.png` | the label `ROI k` |

Numbers are not stable between runs with different settings.

## `dff.csv`

Plain text, one row per frame.

| Column | Meaning |
|---|---|
| `time_s` | Time of the frame in seconds, `frame_index / fps`, starting at 0 |
| `roi_1` … `roi_N` | ΔF/F of each cell, as a fraction (1.0 = 100 %) |

Values are written to 5 decimal places. Samples where the baseline was not positive are
empty.

```python
import pandas as pd
df = pd.read_csv("outputs/dff.csv")
df.plot(x="time_s", y="roi_1")
```

## `dff.npz`

Compressed NumPy archive with everything needed to inspect or redo later stages. `N` is the
number of cells, `T` the number of frames, `Y × X` the image size.

| Key | Shape | Type | Meaning |
|---|---|---|---|
| `dff` | `(N, T)` | float32 | ΔF/F |
| `f0` | `(N, T)` | float32 | Baseline used for each sample |
| `f_corrected` | `(N, T)` | float32 | Neuropil-corrected fluorescence; `dff = (f_corrected − f0) / f0` |
| `f_raw` | `(N, T)` | float32 | Mean fluorescence inside each cell mask |
| `f_neuropil` | `(N, T)` | float32 | Mean fluorescence in each cell's surrounding ring |
| `time_s` | `(T,)` | float64 | Frame times in seconds |
| `fps` | scalar | float64 | Frame rate used |
| `dark_offset` | scalar | float64 | Value subtracted from the movie |
| `labels` | `(Y, X)` | int32 | Cell mask: 0 = background, `k` = cell `k` |
| `shifts_yx` | `(T, 2)` | float32 | Shift applied to each frame, `(dy, dx)` in pixels |
| `mean_image` | `(Y, X)` | float32 | Time average of the motion-corrected movie |
| `correlation_image` | `(Y, X)` | float32 | Local-correlation image used for detection |

All fluorescence values are in the movie's own units after dark-offset subtraction.

```python
import numpy as np

d = np.load("outputs/dff.npz")
dff, t, labels = d["dff"], d["time_s"], d["labels"]

k = 5                           # cell number as shown in the figures
trace = dff[k - 1]              # its ΔF/F trace
mask = labels == k              # its pixels
area_px = mask.sum()
cy, cx = np.argwhere(mask).mean(axis=0)   # centre (row, column)
```

## Figures

All figures are PNG at 160 dpi.

### `rois.png`

Four panels: the mean image, the local-correlation image, and each of them again with the
detected cell outlines and numbers. Use the bottom-right panel to judge detection, since the
correlation image is what the detector works from.

### `dff_traces.png`

ΔF/F against time for the 20 cells with the highest signal-to-noise score, most active at
the top. Traces are offset vertically for readability, so there is no y-axis; the scale bar
at the bottom right shows a ΔF/F of 1.0.

### `dff_heatmap.png`

Every cell as one row, time on the x-axis, colour showing ΔF/F. Rows are sorted from most to
least active (row position is rank, not cell number). The colour scale runs from 0 to the
99.5th percentile, so the very largest events saturate and negative values appear as 0.

### `motion.png`

The x and y shift applied to each frame, in pixels. Use it to check that motion was small
and that the correction did not hit its limit (a trace pinned flat at a maximum value).

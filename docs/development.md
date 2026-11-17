# Development

## Layout

```
pyproject.toml              package metadata, dependencies, the calcium-dff entry point
README.md
docs/                       this documentation, with example figures in docs/images/
src/calcium_imaging/
  __init__.py
  download.py               fetch the demo dataset
  io.py                     load a TIFF stack
  motion.py                 rigid motion correction
  segment.py                correlation image and cell detection
  traces.py                 fluorescence and neuropil extraction
  dff.py                    baseline and ΔF/F
  plotting.py               figures
  cli.py                    run_pipeline() and the command-line interface
tests/
  conftest.py               synthetic movie fixture
  test_pipeline.py          tests for each stage and the whole pipeline
data/                       downloaded movies (not tracked)
outputs/                    results (not tracked)
```

Each stage module depends only on NumPy, SciPy, scikit-image or OpenCV, never on another
stage. `cli.py` is the only place where stages are chained, so that is where to look to see
the order of operations and where to add a step.

## Conventions

- Movies are `(T, Y, X)` float32 arrays: frames, rows, columns.
- Traces are `(n_cells, T)`.
- Image coordinates and shifts are in `(y, x)` = `(row, column)` order, as in NumPy.
- Label masks are int32 with 0 as background and cells numbered from 1; cell `k` is row
  `k − 1` of any trace array.
- Time-based parameters are given in seconds and converted to frames using `fps`.

## Dependencies

| Package | Used for |
|---|---|
| numpy | arrays |
| scipy | filters (Gaussian, percentile, morphology) |
| scikit-image | phase correlation, watershed, region properties |
| opencv-python-headless | fast frame translation and blurring |
| tifffile | reading TIFF stacks |
| matplotlib | figures |
| pandas | writing `dff.csv` |
| pytest (dev) | tests |

Versions are not pinned. The pipeline was developed with Python 3.12, NumPy 2.5,
SciPy 1.18, scikit-image 0.26 and OpenCV 5.1.

## Tests

```bash
.venv/bin/python -m pytest
```

The tests run in a couple of seconds and do not need the demo dataset. They use a synthetic
movie built in `tests/conftest.py`: six Gaussian-shaped cells on a flat background, each
firing five transients with an exponential decay, plus noise. Because the true cell
positions and activity are known, each stage can be checked against the truth.

| Test | Checks |
|---|---|
| `test_dff_recovers_known_amplitude` | A 50 % step on a slowly bleaching baseline gives ΔF/F = 0.5, and the baseline is recovered within 2 % |
| `test_dff_marks_nonpositive_baseline` | A negative baseline produces `NaN`, not a number |
| `test_motion_recovers_known_shifts` | Random shifts of up to 3 px are recovered to within 0.5 px |
| `test_segmentation_finds_planted_cells` | All six cells are found, none merged, at most one false positive |
| `test_traces_follow_ground_truth` | Each extracted ΔF/F trace correlates above 0.95 with the true activity |
| `test_end_to_end_writes_outputs` | The full pipeline runs from a TIFF file and writes all six outputs |

scikit-image currently emits a NumPy deprecation warning during the segmentation tests. It
comes from inside the library and does not affect results.

The synthetic movie is much cleaner than real data. Passing tests show the code does what it
is designed to do; they do not show that detection is accurate on real recordings.

## Changing the pipeline

**Tune an existing stage.** Parameters that are not exposed on the command line (for example
`bin_frames`, `min_circularity`, the neuropil ring size, `smooth_s`) are keyword arguments of
the stage functions. To expose one, add an argument to `run_pipeline` and a matching
`add_argument` in `main`, both in `cli.py`.

**Replace a stage.** Keep the input and output shapes described in
[usage.md](usage.md#function-reference) and change the call in `run_pipeline`. For example,
a different detector only needs to return a `(Y, X)` int32 label mask.

**Add an output.** Add the array to the `np.savez_compressed` call in `run_pipeline`, or a
new function to `plotting.py` called from the `if make_plots:` block, and document it in
[outputs.md](outputs.md).

**Support another dataset.** `download.download` accepts any URL; the size check applies
only to the built-in demo file.

## Possible next steps

- Score detection against hand-labelled data (the Neurofinder datasets include ground-truth
  outlines).
- Piecewise (non-rigid) motion correction.
- Demixing of overlapping cells.
- Memory-mapped loading for movies that do not fit in RAM.
- Spike inference from the ΔF/F traces.

import numpy as np
import tifffile

from calcium_imaging.cli import run_pipeline
from calcium_imaging.dff import compute_dff
from calcium_imaging.motion import apply_shifts, correct_motion
from calcium_imaging.segment import segment_movie
from calcium_imaging.traces import extract_traces


def test_dff_recovers_known_amplitude():
    fps, n = 30.0, 3000
    # Slow bleaching (~1.5% over the recording). A running low percentile lags
    # a falling baseline by about half a window, so much faster drift than
    # this would need a shorter window.
    f0_true = 200.0 * np.exp(-np.arange(n) / 200000.0)
    rel = np.zeros(n)
    rel[1000:1030] = 0.5
    dff, f0 = compute_dff(f0_true * (1 + rel), fps)
    assert dff.shape == (1, n)
    assert abs(dff[0, 1010] - 0.5) < 0.02
    assert np.abs(dff[0, :900]).max() < 0.02
    assert np.allclose(f0[0], f0_true, rtol=0.02)


def test_dff_marks_nonpositive_baseline():
    dff, _ = compute_dff(np.full((1, 500), -5.0), fps=30.0)
    assert np.isnan(dff).all()


def test_motion_recovers_known_shifts(synthetic):
    rng = np.random.default_rng(1)
    movie = synthetic["movie"][:200]
    true = rng.uniform(-3, 3, size=(len(movie), 2)).astype(np.float32)
    true[0] = 0
    moved = apply_shifts(movie, true)
    _, est, _ = correct_motion(moved)
    # Correction undoes the motion up to a constant offset set by the template.
    resid = est + true
    resid -= np.median(resid, axis=0)
    assert np.abs(resid).max() < 0.5


def test_segmentation_finds_planted_cells(synthetic):
    labels, _ = segment_movie(synthetic["movie"], diameter=10)
    found = {labels[cy, cx] for cy, cx in synthetic["centers"]}
    assert 0 not in found, "a planted cell was missed"
    assert len(found) == len(synthetic["centers"]), "two cells were merged"
    assert labels.max() <= len(synthetic["centers"]) + 1, "too many false positives"


def test_traces_follow_ground_truth(synthetic):
    labels, _ = segment_movie(synthetic["movie"], diameter=10)
    tr = extract_traces(synthetic["movie"], labels)
    dff, _ = compute_dff(tr["corrected"], synthetic["fps"])
    for (cy, cx), act in zip(synthetic["centers"], synthetic["activity"]):
        r = np.corrcoef(dff[labels[cy, cx] - 1], act)[0, 1]
        assert r > 0.95


def test_end_to_end_writes_outputs(synthetic, tmp_path):
    src = tmp_path / "movie.tif"
    tifffile.imwrite(src, synthetic["movie"])
    out = tmp_path / "out"
    res = run_pipeline(src, out_dir=out, fps=synthetic["fps"])
    assert res["dff"].shape[1] == len(synthetic["movie"])
    for name in ["dff.csv", "dff.npz", "rois.png", "dff_traces.png", "dff_heatmap.png", "motion.png"]:
        assert (out / name).stat().st_size > 0

import numpy as np
import pytest


@pytest.fixture
def synthetic():
    """Movie with 6 Gaussian cells firing independent exponential transients."""
    rng = np.random.default_rng(0)
    t, h, w, fps = 600, 64, 64, 30.0
    centers = [(14, 14), (14, 46), (32, 30), (48, 14), (48, 48), (30, 52)]
    yy, xx = np.mgrid[:h, :w]
    kernel = np.exp(-np.arange(90) / (0.5 * fps))

    movie = np.full((t, h, w), 100.0, dtype=np.float32)
    activity = []
    for cy, cx in centers:
        spikes = np.zeros(t)
        spikes[rng.choice(np.arange(30, t - 90), size=5, replace=False)] = 1.0
        act = np.convolve(spikes, kernel)[:t]
        activity.append(act)
        footprint = np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * 3.0**2))
        movie += (footprint[None] * (40 + 160 * act[:, None, None])).astype(np.float32)
    movie += rng.normal(0, 3, movie.shape).astype(np.float32)
    return {"movie": movie, "centers": centers, "fps": fps, "activity": np.array(activity)}

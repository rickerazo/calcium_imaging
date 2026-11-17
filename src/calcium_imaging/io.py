"""Movie loading."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile


def load_movie(path: str | Path) -> np.ndarray:
    """Load a TIFF stack as a float32 array of shape (T, Y, X)."""
    movie = tifffile.imread(str(path))
    movie = np.squeeze(movie)
    if movie.ndim != 3:
        raise ValueError(
            f"Expected a single-channel (T, Y, X) movie, got shape {movie.shape}"
        )
    return movie.astype(np.float32, copy=False)

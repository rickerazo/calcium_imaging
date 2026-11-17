"""Fetch the public demo dataset."""

from __future__ import annotations

import urllib.request
from pathlib import Path

# Two-photon GCaMP6f recording from mouse cortex distributed with CaImAn
# (Giovannucci et al., eLife 2019). 3000 frames, ~30 Hz.
DATASET_URL = (
    "https://caiman.flatironinstitute.org/~neuro/caiman_downloadables/"
    "Sue_2x_3000_40_-46.tif"
)
DATASET_BYTES = 347_214_136
DATASET_FPS = 30.0


def download(dest_dir: str | Path = "data/raw", url: str = DATASET_URL) -> Path:
    """Download the dataset into ``dest_dir``; skip if a complete copy exists."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / url.rsplit("/", 1)[-1]

    if dest.exists() and (url != DATASET_URL or dest.stat().st_size == DATASET_BYTES):
        print(f"Already present: {dest}")
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        next_report = 0.1
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if total and done / total >= next_report:
                print(f"  {done / total:4.0%}  ({done / 1e6:.0f} MB)")
                next_report += 0.1

    if url == DATASET_URL and tmp.stat().st_size != DATASET_BYTES:
        raise IOError(
            f"Incomplete download: got {tmp.stat().st_size} bytes, "
            f"expected {DATASET_BYTES}. Partial file left at {tmp}."
        )
    tmp.replace(dest)
    print(f"Saved {dest}")
    return dest

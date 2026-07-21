"""Sample-normalization helpers."""

from __future__ import annotations

import math
from typing import Mapping


def sm_chunk_weights(sample: Mapping) -> dict[str, float | int | bool]:
    """Return per-event SM shape and physical cross-section weights.

    Each production chunk is an independent MC estimate of the same process.
    A per-chunk template therefore uses the actual number written in that
    chunk. Combining multiple chunk templates requires an average, not a sum.
    """
    n_written = int(sample["n_events_per_chunk"])
    if n_written <= 0:
        raise ValueError("n_events_per_chunk must be positive")
    shape_weight = 1.0 / n_written
    cross_section = sample.get("cross_section_fb")
    if cross_section is None:
        physical_weight = math.nan
        normalized = False
    else:
        cross_section = float(cross_section)
        if not math.isfinite(cross_section) or cross_section <= 0.0:
            raise ValueError("cross_section_fb must be finite and positive")
        physical_weight = cross_section / n_written
        normalized = True
    return {
        "n_written": n_written,
        "shape_weight": shape_weight,
        "physical_weight_fb": physical_weight,
        "has_physical_normalization": normalized,
    }

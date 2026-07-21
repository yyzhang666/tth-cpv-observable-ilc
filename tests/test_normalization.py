"""Tests for SM event normalization."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.normalization import sm_chunk_weights


def test_sm_chunk_weights_with_cross_section():
    result = sm_chunk_weights({
        "n_events_per_chunk": 11505,
        "cross_section_fb": 2.96055,
    })
    assert result["n_written"] == 11505
    assert result["shape_weight"] == pytest.approx(1.0 / 11505)
    assert result["physical_weight_fb"] == pytest.approx(2.96055 / 11505)
    assert result["has_physical_normalization"] is True


def test_sm_chunk_weights_without_cross_section_keeps_shape():
    result = sm_chunk_weights({"n_events_per_chunk": 11515})
    assert result["shape_weight"] == pytest.approx(1.0 / 11515)
    assert math.isnan(result["physical_weight_fb"])
    assert result["has_physical_normalization"] is False


@pytest.mark.parametrize("n_written", [0, -1])
def test_sm_chunk_weights_rejects_invalid_count(n_written):
    with pytest.raises(ValueError, match="positive"):
        sm_chunk_weights({"n_events_per_chunk": n_written})


@pytest.mark.parametrize("cross_section", [0.0, -1.0, math.inf])
def test_sm_chunk_weights_rejects_invalid_cross_section(cross_section):
    with pytest.raises(ValueError, match="cross_section_fb"):
        sm_chunk_weights({
            "n_events_per_chunk": 100,
            "cross_section_fb": cross_section,
        })

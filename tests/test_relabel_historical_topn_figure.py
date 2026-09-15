"""Focused checks for the presentation-only historical TopN relabel."""

import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "relabel_historical_topn_figure",
    ROOT / "scripts/reco_performance/relabel_historical_topn_figure.py",
)
RELABEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELABEL)


def test_only_current_user_facing_labels_are_exposed():
    assert RELABEL.PREFIT_LABEL == "mass constraint-only + q_flavor minimize"
    assert RELABEL.POSTFIT_LABEL == "q_reco minimize"
    assert RELABEL.TOP_NS == (1, 5, 10, 20, 30, 45, 60, 90, 180)


def test_changed_topn_grid_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["top_n", "price2014_signed_A_all", "kinfit_signed_A_all", "wall_seconds"],
        )
        writer.writeheader()
        writer.writerow({"top_n": 1, "price2014_signed_A_all": 0.1, "kinfit_signed_A_all": 0.1, "wall_seconds": ""})
    with pytest.raises(RuntimeError, match="TopN grid changed"):
        RELABEL.read_frozen_rows(path)

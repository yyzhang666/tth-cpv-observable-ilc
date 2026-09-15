"""Focused presentation-only CM restyle tests."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "restyle_whizard_jet_cm",
    ROOT / "scripts/reco_performance/restyle_whizard_jet_cm.py",
)
RESTYLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESTYLE)


def test_annotation_contrast_changes_on_cividis_background():
    assert RESTYLE.annotation_color(0.0, 0.7) == "white"
    assert RESTYLE.annotation_color(0.7, 0.7) == "black"


def test_frozen_title_and_labels_are_preserved():
    assert "RefinedJets6–TrueJets six-positive-Dice matching; Weaver 10x10" in RESTYLE.TITLE
    assert len(RESTYLE.DISPLAY_LABELS) == 10

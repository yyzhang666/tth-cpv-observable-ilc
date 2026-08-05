"""Tests for electron/muon table filtering and channel categorisation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from scripts.build_angular_observable import filter_rows


def make_fake_rows():
    """Synthetic feature-table rows to test the row filtering function - no real particles."""
    return [
        {"event_id": 1, "split": "test", "lepton_flavor": "electron"},
        {"event_id": 2, "split": "test", "lepton_flavor": "muon"},
        {"event_id": 3, "split": "test", "lepton_flavor": "electron"},
        {"event_id": 4, "split": "test", "lepton_flavor": "muon"},
        {"event_id": 5, "split": "test", "lepton_flavor": "electron"},
    ]

def test_electron_and_muon_rows_disjoint():
    """Test if filter_rows() correctly separates eletron and muon events."""
    rows = make_fake_rows()

    electron_rows = filter_rows(rows, lepton_flavor="electron")
    muon_rows = filter_rows(rows, lepton_flavor="muon")

    electron_ids = {row["event_id"] for row in electron_rows}
    muon_ids = {row["event_id"] for row in muon_rows}

    assert electron_ids.isdisjoint(muon_ids) # returns True if two sets have zero elements in common


def test_electron_plus_muon_union_equals_all():
    """Test if filter_rows() successfully separates all rows (no missing data)."""
    rows = make_fake_rows()

    all_rows = filter_rows(rows, lepton_flavor="all")
    electron_rows = filter_rows(rows, lepton_flavor="electron")
    muon_rows = filter_rows(rows, lepton_flavor="muon")

    all_ids = {row["event_id"] for row in all_rows}
    electron_ids = {row["event_id"] for row in electron_rows}
    muon_ids = {row["event_id"] for row in muon_rows}

    assert electron_ids | muon_ids == all_ids # True if electron_ids + muon_ids are the same as all_ids
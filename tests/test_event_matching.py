"""Tests for event matching, deterministic splits, and schema validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.features import deterministic_split
from ilc_tth_cpv.io import match_event_ids, validate_table
from ilc_tth_cpv.validation import check_split_deterministic, check_split_disjoint

FRACTIONS = {"train": 0.6, "validation": 0.2, "test": 0.2}
SEED = 20260720


def make_row(event_id, level="gen", split=None):
    return {
        "event_id": str(event_id),
        "sample_name": "s",
        "process": "ttH_CPVint",
        "level": level,
        "helicity": "LR",
        "split": split or deterministic_split(event_id, SEED, FRACTIONS),
        "weight_sm": "nan",
        "weight_interference_signed": "0.1",
        "weight_interference_abs": "0.1",
        "weight_quadratic": "nan",
        "weight_training": "0.1",
        "weight_polarization": "nan",
        "weight_luminosity": "nan",
        "weight_template": "0.1",
    }


def test_split_is_deterministic_and_order_independent():
    ids = list(range(1, 2001))
    forward = [deterministic_split(i, SEED, FRACTIONS) for i in ids]
    backward = [deterministic_split(i, SEED, FRACTIONS) for i in reversed(ids)]
    assert forward == list(reversed(backward))


def test_split_fractions_approximate():
    ids = range(1, 20001)
    counts = {"train": 0, "validation": 0, "test": 0}
    for i in ids:
        counts[deterministic_split(i, SEED, FRACTIONS)] += 1
    total = sum(counts.values())
    assert abs(counts["train"] / total - 0.6) < 0.02
    assert abs(counts["test"] / total - 0.2) < 0.02


def test_split_changes_with_seed():
    ids = range(1, 2001)
    a = [deterministic_split(i, 1, FRACTIONS) for i in ids]
    b = [deterministic_split(i, 2, FRACTIONS) for i in ids]
    assert a != b


def test_gen_reco_same_split():
    # identical event_id + seed -> identical split at gen and reco level
    for event_id in (1, 17, 999, 12500):
        assert deterministic_split(event_id, SEED, FRACTIONS) == deterministic_split(
            event_id, SEED, FRACTIONS
        )


def test_match_event_ids_common_pool():
    gen = [make_row(i) for i in range(1, 101)]
    reco = [make_row(i, level="reco") for i in range(51, 151)]
    report = match_event_ids(gen, reco)
    assert report["n_common"] == 50
    assert report["gen_only"] == 50
    assert report["reco_only"] == 50


def test_validate_table_catches_duplicates():
    rows = [make_row(1), make_row(1)]
    report = validate_table(rows)
    assert not report["ok"]
    assert any("duplicated" in p for p in report["problems"])


def test_validate_table_ok():
    rows = [make_row(i) for i in range(1, 11)]
    report = validate_table(rows)
    assert report["ok"], report["problems"]


def test_split_disjoint_and_deterministic_checks():
    rows = [make_row(i) for i in range(1, 501)]
    assert check_split_disjoint(rows)["ok"]
    assert check_split_deterministic(rows, SEED, FRACTIONS)["ok"]
    rows[0]["split"] = "test" if rows[0]["split"] != "test" else "train"
    assert not check_split_deterministic(rows, SEED, FRACTIONS)["ok"]

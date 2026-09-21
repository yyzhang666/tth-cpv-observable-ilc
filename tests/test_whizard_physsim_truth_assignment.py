"""Focused tests for the frozen Whizard/common4730 PHYSSIM-truth adapter."""

from __future__ import annotations

import csv
import importlib.util
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "report_whizard_physsim_truth_assignment",
    ROOT / "scripts/reco_performance/report_whizard_physsim_truth_assignment.py",
)
REPORT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(REPORT)


def test_candidate_preserves_frozen_qreco_combo_and_explicit_indices():
    assignment = {"combo_id": 7, "W": (0, 1), "top_b": 2, "lep_b": 5, "H": (3, 4)}
    selected = {
        "source_file_id": "chunk", "local_index": 9, "run_number": 4,
        "event_number": 10, "kinfit_signed_combo_id": 7,
    }
    root_row = {
        "accepted": 1, "fit_success": 1, "best_combo_id": 7,
        "run_number": 4, "event_number": 10,
        "jet_collection_name": "OutputErrorFlowJets6",
        "flavor_jet_collection_name": "RefinedJets6",
        "idx_W1": 0, "idx_W2": 1, "idx_bhad": 2, "idx_blep": 5,
        "idx_H1": 3, "idx_H2": 4,
    }
    candidate = REPORT.validate_candidate_row(root_row, selected, assignment)
    assert candidate["best_combo_id"] == 7
    assert candidate["selected"] == {"W": [0, 1], "top": [2, 5], "H": [3, 4]}
    root_row["idx_H2"] = 5
    with pytest.raises(RuntimeError, match="explicit_indices_combo_mismatch"):
        REPORT.validate_candidate_row(root_row, selected, assignment)


def test_source_aware_mapping_rejects_cross_source_join(tmp_path):
    source_rows = [
        {
            "source_file_id": "chunk0", "local_index": 8, "run_number": 1,
            "event_number": 9,
        }
    ]
    mapping = tmp_path / "mapping.csv"
    with mapping.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_file_id", "filtered_local_index", "original_local_index",
                "run_number", "event_number",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_file_id": "chunk1", "filtered_local_index": 0,
                "original_local_index": 8, "run_number": 1, "event_number": 9,
            }
        )
    with pytest.raises(RuntimeError, match="mapping_key_mismatch"):
        REPORT.read_mapping(mapping, REPORT.sha256(mapping), source_rows)


def test_exclusive_rejection_closure_and_all_numerator_gate():
    per_source = {
        source: (
            Counter(base=count, evaluable=count - 1, W_correct=2, top_correct=2, H_correct=2, all_correct=1),
            Counter({"direct_b_truejet_multiplicity_4": 1}),
            Counter(),
        )
        for source, count in REPORT.EXPECTED_PER_SOURCE.items()
    }
    totals, reasons, _diagnostics = REPORT.aggregate(per_source)
    assert totals["base"] == 4730
    assert totals["evaluable"] + sum(reasons.values()) == 4730
    per_source["whizard_I410213_0"][0]["all_correct"] = 99
    with pytest.raises(RuntimeError, match="all-correct"):
        REPORT.aggregate(per_source)


class FakeHelper:
    def __init__(self, direct_b_count):
        self.direct_b_count = direct_b_count

    @staticmethod
    def get_collection(_event, name):
        return name

    @staticmethod
    def build_jet_pfo_infos(_collection):
        return [{"object": object()} for _ in range(6)]

    @staticmethod
    def build_collection_bridge(_fit, _refined, _minimum):
        return {
            "status": "evaluable", "reason": "", "mapping": {i: i for i in range(6)},
            "minimum_dice": 1.0,
        }

    def build_direct_b_truejet_infos(self, _collection, _navigator):
        return [{} for _ in range(self.direct_b_count)]

    @staticmethod
    def match_reco_to_top_truejets(_refined, direct_b, _minimum):
        if len(direct_b) != 2:
            return {
                "status": "unresolved",
                "reason": f"direct_b_truejet_multiplicity_{len(direct_b)}",
                "matches": {},
            }
        return {
            "status": "evaluable", "reason": "", "matches": {0: {}, 1: {}},
        }

    @staticmethod
    def build_seed_groups(_event, _collection):
        return {}, Counter(Hbb_seed_partons=2, topbb_seed_partons=2)

    @staticmethod
    def validate_seed_counts(_counts):
        return True, ""

    @staticmethod
    def analyze_jet_origin(info, *_args):
        return {"truth_origin_local": "Hbb" if id(info) < 0 else "other"}


class FakeUTIL:
    class LCRelationNavigator:
        def __init__(self, _collection):
            pass


def test_synthetic_two_vs_four_direct_b_truth_is_not_silently_loosened():
    candidate = {"selected": {"W": [0, 1], "top": [2, 5], "H": [3, 4]}}
    four = REPORT.evaluate_event(object(), candidate, FakeHelper(4), FakeUTIL)
    assert four["status"] == "unresolved"
    assert four["reason"] == "direct_b_truejet_multiplicity_4"
    two = REPORT.evaluate_event(object(), candidate, FakeHelper(2), FakeUTIL)
    assert not two["reason"].startswith("direct_b_truejet_multiplicity")


def test_coverage_label_boundary_and_zero_plot_contract():
    assert REPORT.diagnostic_status(95, 0.95) == "cross_generator_diagnostic"
    assert REPORT.diagnostic_status(94, 0.94) == "conditional_cross_generator_diagnostic"
    assert REPORT.diagnostic_status(0, 0.0) == "no_evaluable_events"
    assert REPORT.should_plot(1)
    assert not REPORT.should_plot(0)


def test_hard_failure_is_separate_from_truth_unresolved_reason():
    error = REPORT.hard("best_combo_mismatch", "event 3")
    assert isinstance(error, REPORT.IntegrityError)
    assert str(error).startswith("best_combo_mismatch:")
    truth_reason = "direct_b_truejet_multiplicity_4"
    assert truth_reason not in str(error)


def test_all_flag_is_exact_intersection():
    assert REPORT.validate_flags({"W": True, "top": True, "H": True, "all": True})["all"]
    with pytest.raises(RuntimeError, match="all flag"):
        REPORT.validate_flags({"W": True, "top": False, "H": True, "all": True})


def test_nonexclusive_diagnostics_do_not_invent_unreached_seed_counts():
    counters = Counter()
    REPORT.update_diagnostics(
        counters,
        {
            "status": "unresolved",
            "reason": "direct_b_truejet_multiplicity_4",
            "direct_b_truejet_multiplicity": 4,
        },
    )
    assert counters == Counter({"direct_b_truejet_multiplicity:4": 1})

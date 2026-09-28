"""Focused tests for the Whizard-origin/PHYSSIM-Hbb hybrid truth reporter."""

from __future__ import annotations

import importlib.util
import csv
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "report_whizard_hybrid_truth_assignment",
    ROOT / "scripts/reco_performance/report_whizard_hybrid_truth_assignment.py",
)
REPORT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(REPORT)


def info(role, index, pdg):
    return {
        "role": role,
        "truejet_index": index,
        "pdg": pdg,
        "truejet": object(),
        "pfo_ids": {index},
        "energy": 10.0,
    }


def test_origin_aware_selector_keeps_exact_had_and_lep_top_b_only():
    true_map = {
        10: info("H", 0, 5),
        11: info("top_had_b", 1, 5),
        12: info("other", 2, -5),
        13: info("top_lep_b", 3, -5),
        14: info("H", 4, -5),
    }
    selected = REPORT.select_origin_aware_top_truejets(true_map)
    assert selected["status"] == "evaluable"
    assert selected["selected_ids"] == [11, 13]
    assert [item["role"] for item in selected["selected_infos"]] == ["top_had_b", "top_lep_b"]
    assert 10 not in selected["selected_ids"]
    assert 12 not in selected["selected_ids"]


@pytest.mark.parametrize(
    "roles,reason",
    [
        (["top_lep_b"], "top_role_multiplicity_had_0_lep_1"),
        (["top_had_b", "top_had_b", "top_lep_b"], "top_role_multiplicity_had_2_lep_1"),
        (["top_had_b"], "top_role_multiplicity_had_1_lep_0"),
        (["top_had_b", "top_lep_b", "top_lep_b"], "top_role_multiplicity_had_1_lep_2"),
    ],
)
def test_origin_aware_selector_rejects_missing_or_duplicate_top_roles(roles, reason):
    true_map = {index: info(role, index, 5 if index % 2 == 0 else -5) for index, role in enumerate(roles)}
    selected = REPORT.select_origin_aware_top_truejets(true_map)
    assert selected["status"] == "unresolved"
    assert selected["reason"] == reason


def test_origin_aware_selector_is_exchange_safe_by_role_not_input_order():
    first = {
        51: info("top_lep_b", 7, -5),
        42: info("top_had_b", 2, 5),
    }
    second = {
        42: info("top_lep_b", 2, -5),
        51: info("top_had_b", 7, 5),
    }
    assert REPORT.select_origin_aware_top_truejets(first)["selected_ids"] == [42, 51]
    assert REPORT.select_origin_aware_top_truejets(second)["selected_ids"] == [51, 42]


class FakePhyssimHelper:
    @staticmethod
    def build_three_pair_truth_partition(top_indices, higgs_indices, _all_indices):
        top = sorted(top_indices)
        higgs = sorted(higgs_indices)
        if set(top) & set(higgs):
            return {"status": "unresolved", "reason": "top_higgs_overlap", "pairs": {}}
        w = sorted(set(range(6)) - set(top) - set(higgs))
        return {
            "status": "evaluable",
            "reason": "",
            "pairs": {"W": w, "top": top, "H": higgs},
        }

    @staticmethod
    def three_pair_assignment_flags(selected_w, selected_top, selected_h, truth):
        flags = {
            "W": sorted(selected_w) == truth["W"],
            "top": sorted(selected_top) == truth["top"],
            "H": sorted(selected_h) == truth["H"],
        }
        flags["all"] = all(flags.values())
        return {"status": "evaluable", "reason": "", "flags": flags}


def test_falsification_whizard_h_roles_cannot_replace_physsim_hbb_and_w_complement():
    # A canonical Whizard role map could call jets [0, 1] Higgs, while fixed
    # PHYSSIM RecoMC truth calls [4, 5] Hbb.  Only the latter may define H/W.
    selected = {"W": [0, 1], "top": [2, 3], "H": [4, 5]}
    result = REPORT.combine_physsim_h_w_truth(
        FakePhyssimHelper(), top_indices=[2, 3], higgs_indices=[4, 5], selected=selected
    )
    assert result["status"] == "evaluable"
    assert result["truth_partition"]["pairs"] == {
        "W": [0, 1], "top": [2, 3], "H": [4, 5]
    }
    assert result["flags"] == {"W": True, "top": True, "H": True, "all": True}


def test_hybrid_label_and_thresholds_are_frozen():
    assert REPORT.BRIDGE_MINIMUM_DICE == 0.95
    assert REPORT.TOP_MINIMUM_DICE == 0.2
    assert "not pure PHYSSIM truth" in REPORT.TRUTH_DEFINITION
    assert "not canonical Whizard truth" in REPORT.TRUTH_DEFINITION


def test_smoke_signature_contains_every_contracted_equality_field():
    result = {
        "status": "evaluable",
        "reason": "",
        "bridge": {"mapping": {"0": 0}},
        "selected_top_truejet_object_ids_nonpersistent": [4, 8],
        "selected_top_truejet_stable": [
            {"truejet_index": 2, "direct_pdg": 5, "role": "top_had_b"},
            {"truejet_index": 7, "direct_pdg": -5, "role": "top_lep_b"},
        ],
        "top_match": {"indices": [1, 4], "dice": {"1": 0.8, "4": 0.9}},
        "higgs_indices": [1, 5],
        "truth_partition": {"pairs": {"W": [0, 2]}},
        "flags": {"W": True},
        "diagnostic_only": 123,
    }
    assert REPORT.smoke_signature(result) == {
        "status": "evaluable",
        "reason": "",
        "bridge": {"mapping": {"0": 0}},
        "selected_top_truejet_stable": [
            {"truejet_index": 2, "direct_pdg": 5, "role": "top_had_b"},
            {"truejet_index": 7, "direct_pdg": -5, "role": "top_lep_b"},
        ],
        "top_match": {"indices": [1, 4], "dice": {"1": 0.8, "4": 0.9}},
        "higgs_indices": [1, 5],
        "truth_partition": {"pairs": {"W": [0, 2]}},
        "flags": {"W": True},
    }


def test_smoke_identity_ignores_raw_object_ids_but_rejects_stable_tuple_change():
    base = {
        "status": "evaluable",
        "reason": "",
        "bridge": {"mapping": {"0": 0}},
        "selected_top_truejet_stable": [
            {"truejet_index": 2, "direct_pdg": 5, "role": "top_had_b"},
            {"truejet_index": 7, "direct_pdg": -5, "role": "top_lep_b"},
        ],
        "top_match": {"indices": [1, 4], "dice": {"1": 0.8, "4": 0.9}},
        "higgs_indices": [0, 5],
        "truth_partition": {"pairs": {"H": [0, 5]}},
        "flags": {"H": True},
    }
    rewritten = {**base, "selected_top_truejet_object_ids_nonpersistent": [9001, 9002]}
    original = {**base, "selected_top_truejet_object_ids_nonpersistent": [101, 102]}
    assert REPORT.smoke_signature(original) == REPORT.smoke_signature(rewritten)
    changed = {
        **rewritten,
        "selected_top_truejet_stable": [
            {"truejet_index": 3, "direct_pdg": 5, "role": "top_had_b"},
            {"truejet_index": 7, "direct_pdg": -5, "role": "top_lep_b"},
        ],
    }
    assert REPORT.smoke_signature(original) != REPORT.smoke_signature(changed)


def test_pinned_hash_arguments_cannot_be_redefined():
    assert REPORT.PHYSSIM_SHA256 == "0d058caa16ab8e1f560c8cc75d817c5b4ec29a67cb5edd720d0472fb54d9fd33"
    assert REPORT.WHIZARD_TRUTH_SHA256 == "c117466ccd9cd8dca2ff90686f5c937ca32300367c75da32614eee7e04b128f0"
    assert REPORT.CHI2_RECO_SHA256 == "e7c9bbca72afef927ce99786855ec75b651a38c77805ebd9c5490130ecc7d174"


def test_formatting_only_redraw_has_separated_large_canvas_and_frozen_metrics(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    summary = {
        "selection_base_denominator": 4730,
        "evaluable_denominator": 4000,
        "coverage": 4000 / 4730,
        "accuracies": {"W": 0.8, "top": 0.6, "H": 0.5, "all": 0.4},
    }
    (source / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    with (source / "assignment_accuracy.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "selection_base_denominator", "evaluable_denominator", "coverage",
                "A_W", "A_top", "A_H", "A_all",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "selection_base_denominator": 4730,
                "evaluable_denominator": 4000,
                "coverage": 4000 / 4730,
                "A_W": 0.8,
                "A_top": 0.6,
                "A_H": 0.5,
                "A_all": 0.4,
            }
        )
    output = tmp_path / "redraw"
    assert REPORT.redraw_from_existing(source, output, None) == 0
    assert (output / "assignment_accuracy_hybrid_truth_qreco.pdf").stat().st_size > 1000
    import matplotlib.image as mpimg

    image = mpimg.imread(output / "assignment_accuracy_hybrid_truth_qreco.png")
    assert image.shape[1] >= 1900
    assert image.shape[0] >= 1300
    manifest = json.loads((output / "redraw_manifest.json").read_text(encoding="utf-8"))
    assert manifest["physics_and_data_changed"] is False
    assert manifest["metrics"]["A_all"] == 0.4
    with pytest.raises(RuntimeError, match="refusing to reuse"):
        REPORT.redraw_from_existing(source, output, None)

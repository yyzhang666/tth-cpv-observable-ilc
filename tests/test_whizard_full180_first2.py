"""Focused dependency-free tests for the frozen full180 correction."""

import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FILTER = load(
    "filter_whizard_selected_common_lcio",
    "scripts/reco_performance/filter_whizard_selected_common_lcio.py",
)
REPORT = load(
    "report_whizard_full180_first2",
    "scripts/reco_performance/report_whizard_full180_first2.py",
)


def test_exact_display_and_internal_contract():
    assert [row["display_label"] for row in REPORT.DISPLAY] == [
        "mass constraint-only [full180]",
        "kinfit-only [full180]",
        "mass constraint-only + q_flavor minimize [signed-flavor-preselected Top10]",
        "q_reco minimize [signed-flavor-preselected Top10]",
    ]
    assert [row["internal_mode"] for row in REPORT.DISPLAY[:2]] == [
        "price2014_prefit", "kinfit_chi2_only",
    ]
    assert [row["stage"] for row in REPORT.DISPLAY] == [
        "PREFIT", "POSTFIT", "PREFIT", "POSTFIT",
    ]


def test_first10_overlap_uses_filtered_to_original_mapping():
    mapping = {0: ("chunk", 17, 2, 3)}
    full = {0: {"combo_ids": list(range(180))}}
    top10 = {17: {"combo_ids": list(range(10))}}
    assert REPORT.validate_first10(full, top10, mapping, "chunk") == 1
    full[0]["combo_ids"][9], full[0]["combo_ids"][10] = (
        full[0]["combo_ids"][10], full[0]["combo_ids"][9]
    )
    with pytest.raises(RuntimeError, match="first-10 overlap failed"):
        REPORT.validate_first10(full, top10, mapping, "chunk")


def test_copied_top10_numeric_fields_are_string_exact(tmp_path):
    path = tmp_path / "accuracy.csv"
    fields = ["method", *REPORT.NUMERIC_FIELDS]
    rows = []
    for method in REPORT.COPIED_METHODS:
        rows.append({"method": method, **{
            field: "4730" if field == "denominator" else f"{len(rows)+1}.000"
            for field in REPORT.NUMERIC_FIELDS
        }})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    copied = REPORT.copied_rows(path)
    for index, row in enumerate(copied):
        expected = "1.000" if index == 0 else "2.000"
        assert row["A_all"] == expected
        assert row["denominator"] == "4730"


def test_filter_requires_exact_4730_unique_keys(tmp_path):
    path = tmp_path / "selected.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILTER.KEY_FIELDS)
        writer.writeheader()
        for index in range(4730):
            writer.writerow({
                "source_file_id": f"chunk{index % 4}",
                "local_index": index,
                "run_number": 1,
                "event_number": index,
            })
    assert len(FILTER.read_keys(path)) == 4730
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FILTER.KEY_FIELDS)
        writer.writerow({
            "source_file_id": "chunk0", "local_index": 0,
            "run_number": 1, "event_number": 0,
        })
    with pytest.raises(RuntimeError, match="4730 unique"):
        FILTER.read_keys(path)

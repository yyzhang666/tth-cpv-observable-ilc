"""Focused contracts for the Whizard Top1/5/10 scan."""

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "report_whizard_topn_scan",
    ROOT / "scripts/reco_performance/report_whizard_topn_scan.py",
)
SCAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCAN)


def test_scan_is_only_top1_top5_top10_and_two_frozen_methods():
    assert SCAN.TOP_NS == (1, 5, 10)
    assert SCAN.METHODS == {
        "mass constraint-only + q_flavor minimize": {
            "internal_mode": "price2014_prefit_bcharge1p00",
            "stage": "PREFIT",
            "candidate_pool": "signed-flavor-preselected TopN",
        },
        "q_reco minimize": {
            "internal_mode": "authoritative_best_tree",
            "stage": "POSTFIT",
            "candidate_pool": "signed-flavor-preselected TopN",
        },
    }


def test_topn_alignment_preserves_all_sld_rows():
    combo_ids = [8, 4, 2, 9, 1]
    rows = [
        {"candidate_rank": rank, "combo_id": combo_id}
        for rank, combo_id in enumerate(combo_ids)
        for _ in range(rank + 1)
    ]
    assert SCAN.topn_rows_aligned(rows, combo_ids, 5)
    rows[-1]["combo_id"] = 999
    assert not SCAN.topn_rows_aligned(rows, combo_ids, 5)


def test_runtime_is_parsed_from_processor_and_total_log(tmp_path):
    log = tmp_path / "marlin.log"
    log.write_text(
        '[ MESSAGE "MyTTHSemiLepKinFit"] \tTopN:  5\n'
        '[ MESSAGE "MyTTHSemiLepKinFit"] TTHSemiLepKinFit processed 12499 events, accepted 10, fit successes 9, dry-run rows 0\n'
        '[ MESSAGE "Marlin"] MyTTHSemiLepKinFit  1.250000e+02 s in 12499 events ==> 1e-2 [ s/evt.]\n'
        '[ MESSAGE "Marlin"]             Total: 1.260000e+02 s in 12499 events ==> 1e-2 [ s/evt.]\n',
        encoding="utf-8",
    )
    parsed = SCAN.parse_marlin_runtime(log, 5, 12499)
    assert parsed == {"processor_seconds": 125.0, "total_seconds": 126.0, "events": 12499}
    with pytest.raises(RuntimeError, match="TopN timing-log mismatch"):
        SCAN.parse_marlin_runtime(log, 1, 12499)


def test_root_hash_mismatch_stops(tmp_path):
    root = tmp_path / "input.root"
    root.write_bytes(b"content")
    with pytest.raises(RuntimeError, match="ROOT hash mismatch"):
        SCAN.verify_root({"root": str(root), "root_sha256": "0" * 64})


def test_condor_submit_has_eight_independent_top1_top5_jobs_only():
    text = (
        ROOT / "condor/reco_performance/whizard_topn_phase2.sub"
    ).read_text(encoding="utf-8")
    queue_rows = [line for line in text.splitlines() if line.startswith(("1,", "5,"))]
    assert len(queue_rows) == 8
    assert "--expected-top-n $(top_n)" in text
    assert "--event-count 12500" in text
    assert "getenv = false" in text
    assert "Top180" not in text and "180" not in text

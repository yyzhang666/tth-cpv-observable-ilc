"""Tests for sidecar weight handling and alignment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from ilc_tth_cpv.weights import (
    align_sidecar_to_stdhep,
    parse_skipped_events_from_log,
    read_sidecar,
    training_weight,
    validate_signed_weights,
)


def write_sidecar(tmp_path, rows):
    path = tmp_path / "me.csv"
    lines = ["event,sign,event_weight_signed,sigma_absint,n_generated"]
    lines += [",".join(str(v) for v in row) for row in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def test_read_sidecar_ok(tmp_path):
    path = write_sidecar(tmp_path, [
        (1, 1, 0.0004, 5.0, 12500),
        (2, -1, -0.0004, 5.0, 12500),
    ])
    rows = read_sidecar(path)
    assert len(rows) == 2
    assert rows[0]["sign"] == 1
    assert rows[1]["event_weight_signed"] == -0.0004


def test_read_sidecar_rejects_out_of_order(tmp_path):
    path = write_sidecar(tmp_path, [
        (1, 1, 0.0004, 5.0, 12500),
        (3, -1, -0.0004, 5.0, 12500),
    ])
    with pytest.raises(RuntimeError):
        read_sidecar(path)


def test_skip_parsing_and_alignment(tmp_path):
    log = tmp_path / "sim.out"
    log.write_text(
        "info\nJSFHadronizer: requested the event 2 to be skipped.\n"
        "other line\nrequested the event 4 to be skipped\n"
    )
    skipped = parse_skipped_events_from_log(log)
    assert skipped == {2, 4}
    sidecar = [{"event": i, "sign": 1, "event_weight_signed": 0.1,
                "sigma_absint": 5.0, "n_generated": 12500} for i in range(1, 6)]
    aligned = align_sidecar_to_stdhep(sidecar, skipped)
    assert [row["event"] for row in aligned] == [1, 3, 5]


def test_missing_log_means_no_skips(tmp_path):
    assert parse_skipped_events_from_log(tmp_path / "nope.out") == set()
    assert parse_skipped_events_from_log(None) == set()


def test_validate_signed_weights_detects_sign_mismatch():
    rows = [
        {"event": 1, "sign": 1, "event_weight_signed": -0.0004,
         "sigma_absint": 5.0, "n_generated": 12500},
    ]
    report = validate_signed_weights(rows)
    assert not report["ok"]


def test_validate_signed_weights_ok():
    w = 5.0 / 12500
    rows = [
        {"event": 1, "sign": 1, "event_weight_signed": w,
         "sigma_absint": 5.0, "n_generated": 12500},
        {"event": 2, "sign": -1, "event_weight_signed": -w,
         "sigma_absint": 5.0, "n_generated": 12500},
    ]
    report = validate_signed_weights(rows)
    assert report["ok"]
    assert report["n_pos"] == 1 and report["n_neg"] == 1
    assert abs(report["signed_sum_fb"]) < 1e-15


def test_training_weight_is_absolute():
    assert training_weight(-0.25) == 0.25
    assert training_weight(0.25) == 0.25

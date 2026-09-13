import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/reco_performance/report_lepton_selection_truth_composition.py"
spec = importlib.util.spec_from_file_location("truth_composition", SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class Reader:
    def __init__(self, events):
        self.events = iter(events)

    def readNextEvent(self):
        return next(self.events, None)

    def close(self):
        pass


def fake_legacy():
    return SimpleNamespace(
        truth_h_to_bb=lambda event, colMC: event.hbb,
        truth_ttbar_channel_and_tau=lambda event, colMC: (event.channel, False),
        get_n_reco=lambda event, preferred, fallbacks: (
            preferred,
            event.nmu if preferred == "ISOMuons" else event.nel,
        ),
    )


def event(channel, nmu=0, nel=1, hbb=True):
    return SimpleNamespace(channel=channel, nmu=nmu, nel=nel, hbb=hbb)


def test_tagger_exactly_one_selection_and_truth_closure():
    events = [
        event("semilep_e"),
        event("semilep_mu", nmu=1, nel=0),
        event("semilep_tau"),
        event("had"),
        event("dilep"),
        event("semilep_lep"),
        event(None),
        event("semilep_e", nmu=1, nel=1),
        event("semilep_e", hbb=False),
    ]
    result = report.scan_tagger(
        ["complete.slcio"], fake_legacy(), reader_opener=lambda path: Reader(events)
    )
    assert result["events_processed"] == 9
    assert result["raw_counts"] == {
        "direct_semilep_emu": 2,
        "semilep_tau": 1,
        "fully_hadronic": 1,
        "dileptonic": 1,
    }
    assert result["selected_total_4class"] == 5
    assert result["selected_hbb_all"] == 7
    assert result["semilep_lep"] == 1
    assert result["unclassified"] == 1
    assert result["overall_closure"] is True
    assert result["percentage_sum"] == pytest.approx(100.0)


def counts_payload(events_processed=report.EXPECTED_EVENTS):
    values = {
        "HBB|semilep_e": (100, 80),
        "HBB|semilep_mu": (120, 90),
        "HBB|semilep_tau": (60, 20),
        "HBB|had": (200, 10),
        "HBB|dilep": (50, 25),
    }
    return {
        "multiplicity": {
            "events_processed": events_processed,
            "semileptonic_logic": {
                key: {"n": denominator, "cnt": {"Isolep==1": selected}}
                for key, (denominator, selected) in values.items()
            },
        }
    }


def test_finder_reads_only_four_class_i1_counts_and_marks_unrecorded():
    result = report.finder_from_counts(counts_payload())
    assert result["raw_counts"] == {
        "direct_semilep_emu": 170,
        "semilep_tau": 20,
        "fully_hadronic": 10,
        "dileptonic": 25,
    }
    assert result["selected_total_4class"] == 225
    assert result["semilep_lep"] == 0
    assert result["semilep_lep_status"] == "tracked_block_absent_zero"
    assert result["unclassified"] is None
    assert result["unclassified_status"] == "not_recorded_by_source_JSON"
    assert result["overall_closure"] is None
    assert result["percentage_sum"] == pytest.approx(100.0)


def test_finder_requires_validated_event_count_and_category_blocks():
    with pytest.raises(RuntimeError, match="events_processed"):
        report.finder_from_counts(counts_payload(events_processed=20))
    payload = counts_payload()
    del payload["multiplicity"]["semileptonic_logic"]["HBB|dilep"]
    with pytest.raises(RuntimeError, match="HBB\\|dilep"):
        report.finder_from_counts(payload)


def test_method_result_rejects_zero_denominator_and_bad_overall_closure():
    with pytest.raises(RuntimeError, match="zero four-class denominator"):
        report.method_result("Tagger", {}, 0, 0, 0)
    with pytest.raises(RuntimeError, match="selected HBB closure failed"):
        report.method_result(
            "Tagger", {"direct_semilep_emu": 1}, selected_hbb_all=2,
            semilep_lep=0, unclassified=0,
        )


def test_condor_wrapper_scans_only_ten_complete_reco_inputs():
    wrapper = (
        ROOT / "condor/reco_performance/run_lepton_truth_composition.sh"
    ).read_text(encoding="utf-8")
    submit = (
        ROOT / "condor/reco_performance/lepton_truth_composition.sub"
    ).read_text(encoding="utf-8")
    assert "for chunk in {1..10}" in wrapper
    assert "complete_reco_kinfit_ready_" in wrapper
    assert "finder_chunk" not in wrapper
    assert "source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh" in wrapper
    assert "set -eo pipefail" in wrapper
    assert "set -euo pipefail" not in wrapper
    assert "set +e" in wrapper
    assert 'setup_log="$run_root/condor/setup.log"' in wrapper
    assert "setup_rc=$?" in wrapper
    assert "command -v python3" in wrapper
    assert "-c 'import pyLCIO'" in wrapper
    assert 'exec "$python_executable"' in wrapper
    assert '--max-events "$max_events"' in wrapper
    assert "MAX_EVENTS = -1" in submit
    assert "$(MAX_EVENTS)" in submit
    assert "report_lepton_selection_truth_composition.py" in wrapper
    assert "queue 1" in submit

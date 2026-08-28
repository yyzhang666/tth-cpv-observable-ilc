import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/evaluate_event_csv_fisher.py"
SPEC = importlib.util.spec_from_file_location("event_csv_fisher", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_q_sel_cut_is_strict():
    assert not MODULE.strict_q_sel_pass(0.954, 0.954)
    assert MODULE.strict_q_sel_pass(0.95400001, 0.954)


def test_baseline_model_alias_is_separate_from_q_sel():
    assert MODULE.ML_MODEL_COLUMNS["wbjets_lepton_v0"] == "q_CPV_wbjets_lepton"
    assert MODULE.ML_MODEL_COLUMNS["wbjets_lepton"] == "q_CPV_wbjets_lepton"
    assert MODULE.ML_MODEL_COLUMNS["wbjets_lepton_v0"] != "q_sel"

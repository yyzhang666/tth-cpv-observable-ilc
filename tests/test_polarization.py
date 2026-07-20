"""Closure tests for the polarisation combination."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from ilc_tth_cpv.polarization import (
    a_lr,
    b_rl,
    closure_check,
    physical_event_weight,
    running_weights,
)

LCF_RUNNING = {
    "mm": {"electron": -0.8, "positron": -0.6, "fraction": 0.10},
    "mp": {"electron": -0.8, "positron": 0.6, "fraction": 0.40},
    "pm": {"electron": 0.8, "positron": -0.6, "fraction": 0.40},
    "pp": {"electron": 0.8, "positron": 0.6, "fraction": 0.10},
}


def test_reference_table_project_note():
    # project note §2.13 reference values for 80%/60% beams
    assert abs(a_lr(-0.8, -0.6) - 0.18) < 1e-12
    assert abs(b_rl(-0.8, -0.6) - 0.08) < 1e-12
    assert abs(a_lr(-0.8, 0.6) - 0.72) < 1e-12
    assert abs(b_rl(-0.8, 0.6) - 0.02) < 1e-12
    assert abs(a_lr(0.8, -0.6) - 0.02) < 1e-12
    assert abs(b_rl(0.8, -0.6) - 0.72) < 1e-12
    assert abs(a_lr(0.8, 0.6) - 0.08) < 1e-12
    assert abs(b_rl(0.8, 0.6) - 0.18) < 1e-12


def test_fully_polarised_limits():
    assert a_lr(-1.0, 1.0) == 1.0
    assert b_rl(-1.0, 1.0) == 0.0
    assert a_lr(1.0, -1.0) == 0.0
    assert b_rl(1.0, -1.0) == 1.0


def test_a_plus_b_not_renormalised():
    # for partially polarised beams a+b < 1; renormalising is a known mistake
    assert a_lr(-0.8, 0.6) + b_rl(-0.8, 0.6) < 1.0


def test_lcf_scenario_closure():
    report = closure_check(LCF_RUNNING)
    assert report["ok"], report["problems"]
    assert abs(report["fraction_sum"] - 1.0) < 1e-12


def test_closure_detects_bad_fractions():
    bad = {k: dict(v) for k, v in LCF_RUNNING.items()}
    bad["mm"]["fraction"] = 0.5
    assert not closure_check(bad)["ok"]


def test_running_weights_luminosity_split():
    factors = running_weights(LCF_RUNNING, 8.0)
    assert abs(factors["mp"]["luminosity_ab"] - 3.2) < 1e-12
    assert abs(sum(f["luminosity_ab"] for f in factors.values()) - 8.0) < 1e-12


def test_physical_event_weight_by_helicity():
    assert physical_event_weight("LR", 2.0, a=0.72, b=0.02) == 1.44
    assert physical_event_weight("RL", 2.0, a=0.72, b=0.02) == 0.04
    with pytest.raises(ValueError):
        physical_event_weight("LL", 1.0, a=0.5, b=0.5)

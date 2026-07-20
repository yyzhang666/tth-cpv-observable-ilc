"""Toy tests for Fisher information and the likelihood cross-check."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.fisher import fisher_information, intervals, per_bin_fisher
from ilc_tth_cpv.likelihood import asimov_scan, gaussian_cross_check, interval_from_scan


def test_single_bin_closed_form():
    result = fisher_information([100.0], [10.0])
    assert abs(result["fisher_absolute"] - 1.0) < 1e-12
    assert abs(result["c68"] - 1.0) < 1e-12
    assert abs(result["c95"] - 1.96) < 1e-12


def test_sine_toy_analytic():
    n_bins, nu0_val, amp = 36, 100.0, 8.0
    centers = [(-math.pi + (i + 0.5) * 2 * math.pi / n_bins) for i in range(n_bins)]
    nu0 = [nu0_val] * n_bins
    nu1 = [amp * math.sin(c) for c in centers]
    result = fisher_information(nu0, nu1, shape_only=True)
    analytic = amp * amp * n_bins / (2.0 * nu0_val)
    assert abs(result["fisher_absolute"] - analytic) < 1e-9
    # pure sine: sum(nu1)=0 -> shape-only == absolute
    assert abs(result["fisher_shape_only"] - result["fisher_absolute"]) < 1e-9


def test_background_dilutes_information():
    nu0, nu1 = [50.0, 50.0], [5.0, -5.0]
    no_bg = fisher_information(nu0, nu1)["fisher_absolute"]
    with_bg = fisher_information(nu0, nu1, background=[50.0, 50.0])["fisher_absolute"]
    assert with_bg < no_bg
    assert abs(with_bg - no_bg / 2.0) < 1e-12


def test_invalid_bins_flagged_not_dropped():
    rows = per_bin_fisher([0.0, 10.0], [1.0, 2.0])
    assert rows[0]["invalid"] == "empty nu0"
    assert rows[0]["fisher"] == 0.0
    assert rows[1]["invalid"] is None
    total = fisher_information([0.0, 10.0], [1.0, 2.0])
    assert total["n_invalid_bins"] == 1


def test_shape_only_removes_rate():
    # nu1 proportional to nu0 -> pure rate, no shape information
    nu0 = [10.0, 20.0, 30.0]
    nu1 = [1.0, 2.0, 3.0]
    result = fisher_information(nu0, nu1, shape_only=True)
    assert abs(result["fisher_shape_only"]) < 1e-12
    assert result["fisher_absolute"] > 0.0


def test_intervals_infinite_for_zero_information():
    result = intervals(0.0)
    assert result["c68"] == math.inf


def test_likelihood_scan_matches_gaussian_in_linear_regime():
    nu0 = [200.0] * 10
    nu1 = [3.0 * math.sin(2.0 * math.pi * i / 10.0) for i in range(10)]
    fisher = fisher_information(nu0, nu1)["fisher_absolute"]
    c_grid = [x * 0.02 for x in range(-200, 201)]
    scan = asimov_scan(nu0, nu1, c_grid)
    interval = interval_from_scan(scan, level=1.0)
    gauss = gaussian_cross_check(fisher, level=1.0)
    assert interval["lower"] is not None and interval["upper"] is not None
    assert abs(interval["upper"] - gauss["upper"]) / gauss["upper"] < 0.05
    assert abs(interval["lower"] - gauss["lower"]) / abs(gauss["lower"]) < 0.05

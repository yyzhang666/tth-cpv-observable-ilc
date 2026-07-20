#!/usr/bin/env python3
"""TEMPLATE — Fisher information with a closed-form toy test.

Toy: nu0 flat, nu1 = A*sin(phi_center). Then
    I = sum_i (A sin phi_i)^2 / nu0
which for many bins approaches  A^2 * N_bins / (2 * nu0).  The template
verifies the code against this analytic limit — the same style of toy test
lives in tests/test_fisher.py and must keep passing.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.fisher import fisher_information
from ilc_tth_cpv.likelihood import asimov_scan, interval_from_scan

N_BINS = 36
NU0_PER_BIN = 100.0
AMPLITUDE = 8.0


def main() -> int:
    centers = [(-math.pi + (i + 0.5) * 2.0 * math.pi / N_BINS) for i in range(N_BINS)]
    nu0 = [NU0_PER_BIN] * N_BINS
    nu1 = [AMPLITUDE * math.sin(c) for c in centers]

    result = fisher_information(nu0, nu1, shape_only=True)
    analytic = AMPLITUDE**2 * N_BINS / (2.0 * NU0_PER_BIN)
    print(f"Fisher (code)     = {result['fisher_absolute']:.6f}")
    print(f"Fisher (analytic) = {analytic:.6f}")
    assert abs(result["fisher_absolute"] - analytic) < 1e-9 * max(1.0, analytic)

    # shape-only equals absolute here because sum(nu1) = 0 for a pure sine
    print(f"Fisher shape-only = {result['fisher_shape_only']:.6f}")

    print(f"sigma_c ~ {result['c68']:.4f}, 95% ~ {result['c95']:.4f}")

    # Cross-check with a Poisson Asimov likelihood scan.
    c_grid = [x * 0.005 for x in range(-100, 101)]
    scan = asimov_scan(nu0, nu1, c_grid)
    interval = interval_from_scan(scan, level=1.0)
    print(f"likelihood 68% interval: [{interval['lower']:.4f}, {interval['upper']:.4f}]")
    print(f"Gaussian expectation   : +/- {result['c68']:.4f}")
    print("toy test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Tests for the frozen angle conventions (pure python, no dependencies)."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.angles import delta_phi, observable_signs, sign_of, wrap_phi


def test_wrap_range_half_open():
    # Frozen convention [-pi, pi): +pi maps to -pi.
    assert wrap_phi(math.pi) == -math.pi
    assert wrap_phi(-math.pi) == -math.pi
    assert wrap_phi(0.0) == 0.0


def test_wrap_periodicity():
    for x in (-7.5, -3.2, -0.1, 0.4, 2.9, 6.8, 12.0):
        w = wrap_phi(x)
        assert -math.pi <= w < math.pi
        assert abs(wrap_phi(x + 2.0 * math.pi) - w) < 1e-12
        assert abs(wrap_phi(x - 2.0 * math.pi) - w) < 1e-12


def test_wrap_idempotent():
    for x in (-3.0, -1.0, 0.0, 1.5, 3.1):
        assert wrap_phi(wrap_phi(x)) == wrap_phi(x)


def test_delta_phi_sign_and_order():
    # order matters: delta_phi(a,b) = -delta_phi(b,a) away from the boundary
    a, b = 2.5, -2.0
    d = delta_phi(a, b)
    assert abs(d - wrap_phi(4.5)) < 1e-12
    assert abs(delta_phi(b, a) + d) < 1e-12


def test_delta_phi_wraps_across_boundary():
    assert abs(delta_phi(3.0, -3.0) - (6.0 - 2.0 * math.pi)) < 1e-12


def test_sign_of_dead_zone():
    assert sign_of(1e-6) == 1
    assert sign_of(-1e-6) == -1
    assert sign_of(0.0) == 0
    assert sign_of(1e-13) == 0  # below EPS


def test_observable_signs_cp_structure():
    signs = observable_signs(0.5, 0.3, -0.5, -0.3)
    assert signs["C_phi1"] == 1
    assert signs["C_phi2"] == -1
    # phi_plus = 0 -> sin(2*0) = 0 -> sign 0
    assert signs["C_phi_plus"] == 0

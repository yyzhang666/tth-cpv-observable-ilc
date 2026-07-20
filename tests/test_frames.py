"""Tests for the shared frame library (boosts, bases, angles)."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.frames import (
    BasisQuality,
    boost_only_angles,
    boost_to_rest,
    frame_angles,
    invariant_mass,
    make_frame,
    rest_p4_for_frame,
    unit,
)


def p4_from_mass(m, px, py, pz):
    return (math.sqrt(m * m + px * px + py * py + pz * pz), px, py, pz)


def test_boost_only_angles_lab_matches_atan2():
    # Convention A in the lab frame reduces to plain atan2(py, px)
    particle = p4_from_mass(0.0, 3.0, 4.0, 5.0)
    lab_rest = rest_p4_for_frame("lab", None, None, None)
    energy, cos_theta, phi = boost_only_angles(particle, lab_rest)
    assert abs(phi - math.atan2(4.0, 3.0)) < 1e-12
    assert abs(energy - particle[0]) < 1e-12
    assert abs(cos_theta - 5.0 / math.sqrt(50.0)) < 1e-12


def test_boost_only_angles_z_boost_preserves_phi():
    # a boost along z leaves the transverse plane (hence phi) unchanged
    particle = p4_from_mass(0.0, 3.0, 4.0, 5.0)
    system = p4_from_mass(300.0, 0.0, 0.0, 120.0)
    _, _, phi = boost_only_angles(particle, system)
    assert abs(phi - math.atan2(4.0, 3.0)) < 1e-12


def test_rest_p4_for_frame_variants():
    top = p4_from_mass(173.0, 40.0, 25.0, 90.0)
    antitop = p4_from_mass(173.0, -60.0, 15.0, -30.0)
    higgs = p4_from_mass(125.0, 20.0, -40.0, -60.0)
    assert rest_p4_for_frame("lab", None, None, None) == (1.0, 0.0, 0.0, 0.0)
    assert rest_p4_for_frame("higgs_rest", top, antitop, higgs) == higgs
    ttbar = rest_p4_for_frame("ttbar_rest", top, antitop, higgs)
    assert abs(ttbar[0] - (top[0] + antitop[0])) < 1e-12
    assert rest_p4_for_frame("ttbar_rest", None, antitop, higgs) is None


def test_boost_to_own_rest_frame_gives_mass_energy():
    p = p4_from_mass(125.0, 30.0, -20.0, 55.0)
    rest = boost_to_rest(p, p)
    assert abs(rest[0] - 125.0) < 1e-9
    assert abs(rest[1]) < 1e-9 and abs(rest[2]) < 1e-9 and abs(rest[3]) < 1e-9


def test_boost_preserves_invariant_mass():
    system = p4_from_mass(350.0, 60.0, 10.0, -80.0)
    particle = p4_from_mass(4.8, 12.0, -8.0, 30.0)
    boosted = boost_to_rest(particle, system)
    assert abs(invariant_mass(boosted) - invariant_mass(particle)) < 1e-8


def test_boost_rejects_unphysical():
    assert boost_to_rest((1.0, 0.0, 0.0, 0.0), (1.0, 2.0, 0.0, 0.0)) is None


def test_make_frame_basis_orthonormal():
    top = p4_from_mass(173.0, 40.0, 25.0, 90.0)
    antitop = p4_from_mass(173.0, -60.0, 15.0, -30.0)
    higgs = p4_from_mass(125.0, 20.0, -40.0, -60.0)
    e_dir = (0.0, 0.0, 1.0)
    quality = BasisQuality()
    for name in ("higgs_rest", "ttbar_rest", "lab"):
        frame = make_frame(name, top, antitop, higgs, e_dir)
        assert frame is not None, name
        assert quality.update(frame.x_hat, frame.y_hat, frame.z_hat), name
    assert quality.failures == 0


def test_x_axis_from_electron_beam_is_transverse():
    higgs = p4_from_mass(125.0, 20.0, -40.0, -60.0)
    frame = make_frame("higgs_rest", None, None, higgs, (0.0, 0.0, 1.0))
    dot_zx = sum(a * b for a, b in zip(frame.x_hat, frame.z_hat))
    assert abs(dot_zx) < 1e-12


def test_frame_angles_ranges():
    higgs = p4_from_mass(125.0, 20.0, -40.0, -60.0)
    frame = make_frame("higgs_rest", None, None, higgs, (0.0, 0.0, 1.0))
    particle = p4_from_mass(0.0, 10.0, 20.0, -5.0)
    result = frame_angles(particle, frame)
    assert result is not None
    energy, cos_theta, phi = result
    assert energy > 0.0
    assert -1.0 <= cos_theta <= 1.0
    assert -math.pi <= phi < math.pi


def test_lab_frame_no_boost():
    particle = p4_from_mass(0.0, 3.0, 4.0, 0.0)
    frame = make_frame("lab", None, None, None, (1.0, 0.0, 0.0))
    energy, cos_theta, phi = frame_angles(particle, frame)
    assert abs(energy - 5.0) < 1e-12
    assert abs(cos_theta) < 1e-12  # transverse particle


def test_unit_of_zero_vector():
    assert unit((0.0, 0.0, 0.0)) is None

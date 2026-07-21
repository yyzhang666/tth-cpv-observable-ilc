"""Angle conventions.

Ported from the authoritative theory-study implementation
analysis/tth/generator_study/compute_tthcpv_ma2018_observables.py
(see docs/CODE_PROVENANCE.md). Do not re-derive elsewhere.
"""

from __future__ import annotations

import math

EPS = 1.0e-12

TWO_PI = 2.0 * math.pi


def wrap_phi(x: float) -> float:
    """Wrap an angle into [-pi, pi).

    Frozen convention (docs/PHYSICS_CONVENTIONS.md section 2).
    """
    wrapped = (float(x) + math.pi) % TWO_PI - math.pi
    if wrapped >= math.pi:
        wrapped -= TWO_PI
    return wrapped


def delta_phi(phi_a: float, phi_b: float) -> float:
    """Signed azimuthal difference wrap(phi_a - phi_b).

    Argument order matters. Each observable defines its own frozen
    particle-minus-antiparticle order (docs/PHYSICS_CONVENTIONS.md sections 3-4).
    """
    return wrap_phi(float(phi_a) - float(phi_b))


def sign_of(x: float) -> int:
    """Sign with a dead zone of EPS, as in the theory study."""
    if x > EPS:
        return 1
    if x < -EPS:
        return -1
    return 0


def observable_signs(theta1: float, phi1: float, theta2: float, phi2: float) -> dict:
    """Ma2018-style sign observables (ported verbatim from the theory study)."""
    phi_plus = wrap_phi((phi1 + phi2) / 2.0)
    phi_minus = wrap_phi((phi1 - phi2) / 2.0)
    return {
        "C_phi1": sign_of(math.sin(phi1)),
        "C_phi2": sign_of(math.sin(phi2)),
        "C_phi_plus": sign_of(math.sin(2.0 * phi_plus)),
        "C_phi_minus": sign_of(math.sin(2.0 * phi_minus)),
        "C_theta1_phi2": sign_of(theta1 * math.sin(phi2)),
        "C_theta2_phi1": sign_of(theta2 * math.sin(phi1)),
    }

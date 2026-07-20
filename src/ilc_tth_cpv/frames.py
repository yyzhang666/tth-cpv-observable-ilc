"""Reference frames: the two frozen basis conventions of the theory study.

Ported from the theory-study scripts (docs/CODE_PROVENANCE.md). The
authoritative convention report is mirrored in docs/PHYSICS_CONVENTIONS.md §5.

Convention A — phi-histogram basis (`lab_axes`), PRIMARY for the O_W/O_b/...
delta-phi observables (theory-study "Original Phi Frame Convention"):
    boost the four-vector into the frame, then measure
        phi = atan2(py, px)   against the FIXED lab x-y axes,
        cos_theta = pz / |p|  against the lab z axis.
    After the boost no coordinate rotation is applied.
    -> use `boost_only_angles`.

Convention B — Ma-style production-plane basis (`production_plane`), used for
the Ma2018 sign observables (C_phi1, ...):
    z = lab direction of the boosted-to system,
    x = transverse part of the electron beam direction, y = z x x.
    -> use `make_frame` + `frame_angles`.

Frame names used across configs:
    lab         -> no boost
    higgs_rest  -> theory-study "higgs-rest" / "Rh"
    ttbar_rest  -> theory-study "ttbar-rest" / "Rpsi"
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from .angles import wrap_phi

Vec3 = Tuple[float, float, float]
P4 = Tuple[float, float, float, float]  # (E, px, py, pz)

EPS = 1.0e-12
BASIS_TOL = 1.0e-9

FRAME_NAMES = ("lab", "higgs_rest", "ttbar_rest")


# ---------------------------------------------------------------- vector math

def spatial(p4: P4) -> Vec3:
    return (p4[1], p4[2], p4[3])


def add_p4(a: P4, b: P4) -> P4:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Optional[Vec3]:
    length = norm(a)
    if length <= EPS:
        return None
    return (a[0] / length, a[1] / length, a[2] / length)


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec3, c: float) -> Vec3:
    return (a[0] * c, a[1] * c, a[2] * c)


def invariant_mass(p4: P4) -> float:
    m2 = p4[0] * p4[0] - dot(spatial(p4), spatial(p4))
    return math.sqrt(m2) if m2 > 0.0 else 0.0


# ---------------------------------------------------------------- Lorentz boost

def boost_to_rest(p4: P4, rest_p4: P4) -> Optional[P4]:
    """Boost p4 into the rest frame of the system with four-momentum rest_p4.

    Ported verbatim from the theory study. Returns None for unphysical input.
    """
    energy, px, py, pz = p4
    rest_energy, bx_num, by_num, bz_num = rest_p4
    if rest_energy <= 0.0:
        return None
    beta = (bx_num / rest_energy, by_num / rest_energy, bz_num / rest_energy)
    beta2 = dot(beta, beta)
    if beta2 >= 1.0:
        return None
    if beta2 <= EPS:
        return p4
    gamma = 1.0 / math.sqrt(1.0 - beta2)
    beta_dot_p = beta[0] * px + beta[1] * py + beta[2] * pz
    factor = ((gamma - 1.0) * beta_dot_p / beta2) - gamma * energy
    return (
        gamma * (energy - beta_dot_p),
        px + factor * beta[0],
        py + factor * beta[1],
        pz + factor * beta[2],
    )


# ---------------------------------------------------------------- basis quality

@dataclass
class BasisQuality:
    """Track orthonormality of constructed bases (theory-study check)."""

    max_norm_deviation: float = 0.0
    max_dot_abs: float = 0.0
    max_cross_deviation: float = 0.0
    failures: int = 0

    def update(self, x_hat: Vec3, y_hat: Vec3, z_hat: Vec3) -> bool:
        norm_dev = max(
            abs(norm(x_hat) - 1.0),
            abs(norm(y_hat) - 1.0),
            abs(norm(z_hat) - 1.0),
        )
        dot_abs = max(
            abs(dot(x_hat, y_hat)), abs(dot(y_hat, z_hat)), abs(dot(z_hat, x_hat))
        )
        cross_dev = norm(sub(cross(x_hat, y_hat), z_hat))
        self.max_norm_deviation = max(self.max_norm_deviation, norm_dev)
        self.max_dot_abs = max(self.max_dot_abs, dot_abs)
        self.max_cross_deviation = max(self.max_cross_deviation, cross_dev)
        valid = (
            norm_dev <= BASIS_TOL and dot_abs <= BASIS_TOL and cross_dev <= BASIS_TOL
        )
        if not valid:
            self.failures += 1
        return valid

    def as_dict(self) -> dict:
        return {
            "max_norm_deviation": self.max_norm_deviation,
            "max_dot_abs": self.max_dot_abs,
            "max_cross_deviation": self.max_cross_deviation,
            "failures": self.failures,
            "tolerance": BASIS_TOL,
        }


# ------------------------------------------------ Convention A: lab-axes phi

def rest_p4_for_frame(
    frame: str,
    top_p4: Optional[P4],
    antitop_p4: Optional[P4],
    higgs_p4: Optional[P4],
) -> Optional[P4]:
    """Four-momentum of the system defining the requested rest frame.

    For 'lab' returns the zero-boost placeholder accepted by boost_to_rest.
    """
    if frame == "lab":
        return (1.0, 0.0, 0.0, 0.0)
    if frame == "higgs_rest":
        return higgs_p4
    if frame == "ttbar_rest":
        if top_p4 is None or antitop_p4 is None:
            return None
        return add_p4(top_p4, antitop_p4)
    raise ValueError(f"Unknown frame: {frame}")


def boost_only_angles(p4: P4, rest_p4: P4) -> Optional[Tuple[float, float, float]]:
    """(E, cos_theta, phi) in the frame, measured against the FIXED lab axes.

    This is the theory-study primary convention for the delta-phi
    observables: boost, then phi = atan2(py, px), cos_theta = pz/|p|,
    with no coordinate rotation after the boost.
    """
    boosted = boost_to_rest(p4, rest_p4)
    if boosted is None:
        return None
    p_unit = unit(spatial(boosted))
    if p_unit is None:
        return None
    return (boosted[0], p_unit[2], wrap_phi(math.atan2(p_unit[1], p_unit[0])))


# ---------------------------------------- Convention B: production-plane basis

@dataclass
class FrameResult:
    rest_p4: P4
    x_hat: Vec3
    y_hat: Vec3
    z_hat: Vec3
    electron_beam_source: str


def make_frame(
    frame: str,
    top_p4: Optional[P4],
    antitop_p4: Optional[P4],
    higgs_p4: Optional[P4],
    electron_dir: Vec3,
    electron_source: str = "config",
) -> Optional[FrameResult]:
    """Build the production-plane basis for the requested frame.

    Boosted frames (higgs_rest / ttbar_rest): z = lab direction of the
    boosted-to system; x = transverse part of the electron beam direction;
    y = z x x (theory-study make_frame).

    'lab': fixed detector axes x=(1,0,0), y=(0,1,0), z=(0,0,1), so that
    phi = atan2(py, px) exactly as in the authoritative lab-frame plots
    (plot_tthcpv_gen_phi.py). The beam-transverse construction would be
    degenerate for a beam along z.
    """
    if frame == "ttbar_rest":
        if top_p4 is None or antitop_p4 is None:
            return None
        rest_p4 = add_p4(top_p4, antitop_p4)
        z_hat = unit(spatial(rest_p4))
    elif frame == "higgs_rest":
        if higgs_p4 is None:
            return None
        rest_p4 = higgs_p4
        z_hat = unit(spatial(rest_p4))
    elif frame == "lab":
        return FrameResult(
            rest_p4=(1.0, 0.0, 0.0, 0.0),  # no boost
            x_hat=(1.0, 0.0, 0.0),
            y_hat=(0.0, 1.0, 0.0),
            z_hat=(0.0, 0.0, 1.0),
            electron_beam_source="lab_fixed_axes",
        )
    else:
        raise ValueError(f"Unknown frame: {frame}")

    if z_hat is None:
        return None
    x_raw = sub(electron_dir, scale(z_hat, dot(electron_dir, z_hat)))
    x_hat = unit(x_raw)
    if x_hat is None:
        return None
    y_hat = unit(cross(z_hat, x_hat))
    if y_hat is None:
        return None
    return FrameResult(
        rest_p4=rest_p4,
        x_hat=x_hat,
        y_hat=y_hat,
        z_hat=z_hat,
        electron_beam_source=electron_source,
    )


def frame_angles(p4: P4, frame_result: FrameResult) -> Optional[Tuple[float, float, float]]:
    """Boost p4 into the frame and return (E, cos_theta, phi).

    cos_theta is measured against z_hat; phi = atan2(p.y_hat, p.x_hat),
    wrapped into [-pi, pi).
    """
    boosted = boost_to_rest(p4, frame_result.rest_p4)
    if boosted is None:
        return None
    p_unit = unit(spatial(boosted))
    if p_unit is None:
        return None
    cos_theta = dot(p_unit, frame_result.z_hat)
    if 1.0 < cos_theta < 1.0 + 1.0e-10:
        cos_theta = 1.0
    if -1.0 - 1.0e-10 < cos_theta < -1.0:
        cos_theta = -1.0
    phi = wrap_phi(
        math.atan2(dot(p_unit, frame_result.y_hat), dot(p_unit, frame_result.x_hat))
    )
    return (boosted[0], cos_theta, phi)


def find_electron_beam_direction(
    beam_candidates: Iterable[Tuple[float, Vec3]], fallback_sign: int = 1
) -> Tuple[Vec3, str]:
    """Pick the electron beam direction from (energy, unit-direction) pairs.

    Ported logic: highest-energy parentless PDG 11 particle; the caller is
    responsible for pre-filtering to parentless electrons. Fallback: +/- z.
    """
    best = None
    for energy, direction in beam_candidates:
        if direction is None:
            continue
        if best is None or energy > best[0]:
            best = (energy, direction)
    if best is not None:
        return best[1], "stdhep_pdg11_no_parent"
    return (0.0, 0.0, float(fallback_sign)), "fallback_z_sign"

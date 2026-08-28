"""Event-level angular observables derived from versioned CSV columns.

The input column names describe already oriented Higgs-rest objects.  This
module only performs the final signed azimuthal difference; it does not infer
jet assignments or change reconstruction stages.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping

from .angles import delta_phi


class CsvObservableError(ValueError):
    """Raised when a CSV row cannot provide a requested observable."""


def _finite(row: Mapping[str, object], column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as exc:
        raise CsvObservableError(f"missing/non-numeric CSV column {column!r}") from exc
    if not math.isfinite(value):
        raise CsvObservableError(f"non-finite CSV column {column!r}")
    return value


def o_lnu(row: Mapping[str, object]) -> float:
    """Charge-ordered lepton-neutrino Delta-phi in [-pi, pi)."""
    charge = _finite(row, "lepton_charge")
    lepton_phi = _finite(row, "lepton_phi")
    neutrino_phi = _finite(row, "neutrino_phi")
    if charge < 0.0:
        return delta_phi(lepton_phi, neutrino_phi)
    if charge > 0.0:
        return delta_phi(neutrino_phi, lepton_phi)
    raise CsvObservableError("zero lepton charge")


def o_ld(row: Mapping[str, object]) -> float:
    """Top-side minus anti-top-side down-type-fermion Delta-phi."""
    return delta_phi(
        _finite(row, "top_side_fermion_phi"),
        _finite(row, "anti_top_side_fermion_phi"),
    )


def o_w(row: Mapping[str, object]) -> float:
    """Oriented W-quark minus W-antiquark Delta-phi."""
    return delta_phi(
        _finite(row, "wjet_quark_phi"),
        _finite(row, "wjet_antiquark_phi"),
    )


def o_b(row: Mapping[str, object]) -> float:
    """Charge-oriented top-b minus antitop-bbar Delta-phi."""
    return delta_phi(
        _finite(row, "top_b_phi"),
        _finite(row, "antitop_bbar_phi"),
    )


def o_top(row: Mapping[str, object]) -> float:
    """Top minus antitop Delta-phi for CSVs carrying oriented top columns."""
    return delta_phi(_finite(row, "top_phi"), _finite(row, "antitop_phi"))


_ANGLE_FUNCTIONS: dict[str, Callable[[Mapping[str, object]], float]] = {
    "O_lnu": o_lnu,
    "O_lD": o_ld,
    "O_W": o_w,
    "O_jj_W": o_w,
    "O_b": o_b,
    "O_top": o_top,
}


def available_csv_angles() -> tuple[str, ...]:
    """Return stable CLI names for the registered CSV angles."""
    return tuple(_ANGLE_FUNCTIONS)


def compute_csv_angle(name: str, row: Mapping[str, object]) -> float:
    """Compute one registered angle from a CSV row."""
    try:
        function = _ANGLE_FUNCTIONS[name]
    except KeyError as exc:
        choices = ", ".join(available_csv_angles())
        raise CsvObservableError(f"unknown CSV angle {name!r}; choose one of: {choices}") from exc
    return function(row)

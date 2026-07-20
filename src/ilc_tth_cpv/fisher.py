"""Fisher information for linear signed-interference templates.

Formulas frozen in the project note §2.10–2.12:
    nu_i(c) = nu0_i + c * nu1_i
    I       = sum_i nu1_i^2 / nu0_i          (absolute yield)
    I_shape = I - (sum nu1)^2 / (sum nu0)    (normalisation removed)
With parameter-independent background: nu0_i = s0_i + b_i, nu1_i = s1_i.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence


def per_bin_fisher(
    nu0: Sequence[float],
    nu1: Sequence[float],
    min_nu0: float = 0.0,
) -> List[dict]:
    """Per-bin Fisher terms with invalid-bin flags.

    A bin is invalid if nu0 <= min_nu0 (empty or unphysical SM+bg yield) —
    such bins contribute 0 and are reported, never silently dropped.
    """
    if len(nu0) != len(nu1):
        raise ValueError("nu0 and nu1 must have the same length")
    rows = []
    for i, (n0, n1) in enumerate(zip(nu0, nu1)):
        invalid = None
        if n0 < 0.0:
            invalid = "negative nu0"
        elif n0 <= min_nu0:
            invalid = "empty nu0"
        elif n0 + min(0.0, n1) < 0.0:
            invalid = "linear template can go negative"
        term = (n1 * n1 / n0) if invalid is None else 0.0
        rows.append(
            {
                "bin_index": i,
                "nu0": float(n0),
                "nu1": float(n1),
                "fisher": term,
                "invalid": invalid,
            }
        )
    return rows


def fisher_information(
    nu0: Sequence[float],
    nu1: Sequence[float],
    background: Optional[Sequence[float]] = None,
    shape_only: bool = False,
    min_nu0: float = 0.0,
) -> dict:
    """Total Fisher information and Gaussian interval estimates.

    background, if given, is added to nu0 (signal-plus-background mode).
    """
    if background is not None:
        if len(background) != len(nu0):
            raise ValueError("background length mismatch")
        nu0 = [a + b for a, b in zip(nu0, background)]
    rows = per_bin_fisher(nu0, nu1, min_nu0=min_nu0)
    total = sum(row["fisher"] for row in rows)
    result = {
        "per_bin": rows,
        "fisher_absolute": total,
        "n_invalid_bins": sum(1 for row in rows if row["invalid"]),
    }
    if shape_only:
        sum0 = sum(row["nu0"] for row in rows if row["invalid"] is None)
        sum1 = sum(row["nu1"] for row in rows if row["invalid"] is None)
        shape = total - (sum1 * sum1 / sum0 if sum0 > 0.0 else 0.0)
        result["fisher_shape_only"] = shape
    used = result.get("fisher_shape_only") if shape_only else total
    result["fisher_used"] = used
    result.update(intervals(used))
    return result


def intervals(fisher: float) -> dict:
    """Approximate Gaussian 68%/95% intervals; local estimate only.

    Final intervals require a likelihood scan (KNOWN_ISSUES #14).
    """
    if fisher <= 0.0:
        return {"sigma_c": math.inf, "c68": math.inf, "c95": math.inf}
    sigma = 1.0 / math.sqrt(fisher)
    return {"sigma_c": sigma, "c68": sigma, "c95": 1.96 * sigma}

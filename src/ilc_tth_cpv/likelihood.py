"""Poisson likelihood scan for the linear (optionally quadratic) template.

Standard is the Poisson Asimov likelihood (ZH CPV convention); Gaussian is a
fallback cross-check. Pure python.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence


def expected_yields(
    nu0: Sequence[float],
    nu1: Sequence[float],
    c: float,
    nu2: Optional[Sequence[float]] = None,
) -> List[float]:
    out = []
    for i in range(len(nu0)):
        val = nu0[i] + c * nu1[i]
        if nu2 is not None:
            val += c * c * nu2[i]
        out.append(val)
    return out


def poisson_nll(observed: Sequence[float], expected: Sequence[float]) -> float:
    """Negative log likelihood, constant terms dropped; invalid bins raise."""
    nll = 0.0
    for n, mu in zip(observed, expected):
        if mu <= 0.0:
            if n == 0.0:
                continue
            raise ValueError(f"Non-positive expectation {mu} with observed {n}")
        nll += mu - n * math.log(mu)
    return nll


def asimov_scan(
    nu0: Sequence[float],
    nu1: Sequence[float],
    c_values: Sequence[float],
    nu2: Optional[Sequence[float]] = None,
) -> List[dict]:
    """-2 Delta lnL(c) with the Asimov dataset observed = nu(c=0)."""
    observed = expected_yields(nu0, nu1, 0.0, nu2)
    nll0 = poisson_nll(observed, observed)
    rows = []
    for c in c_values:
        expected = expected_yields(nu0, nu1, c, nu2)
        if any(mu <= 0.0 for mu in expected):
            rows.append({"c": c, "m2dll": None, "note": "negative expectation"})
            continue
        nll = poisson_nll(observed, expected)
        rows.append({"c": c, "m2dll": 2.0 * (nll - nll0), "note": ""})
    return rows


def interval_from_scan(rows: Sequence[dict], level: float = 1.0) -> dict:
    """Crossing points of -2dlnL = level (1.0 -> 68%, 3.84 -> 95%).

    Linear interpolation between scan points; None side means no crossing in
    the scanned range (scan wider or check for non-local intervals).
    """
    valid = [row for row in rows if row["m2dll"] is not None]
    lower = upper = None
    for i in range(1, len(valid)):
        c0, y0 = valid[i - 1]["c"], valid[i - 1]["m2dll"]
        c1, y1 = valid[i]["c"], valid[i]["m2dll"]
        if (y0 - level) * (y1 - level) < 0.0:
            c_cross = c0 + (level - y0) * (c1 - c0) / (y1 - y0)
            if c_cross < 0.0:
                lower = c_cross if lower is None else max(lower, c_cross)
            else:
                upper = c_cross if upper is None else min(upper, c_cross)
    return {"level": level, "lower": lower, "upper": upper}


def gaussian_cross_check(fisher_information: float, level: float = 1.0) -> dict:
    """Gaussian fallback: |c| = sqrt(level / I)."""
    if fisher_information <= 0.0:
        return {"level": level, "lower": None, "upper": None}
    half = math.sqrt(level / fisher_information)
    return {"level": level, "lower": -half, "upper": half}

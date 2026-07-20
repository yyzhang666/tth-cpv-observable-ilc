"""Binned templates with signed weights.

Binning conventions ported from the theory-study script
analysis/tth/generator_study/CPV/summarize_tthcpv_phi_sensitivity.py:
for each observable we keep three parallel histograms —
signed weights, absolute weights, and raw entries — plus the per-bin
local signed fraction. Pure python; no numpy dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

DEFAULT_N_BINS = 36
PHI_RANGE = (-math.pi, math.pi)


def linear_edges(low: float, high: float, n_bins: int) -> List[float]:
    step = (high - low) / n_bins
    return [low + i * step for i in range(n_bins + 1)]


def find_bin(edges: Sequence[float], value: float) -> Optional[int]:
    """Index of the bin containing value; None if out of range.

    Bins are half-open [low, high) except the last, which includes high.
    """
    if value < edges[0] or value > edges[-1]:
        return None
    if value == edges[-1]:
        return len(edges) - 2
    lo, hi = 0, len(edges) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if value < edges[mid]:
            hi = mid
        else:
            lo = mid
    return lo


@dataclass
class SignedHistogram:
    """Signed-weight histogram triple (signed / abs / entries)."""

    edges: List[float]
    signed: List[float] = field(default_factory=list)
    absw: List[float] = field(default_factory=list)
    entries: List[int] = field(default_factory=list)
    sumw2: List[float] = field(default_factory=list)
    n_out_of_range: int = 0

    def __post_init__(self) -> None:
        n = len(self.edges) - 1
        if not self.signed:
            self.signed = [0.0] * n
            self.absw = [0.0] * n
            self.entries = [0] * n
            self.sumw2 = [0.0] * n

    @classmethod
    def phi_binning(cls, n_bins: int = DEFAULT_N_BINS) -> "SignedHistogram":
        return cls(edges=linear_edges(PHI_RANGE[0], PHI_RANGE[1], n_bins))

    def fill(self, value: float, weight: float) -> None:
        idx = find_bin(self.edges, value)
        if idx is None:
            self.n_out_of_range += 1
            return
        self.signed[idx] += weight
        self.absw[idx] += abs(weight)
        self.entries[idx] += 1
        self.sumw2[idx] += weight * weight

    def local_signed_fraction(self) -> List[float]:
        return [
            s / a if a > 0.0 else 0.0 for s, a in zip(self.signed, self.absw)
        ]

    def integral_signed(self) -> float:
        return sum(self.signed)

    def integral_abs(self) -> float:
        return sum(self.absw)

    def scaled(self, factor: float) -> "SignedHistogram":
        out = SignedHistogram(edges=list(self.edges))
        out.signed = [s * factor for s in self.signed]
        out.absw = [a * abs(factor) for a in self.absw]
        out.entries = list(self.entries)
        out.sumw2 = [w2 * factor * factor for w2 in self.sumw2]
        out.n_out_of_range = self.n_out_of_range
        return out

    def unit_area(self) -> "SignedHistogram":
        """Unit-area copy (shape display only, never for Fisher yields)."""
        total = abs(self.integral_signed())
        if total <= 0.0:
            raise ValueError("Cannot unit-area normalise a zero-integral histogram")
        return self.scaled(1.0 / total)

    def as_rows(self, frame: str = "", observable: str = "") -> List[dict]:
        """Bin table rows matching the theory-study sensitivity CSV columns."""
        fractions = self.local_signed_fraction()
        rows = []
        for i in range(len(self.signed)):
            rows.append(
                {
                    "frame": frame,
                    "observable": observable,
                    "bin_index": i,
                    "bin_low": self.edges[i],
                    "bin_high": self.edges[i + 1],
                    "bin_center": 0.5 * (self.edges[i] + self.edges[i + 1]),
                    "signed_weight_fb": self.signed[i],
                    "abs_weight_fb": self.absw[i],
                    "local_signed_fraction": fractions[i],
                    "entries": self.entries[i],
                }
            )
        return rows


@dataclass
class ObservableAccumulator:
    """Signed sign-observable accumulator (theory-study port).

    Tracks S_pos/S_neg (signed sums by observable sign), D_abs, and counts.
    """

    S_pos: float = 0.0
    S_neg: float = 0.0
    D_abs: float = 0.0
    sumw2_N: float = 0.0
    n_pos: int = 0
    n_neg: int = 0
    n_zero: int = 0

    def fill(self, observable_sign: int, weight: float) -> None:
        if observable_sign > 0:
            self.S_pos += weight
            self.n_pos += 1
        elif observable_sign < 0:
            self.S_neg += weight
            self.n_neg += 1
        else:
            self.n_zero += 1
            return
        abs_weight = abs(weight)
        self.D_abs += abs_weight
        self.sumw2_N += abs_weight * abs_weight

    def as_dict(self) -> dict:
        n_int = self.S_pos - self.S_neg
        err_n = math.sqrt(self.sumw2_N)
        return {
            "S_pos": self.S_pos,
            "S_neg": self.S_neg,
            "N_int": n_int,
            "D_abs": self.D_abs,
            "A_abs": n_int / self.D_abs if self.D_abs > 0.0 else 0.0,
            "err_N": err_n,
            "z_N": n_int / err_n if err_n > 0.0 else 0.0,
            "n_pos": self.n_pos,
            "n_neg": self.n_neg,
            "n_zero": self.n_zero,
            "sumw2_N": self.sumw2_N,
        }

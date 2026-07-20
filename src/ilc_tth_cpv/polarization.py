"""Beam polarisation combination (docs/PHYSICS_CONVENTIONS.md §7)."""

from __future__ import annotations

from typing import Dict


def a_lr(p_minus: float, p_plus: float) -> float:
    """Weight of the pure-LR sample: a = (1-P-)(1+P+)/4."""
    return (1.0 - p_minus) * (1.0 + p_plus) / 4.0


def b_rl(p_minus: float, p_plus: float) -> float:
    """Weight of the pure-RL sample: b = (1+P-)(1-P+)/4."""
    return (1.0 + p_minus) * (1.0 - p_plus) / 4.0


def running_weights(running: Dict[str, dict], total_luminosity_ab: float) -> Dict[str, dict]:
    """Expand a lcf_polarization.yaml 'running' block into per-config factors.

    Returns {config: {a, b, fraction, luminosity_ab}}.
    a+b is NOT renormalised to 1 (closure test guards against that mistake).
    """
    out = {}
    for key, cfg in running.items():
        pm = float(cfg["electron"])
        pp = float(cfg["positron"])
        fraction = float(cfg["fraction"])
        out[key] = {
            "a": a_lr(pm, pp),
            "b": b_rl(pm, pp),
            "fraction": fraction,
            "luminosity_ab": fraction * float(total_luminosity_ab),
        }
    return out


def closure_check(running: Dict[str, dict], tolerance: float = 1.0e-9) -> dict:
    """Closure tests required before using the scenario.

    - fractions sum to 1;
    - each a,b in [0,1] and a+b <= 1;
    - a+b was NOT renormalised to 1 for partially polarised beams.
    """
    problems = []
    frac_sum = sum(float(cfg["fraction"]) for cfg in running.values())
    if abs(frac_sum - 1.0) > tolerance:
        problems.append(f"fractions sum to {frac_sum}, expected 1")
    for key, cfg in running.items():
        pm, pp = float(cfg["electron"]), float(cfg["positron"])
        a, b = a_lr(pm, pp), b_rl(pm, pp)
        if not (0.0 <= a <= 1.0 and 0.0 <= b <= 1.0):
            problems.append(f"{key}: a={a}, b={b} out of range")
        if a + b > 1.0 + tolerance:
            problems.append(f"{key}: a+b={a+b} > 1")
        partially_polarised = abs(pm) < 1.0 or abs(pp) < 1.0
        if partially_polarised and abs((a + b) - 1.0) <= tolerance:
            problems.append(
                f"{key}: a+b == 1 for partially polarised beams — "
                "suspicious renormalisation"
            )
    return {"ok": not problems, "problems": problems, "fraction_sum": frac_sum}


def physical_event_weight(
    helicity: str, base_weight: float, a: float, b: float
) -> float:
    """Mixture weight for one event in a physical running configuration."""
    if helicity == "LR":
        return a * base_weight
    if helicity == "RL":
        return b * base_weight
    raise ValueError(f"Unknown helicity {helicity!r}, expected LR or RL")

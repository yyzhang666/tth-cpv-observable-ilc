"""Small, dependency-free helpers shared by reco-performance studies.

The helpers in this module deliberately contain no LCIO collection discovery,
truth-role policy, denominator policy, or steering/runtime selection.  Those
choices stay in the study that owns them.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Mapping, Sequence


def event_key(source_file_id: str, run: int, event: int) -> tuple[str, int, int]:
    """Return the frozen cross-branch event join key."""
    source = str(source_file_id).strip()
    if not source:
        raise ValueError("source_file_id must not be empty")
    return source, int(run), int(event)


def invariant_mass(first: Sequence[float], second: Sequence[float]) -> float:
    """Return the invariant mass of two ``(px, py, pz, energy)`` vectors."""
    if len(first) != 4 or len(second) != 4:
        raise ValueError("four-vectors must contain (px, py, pz, energy)")
    px = float(first[0]) + float(second[0])
    py = float(first[1]) + float(second[1])
    pz = float(first[2]) + float(second[2])
    energy = float(first[3]) + float(second[3])
    mass_squared = energy * energy - px * px - py * py - pz * pz
    if mass_squared < -1.0e-9:
        raise ValueError(f"negative invariant-mass squared: {mass_squared}")
    return math.sqrt(max(0.0, mass_squared))


def find_hard_particle(particles: Iterable, target_pdg: int):
    """Apply the historical hard-particle rule used by the m_ttbar plot.

    A hard particle is the first particle with ``target_pdg`` that has no
    parent with the same PDG code.  Objects are expected to provide the LCIO
    ``getPDG`` and ``getParents`` methods.
    """
    candidates = []
    for index, particle in enumerate(particles):
        if int(particle.getPDG()) != int(target_pdg):
            continue
        if any(int(parent.getPDG()) == int(target_pdg) for parent in particle.getParents()):
            continue
        candidates.append((index, particle))
    if not candidates:
        return None, None
    electron_parented = [
        candidate
        for candidate in candidates
        if sorted(int(parent.getPDG()) for parent in candidate[1].getParents()) == [-11, 11]
    ]
    if electron_parented:
        candidates = electron_parented
    with_daughters = [candidate for candidate in candidates if len(candidate[1].getDaughters()) > 0]
    return (with_daughters or candidates)[0]


def dice_score(shared_energy: float, reco_energy: float, truth_energy: float) -> float:
    """Return the energy-weighted Dice score used for reco/TrueJet matching."""
    denominator = float(reco_energy) + float(truth_energy)
    if denominator <= 0.0:
        return 0.0
    return 2.0 * float(shared_energy) / denominator


def best_one_to_one_assignment(score_matrix: Sequence[Sequence[float]]) -> tuple[tuple[int, ...], float]:
    """Maximise the summed score over all square one-to-one assignments."""
    rows = [tuple(float(value) for value in row) for row in score_matrix]
    size = len(rows)
    if size == 0 or any(len(row) != size for row in rows):
        raise ValueError("score matrix must be non-empty and square")
    best_permutation: tuple[int, ...] | None = None
    best_score = -math.inf
    for permutation in itertools.permutations(range(size)):
        score = sum(rows[index][permutation[index]] for index in range(size))
        if score > best_score:
            best_permutation = permutation
            best_score = score
    assert best_permutation is not None
    return best_permutation, best_score


def normalize_true_columns(counts: Sequence[Sequence[float]]) -> list[list[float]]:
    """Column-normalize a predicted-row/true-column confusion matrix."""
    rows = [tuple(float(value) for value in row) for row in counts]
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("counts must be a non-empty rectangular matrix")
    column_sums = [sum(row[column] for row in rows) for column in range(len(rows[0]))]
    return [
        [value / column_sums[column] if column_sums[column] > 0.0 else 0.0 for column, value in enumerate(row)]
        for row in rows
    ]


def log1p_chi2_plus_flavor(chi2: float, flavor_score: float, flavor_weight: float = 0.3) -> float:
    """Frozen assignment score: ``log1p(max(0, chi2)) + w*flavor``."""
    values = (float(chi2), float(flavor_score), float(flavor_weight))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("chi2, flavor score, and weight must be finite")
    return math.log1p(max(0.0, values[0])) + values[2] * values[1]


def select_unique_combo_top_n(rows: Sequence[Mapping], top_n: int) -> list[Mapping]:
    """Keep every row belonging to the best N unique base ``combo_id`` values.

    Ordering reproduces the historical SLD/neutrino reranker: flavor prior,
    then candidate rank, then combo id.  Multiple subsolutions of a retained
    combo remain in their original input order.
    """
    if int(top_n) <= 0:
        raise ValueError("top_n must be positive")
    ordered_ids: list[int] = []
    seen: set[int] = set()
    for row in sorted(
        rows,
        key=lambda item: (
            float(item.get("flavor_charge_prior_total", item.get("flavor_score", math.inf))),
            int(item["candidate_rank"]),
            int(item["combo_id"]),
        ),
    ):
        combo_id = int(row["combo_id"])
        if combo_id in seen:
            continue
        seen.add(combo_id)
        ordered_ids.append(combo_id)
        if len(ordered_ids) >= int(top_n):
            break
    allowed = set(ordered_ids)
    return [row for row in rows if int(row["combo_id"]) in allowed]

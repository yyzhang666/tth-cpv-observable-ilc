"""Equivalence tests for extracted reco-performance pure helpers."""

import itertools
import math

import pytest

from ilc_tth_cpv.reco_performance import (
    best_one_to_one_assignment,
    dice_score,
    event_key,
    find_hard_particle,
    invariant_mass,
    log1p_chi2_plus_flavor,
    normalize_true_columns,
    select_unique_combo_top_n,
)


def test_event_key_includes_source_file_identity():
    assert event_key("physsim_chunk_1", 0, 17) == ("physsim_chunk_1", 0, 17)
    assert event_key("physsim_chunk_1", 0, 17) != event_key("physsim_chunk_2", 0, 17)


class Particle:
    def __init__(self, pdg, parents=(), daughters=()):
        self._pdg = pdg
        self._parents = list(parents)
        self._daughters = list(daughters)

    def getPDG(self):
        return self._pdg

    def getParents(self):
        return self._parents

    def getDaughters(self):
        return self._daughters


def test_hard_top_and_invariant_mass_match_historical_rule():
    parent_top = Particle(6)
    self_copy = Particle(6, [parent_top])
    other = Particle(25)
    index, selected = find_hard_particle([self_copy, other, parent_top], 6)
    assert (index, selected) == (2, parent_top)
    assert invariant_mass((0, 0, 100, 150), (0, 0, -100, 150)) == pytest.approx(300.0)


def test_hard_top_prefers_exact_beam_parents_then_daughters():
    electron, positron = Particle(11), Particle(-11)
    ordinary = Particle(6, daughters=[Particle(24)])
    beam_parented_without_daughters = Particle(6, parents=[electron, positron])
    beam_parented_with_daughters = Particle(6, parents=[electron, positron], daughters=[Particle(24)])
    index, selected = find_hard_particle(
        [ordinary, beam_parented_without_daughters, beam_parented_with_daughters], 6
    )
    assert (index, selected) == (2, beam_parented_with_daughters)


def test_dice_and_one_to_one_match_reference_implementation():
    matrix = [[0.9, 0.2, 0.1], [0.1, 0.8, 0.4], [0.2, 0.3, 0.7]]
    reference = max(
        ((perm, sum(matrix[i][perm[i]] for i in range(3))) for perm in itertools.permutations(range(3))),
        key=lambda item: item[1],
    )
    assert dice_score(4.0, 5.0, 7.0) == pytest.approx(8.0 / 12.0)
    assert best_one_to_one_assignment(matrix) == reference


def test_column_normalization_matches_old_loop_and_keeps_empty_column_zero():
    counts = [[7, 0, 2], [3, 0, 6]]
    expected = [[0.7, 0.0, 0.25], [0.3, 0.0, 0.75]]
    assert normalize_true_columns(counts) == expected


def test_logchi2_flavor_score_keeps_historical_nonnegative_chi2_rule():
    assert log1p_chi2_plus_flavor(3.0, 2.0) == pytest.approx(math.log(4.0) + 0.6)
    assert log1p_chi2_plus_flavor(-1.0, 2.0) == pytest.approx(0.6)


def test_unique_combo_topn_counts_base_combos_and_preserves_subsolutions():
    rows = [
        {"combo_id": 20, "candidate_rank": 1, "flavor_score": 0.2, "sub": "a"},
        {"combo_id": 10, "candidate_rank": 2, "flavor_score": 0.1, "sub": "a"},
        {"combo_id": 10, "candidate_rank": 3, "flavor_score": 0.1, "sub": "b"},
        {"combo_id": 30, "candidate_rank": 0, "flavor_score": 0.3, "sub": "a"},
    ]
    assert select_unique_combo_top_n(rows, 2) == rows[:3]


@pytest.mark.parametrize("bad", [[], [[1.0, 2.0]], [[1.0], [2.0]]])
def test_one_to_one_rejects_non_square_or_empty_input(bad):
    with pytest.raises(ValueError):
        best_one_to_one_assignment(bad)

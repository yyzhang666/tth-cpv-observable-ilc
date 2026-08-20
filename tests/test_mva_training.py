import copy
from pathlib import Path

import h5py
import numpy as np
import pytest

from scripts.mva.apply_selection import (
    reusable_score_file,
    validate_score_file,
    write_score_file,
)
from scripts.mva.evaluate_selection import choose_threshold
from scripts.mva.selection_mva_common import (
    apply_training_weights,
    binary_labels,
    training_weight_coefficients,
    implementation_identity,
    repo_root,
    sha256_file,
    validate_best_iteration,
    verify_implementation_identity,
)
from scripts.mva.train_selection_mva import train_booster


def test_cpv_is_excluded_and_tth_target_uses_category() -> None:
    categories = np.asarray([b"tth-hbb", b"tth-nonbb"])
    assert binary_labels(categories, "tth-sm").tolist() == [1, 0]
    assert binary_labels(categories, "tth-cpv").tolist() == [-1, -1]


def test_training_weights_balance_class_and_helicity() -> None:
    labels = np.asarray([0] * 10 + [0] * 5 + [0] * 4 + [0] * 1 + [1] * 6 + [1] * 2)
    polarization = np.asarray(
        ["eL.pL"] * 10 + ["eL.pR"] * 5 + ["eR.pL"] * 4 + ["eR.pR"]
        + ["eL.pR"] * 6 + ["eR.pL"] * 2
    )
    coefficients = training_weight_coefficients(labels, polarization)
    weights = apply_training_weights(labels, polarization, coefficients)
    total = len(labels)
    assert np.isclose(weights[labels == 0].sum(), total / 2)
    assert np.isclose(weights[labels == 1].sum(), total / 2)
    for label, helicity_count in ((0, 4), (1, 2)):
        shares = [
            weights[(labels == label) & (polarization == helicity)].sum()
            for helicity in sorted(set(polarization[labels == label]))
        ]
        assert np.allclose(shares, total / (2 * helicity_count))


def test_threshold_is_validation_only_and_lower_tie_wins() -> None:
    labels = np.asarray([1, 1, 0, 0], dtype=np.int8)
    scores = np.asarray([0.9, 0.8, 0.7, 0.1])
    weights = np.ones(4)
    threshold, scan = choose_threshold(labels, scores, weights)
    assert np.isclose(threshold, 0.7)
    assert len(scan) == 1001
    # A hypothetical test score array is deliberately not an input.
    changed_test_scores = np.asarray([0.0, 0.0, 1.0, 1.0])
    assert changed_test_scores.tolist() != scores.tolist()
    assert choose_threshold(labels, scores, weights)[0] == threshold


def test_fixed_seed_toy_xgboost_is_reproducible() -> None:
    rng = np.random.default_rng(7)
    train_x = rng.normal(size=(200, 25)).astype(np.float32)
    train_y = (train_x[:, 0] + 0.2 * train_x[:, 1] > 0).astype(np.int8)
    validation_x = rng.normal(size=(80, 25)).astype(np.float32)
    validation_y = (validation_x[:, 0] + 0.2 * validation_x[:, 1] > 0).astype(np.int8)
    train_weight = np.ones(len(train_y), dtype=np.float32)
    validation_weight = np.ones(len(validation_y), dtype=np.float32)
    config = {
        "tree_method": "hist",
        "max_depth": 3,
        "learning_rate": 0.1,
        "min_child_weight": 1,
        "reg_lambda": 1,
        "subsample": 1.0,
        "colsample_bytree": 1.0,
        "max_bin": 64,
        "eval_metric": "logloss",
        "seed": 123,
        "nthread": 1,
        "num_boost_round": 30,
        "early_stopping_rounds": 5,
    }
    _, _, first = train_booster(
        train_x, train_y, train_weight,
        validation_x, validation_y, validation_weight,
        config,
    )
    _, _, second = train_booster(
        train_x, train_y, train_weight,
        validation_x, validation_y, validation_weight,
        config,
    )
    assert np.array_equal(first, second)


def test_partial_apply_batch_reuses_valid_score_shard(tmp_path: Path) -> None:
    arrays = {
        "event_index": np.asarray([0, 1, 2], dtype=np.int64),
        "job_key": "job-a",
        "sample_key": np.asarray(["ttbb"] * 3),
        "polarization": np.asarray(["eL.pR"] * 3),
        "source_hdf5": tmp_path / "source.h5",
        "source_hdf5_sha256": "source-hash",
    }
    provenance = {
        "model_hash": "model-hash",
        "catalog_hash": "catalog-hash",
        "provenance_hash": "provenance-hash",
        "implementation_hash": "implementation-hash",
        "apply_script_hash": "apply-hash",
    }
    score_path = tmp_path / "job-a.scores.h5"
    write_score_file(
        score_path,
        arrays,
        np.asarray([0.1, 0.5, 0.9]),
        **provenance,
    )
    before = sha256_file(score_path)
    assert reusable_score_file(score_path, arrays, **provenance)
    assert sha256_file(score_path) == before
    assert not reusable_score_file(tmp_path / "job-b.scores.h5", arrays, **provenance)

    with h5py.File(score_path, "r+") as target:
        target.attrs["model_sha256"] = "wrong"
    with pytest.raises(RuntimeError, match="existing score mismatch for model_sha256"):
        validate_score_file(score_path, arrays, **provenance)


def test_tampered_best_iteration_fails() -> None:
    class FakeBooster:
        def attr(self, name: str) -> str | None:
            return "7" if name == "best_iteration" else None

    assert validate_best_iteration(FakeBooster(), {"best_iteration": 7}) == 7
    with pytest.raises(RuntimeError, match="best_iteration mismatch"):
        validate_best_iteration(FakeBooster(), {"best_iteration": 8})


def test_tampered_implementation_identity_fails() -> None:
    root = repo_root()
    expected = implementation_identity(root)
    tampered = copy.deepcopy(expected)
    tampered["script_sha256"]["scripts/mva/train_selection_mva.py"] = "0" * 64
    with pytest.raises(RuntimeError, match="implementation hash mismatch"):
        verify_implementation_identity(root, tampered)

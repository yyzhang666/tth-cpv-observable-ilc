import json
from pathlib import Path

import h5py
import pytest
import yaml

from scripts.mva.selection_mva_common import (
    load_authority,
    validate_feature_list,
    validate_job_hdf5,
)
from tests.mva_test_helpers import rehash_catalog, write_authority


def test_catalog_authority_and_hdf5_close(tmp_path: Path) -> None:
    config = write_authority(tmp_path)
    authority = load_authority(config)
    path, row, split = validate_job_hdf5(authority, "job-a")
    assert path.name == "job-a.h5"
    assert row["n_events"] == split["n_events"] == 4


def test_stale_mva_config_hash_fails(tmp_path: Path) -> None:
    config = write_authority(tmp_path)
    paths = yaml.safe_load(config.read_text())["paths"]
    Path(paths["mva_config"]).write_text("meta: {analysis_name: changed}\n")
    with pytest.raises(RuntimeError, match="stale weights catalog source hash"):
        load_authority(config)


def test_duplicate_and_missing_jobs_fail(tmp_path: Path) -> None:
    config = write_authority(tmp_path)
    paths = yaml.safe_load(config.read_text())["paths"]
    split_path = Path(paths["split_assignment"])
    split = json.loads(split_path.read_text())
    split["jobs"].append(dict(split["jobs"][0]))
    split_path.write_text(json.dumps(split))
    rehash_catalog(config)
    with pytest.raises(RuntimeError, match="duplicate job_key"):
        load_authority(config)

    config = write_authority(tmp_path / "missing")
    paths = yaml.safe_load(config.read_text())["paths"]
    split_path = Path(paths["split_assignment"])
    split = json.loads(split_path.read_text())
    split["jobs"] = []
    split_path.write_text(json.dumps(split))
    rehash_catalog(config)
    with pytest.raises(RuntimeError, match="exact job-set mismatch"):
        load_authority(config)


def test_hdf5_identity_and_content_hash_fail(tmp_path: Path) -> None:
    config = write_authority(tmp_path)
    authority = load_authority(config)
    h5_path = tmp_path / "job-a.h5"
    with h5py.File(h5_path, "r+") as target:
        target["event_index"][0] = 99
    with pytest.raises(RuntimeError, match="content hash mismatch"):
        validate_job_hdf5(authority, "job-a")


def test_hdf5_identity_fails_after_catalog_rehash(tmp_path: Path) -> None:
    config = write_authority(tmp_path)
    authority = load_authority(config)
    h5_path = tmp_path / "job-a.h5"
    with h5py.File(h5_path, "r+") as target:
        target["sample_key"][:] = "ttz"
    with pytest.raises(RuntimeError, match="HDF5 sample_key mismatch"):
        validate_job_hdf5(authority, "job-a", verify_hash=False)


def test_hdf5_dataset_length_fails_after_catalog_rehash(tmp_path: Path) -> None:
    from scripts.mva.selection_mva_common import BASELINE_FEATURES

    config = write_authority(tmp_path)
    authority = load_authority(config)
    h5_path = tmp_path / "job-a.h5"
    with h5py.File(h5_path, "r+") as target:
        del target[BASELINE_FEATURES[0]]
        target.create_dataset(BASELINE_FEATURES[0], data=[0.1, 0.2, 0.3])
    with pytest.raises(RuntimeError, match="dataset .* length mismatch"):
        validate_job_hdf5(authority, "job-a", verify_hash=False)


def test_leakage_or_feature_reordering_fails() -> None:
    from scripts.mva.selection_mva_common import BASELINE_FEATURES

    with pytest.raises(RuntimeError, match="25-feature order"):
        validate_feature_list(BASELINE_FEATURES[:-1] + ["weight_phys"])
    with pytest.raises(RuntimeError, match="25-feature order"):
        validate_feature_list(list(reversed(BASELINE_FEATURES)))

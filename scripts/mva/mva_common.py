#!/usr/bin/env python3
"""Common utilities for the semileptonic selection-MVA pipeline."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import uproot

from ilc_tth_cpv.objects import classify_higgs_decay


TTH_TRUTH_CLASSIFIED_SAMPLES = frozenset(
    {
        "tth-sm",
        "tth-cpv",
    }
)

class UndefinedOpeningAngleError(ValueError):
    """Raised when an opening angle has a zero-momentum input."""


class SkipMVAEvent(RuntimeError):
    """A reconstructed event that cannot enter the frozen MVA schema."""

    def __init__(
        self,
        *,
        event_index: int,
        reason: str,
        feature: str,
        details: dict[str, Any],
    ) -> None:
        super().__init__(
            f"event_index={event_index}: "
            f"skip event because {reason}; "
            f"feature={feature}"
        )

        self.event_index = int(event_index)
        self.reason = str(reason)
        self.feature = str(feature)
        self.details = dict(details)

    def as_record(self) -> dict[str, Any]:
        """Return a JSON-serializable skip record."""
        return {
            "event_index": self.event_index,
            "reason": self.reason,
            "feature": self.feature,
            "details": self.details,
        }


def load_manifest_rows(
    manifest_path: Path,
    *,
    included_only: bool = True,
) -> list[dict[str, str]]:
    """Read the canonical CSV manifest."""
    with manifest_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))

    if included_only:
        rows = [
            row
            for row in rows
            if int(row["include"]) == 1
        ]

    if not rows:
        raise ValueError(
            f"No usable rows found in manifest: {manifest_path}"
        )

    return rows


def import_lcio():
    """Import LCIO bindings from either supported Python namespace."""
    try:
        from pyLCIO import IOIMPL

        return IOIMPL
    except ImportError:
        try:
            from lcio import IOIMPL

            return IOIMPL
        except ImportError as exc:
            raise RuntimeError(
                "Cannot import pyLCIO or lcio. "
                "Source the ILCSoft/Key4hep environment first."
            ) from exc


def derive_event_id(
    manifest_row: dict[str, str],
    event_index: int,
) -> str:
    """Construct a globally unique reconstructed-event identity."""
    fields = [
        manifest_row["generator"],
        manifest_row["sample_key"],
        manifest_row["polarization"],
        manifest_row["job_key"],
        manifest_row["physical_part"],
        str(event_index),
    ]

    return "::".join(fields)


def read_selected_kinfit_rows(
    root_path: Path,
    *,
    tree_name: str,
    required_branches: Iterable[str],
) -> dict[str, np.ndarray]:
    """Read accepted and fit-successful rows from one KinFit best tree."""
    required = list(required_branches)

    with uproot.open(root_path) as root_file:
        if tree_name not in root_file:
            available = sorted(
                key.split(";")[0]
                for key in root_file.keys()
            )
            raise KeyError(
                f"Tree {tree_name!r} not found in {root_path}; "
                f"available={available}"
            )

        tree = root_file[tree_name]
        available_branches = set(tree.keys())

        missing = sorted(
            set(required) - available_branches
        )
        if missing:
            raise KeyError(
                f"Missing KinFit branches in {root_path}: {missing}"
            )

        arrays = tree.arrays(
            required,
            library="np",
        )

    lengths = {
        name: len(values)
        for name, values in arrays.items()
    }
    if len(set(lengths.values())) != 1:
        raise RuntimeError(
            f"Inconsistent branch lengths in {root_path}: {lengths}"
        )

    tree_entries = next(iter(lengths.values()), 0)

    accepted = np.asarray(
        arrays["accepted"],
        dtype=np.int64,
    )
    fit_success = np.asarray(
        arrays["fit_success"],
        dtype=np.int64,
    )

    # The formal best tree contains one row per accepted event.
    if tree_entries and not np.all(accepted == 1):
        bad = np.flatnonzero(accepted != 1)[:10]
        raise RuntimeError(
            f"Best tree contains non-accepted rows in {root_path}; "
            f"entry indices={bad.tolist()}"
        )

    selected_mask = (
        (accepted == 1)
        & (fit_success == 1)
    )

    selected = {
        name: np.asarray(values)[selected_mask]
        for name, values in arrays.items()
    }

    event_indices = np.asarray(
        selected["event_index"],
        dtype=np.int64,
    )

    if np.any(event_indices < 0):
        bad = event_indices[event_indices < 0][:10]
        raise RuntimeError(
            f"Negative event_index values in {root_path}: "
            f"{bad.tolist()}"
        )

    if len(np.unique(event_indices)) != len(event_indices):
        duplicates = [
            value
            for value, count in Counter(
                event_indices.tolist()
            ).items()
            if count > 1
        ]
        raise RuntimeError(
            f"Duplicated event_index values in {root_path}: "
            f"{duplicates[:10]}"
        )

    if len(event_indices) > 1:
        if not np.all(np.diff(event_indices) > 0):
            raise RuntimeError(
                f"Selected event_index values are not strictly "
                f"increasing in {root_path}"
            )

    selected["_tree_entries"] = np.asarray(
        [tree_entries],
        dtype=np.int64,
    )
    selected["_accepted_entries"] = np.asarray(
        [int(np.count_nonzero(accepted == 1))],
        dtype=np.int64,
    )
    selected["_selected_entries"] = np.asarray(
        [int(np.count_nonzero(selected_mask))],
        dtype=np.int64,
    )

    return selected


def collection_size(
    event: Any,
    collection_name: str,
) -> int:
    """Return an LCCollection size or fail with collection context."""
    try:
        collection = event.getCollection(
            collection_name
        )
    except Exception as exc:
        raise RuntimeError(
            f"Missing LCIO collection {collection_name!r}"
        ) from exc

    return int(collection.getNumberOfElements())


def read_lcio_snapshots(
    input_path: Path,
    requested_event_indices: Iterable[int],
    *,
    collection_names: dict[str, str],
) -> dict[int, dict[str, Any]]:
    """Read only requested event indices from one SLCIO file.

    event_index is interpreted as the zero-based sequential event position,
    matching TTHSemiLepKinFit::_eventIndex = _nEvt - 1.
    """
    requested = {
        int(value)
        for value in requested_event_indices
    }

    if not requested:
        return {}

    max_requested = max(requested)
    found: dict[int, dict[str, Any]] = {}

    IOIMPL = import_lcio()
    reader = (
        IOIMPL.LCFactory
        .getInstance()
        .createLCReader()
    )
    reader.open(str(input_path))

    try:
        sequential_index = 0

        while sequential_index <= max_requested:
            try:
                event = reader.readNextEvent()
            except ReferenceError:
                event = None
            except Exception as exc:
                raise RuntimeError(
                    f"Failed reading {input_path} at sequential "
                    f"event index {sequential_index}: {exc}"
                ) from exc

            if event is None:
                break

            if sequential_index in requested:
                sizes = {
                    logical_name: collection_size(
                        event,
                        collection_name,
                    )
                    for logical_name, collection_name
                    in collection_names.items()
                }

                found[sequential_index] = {
                    "run_number": int(
                        event.getRunNumber()
                    ),
                    "event_number": int(
                        event.getEventNumber()
                    ),
                    "collection_sizes": sizes,
                }

            sequential_index += 1

    finally:
        try:
            reader.close()
        except Exception:
            pass

    missing = sorted(requested - set(found))
    if missing:
        raise RuntimeError(
            f"SLCIO ended before requested event indices were found: "
            f"path={input_path}, missing={missing[:20]}"
        )

    return found


def validate_root_slcio_join(
    manifest_row: dict[str, str],
    *,
    tree_name: str,
    required_branches: Iterable[str],
    collection_names: dict[str, str],
    expected_iso_multiplicity: int,
    expected_fit_jets: int,
    expected_flavor_jets: int,
) -> dict[str, Any]:
    """Run a fail-closed ROOT-to-SLCIO join for one manifest row."""
    root_path = Path(
        manifest_row["kinfit_root_path"]
    )
    input_path = Path(
        manifest_row["input_path"]
    )

    root_rows = read_selected_kinfit_rows(
        root_path,
        tree_name=tree_name,
        required_branches=required_branches,
    )

    event_indices = np.asarray(
        root_rows["event_index"],
        dtype=np.int64,
    )

    if len(event_indices) == 0:
        raise RuntimeError(
            f"No accepted && fit_success rows in {root_path}"
        )

    input_readable_events = int(
        manifest_row["input_readable_events"]
    )

    if int(event_indices[-1]) >= input_readable_events:
        raise RuntimeError(
            f"ROOT event_index exceeds manifest input denominator: "
            f"job={manifest_row['job_key']}, "
            f"max_event_index={int(event_indices[-1])}, "
            f"input_readable_events={input_readable_events}"
        )

    snapshots = read_lcio_snapshots(
        input_path,
        event_indices,
        collection_names=collection_names,
    )

    event_ids: list[str] = []
    lepton_flavors = Counter()
    mismatches: list[str] = []

    for position, event_index_value in enumerate(
        event_indices
    ):
        event_index = int(event_index_value)
        snapshot = snapshots[event_index]

        root_run = int(
            root_rows["run_number"][position]
        )
        root_event = int(
            root_rows["event_number"][position]
        )

        lcio_run = int(snapshot["run_number"])
        lcio_event = int(
            snapshot["event_number"]
        )

        if (
            root_run != lcio_run
            or root_event != lcio_event
        ):
            mismatches.append(
                f"event_index={event_index}: "
                f"ROOT=({root_run},{root_event}), "
                f"SLCIO=({lcio_run},{lcio_event})"
            )
            continue

        sizes = snapshot["collection_sizes"]

        n_iso_e = int(sizes["iso_electrons"])
        n_iso_mu = int(sizes["iso_muons"])
        n_iso = n_iso_e + n_iso_mu

        if n_iso != expected_iso_multiplicity:
            mismatches.append(
                f"event_index={event_index}: "
                f"n_iso_e={n_iso_e}, n_iso_mu={n_iso_mu}, "
                f"expected_total={expected_iso_multiplicity}"
            )

        if int(sizes["fit_jets"]) != expected_fit_jets:
            mismatches.append(
                f"event_index={event_index}: "
                f"fit_jets={sizes['fit_jets']}, "
                f"expected={expected_fit_jets}"
            )

        if (
            int(sizes["flavor_jets"])
            != expected_flavor_jets
        ):
            mismatches.append(
                f"event_index={event_index}: "
                f"flavor_jets={sizes['flavor_jets']}, "
                f"expected={expected_flavor_jets}"
            )

        if n_iso_e == 1 and n_iso_mu == 0:
            lepton_flavors["electron"] += 1
        elif n_iso_e == 0 and n_iso_mu == 1:
            lepton_flavors["muon"] += 1
        else:
            lepton_flavors["invalid"] += 1

        event_ids.append(
            derive_event_id(
                manifest_row,
                event_index,
            )
        )

    if mismatches:
        preview = "\n".join(
            f"  - {message}"
            for message in mismatches[:20]
        )
        raise RuntimeError(
            f"ROOT–SLCIO join failed for "
            f"{manifest_row['job_key']} with "
            f"{len(mismatches)} mismatches:\n{preview}"
        )

    if len(set(event_ids)) != len(event_ids):
        raise RuntimeError(
            f"Duplicated event IDs for "
            f"{manifest_row['job_key']}"
        )

    return {
        "sample_key": manifest_row["sample_key"],
        "job_key": manifest_row["job_key"],
        "polarization": manifest_row["polarization"],
        "logical_shard": manifest_row["logical_shard"],
        "physical_part": manifest_row["physical_part"],
        "input_path": str(input_path),
        "kinfit_root_path": str(root_path),
        "tree_entries": int(
            root_rows["_tree_entries"][0]
        ),
        "accepted_entries": int(
            root_rows["_accepted_entries"][0]
        ),
        "selected_entries": int(
            root_rows["_selected_entries"][0]
        ),
        "first_event_index": int(
            event_indices[0]
        ),
        "last_event_index": int(
            event_indices[-1]
        ),
        "event_id_unique": True,
        "run_event_match": True,
        "single_isolated_lepton": True,
        "six_fit_jets": True,
        "six_flavor_jets": True,
        "lepton_flavors": dict(
            sorted(lepton_flavors.items())
        ),
    }


def find_smoke_row(
    manifest_rows: list[dict[str, str]],
    *,
    sample_key: str,
    tree_name: str,
    required_branches: Iterable[str],
) -> dict[str, str]:
    """Find the first manifest row containing a selected KinFit event."""
    candidates = [
        row
        for row in manifest_rows
        if row["sample_key"] == sample_key
    ]

    if not candidates:
        raise ValueError(
            f"No manifest rows for sample_key={sample_key!r}"
        )

    failures: list[str] = []

    for row in candidates:
        root_path = Path(
            row["kinfit_root_path"]
        )

        try:
            selected = read_selected_kinfit_rows(
                root_path,
                tree_name=tree_name,
                required_branches=required_branches,
            )
        except Exception as exc:
            failures.append(
                f"{row['job_key']}: {exc}"
            )
            continue

        if int(selected["_selected_entries"][0]) > 0:
            return row

        failures.append(
            f"{row['job_key']}: no selected rows"
        )

    preview = "\n".join(
        f"  - {message}"
        for message in failures[:10]
    )

    raise RuntimeError(
        f"No usable smoke row found for "
        f"sample_key={sample_key!r}:\n{preview}"
    )


# =============================================================================
# MVA feature extraction
# =============================================================================

ROOT_EXPORT_BRANCHES = [
    "run_number",
    "event_number",
    "event_index",
    "accepted",
    "fit_status",
    "fit_success",

    "best_combo_id",
    "idx_W1",
    "idx_W2",
    "idx_bhad",
    "idx_blep",
    "idx_H1",
    "idx_H2",

    "fitprob",
    "fitchi2",
    "chi2_over_ndof",
    "ndof",

    "final_selection_score",
    "final_fit_score",
    "final_flavor_score",

    "mW_had_postfit",
    "mt_had_postfit",
    "mt_lep_postfit",
    "mH_postfit",

    "nu_fit_px",
    "nu_fit_py",
    "nu_fit_pz",
    "nu_fit_E",

    "lepton_charge",
    "lepton_flavor",
]


ASSIGNMENT_BRANCHES = {
    "W1": "idx_W1",
    "W2": "idx_W2",
    "bhad": "idx_bhad",
    "blep": "idx_blep",
    "H1": "idx_H1",
    "H2": "idx_H2",
}


ROOT_SCALAR_FEATURES = [
    "fitprob",
    "fitchi2",
    "chi2_over_ndof",
    "ndof",

    "final_selection_score",
    "final_fit_score",
    "final_flavor_score",

    "mW_had_postfit",
    "mt_had_postfit",
    "mt_lep_postfit",
    "mH_postfit",

    "nu_fit_px",
    "nu_fit_py",
    "nu_fit_pz",
    "nu_fit_E",
]


def import_lcio_util():
    """Import the LCIO UTIL module from either supported namespace."""
    try:
        from pyLCIO import UTIL

        return UTIL
    except ImportError:
        try:
            from lcio import UTIL

            return UTIL
        except ImportError as exc:
            raise RuntimeError(
                "Cannot import pyLCIO. "
                "Source the ILCSoft/Key4hep environment first."
            ) from exc


def collection_objects(
    event: Any,
    collection_name: str,
) -> tuple[Any, list[Any]]:
    """Return one LCCollection and its elements."""
    try:
        collection = event.getCollection(
            collection_name
        )
    except Exception as exc:
        raise RuntimeError(
            f"Missing LCIO collection {collection_name!r}"
        ) from exc

    objects = [
        collection.getElementAt(index)
        for index in range(
            collection.getNumberOfElements()
        )
    ]

    return collection, objects


def normalize_manifest_class_label(
    value: Any,
) -> str:
    """Normalize common binary-label spellings to signal/background."""
    text = str(value).strip()
    lowered = text.lower()

    if lowered in {
        "1",
        "signal",
        "sig",
        "true",
    }:
        return "signal"

    if lowered in {
        "0",
        "background",
        "bkg",
        "false",
    }:
        return "background"

    return text


def classify_event_target(
    *,
    event: Any,
    sequential_index: int,
    sample_key: str,
    manifest_class_label: str,
    collections: dict[str, str],
) -> dict[str, Any]:
    """Assign the event-level MVA class using Higgs truth for ttH.

    Inclusive ttH samples are retained in full:
      - truth H->bb is signal;
      - every identified H->non-bb mode is background.

    Other samples retain their manifest class label.
    """
    normalized_manifest_label = normalize_manifest_class_label(
        manifest_class_label
    )

    if sample_key not in TTH_TRUTH_CLASSIFIED_SAMPLES:
        return {
            "manifest_class_label": str(
                manifest_class_label
            ),
            "class_label": normalized_manifest_label,
            "analysis_category": sample_key,
            "truth_higgs_decay": "not-applicable",
            "truth_is_hbb": -1,
        }

    _, mc_particles = collection_objects(
        event,
        str(
            collections.get(
                "mc_particles",
                "MCParticle",
            )
        ),
    )

    truth_higgs_decay = classify_higgs_decay(
        mc_particles
    )

    # H->none means the ttH truth record could not be resolved. Do not
    # silently reinterpret this as a physical non-bb decay.
    if truth_higgs_decay == "H->none":
        raise RuntimeError(
            f"event_index={sequential_index}: "
            "cannot identify a hard-process Higgs in the ttH MC truth"
        )

    truth_is_hbb = int(
        truth_higgs_decay == "H->bb"
    )

    return {
        "manifest_class_label": str(
            manifest_class_label
        ),
        "class_label": (
            "signal"
            if truth_is_hbb
            else "background"
        ),
        "analysis_category": (
            "tth-hbb"
            if truth_is_hbb
            else "tth-nonbb"
        ),
        "truth_higgs_decay": truth_higgs_decay,
        "truth_is_hbb": truth_is_hbb,
    }


def particle_four_momentum(
    particle: Any,
) -> np.ndarray:
    """Return [E, px, py, pz] for one ReconstructedParticle."""
    momentum = particle.getMomentum()

    return np.asarray(
        [
            float(particle.getEnergy()),
            float(momentum[0]),
            float(momentum[1]),
            float(momentum[2]),
        ],
        dtype=np.float64,
    )


def transverse_momentum(
    four_vector: np.ndarray,
) -> float:
    """Return transverse momentum from [E, px, py, pz]."""
    return float(
        math.hypot(
            float(four_vector[1]),
            float(four_vector[2]),
        )
    )


def polar_angle(
    four_vector: np.ndarray,
) -> float:
    """Return theta in [0, pi] from [E, px, py, pz]."""
    pt = transverse_momentum(
        four_vector
    )

    return float(
        math.atan2(
            pt,
            float(four_vector[3]),
        )
    )


def cosine_opening_angle(first: np.ndarray, second: np.ndarray) -> float:
    """Return the opening-angle cosine of two four-momenta."""
    first_p = np.asarray(first[1:4], dtype=np.float64)
    second_p = np.asarray(second[1:4], dtype=np.float64)

    if not np.all(np.isfinite(first_p)) or not np.all(np.isfinite(second_p)):
        raise ValueError("Cannot define an opening angle with non-finite momentum components")

    first_norm = math.hypot(*first_p)
    second_norm = math.hypot(*second_p)

    if first_norm == 0.0 or second_norm == 0.0:
        raise UndefinedOpeningAngleError(
            "Cannot define an opening angle for a zero-momentum object"
        )

    value = float(np.dot(first_p / first_norm, second_p / second_norm))

    if not math.isfinite(value):
        raise ValueError("Opening-angle cosine is non-finite after normalization")

    return float(np.clip(value, -1.0, 1.0))
def required_opening_angle(
    first: np.ndarray,
    second: np.ndarray,
    *,
    event_index: int,
    feature: str,
) -> float:
    """Calculate a required angle or skip an invalid event."""
    try:
        return cosine_opening_angle(first, second)

    except (UndefinedOpeningAngleError, ValueError) as exc:
        reason = (
            "zero_momentum_opening_angle"
            if isinstance(exc, UndefinedOpeningAngleError)
            else "non_finite_opening_angle"
        )

        raise SkipMVAEvent(
            event_index=event_index,
            reason=reason,
            feature=feature,
            details={
                "first_p4": [float(x) for x in first],
                "second_p4": [float(x) for x in second],
                "error": str(exc),
            },
        ) from exc

def normalized_pid_name(
    value: str,
) -> str:
    """Normalize ParticleID parameter names for alias matching."""
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).lower(),
    )


def make_pid_accessor(
    collection: Any,
    algorithm_name: str,
):
    """Create an accessor for one ParticleID algorithm."""
    UTIL = import_lcio_util()

    try:
        handler = UTIL.PIDHandler(
            collection
        )
        algorithm_id = handler.getAlgorithmID(
            algorithm_name
        )
    except Exception as exc:
        raise RuntimeError(
            f"Cannot find ParticleID algorithm "
            f"{algorithm_name!r}"
        ) from exc

    try:
        parameter_names = [
            str(value)
            for value in handler.getParameterNames(
                algorithm_id
            )
        ]
    except Exception:
        parameter_names = []

    def read_parameters(
        particle: Any,
    ) -> tuple[dict[str, float], list[float]]:
        try:
            particle_id = handler.getParticleID(
                particle,
                algorithm_id,
            )
            values = [
                float(value)
                for value in particle_id.getParameters()
            ]
        except Exception as exc:
            raise RuntimeError(
                f"Cannot read ParticleID algorithm "
                f"{algorithm_name!r}"
            ) from exc

        if (
            parameter_names
            and len(parameter_names) != len(values)
        ):
            raise RuntimeError(
                f"ParticleID parameter-name/value mismatch for "
                f"{algorithm_name!r}: "
                f"names={parameter_names}, values={values}"
            )

        mapping = (
            dict(zip(parameter_names, values))
            if parameter_names
            else {}
        )

        return mapping, values

    return parameter_names, read_parameters


def resolve_pid_parameter(
    mapping: dict[str, float],
    aliases: Iterable[str],
    *,
    algorithm_name: str,
    field_name: str,
    raw_values: list[float],
) -> float:
    """Resolve a ParticleID value using actual parameter names."""
    normalized_mapping: dict[str, tuple[str, float]] = {}

    for source_name, source_value in mapping.items():
        normalized = normalized_pid_name(
            source_name
        )

        if normalized in normalized_mapping:
            previous_name, previous_value = (
                normalized_mapping[normalized]
            )

            if not math.isclose(
                float(previous_value),
                float(source_value),
                rel_tol=0.0,
                abs_tol=0.0,
            ):
                raise RuntimeError(
                    f"Ambiguous ParticleID names "
                    f"{previous_name!r} and {source_name!r}"
                )

        normalized_mapping[normalized] = (
            source_name,
            float(source_value),
        )

    for alias in aliases:
        normalized_alias = normalized_pid_name(
            alias
        )

        if normalized_alias in normalized_mapping:
            return float(
                normalized_mapping[
                    normalized_alias
                ][1]
            )

    raise RuntimeError(
        f"Cannot resolve ParticleID field {field_name!r} "
        f"for algorithm {algorithm_name!r}. "
        f"Available names={list(mapping)}, "
        f"raw_values={raw_values}"
    )


def update_pid_schema(
    schema_state: dict[str, list[str]],
    algorithm_name: str,
    parameter_names: list[str],
) -> None:
    """Require a stable ParticleID schema across exported events."""
    names = [
        str(value)
        for value in parameter_names
    ]

    if algorithm_name not in schema_state:
        schema_state[algorithm_name] = names
        return

    if schema_state[algorithm_name] != names:
        raise RuntimeError(
            f"ParticleID schema changed for "
            f"{algorithm_name!r}: "
            f"first={schema_state[algorithm_name]}, "
            f"current={names}"
        )


def read_weaver_tags(
    flavor_collection: Any,
    flavor_jets: list[Any],
    *,
    config: dict,
    schema_state: dict[str, list[str]],
) -> tuple[np.ndarray, np.ndarray]:
    """Read six per-jet B and C probabilities."""
    algorithm_name = str(
        config["algorithm"]
    )
    fields = config["fields"]

    parameter_names, accessor = (
        make_pid_accessor(
            flavor_collection,
            algorithm_name,
        )
    )

    update_pid_schema(
        schema_state,
        algorithm_name,
        parameter_names,
    )

    b_tags = []
    c_tags = []

    for jet_index, jet in enumerate(
        flavor_jets
    ):
        mapping, raw_values = accessor(
            jet
        )

        pb = resolve_pid_parameter(
            mapping,
            fields["pb"],
            algorithm_name=algorithm_name,
            field_name="pb",
            raw_values=raw_values,
        )
        pbbar = resolve_pid_parameter(
            mapping,
            fields["pbbar"],
            algorithm_name=algorithm_name,
            field_name="pbbar",
            raw_values=raw_values,
        )
        pc = resolve_pid_parameter(
            mapping,
            fields["pc"],
            algorithm_name=algorithm_name,
            field_name="pc",
            raw_values=raw_values,
        )
        pcbar = resolve_pid_parameter(
            mapping,
            fields["pcbar"],
            algorithm_name=algorithm_name,
            field_name="pcbar",
            raw_values=raw_values,
        )

        values = [pb, pbbar, pc, pcbar]

        if not all(
            math.isfinite(value)
            for value in values
        ):
            raise RuntimeError(
                f"Non-finite Weaver output for jet "
                f"{jet_index}: {values}"
            )

        b_tag = pb + pbbar
        c_tag = pc + pcbar

        if not (
            -1.0e-5 <= b_tag <= 1.0 + 1.0e-5
        ):
            raise RuntimeError(
                f"Invalid B probability for jet "
                f"{jet_index}: {b_tag}"
            )

        if not (
            -1.0e-5 <= c_tag <= 1.0 + 1.0e-5
        ):
            raise RuntimeError(
                f"Invalid C probability for jet "
                f"{jet_index}: {c_tag}"
            )

        b_tags.append(b_tag)
        c_tags.append(c_tag)

    return (
        np.asarray(
            b_tags,
            dtype=np.float64,
        ),
        np.asarray(
            c_tags,
            dtype=np.float64,
        ),
    )


def read_yth_values(
    flavor_collection: Any,
    flavor_jets: list[Any],
    *,
    config: dict,
    schema_state: dict[str, list[str]],
) -> tuple[dict[str, float], int]:
    """Read event-level y45/y56/y67 from the first usable jet PID."""
    algorithm_name = str(
        config["algorithm"]
    )
    fields = config["fields"]

    parameter_names, accessor = (
        make_pid_accessor(
            flavor_collection,
            algorithm_name,
        )
    )

    update_pid_schema(
        schema_state,
        algorithm_name,
        parameter_names,
    )

    failures = []

    for jet_index, jet in enumerate(
        flavor_jets
    ):
        try:
            mapping, raw_values = accessor(
                jet
            )

            result = {
                name: resolve_pid_parameter(
                    mapping,
                    aliases,
                    algorithm_name=algorithm_name,
                    field_name=name,
                    raw_values=raw_values,
                )
                for name, aliases in fields.items()
            }

            if not all(
                math.isfinite(value)
                for value in result.values()
            ):
                raise RuntimeError(
                    f"Non-finite yth values: {result}"
                )

            return result, jet_index

        except Exception as exc:
            failures.append(
                f"jet {jet_index}: {exc}"
            )

    raise RuntimeError(
        f"Cannot read yth values from any flavor jet. "
        f"Failures={failures}"
    )


def python_scalar(
    value: Any,
) -> int | float | str:
    """Convert a NumPy scalar to a plain Python scalar."""
    if isinstance(value, np.generic):
        return value.item()

    return value


def build_export_event_row(
    *,
    event: Any,
    sequential_index: int,
    root_position: int,
    root_rows: dict[str, np.ndarray],
    manifest_row: dict[str, str],
    cfg: dict,
    pid_schema_state: dict[str, list[str]],
) -> dict[str, Any]:
    """Build one MVA event row after the ROOT–SLCIO join."""
    collections = cfg["collections"]

    _, fit_jets = collection_objects(
        event,
        str(collections["fit_jets"]),
    )
    flavor_collection, flavor_jets = collection_objects(
        event,
        str(collections["flavor_jets"]),
    )
    electron_collection, electrons = collection_objects(
        event,
        str(collections["iso_electrons"]),
    )
    muon_collection, muons = collection_objects(
        event,
        str(collections["iso_muons"]),
    )

    sample_key = str(
        manifest_row["sample_key"]
    )

    target = classify_event_target(
        event=event,
        sequential_index=sequential_index,
        sample_key=sample_key,
        manifest_class_label=manifest_row["class_label"],
        collections=collections,
    )

    if len(fit_jets) != 6:
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"expected 6 fit jets, found {len(fit_jets)}"
        )

    if len(flavor_jets) != 6:
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"expected 6 flavor jets, found {len(flavor_jets)}"
        )

    if len(electrons) + len(muons) != 1:
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"n_e={len(electrons)}, n_mu={len(muons)}"
        )

    if electrons:
        lepton = electrons[0]
        lepton_collection = electron_collection
        lepton_collection_name = str(
            collections["iso_electrons"]
        )
    else:
        lepton = muons[0]
        lepton_collection = muon_collection
        lepton_collection_name = str(
            collections["iso_muons"]
        )

    try:
        lepton_tag_type = int(
            lepton_collection
            .getParameters()
            .getIntVal("ISOLepType")
        )
        lepton_tag_score = float(
            lepton_collection
            .getParameters()
            .getFloatVal("ISOLepTagging")
        )
    except Exception as exc:
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"cannot read ISOLepType/ISOLepTagging from "
            f"{lepton_collection_name}"
        ) from exc

    if lepton_tag_type == 11:
        lepton_tag_flavor = "electron"
    elif lepton_tag_type == 13:
        lepton_tag_flavor = "muon"
    else:
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"invalid ISOLepType={lepton_tag_type}"
        )

    lepton_reco_type = int(
        lepton.getType()
    )
    lepton_reco_type_abs = abs(
        lepton_reco_type
    )

    root_run = int(
        root_rows["run_number"][root_position]
    )
    root_event = int(
        root_rows["event_number"][root_position]
    )

    lcio_run = int(
        event.getRunNumber()
    )
    lcio_event = int(
        event.getEventNumber()
    )

    if (
        root_run != lcio_run
        or root_event != lcio_event
    ):
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"ROOT=({root_run},{root_event}), "
            f"SLCIO=({lcio_run},{lcio_event})"
        )

    kinfit_lepton_reco_type_abs = int(
        root_rows["lepton_flavor"][
            root_position
        ]
    )

    if (
        kinfit_lepton_reco_type_abs
        != lepton_reco_type_abs
    ):
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"ROOT lepton_flavor="
            f"{kinfit_lepton_reco_type_abs}, "
            f"SLCIO abs(getType())="
            f"{lepton_reco_type_abs}"
        )

    root_charge = float(
        root_rows["lepton_charge"][
            root_position
        ]
    )
    lcio_charge = float(
        lepton.getCharge()
    )

    if not math.isclose(
        root_charge,
        lcio_charge,
        rel_tol=0.0,
        abs_tol=1.0e-5,
    ):
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"ROOT charge={root_charge}, "
            f"LCIO charge={lcio_charge}"
        )

    assignment = {
        role: int(
            root_rows[branch][root_position]
        )
        for role, branch
        in ASSIGNMENT_BRANCHES.items()
    }

    assignment_indices = list(
        assignment.values()
    )

    if sorted(assignment_indices) != list(
        range(6)
    ):
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"invalid assignment={assignment}"
        )

    jet_p4 = np.asarray(
        [
            particle_four_momentum(jet)
            for jet in fit_jets
        ],
        dtype=np.float64,
    )
    lepton_p4 = particle_four_momentum(
        lepton
    )

    b_tags, c_tags = read_weaver_tags(
        flavor_collection,
        flavor_jets,
        config=cfg["pid"]["weaver"],
        schema_state=pid_schema_state,
    )

    yth_values, yth_source_jet = read_yth_values(
        flavor_collection,
        flavor_jets,
        config=cfg["pid"]["yth"],
        schema_state=pid_schema_state,
    )

    sorted_b = np.sort(
        b_tags
    )[::-1]
    sorted_c = np.sort(
        c_tags
    )[::-1]

    p_H1 = jet_p4[
        assignment["H1"]
    ]
    p_H2 = jet_p4[
        assignment["H2"]
    ]
    p_H = p_H1 + p_H2

    p_hadtop = (
        jet_p4[assignment["W1"]]
        + jet_p4[assignment["W2"]]
        + jet_p4[assignment["bhad"]]
    )

    # "Visible" explicitly excludes the fitted neutrino.
    p_leptop_visible = (
        jet_p4[assignment["blep"]]
        + lepton_p4
    )

    cos_theta_bb = required_opening_angle(
        p_H1,
        p_H2,
        event_index=sequential_index,
        feature="cos_theta_bb_assigned_prefit",
    )

    cos_theta_H_hadtop = required_opening_angle(
        p_H,
        p_hadtop,
        event_index=sequential_index,
        feature=(
            "cos_theta_H_hadtop_assigned_prefit"
        ),
    )

    cos_theta_H_leptop_visible = (
        required_opening_angle(
            p_H,
            p_leptop_visible,
            event_index=sequential_index,
            feature=(
                "cos_theta_H_leptop_visible_"
                "assigned_prefit"
            ),
        )
    )

    row: dict[str, Any] = {
        "event_id": derive_event_id(
            manifest_row,
            sequential_index,
        ),
        "event": sequential_index,
        "event_index": sequential_index,
        "run_number": root_run,
        "event_number": root_event,

        "job_key": manifest_row["job_key"],
        "sample_name": manifest_row["sample_key"],
        "sample_key": manifest_row["sample_key"],

        # The manifest label is retained for provenance. The event-level
        # class label is overridden only for inclusive ttH samples.
        "manifest_class_label":
            target["manifest_class_label"],
        "class_label":
            target["class_label"],
        "analysis_category":
            target["analysis_category"],
        "truth_higgs_decay":
            target["truth_higgs_decay"],
        "truth_is_hbb": int(
            target["truth_is_hbb"]
        ),

        "event_category": int(
            manifest_row["event_category"]
        ),
        "process": manifest_row["source_process"],
        "process_mask": manifest_row["process_mask"],
        "source": manifest_row["source"],
        "generator": manifest_row["generator"],
        "polarization": manifest_row["polarization"],
        "helicity": manifest_row["helicity"],
        "logical_shard": manifest_row["logical_shard"],
        "physical_part": manifest_row["physical_part"],
        "split_group": manifest_row["split_group"],

        # Split and weights are deliberately unresolved at export-test stage.
        "split": "unassigned",
        "weight_phys": float("nan"),
        "weight_train": float("nan"),

        "accepted": int(
            root_rows["accepted"][
                root_position
            ]
        ),
        "fit_success": int(
            root_rows["fit_success"][
                root_position
            ]
        ),
        "fit_status": int(
            root_rows["fit_status"][
                root_position
            ]
        ),

        "best_combo_id": int(
            root_rows["best_combo_id"][
                root_position
            ]
        ),

        "lepton_flavor": lepton_tag_flavor,
        "lepton_tag_flavor": lepton_tag_flavor,
        "lepton_tag_type": lepton_tag_type,
        "lepton_tag_score": lepton_tag_score,
        "lepton_tag_collection": lepton_collection_name,

        "lepton_reco_type": lepton_reco_type,
        "lepton_reco_type_abs": lepton_reco_type_abs,
        "kinfit_lepton_reco_type_abs":
            kinfit_lepton_reco_type_abs,

        "lepton_type_matches_tag": int(
            lepton_reco_type_abs
            == lepton_tag_type
        ),
        "lepton_E": float(
            lepton_p4[0]
        ),
        "lepton_px": float(
            lepton_p4[1]
        ),
        "lepton_py": float(
            lepton_p4[2]
        ),
        "lepton_pz": float(
            lepton_p4[3]
        ),
        "lepton_pt": transverse_momentum(
            lepton_p4
        ),
        "lepton_theta": polar_angle(
            lepton_p4
        ),
        "lepton_charge": lcio_charge,

        "y45": float(
            yth_values["y45"]
        ),
        "y56": float(
            yth_values["y56"]
        ),
        "y67": float(
            yth_values["y67"]
        ),
        "yth_source_jet_index": int(
            yth_source_jet
        ),

        "cos_theta_bb_assigned_prefit": cos_theta_bb,

        "cos_theta_H_hadtop_assigned_prefit": cos_theta_H_hadtop,

        "cos_theta_H_leptop_visible_assigned_prefit": cos_theta_H_leptop_visible,
    }

    for role, index in assignment.items():
        row[f"idx_{role}"] = int(
            index
        )

    for field in ROOT_SCALAR_FEATURES:
        row[field] = python_scalar(
            root_rows[field][root_position]
        )

    for jet_index in range(6):
        row[f"jet{jet_index}_E"] = float(
            jet_p4[jet_index, 0]
        )
        row[f"jet{jet_index}_px"] = float(
            jet_p4[jet_index, 1]
        )
        row[f"jet{jet_index}_py"] = float(
            jet_p4[jet_index, 2]
        )
        row[f"jet{jet_index}_pz"] = float(
            jet_p4[jet_index, 3]
        )

        row[f"btag_jet{jet_index}"] = float(
            b_tags[jet_index]
        )
        row[f"ctag_jet{jet_index}"] = float(
            c_tags[jet_index]
        )

    for rank in range(4):
        row[f"btag_{rank + 1}"] = float(
            sorted_b[rank]
        )
        row[f"ctag_{rank + 1}"] = float(
            sorted_c[rank]
        )

    baseline_features = cfg[
        "feature_schema"
    ]["baseline_features"]

    non_finite = [
        field
        for field in baseline_features
        if (
            field not in row
            or not math.isfinite(
                float(row[field])
            )
        )
    ]

    if non_finite:
        raise RuntimeError(
            f"event_index={sequential_index}: "
            f"non-finite or missing baseline features="
            f"{non_finite}"
        )

    return row


def extract_mva_feature_rows(
    manifest_row: dict[str, str],
    root_rows: dict[str, np.ndarray],
    cfg: dict,
    *,
    max_events: int,
) ->  tuple[
    list[dict[str, Any]],
    dict[str, list[str]],
    list[dict[str, Any]],
]:
    """Join selected ROOT rows to SLCIO and build MVA feature rows."""
    available = len(
        root_rows["event_index"]
    )

    if available == 0:
        raise RuntimeError(
            f"No selected ROOT rows for "
            f"{manifest_row['job_key']}"
        )

    n_take = (
        available
        if max_events <= 0
        else min(
            available,
            max_events,
        )
    )

    selected_indices = np.asarray(
        root_rows["event_index"][:n_take],
        dtype=np.int64,
    )

    root_position_by_index = {
        int(event_index): position
        for position, event_index
        in enumerate(selected_indices)
    }

    requested = set(
        root_position_by_index
    )
    maximum_index = max(
        requested
    )

    IOIMPL = import_lcio()
    reader = (
        IOIMPL.LCFactory
        .getInstance()
        .createLCReader()
    )
    reader.open(
        str(manifest_row["input_path"])
    )

    rows_by_position: dict[
        int,
        dict[str, Any],
    ] = {}
    pid_schema_state: dict[
        str,
        list[str],
    ] = {}

    skipped_events: list[
        dict[str, Any]
    ] = []

    skipped_positions: set[int] = set()
    try:
        sequential_index = 0

        while sequential_index <= maximum_index:
            try:
                event = reader.readNextEvent()
            except ReferenceError:
                event = None
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to read "
                    f"{manifest_row['input_path']} at "
                    f"event_index={sequential_index}: {exc}"
                ) from exc

            if event is None:
                break

            if sequential_index in requested:
                root_position = root_position_by_index[sequential_index]

                try:
                    row = build_export_event_row(
                        event=event,
                        sequential_index=sequential_index,
                        root_position=root_position,
                        root_rows=root_rows,
                        manifest_row=manifest_row,
                        cfg=cfg,
                        pid_schema_state=pid_schema_state,
                    )
                except SkipMVAEvent as exc:
                    skipped_positions.add(root_position)

                    record = exc.as_record()
                    record.update({
                        "job_key": manifest_row["job_key"],
                        "sample_key": manifest_row["sample_key"],
                        "run_number": int(event.getRunNumber()),
                        "event_number": int(event.getEventNumber()),
                    })
                    skipped_events.append(record)

                    print(
                        f"[export] SKIP: event_index={sequential_index}, "
                        f"reason={record['reason']}, feature={record['feature']}"
                    )
                    sequential_index += 1
                    continue

                rows_by_position[root_position] = row
            sequential_index += 1

    finally:
        try:
            reader.close()
        except Exception:
            pass

    missing_positions = sorted(
        set(range(n_take))
        - set(rows_by_position)
        - skipped_positions
    )

    if missing_positions:
        missing_event_indices = [
            int(selected_indices[position])
            for position in missing_positions
        ]

        raise RuntimeError(
            f"Missing SLCIO events for "
            f"{manifest_row['job_key']}: "
            f"{missing_event_indices[:20]}"
        )

    rows = [
        rows_by_position[position]
        for position in range(n_take)
        if position not in skipped_positions
    ]

    event_ids = [
        row["event_id"]
        for row in rows
    ]

    if len(set(event_ids)) != len(event_ids):
        raise RuntimeError(
            "Duplicated event IDs in exported rows"
        )

    return rows, pid_schema_state, skipped_events


def write_hdf5_table(
    output_path: Path,
    rows: list[dict[str, Any]],
    *,
    attributes: dict[str, Any],
) -> None:
    """Atomically write root-level HDF5 column datasets."""
    if not rows:
        raise ValueError(
            "Cannot write an empty HDF5 table"
        )

    reference_keys = set(
        rows[0]
    )

    for row_index, row in enumerate(
        rows
    ):
        if set(row) != reference_keys:
            raise RuntimeError(
                f"Inconsistent feature columns at row "
                f"{row_index}"
            )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    string_dtype = h5py.string_dtype(
        encoding="utf-8"
    )

    with h5py.File(
        temporary_path,
        "w",
    ) as output:
        for key in sorted(reference_keys):
            values = [
                row[key]
                for row in rows
            ]

            if all(
                isinstance(value, str)
                for value in values
            ):
                array = np.asarray(
                    values,
                    dtype=object,
                )
                output.create_dataset(
                    key,
                    data=array,
                    dtype=string_dtype,
                )

            elif all(
                isinstance(
                    value,
                    (
                        bool,
                        int,
                        np.integer,
                    ),
                )
                for value in values
            ):
                array = np.asarray(
                    values,
                    dtype=np.int64,
                )
                output.create_dataset(
                    key,
                    data=array,
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )

            else:
                array = np.asarray(
                    values,
                    dtype=np.float64,
                )
                output.create_dataset(
                    key,
                    data=array,
                    compression="gzip",
                    compression_opts=4,
                    shuffle=True,
                )

        output.attrs[
            "n_events"
        ] = len(rows)

        for key, value in attributes.items():
            if isinstance(
                value,
                (
                    str,
                    int,
                    float,
                    bool,
                    np.integer,
                    np.floating,
                ),
            ):
                output.attrs[key] = value
            else:
                output.attrs[key] = json.dumps(
                    value,
                    sort_keys=True,
                )

    temporary_path.replace(
        output_path
    )


def validate_hdf5_table(
    input_path: Path,
    *,
    baseline_features: Iterable[str],
) -> dict[str, Any]:
    """Reopen an exported HDF5 table and validate its schema."""
    with h5py.File(
        input_path,
        "r",
    ) as source:
        dataset_names = sorted(
            source.keys()
        )

        lengths = {
            name: int(
                source[name].shape[0]
            )
            for name in dataset_names
        }

        if len(set(lengths.values())) != 1:
            raise RuntimeError(
                f"Inconsistent HDF5 dataset lengths: "
                f"{lengths}"
            )

        n_events = next(
            iter(lengths.values()),
            0,
        )

        if n_events <= 0:
            raise RuntimeError(
                "Exported HDF5 contains no events"
            )

        required_metadata = {
            "analysis_category",
            "class_label",
            "manifest_class_label",
            "truth_higgs_decay",
            "truth_is_hbb",
        }

        missing_metadata = sorted(
            required_metadata
            - set(dataset_names)
        )
        if missing_metadata:
            raise RuntimeError(
                f"Missing classification datasets: "
                f"{missing_metadata}"
            )

        missing_features = sorted(
            set(baseline_features)
            - set(dataset_names)
        )

        if missing_features:
            raise RuntimeError(
                f"Missing baseline datasets: "
                f"{missing_features}"
            )

        non_finite_counts = {}

        for feature in baseline_features:
            values = np.asarray(
                source[feature][...],
                dtype=np.float64,
            )
            count = int(
                np.count_nonzero(
                    ~np.isfinite(values)
                )
            )

            if count:
                non_finite_counts[
                    feature
                ] = count

        if non_finite_counts:
            raise RuntimeError(
                f"Non-finite baseline features in HDF5: "
                f"{non_finite_counts}"
            )

        raw_event_ids = source[
            "event_id"
        ][...]

        event_ids = [
            (
                value.decode("utf-8")
                if isinstance(value, bytes)
                else str(value)
            )
            for value in raw_event_ids
        ]

        duplicate_event_ids = (
            len(event_ids)
            - len(set(event_ids))
        )

        if duplicate_event_ids:
            raise RuntimeError(
                f"Duplicated event IDs in HDF5: "
                f"{duplicate_event_ids}"
            )

    return {
        "ok": True,
        "n_events": n_events,
        "n_datasets": len(
            dataset_names
        ),
        "dataset_names": dataset_names,
        "duplicate_event_ids": 0,
        "non_finite_baseline_values": 0,
    }

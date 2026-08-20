#!/usr/bin/env python3
"""Build the frozen physical-normalization inventory for the MVA analysis."""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any
from collections import Counter

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]

FLOAT_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("configs/mva_normalization_sources.yaml"),
    )

    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise RuntimeError(f"Expected YAML mapping: {path}")

    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> str:
    if not path.exists():
        raise FileNotFoundError(path)

    observed = sha256_file(path)

    if observed != expected:
        raise RuntimeError(
            f"SHA256 mismatch for {path}\n"
            f"expected: {expected}\n"
            f"observed: {observed}"
        )

    return observed


def close(a: float, b: float, tol: float = 1e-10) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


# =============================================================================
# Luminosity
# =============================================================================


def helicity_probability(
    polarization: float,
    helicity: str,
) -> float:
    """Return the L/R population for P=(N_R-N_L)/(N_R+N_L)."""

    if helicity == "L":
        return (1.0 - polarization) / 2.0

    if helicity == "R":
        return (1.0 + polarization) / 2.0

    raise ValueError(helicity)


def compute_effective_luminosities(
    scenario: dict[str, Any],
) -> dict[str, float]:
    total_lumi = float(
        scenario["total_luminosity_fb_inv"]
    )

    output = {
        "eL.pL": 0.0,
        "eL.pR": 0.0,
        "eR.pL": 0.0,
        "eR.pR": 0.0,
    }

    fraction_sum = 0.0

    for state_name, state in scenario["run_states"].items():
        fraction = float(state["fraction"])
        fraction_sum += fraction

        pe = float(state["electron_polarization"])
        pp = float(state["positron_polarization"])

        state_lumi = total_lumi * fraction

        for e_helicity in ("L", "R"):
            for p_helicity in ("L", "R"):
                key = f"e{e_helicity}.p{p_helicity}"

                probability = (
                    helicity_probability(pe, e_helicity)
                    * helicity_probability(pp, p_helicity)
                )

                output[key] += state_lumi * probability

    if not close(fraction_sum, 1.0):
        raise RuntimeError(
            f"Run-state fractions sum to {fraction_sum}, not 1."
        )

    if not close(sum(output.values()), total_lumi):
        raise RuntimeError(
            "Effective-helicity luminosities do not close "
            "to the total luminosity."
        )

    expected = scenario.get(
        "expected_effective_pure_helicity_luminosity_fb_inv",
        {},
    )

    for helicity, target in expected.items():
        observed = output[helicity]

        if not close(observed, float(target)):
            raise RuntimeError(
                f"Effective luminosity mismatch for {helicity}: "
                f"{observed} vs expected {target}"
            )

    return output


# =============================================================================
# Standard Physsim
# =============================================================================


def parse_meta(path: Path) -> dict[str, str]:
    output: dict[str, str] = {}

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        output[key.strip()] = value.strip()

    return output


def extract_writer_events(path: Path) -> int:
    pattern = re.compile(
        rb"Number of write events\s*:\s*(\d+)"
    )
    chunk_size = 1024 * 1024
    suffix = b""

    with path.open("rb") as stream:
        stream.seek(0, 2)
        position = stream.tell()

        while position:
            size = min(chunk_size, position)
            position -= size
            stream.seek(position)
            suffix = stream.read(size) + suffix
            matches = pattern.findall(suffix)

            if matches:
                # Scanning starts at EOF, so this is the final summary.
                return int(matches[-1])

    raise RuntimeError(
        f"No 'Number of write events' found in {path}"
    )


def extract_text_cross_section(
    path: Path,
) -> tuple[float, float]:
    pattern = re.compile(
        rf"Total Cross section\s*=\s*"
        rf"({FLOAT_PATTERN})\s*\+\-\s*({FLOAT_PATTERN})"
        rf"\s*\(fb\)"
    )

    matches = pattern.findall(
        path.read_text(errors="replace")
    )

    if not matches:
        raise RuntimeError(
            f"Could not parse cross section from {path}"
        )

    value, error = matches[-1]

    return float(value), float(error)


def validate_cross_section(
    config: dict[str, Any],
) -> dict[str, Any]:
    source_path = resolve_path(
        config["source_path"]
    )

    source_hash = require_hash(
        source_path,
        config["source_sha256"],
    )

    value = float(config["value_fb"])
    uncertainty = float(
        config["uncertainty_fb"]
    )

    parser = config["parser"]

    if parser == "text_total_cross_section":
        parsed_value, parsed_uncertainty = (
            extract_text_cross_section(
                source_path
            )
        )

        if not close(parsed_value, value):
            raise RuntimeError(
                f"Cross-section mismatch in {source_path}: "
                f"{parsed_value} vs configured {value}"
            )

        if not close(parsed_uncertainty, uncertainty):
            raise RuntimeError(
                f"Cross-section uncertainty mismatch in {source_path}: "
                f"{parsed_uncertainty} vs configured {uncertainty}"
            )

    elif parser == "locked_value":
        pass

    else:
        raise RuntimeError(
            f"Unsupported cross-section parser: {parser}"
        )

    return {
        "value_fb": value,
        "uncertainty_fb": uncertainty,
        "source_path": str(source_path),
        "source_sha256": source_hash,
        "parser": parser,
    }


def scan_standard_physsim(
    sample_key: str,
    polarization: str,
    config: dict[str, Any],
    effective_lumi: float,
) -> dict[str, Any]:
    meta_paths = sorted(
        Path(path)
        for path in glob.glob(
            config["meta_glob"],
            recursive=True,
        )
    )

    expected_meta_files = int(
        config["expected_meta_files"]
    )

    if len(meta_paths) != expected_meta_files:
        raise RuntimeError(
            f"{sample_key}/{polarization}: "
            f"found {len(meta_paths)} meta files, "
            f"expected {expected_meta_files}"
        )

    seen_run_logs: set[str] = set()
    shards: list[dict[str, Any]] = []

    total_writer_events = 0

    for meta_path in meta_paths:
        meta = parse_meta(meta_path)

        expected_process = str(
            config["expected_process"]
        )

        if meta.get("process") != expected_process:
            raise RuntimeError(
                f"{meta_path}: process={meta.get('process')!r}, "
                f"expected {expected_process!r}"
            )

        if meta.get("polarization") != polarization:
            raise RuntimeError(
                f"{meta_path}: polarization="
                f"{meta.get('polarization')!r}, "
                f"expected {polarization!r}"
            )

        if "run_log" not in meta:
            raise RuntimeError(
                f"{meta_path}: missing run_log"
            )

        run_log = resolve_path(
            meta["run_log"]
        )

        run_log_key = str(
            run_log.resolve()
        )

        # A duplicated metadata reference must not duplicate exposure.
        if run_log_key in seen_run_logs:
            continue

        seen_run_logs.add(
            run_log_key
        )

        writer_events = extract_writer_events(
            run_log
        )

        total_writer_events += writer_events

        shards.append(
            {
                "shard_id": meta_path.stem,
                "chunk": meta.get("chunk"),
                "requested_events": (
                    int(meta["nevents"])
                    if meta.get("nevents")
                    else None
                ),
                "writer_events": writer_events,
                "meta_path": str(meta_path),
                "meta_sha256": sha256_file(meta_path),
                "run_log": str(run_log),
                "run_log_sha256": sha256_file(run_log),
            }
        )

    expected_events = int(
        config["expected_generator_events"]
    )

    if total_writer_events != expected_events:
        raise RuntimeError(
            f"{sample_key}/{polarization}: "
            f"writer-event denominator={total_writer_events}, "
            f"expected={expected_events}"
        )

    cross_section = validate_cross_section(
        config["cross_section"]
    )

    weight = (
        cross_section["value_fb"]
        * effective_lumi
        / total_writer_events
    )

    expected_weight = float(
        config["expected_nominal_weight"]
    )

    if not close(weight, expected_weight):
        raise RuntimeError(
            f"{sample_key}/{polarization}: "
            f"weight={weight:.15g}, "
            f"expected={expected_weight:.15g}"
        )

    return {
        "normalization_key": (
            f"physsim::{sample_key}::{polarization}"
        ),
        "sample_key": sample_key,
        "generator": "physsim",
        "polarization": polarization,
        "process_mask": None,
        "normalization_type": "positive_cross_section",
        "cross_section_fb": cross_section["value_fb"],
        "cross_section_uncertainty_fb": (
            cross_section["uncertainty_fb"]
        ),
        "generator_events": total_writer_events,
        "denominator_definition": (
            "sum_of_unique_physsim_Number_of_write_events"
        ),
        "effective_luminosity_fb_inv": effective_lumi,
        "weight_phys": weight,
        "cross_section_provenance": cross_section,
        "included_shards": shards,
    }


# =============================================================================
# CPV sidecars
# =============================================================================


def validate_interference_sidecar(
    path: Path,
    expected_sigma: float,
    expected_sigma_error: float,
) -> dict[str, Any]:
    """Stream and validate every accepted-event row in one CPV sidecar."""

    required = {
        "event",
        "n_generated",
        "sigma_absint",
        "sigma_absint_error",
        "sign",
        "event_weight_signed",
    }

    first_n_generated: int | None = None
    row_count = 0

    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = set(reader.fieldnames or [])
        missing = required - fieldnames

        if missing:
            raise RuntimeError(
                f"{path}: missing fields {sorted(missing)}"
            )

        for row_count, row in enumerate(reader, start=1):
            event = int(float(row["event"]))

            if event != row_count:
                raise RuntimeError(
                    f"{path}: event sequence mismatch at row {row_count}: "
                    f"event={event}"
                )

            n_generated = int(float(row["n_generated"]))
            sigma = float(row["sigma_absint"])
            sigma_error = float(row["sigma_absint_error"])
            sign = int(float(row["sign"]))
            event_weight = float(row["event_weight_signed"])

            if first_n_generated is None:
                first_n_generated = n_generated

            if n_generated != first_n_generated:
                raise RuntimeError(
                    f"{path}: n_generated changes at event {event}"
                )

            if not close(sigma, expected_sigma):
                raise RuntimeError(
                    f"{path}: sigma_absint={sigma}, expected {expected_sigma}"
                )

            if not close(sigma_error, expected_sigma_error):
                raise RuntimeError(
                    f"{path}: sigma_absint_error={sigma_error}, "
                    f"expected {expected_sigma_error}"
                )

            if sign not in {-1, 1}:
                raise RuntimeError(
                    f"{path}: invalid interference sign {sign} at event {event}"
                )

            expected_event_weight = sign * sigma / n_generated

            if not close(event_weight, expected_event_weight):
                raise RuntimeError(
                    f"{path}: event_weight_signed mismatch at event {event}: "
                    f"{event_weight} != {expected_event_weight}"
                )

    if first_n_generated is None:
        raise RuntimeError(f"Empty CSV: {path}")

    if row_count != first_n_generated:
        raise RuntimeError(
            f"{path}: sidecar rows={row_count}, n_generated={first_n_generated}"
        )

    suffix = ".tthcpv_me.csv"
    shard_id = path.name[:-len(suffix)] if path.name.endswith(suffix) else path.stem

    return {
        "shard_id": shard_id,
        "n_generated": first_n_generated,
        "rows": row_count,
    }


def scan_interference_physsim(
    sample_key: str,
    polarization: str,
    config: dict[str, Any],
    effective_lumi: float,
) -> dict[str, Any]:
    reference = config["reference_sidecar"]

    require_hash(
        resolve_path(reference["path"]),
        reference["sha256"],
    )

    sidecars = sorted(
        Path(path)
        for path in glob.glob(
            config["sidecar_glob"],
            recursive=True,
        )
    )

    expected_sidecars = int(
        config["expected_sidecars"]
    )

    if len(sidecars) != expected_sidecars:
        raise RuntimeError(
            f"{sample_key}/{polarization}: "
            f"found {len(sidecars)} sidecars, "
            f"expected {expected_sidecars}"
        )

    expected_sigma = float(
        config["sigma_absint_fb"]
    )

    expected_sigma_error = float(
        config[
            "sigma_absint_uncertainty_fb"
        ]
    )

    total_generated = 0
    shard_records = []
    seen_shards: set[str] = set()

    for sidecar in sidecars:
        validated = validate_interference_sidecar(
            sidecar,
            expected_sigma,
            expected_sigma_error,
        )

        shard_id = str(validated["shard_id"])

        if shard_id in seen_shards:
            raise RuntimeError(
                f"{sample_key}/{polarization}: duplicate physical "
                f"sidecar shard {shard_id}"
            )

        seen_shards.add(shard_id)
        n_generated = int(validated["n_generated"])

        total_generated += n_generated

        shard_records.append(
            {
                "shard_id": shard_id,
                "n_generated": n_generated,
                "sidecar_rows": int(validated["rows"]),
                "sidecar_path": str(sidecar),
                "sidecar_sha256": sha256_file(sidecar),
            }
        )

    if len(seen_shards) != expected_sidecars:
        raise RuntimeError(
            f"{sample_key}/{polarization}: unique sidecars="
            f"{len(seen_shards)}, expected={expected_sidecars}"
        )

    expected_events = int(
        config["expected_generator_events"]
    )

    if total_generated != expected_events:
        raise RuntimeError(
            f"{sample_key}/{polarization}: "
            f"sidecar denominator={total_generated}, "
            f"expected={expected_events}"
        )

    magnitude = (
        expected_sigma
        * effective_lumi
        / total_generated
    )

    expected_magnitude = float(
        config[
            "expected_nominal_weight_magnitude"
        ]
    )

    if not close(
        magnitude,
        expected_magnitude,
    ):
        raise RuntimeError(
            f"{sample_key}/{polarization}: "
            f"|weight_interference|={magnitude:.15g}, "
            f"expected={expected_magnitude:.15g}"
        )

    return {
        "normalization_key": (
            f"physsim::{sample_key}::{polarization}"
        ),
        "sample_key": sample_key,
        "generator": "physsim",
        "polarization": polarization,
        "process_mask": None,
        "normalization_type": "signed_interference",
        "sigma_absint_fb": expected_sigma,
        "sigma_absint_uncertainty_fb": (
            expected_sigma_error
        ),
        "generator_events": total_generated,
        "denominator_definition": (
            "sum_of_unique_sidecar_n_generated"
        ),
        "effective_luminosity_fb_inv": effective_lumi,
        "weight_phys": None,
        "weight_interference_magnitude": magnitude,
        "requires_event_sign": True,
        "event_weight_signed_from_original_sidecar_is_valid_after_merge": False,
        "included_shards": shard_records,
    }


# =============================================================================
# Whizard
# =============================================================================


def canonical_helicity(
    value: str,
    aliases: dict[str, str],
) -> str:
    value = value.strip()

    if value not in aliases:
        raise RuntimeError(
            f"Unknown Whizard helicity label: {value!r}"
        )

    return aliases[value]

def validate_source_config(
    source_cfg: dict[str, Any],
) -> None:
    """Validate configuration structure before scanning large files."""

    required_top_level = {
        "luminosity_scenarios",
        "scenario_id",
        "output_inventory",
        "physsim_positive",
        "physsim_interference",
        "whizard",
    }

    missing_top = (
        required_top_level
        - set(source_cfg)
    )

    if missing_top:
        raise RuntimeError(
            "Normalization source config is missing "
            f"top-level field(s): {sorted(missing_top)}"
        )

    whizard_cfg = source_cfg["whizard"]

    required_whizard = {
        "manifest_path",
        "manifest_sha256",
        "normalization_type",
        "allowed_category",
        "process_mask_to_sample_key",
        "helicity_aliases",
        "expected",
    }

    missing_whizard = (
        required_whizard
        - set(whizard_cfg)
    )

    if missing_whizard:
        raise RuntimeError(
            "Whizard normalization config is missing "
            f"field(s): {sorted(missing_whizard)}"
        )

    required_expected = {
        "source_rows",
        "allowed_category_rows",
        "ignored_other_category_rows",
        "excluded_unreadable_rows",
        "included_generator_rows",
        "sample_generator_rows",
        "normalization_entries",
        "sample_normalization_entries",
    }

    missing_expected = (
        required_expected
        - set(whizard_cfg["expected"])
    )

    if missing_expected:
        raise RuntimeError(
            "Whizard expected-audit config is missing "
            f"field(s): {sorted(missing_expected)}"
        )

def scan_whizard(
    config: dict[str, Any],
    effective_luminosities: dict[str, float],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Build Whizard normalizations from the authoritative generator manifest."""

    manifest_path = resolve_path(
        config["manifest_path"]
    )

    manifest_hash = require_hash(
        manifest_path,
        config["manifest_sha256"],
    )

    allowed_category = str(
        config["allowed_category"]
    )

    process_map = {
        str(key): str(value)
        for key, value
        in config[
            "process_mask_to_sample_key"
        ].items()
    }

    aliases = {
        str(key): str(value)
        for key, value
        in config[
            "helicity_aliases"
        ].items()
    }

    expected = config[
        "expected"
    ]

    with manifest_path.open(
        newline=""
    ) as stream:
        rows = list(
            csv.DictReader(stream)
        )

    required = {
        "category",
        "process_mask",
        "process_name",
        "generator",
        "helicity",
        "process_id",
        "file_path",
        "shard_id",
        "readable",
        "n_events",
        "cross_section_fb",
        "cross_section_error_fb",
    }

    if not rows:
        raise RuntimeError(
            f"Empty Whizard manifest: "
            f"{manifest_path}"
        )

    missing = (
        required
        - set(rows[0])
    )

    if missing:
        raise RuntimeError(
            "Whizard manifest missing columns: "
            f"{sorted(missing)}"
        )

    # -------------------------------------------------------------------------
    # Global manifest accounting.
    # -------------------------------------------------------------------------

    if len(rows) != int(
        expected[
            "source_rows"
        ]
    ):
        raise RuntimeError(
            "Whizard source-row count mismatch: "
            f"{len(rows)} != "
            f"{expected['source_rows']}"
        )

    category_rows = [
        row
        for row in rows
        if row[
            "category"
        ].strip() == allowed_category
    ]

    ignored_rows = [
        row
        for row in rows
        if row[
            "category"
        ].strip() != allowed_category
    ]

    if len(category_rows) != int(
        expected[
            "allowed_category_rows"
        ]
    ):
        raise RuntimeError(
            "Whizard allowed-category row count mismatch: "
            f"{len(category_rows)} != "
            f"{expected['allowed_category_rows']}"
        )

    if len(ignored_rows) != int(
        expected[
            "ignored_other_category_rows"
        ]
    ):
        raise RuntimeError(
            "Whizard ignored-category row count mismatch: "
            f"{len(ignored_rows)} != "
            f"{expected['ignored_other_category_rows']}"
        )

    # -------------------------------------------------------------------------
    # Reject unreadable/broken generator shards from the denominator.
    #
    # In the current manifest these rows have readable=0, n_events=-1,
    # and no valid cross section.
    # -------------------------------------------------------------------------

    valid_rows: list[
        dict[str, str]
    ] = []

    excluded_rows: list[
        dict[str, Any]
    ] = []

    for row in category_rows:
        readable = (
            row[
                "readable"
            ].strip()
            == "1"
        )

        try:
            n_events = int(
                row[
                    "n_events"
                ]
            )
        except ValueError:
            n_events = -1

        try:
            xsec = float(
                row[
                    "cross_section_fb"
                ]
            )
        except ValueError:
            xsec = float(
                "nan"
            )

        try:
            xsec_error = float(
                row[
                    "cross_section_error_fb"
                ]
            )
        except ValueError:
            xsec_error = float(
                "nan"
            )

        valid = (
            readable
            and n_events > 0
            and math.isfinite(
                xsec
            )
            and math.isfinite(
                xsec_error
            )
        )

        if not valid:
            excluded_rows.append(
                {
                    "process_mask":
                        row[
                            "process_mask"
                        ].strip(),
                    "helicity":
                        row[
                            "helicity"
                        ].strip(),
                    "process_id":
                        row[
                            "process_id"
                        ].strip(),
                    "shard_id":
                        row[
                            "shard_id"
                        ].strip(),
                    "file_path":
                        row[
                            "file_path"
                        ].strip(),
                    "readable":
                        row[
                            "readable"
                        ].strip(),
                    "n_events":
                        row[
                            "n_events"
                        ].strip(),
                    "notes":
                        row.get(
                            "notes",
                            "",
                        ),
                }
            )

            continue

        valid_rows.append(
            row
        )

    if len(excluded_rows) != int(
        expected[
            "excluded_unreadable_rows"
        ]
    ):
        raise RuntimeError(
            "Whizard excluded-row count mismatch: "
            f"{len(excluded_rows)} != "
            f"{expected['excluded_unreadable_rows']}"
        )

    if len(valid_rows) != int(
        expected[
            "included_generator_rows"
        ]
    ):
        raise RuntimeError(
            "Whizard included generator-row count mismatch: "
            f"{len(valid_rows)} != "
            f"{expected['included_generator_rows']}"
        )

    # -------------------------------------------------------------------------
    # Every valid 6f process mask must be explicitly classified.
    # -------------------------------------------------------------------------

    observed_masks = {
        row[
            "process_mask"
        ].strip()
        for row
        in valid_rows
    }

    configured_masks = set(
        process_map
    )

    unknown_masks = sorted(
        observed_masks
        - configured_masks
    )

    unused_configured_masks = sorted(
        configured_masks
        - observed_masks
    )

    if unknown_masks:
        raise RuntimeError(
            "Unclassified Whizard process masks: "
            f"{unknown_masks}"
        )

    if unused_configured_masks:
        raise RuntimeError(
            "Configured Whizard process masks "
            "not present in manifest: "
            f"{unused_configured_masks}"
        )

    # -------------------------------------------------------------------------
    # Group by:
    #
    # sample_key × process_mask × pure helicity
    #
    # Each process has its own cross section and generator denominator.
    # -------------------------------------------------------------------------

    grouped: dict[
        tuple[
            str,
            str,
            str,
        ],
        list[
            dict[str, str]
        ],
    ] = {}

    sample_row_counts: Counter[
        str
    ] = Counter()

    for row in valid_rows:
        process_mask = row[
            "process_mask"
        ].strip()

        sample_key = process_map[
            process_mask
        ]

        polarization = (
            canonical_helicity(
                row[
                    "helicity"
                ],
                aliases,
            )
        )

        key = (
            sample_key,
            process_mask,
            polarization,
        )

        grouped.setdefault(
            key,
            [],
        ).append(
            row
        )

        sample_row_counts[
            sample_key
        ] += 1

    expected_sample_rows = expected[
        "sample_generator_rows"
    ]

    for sample_key in [
        "6q",
        "4f2l",
    ]:
        observed = sample_row_counts[
            sample_key
        ]

        target = int(
            expected_sample_rows[
                sample_key
            ]
        )

        if observed != target:
            raise RuntimeError(
                "Whizard generator-row count mismatch "
                f"for {sample_key}: "
                f"{observed} != {target}"
            )

    output: list[
        dict[str, Any]
    ] = []

    sample_entry_counts: Counter[
        str
    ] = Counter()

    for (
        sample_key,
        process_mask,
        polarization,
    ), group_rows in sorted(
        grouped.items()
    ):

        # ---------------------------------------------------------------------
        # De-duplicate exact physical generator shards.
        # ---------------------------------------------------------------------

        by_physical_shard: dict[
            tuple[
                str,
                str,
            ],
            dict[str, str],
        ] = {}

        for row in group_rows:
            process_id = row[
                "process_id"
            ].strip()

            shard_id = row[
                "shard_id"
            ].strip()

            physical_key = (
                process_id,
                shard_id,
            )

            if (
                physical_key
                in by_physical_shard
            ):
                previous = (
                    by_physical_shard[
                        physical_key
                    ]
                )

                if (
                    previous[
                        "file_path"
                    ]
                    != row[
                        "file_path"
                    ]
                    or previous[
                        "n_events"
                    ]
                    != row[
                        "n_events"
                    ]
                ):
                    raise RuntimeError(
                        "Conflicting duplicate Whizard "
                        "physical shard: "
                        f"{sample_key}/"
                        f"{process_mask}/"
                        f"{polarization}/"
                        f"{physical_key}"
                    )

                continue

            by_physical_shard[
                physical_key
            ] = row

        # ---------------------------------------------------------------------
        # Cross section is repeated per shard.
        # It must be identical; it is never summed.
        # ---------------------------------------------------------------------

        xsecs = [
            float(
                row[
                    "cross_section_fb"
                ]
            )
            for row
            in by_physical_shard.values()
        ]

        xsec_errors = [
            float(
                row[
                    "cross_section_error_fb"
                ]
            )
            for row
            in by_physical_shard.values()
        ]

        xsec = xsecs[0]
        xsec_error = (
            xsec_errors[0]
        )

        if any(
            not close(
                value,
                xsec,
            )
            for value
            in xsecs
        ):
            raise RuntimeError(
                "Inconsistent Whizard cross section for "
                f"{sample_key}/"
                f"{process_mask}/"
                f"{polarization}"
            )

        if any(
            not close(
                value,
                xsec_error,
            )
            for value
            in xsec_errors
        ):
            raise RuntimeError(
                "Inconsistent Whizard "
                "cross-section uncertainty for "
                f"{sample_key}/"
                f"{process_mask}/"
                f"{polarization}"
            )

        generator_events = sum(
            int(
                row[
                    "n_events"
                ]
            )
            for row
            in by_physical_shard.values()
        )

        if generator_events <= 0:
            raise RuntimeError(
                "Non-positive Whizard generator denominator for "
                f"{sample_key}/"
                f"{process_mask}/"
                f"{polarization}"
            )

        effective_lumi = (
            effective_luminosities[
                polarization
            ]
        )

        weight = (
            xsec
            * effective_lumi
            / generator_events
        )

        shards = [
            {
                "process_id":
                    row[
                        "process_id"
                    ].strip(),
                "shard_id":
                    row[
                        "shard_id"
                    ].strip(),
                "file_path":
                    row[
                        "file_path"
                    ].strip(),
                "n_events":
                    int(
                        row[
                            "n_events"
                        ]
                    ),
                "process_name":
                    row[
                        "process_name"
                    ].strip(),
            }
            for (
                process_id,
                shard_id,
            ), row
            in sorted(
                by_physical_shard.items()
            )
        ]

        output.append(
            {
                "normalization_key": (
                    f"whizard::"
                    f"{sample_key}::"
                    f"{process_mask}::"
                    f"{polarization}"
                ),

                "sample_key":
                    sample_key,

                "generator":
                    "whizard",

                "polarization":
                    polarization,

                "process_mask":
                    process_mask,

                "normalization_type":
                    "positive_cross_section",

                "cross_section_fb":
                    xsec,

                "cross_section_uncertainty_fb":
                    xsec_error,

                "generator_events":
                    generator_events,

                "denominator_definition": (
                    "sum_of_unique_readable_"
                    "whizard_generator_shards"
                ),

                "effective_luminosity_fb_inv":
                    effective_lumi,

                "weight_phys":
                    weight,

                "included_shards":
                    shards,

                "manifest_path":
                    str(
                        manifest_path
                    ),

                "manifest_sha256":
                    manifest_hash,
            }
        )

        sample_entry_counts[
            sample_key
        ] += 1

    # -------------------------------------------------------------------------
    # Final Whizard closure checks.
    # -------------------------------------------------------------------------

    expected_entries = int(
        expected[
            "normalization_entries"
        ]
    )

    if len(output) != expected_entries:
        raise RuntimeError(
            "Whizard normalization-entry count mismatch: "
            f"{len(output)} != "
            f"{expected_entries}"
        )

    expected_sample_entries = expected[
        "sample_normalization_entries"
    ]

    for sample_key in [
        "6q",
        "4f2l",
    ]:
        observed = (
            sample_entry_counts[
                sample_key
            ]
        )

        target = int(
            expected_sample_entries[
                sample_key
            ]
        )

        if observed != target:
            raise RuntimeError(
                "Whizard normalization-entry mismatch "
                f"for {sample_key}: "
                f"{observed} != {target}"
            )

    audit = {
        "source_rows":
            len(
                rows
            ),

        "allowed_category":
            allowed_category,

        "allowed_category_rows":
            len(
                category_rows
            ),

        "ignored_other_category_rows":
            len(
                ignored_rows
            ),

        "excluded_unreadable_rows":
            len(
                excluded_rows
            ),

        "included_generator_rows":
            len(
                valid_rows
            ),

        "sample_generator_rows":
            dict(
                sorted(
                    sample_row_counts.items()
                )
            ),

        "normalization_entries":
            len(
                output
            ),

        "sample_normalization_entries":
            dict(
                sorted(
                    sample_entry_counts.items()
                )
            ),

        "excluded_rows":
            excluded_rows,
    }

    print()
    print(
        "=== Whizard normalization audit ==="
    )
    print(
        f"source rows:          "
        f"{len(rows)}"
    )
    print(
        f"6f rows:              "
        f"{len(category_rows)}"
    )
    print(
        f"ignored non-6f rows:  "
        f"{len(ignored_rows)}"
    )
    print(
        f"excluded bad rows:    "
        f"{len(excluded_rows)}"
    )
    print(
        f"included shards:      "
        f"{len(valid_rows)}"
    )
    print(
        f"6q shards:            "
        f"{sample_row_counts['6q']}"
    )
    print(
        f"4f2l shards:          "
        f"{sample_row_counts['4f2l']}"
    )
    print(
        f"normalization entries:"
        f" {len(output)}"
    )
    print(
        f"  6q:                 "
        f"{sample_entry_counts['6q']}"
    )
    print(
        f"  4f2l:               "
        f"{sample_entry_counts['4f2l']}"
    )

    return (
        output,
        audit,
    )


# =============================================================================
# Main
# =============================================================================


def main() -> None:

    args = parse_args()

    source_path = resolve_path(
        args.sources
    )

    source_cfg = load_yaml(
        source_path
    )

    # -------------------------------------------------------------------------
    # Preflight configuration validation.
    # -------------------------------------------------------------------------

    whizard_cfg = source_cfg["whizard"]

    required_whizard = {
        "manifest_path",
        "manifest_sha256",
        "normalization_type",
        "allowed_category",
        "process_mask_to_sample_key",
        "helicity_aliases",
        "expected",
    }

    missing = (
        required_whizard
        - set(whizard_cfg)
    )

    if missing:
        raise RuntimeError(
            "Whizard config missing fields: "
            f"{sorted(missing)}"
        )

    print(
        "[preflight] Whizard config OK: "
        f"category={whizard_cfg['allowed_category']}, "
        f"expected_entries="
        f"{whizard_cfg['expected']['normalization_entries']}",
        flush=True,
    )

    validate_source_config(
        source_cfg
    )

    scenario_path = resolve_path(
        source_cfg["luminosity_scenarios"]
    )

    scenario_cfg = load_yaml(
        scenario_path
    )

    scenario_id = source_cfg[
        "scenario_id"
    ]

    scenarios = scenario_cfg[
        "scenarios"
    ]

    if scenario_id not in scenarios:
        raise RuntimeError(
            f"Unknown scenario_id: {scenario_id}"
        )

    scenario = scenarios[
        scenario_id
    ]

    effective_luminosities = (
        compute_effective_luminosities(
            scenario
        )
    )

    normalizations = []

    for sample_key, sample_cfg in source_cfg.get(
        "physsim_positive",
        {},
    ).items():

        for polarization, hel_cfg in sample_cfg[
            "helicities"
        ].items():

            normalizations.append(
                scan_standard_physsim(
                    sample_key=sample_key,
                    polarization=polarization,
                    config=hel_cfg,
                    effective_lumi=effective_luminosities[
                        polarization
                    ],
                )
            )

    for sample_key, sample_cfg in source_cfg.get(
        "physsim_interference",
        {},
    ).items():

        for polarization, hel_cfg in sample_cfg[
            "helicities"
        ].items():

            normalizations.append(
                scan_interference_physsim(
                    sample_key=sample_key,
                    polarization=polarization,
                    config=hel_cfg,
                    effective_lumi=effective_luminosities[
                        polarization
                    ],
                )
            )

    whizard_entries, whizard_audit = (
        scan_whizard(
            source_cfg[
                "whizard"
            ],
            effective_luminosities,
        )
    )

    normalizations.extend(
        whizard_entries
    )

    normalizations = sorted(
        normalizations,
        key=lambda item: item[
            "normalization_key"
        ],
    )

    inventory = {
        "schema_version": 1,
        "scenario_id": scenario_id,

        "luminosity": {
            "source": scenario_cfg.get("source"),
            "sqrt_s_gev": float(
                scenario["sqrt_s_gev"]
            ),
            "total_luminosity_fb_inv": float(
                scenario[
                    "total_luminosity_fb_inv"
                ]
            ),
            "effective_pure_helicity_luminosity_fb_inv":
                effective_luminosities,
        },

        "normalization_rules": {
            "standard_weight": (
                "cross_section_fb * "
                "effective_luminosity_fb_inv / "
                "generator_events"
            ),
            "interference_weight": (
                "event_sign * sigma_absint_fb * "
                "effective_luminosity_fb_inv / "
                "generator_events"
            ),
            "reconstructed_counts_used_as_denominator": False,
            "exported_counts_used_as_denominator": False,
            "inclusive_tth_truth_categories_renormalized_separately": False,
        },

        "source_config": {
            "path": str(source_path),
            "sha256": sha256_file(source_path),
        },

        "luminosity_config": {
            "path": str(scenario_path),
            "sha256": sha256_file(scenario_path),
        },

        "whizard_audit": whizard_audit,

        "normalizations": normalizations,
    }

    canonical = json.dumps(
        inventory,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    inventory[
        "inventory_content_hash"
    ] = hashlib.sha256(
        canonical
    ).hexdigest()

    output_path = resolve_path(
        source_cfg["output_inventory"]
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            inventory,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print("=== Physical normalization inventory ===")
    print(f"scenario: {scenario_id}")
    print(
        "effective luminosities [fb^-1]: "
        f"{effective_luminosities}"
    )
    print(
        f"normalization entries: "
        f"{len(normalizations)}"
    )
    print(
        f"inventory hash: "
        f"{inventory['inventory_content_hash']}"
    )
    print(f"output: {output_path}")
    print()
    print("NORMALIZATION INVENTORY AUDIT PASS")


if __name__ == "__main__":
    main()

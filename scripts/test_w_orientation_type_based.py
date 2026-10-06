#!/usr/bin/env python3
"""Test v2 W-daughter orientation and compute Fisher information from baseline-v3 CSVs.

The baseline contains raw lab-frame jet/lepton four-momenta, KinFit-selected
jet indices and Weaver PID scores.

W-daughter assignment is NOT reimplemented here. This script directly uses
the authoritative functions in ilc_tth_cpv.flavor:

    flavor.orient_w_pair_v2
    flavor.quark_antiquark_slots_from_type
    flavor.semileptonic_down_type_order

The angular observables are evaluated in the Higgs rest frame.

Supported input modes:

1. Explicit single CPV/SM CSV pair:

   python3 scripts/test_w_orientation_v2.py \
       --cpv-csv /path/to/features_reco_baseline_v3_interference_chunk1.csv \
       --sm-csv /path/to/features_reco_baseline_v3_sm_chunk1.csv

2. Separate CPV/SM directories for many chunks:

   python3 scripts/test_w_orientation_v2.py \
       --cpv-dir /path/to/interference_dir \
       --sm-dir /path/to/sm_dir \
       --chunks 1-79

3. Same directory for CPV and SM:

   python3 scripts/test_w_orientation_v2.py \
       --input-dir /path/to/baselines \
       --chunks 1-79
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from ilc_tth_cpv import angles, flavor, frames
from ilc_tth_cpv.fisher import fisher_information


OBSERVABLES = ("O_jj_v2", "O_lD_v2")
FLAVORS = ("electron", "muon")

WEAVER_KEYS = (
    "mc_u", "mc_d", "mc_s", "mc_c", "mc_b",
    "mc_ubar", "mc_dbar", "mc_sbar", "mc_cbar", "mc_bbar",
)


def parse_chunks(spec: str) -> list[int]:
    chunks = set()

    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            lo, hi = map(int, part.split("-", 1))
            if lo > hi:
                raise ValueError(f"invalid chunk range: {part}")
            chunks.update(range(lo, hi + 1))
        else:
            chunks.add(int(part))

    if not chunks:
        raise ValueError(f"no chunks parsed from {spec!r}")

    return sorted(chunks)


def finite_float(row: dict, name: str) -> float:
    value = float(row[name])

    if not math.isfinite(value):
        raise ValueError(f"non-finite {name}")

    return value


def integer_slot(row: dict, name: str) -> int:
    value = finite_float(row, name)
    slot = int(value)

    if value != slot or slot < 0 or slot >= 6:
        raise ValueError(f"invalid {name}={value}")

    return slot


def jet_p4(row: dict, slot: int) -> tuple[float, float, float, float]:
    return (
        finite_float(row, f"jet{slot}_E"),
        finite_float(row, f"jet{slot}_px"),
        finite_float(row, f"jet{slot}_py"),
        finite_float(row, f"jet{slot}_pz"),
    )


def lepton_p4(row: dict) -> tuple[float, float, float, float]:
    return (
        finite_float(row, "lepton_lab_E"),
        finite_float(row, "lepton_lab_px"),
        finite_float(row, "lepton_lab_py"),
        finite_float(row, "lepton_lab_pz"),
    )


def weaver_scores(row: dict, slot: int) -> dict[str, float]:
    return {key: finite_float(row, f"jet{slot}_weaver_{key}") for key in WEAVER_KEYS}


def phi_in_higgs_rest(
    p4: tuple[float, float, float, float],
    higgs_p4: tuple[float, float, float, float],
) -> float:
    result = frames.boost_only_angles(p4, higgs_p4)

    if result is None:
        raise ValueError("invalid Higgs-rest boost")

    return float(result[2])


def compute_v2_observables(row: dict) -> tuple[float, float, dict]:
    """Compute O_jj_v2 and O_lD_v2 using flavor.py directly."""

    idx_w1 = integer_slot(row, "idx_W1")
    idx_w2 = integer_slot(row, "idx_W2")
    idx_h1 = integer_slot(row, "idx_H1")
    idx_h2 = integer_slot(row, "idx_H2")

    lepton_charge = finite_float(row, "lepton_charge")

    if lepton_charge == 0.0:
        raise ValueError("zero lepton charge")

    w_indices = (idx_w1, idx_w2)

    scores1 = weaver_scores(row, idx_w1)
    scores2 = weaver_scores(row, idx_w2)

    # ------------------------------------------------------------
    # Authoritative v2 D/U assignment from flavor.py
    # ------------------------------------------------------------

    orientation = flavor.orient_w_pair_v2(scores1, scores2)

    down_local = int(orientation["down_slot"])
    up_local = int(orientation["up_slot"])

    down_index = w_indices[down_local]
    up_index = w_indices[up_local]

    # ------------------------------------------------------------
    # Convert D/U ordering into q/qbar ordering using lepton charge
    # ------------------------------------------------------------

    quark_local, antiquark_local = flavor.quark_antiquark_slots_from_type(
        lepton_charge,
        down_local,
        up_local,
    )

    quark_index = w_indices[quark_local]
    antiquark_index = w_indices[antiquark_local]

    # ------------------------------------------------------------
    # Reconstruct Higgs four-momentum from selected H -> bb jets
    # ------------------------------------------------------------

    higgs_p4 = frames.add_p4(
        jet_p4(row, idx_h1),
        jet_p4(row, idx_h2),
    )

    # ------------------------------------------------------------
    # Boost relevant objects from lab into Higgs rest frame
    # ------------------------------------------------------------

    phi_q = phi_in_higgs_rest(jet_p4(row, quark_index), higgs_p4)
    phi_qbar = phi_in_higgs_rest(jet_p4(row, antiquark_index), higgs_p4)
    phi_lepton = phi_in_higgs_rest(lepton_p4(row), higgs_p4)

    # ------------------------------------------------------------
    # O_jj = wrap(phi_q - phi_qbar)
    # ------------------------------------------------------------

    o_jj = angles.delta_phi(phi_q, phi_qbar)

    # ------------------------------------------------------------
    # O_lD:
    #
    # q_l > 0 -> ("lepton", "wjet_quark")
    # q_l < 0 -> ("wjet_antiquark", "lepton")
    #
    # The q/qbar labels above already came from v2 D/U assignment.
    # ------------------------------------------------------------

    analyzer_order = flavor.semileptonic_down_type_order(lepton_charge)

    if analyzer_order is None:
        raise ValueError(f"invalid lepton charge: {lepton_charge}")

    phi_map = {
        "lepton": phi_lepton,
        "wjet_quark": phi_q,
        "wjet_antiquark": phi_qbar,
    }

    first_name, second_name = analyzer_order
    o_ld = angles.delta_phi(phi_map[first_name], phi_map[second_name])

    diagnostics = {
        **orientation,
        "idx_W1": idx_w1,
        "idx_W2": idx_w2,
        "down_index": down_index,
        "up_index": up_index,
        "quark_index": quark_index,
        "antiquark_index": antiquark_index,
    }

    return o_jj, o_ld, diagnostics


def metadata_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".meta.json")


def read_metadata(csv_path: Path) -> dict:
    path = metadata_path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"missing metadata: {path}")

    with path.open() as stream:
        return json.load(stream)


def chunk_event_count(meta: dict, component: str) -> float:
    """Return N_k using the same chunk-pooling convention as the angular workflow."""

    if component == "interference":
        n_k = meta.get("n_sidecar")

    elif component == "sm":
        sm_normalization = meta.get("sm_normalization") or {}
        n_k = sm_normalization.get("n_written")

        # Fallback in case a future metadata version exposes it at top level.
        if n_k is None:
            n_k = meta.get("n_written")

    else:
        raise ValueError(f"unsupported component: {component}")

    if n_k is None:
        raise ValueError(f"cannot determine N_k for {component}")

    n_k = float(n_k)

    if not math.isfinite(n_k) or n_k <= 0.0:
        raise ValueError(f"invalid N_k={n_k} for {component}")

    return n_k


def baseline_filename(component: str, chunk: int) -> str:
    if component == "interference":
        return f"features_reco_baseline_v3_interference_chunk{chunk}.csv"

    if component == "sm":
        return f"features_reco_baseline_v3_sm_chunk{chunk}.csv"

    raise ValueError(component)


def empty_histograms(n_bins: int) -> dict:
    return {
        observable: {
            lep_flavor: np.zeros(n_bins, dtype=np.float64)
            for lep_flavor in FLAVORS
        }
        for observable in OBSERVABLES
    }


def process_csv(
    csv_path: Path,
    component: str,
    edges: np.ndarray,
) -> tuple[dict, float]:
    """Build v2 angular templates from one baseline CSV."""

    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    n_bins = len(edges) - 1
    histograms = empty_histograms(n_bins)

    counts = {
        observable: {lep_flavor: 0 for lep_flavor in FLAVORS}
        for observable in OBSERVABLES
    }

    invalid = {
        observable: {lep_flavor: 0 for lep_flavor in FLAVORS}
        for observable in OBSERVABLES
    }

    orientation_status = Counter()
    total_rows = 0
    used_rows = 0

    with csv_path.open(newline="") as stream:
        reader = csv.DictReader(stream)

        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {csv_path}")

        for row in reader:
            total_rows += 1

            lep_flavor = row.get("lepton_flavor")

            if lep_flavor not in FLAVORS:
                continue

            try:
                weight_column = (
                    "weight_interference_signed"
                    if component == "interference"
                    else "weight_sm"
                )

                weight = finite_float(row, weight_column)
                o_jj, o_ld, diagnostics = compute_v2_observables(row)

            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                for observable in OBSERVABLES:
                    invalid[observable][lep_flavor] += 1
                continue

            used_rows += 1
            orientation_status[str(diagnostics.get("status", "unknown"))] += 1

            values = {
                "O_jj_v2": o_jj,
                "O_lD_v2": o_ld,
            }

            for observable, value in values.items():
                if not math.isfinite(value):
                    invalid[observable][lep_flavor] += 1
                    continue

                index = np.searchsorted(edges, value, side="right") - 1

                # Include exactly +pi in the final bin.
                if index == n_bins and math.isclose(
                    value,
                    edges[-1],
                    abs_tol=1.0e-12,
                ):
                    index = n_bins - 1

                if index < 0 or index >= n_bins:
                    invalid[observable][lep_flavor] += 1
                    continue

                histograms[observable][lep_flavor][index] += weight
                counts[observable][lep_flavor] += 1

    meta = read_metadata(csv_path)
    n_k = chunk_event_count(meta, component)

    print()
    print(f"{component}: {csv_path}")
    print(f"  rows       = {total_rows}")
    print(f"  used rows  = {used_rows}")
    print(f"  N_k        = {n_k:g}")
    print(f"  orientation statuses = {dict(orientation_status)}")

    for observable in OBSERVABLES:
        print(
            f"  {observable}: "
            f"electron={counts[observable]['electron']} "
            f"muon={counts[observable]['muon']} "
            f"invalid_e={invalid[observable]['electron']} "
            f"invalid_mu={invalid[observable]['muon']}"
        )

    return histograms, n_k


def pooled_templates(
    input_dir: Path,
    chunks: list[int],
    component: str,
    edges: np.ndarray,
) -> dict:
    """Pool per-chunk cross-section templates with N_k weighting."""

    n_bins = len(edges) - 1
    numerator = empty_histograms(n_bins)
    total_n = 0.0

    print()
    print("=" * 80)
    print(f"Building {component} template from chunks {chunks[0]}-{chunks[-1]}")
    print("=" * 80)

    for chunk in chunks:
        csv_path = input_dir / baseline_filename(component, chunk)

        histograms, n_k = process_csv(
            csv_path,
            component,
            edges,
        )

        total_n += n_k

        for observable in OBSERVABLES:
            for lep_flavor in FLAVORS:
                numerator[observable][lep_flavor] += (
                    n_k * histograms[observable][lep_flavor]
                )

    if total_n <= 0.0:
        raise ValueError(f"total N_k <= 0 for {component}")

    pooled = empty_histograms(n_bins)

    for observable in OBSERVABLES:
        for lep_flavor in FLAVORS:
            pooled[observable][lep_flavor] = (
                numerator[observable][lep_flavor] / total_n
            )

    print()
    print(f"{component} N_total = {total_n:g}")

    return pooled


def evaluate_fisher(
    cpv: dict,
    sm: dict,
    luminosity_fb: float,
) -> None:
    print()
    print("=" * 80)
    print("V2 Fisher information")
    print("=" * 80)
    print(f"luminosity = {luminosity_fb:g} fb^-1")

    for observable in OBSERVABLES:
        combined_fisher = 0.0

        print()
        print(observable)
        print("-" * 60)

        for lep_flavor in FLAVORS:
            nu1 = cpv[observable][lep_flavor] * luminosity_fb
            nu0 = sm[observable][lep_flavor] * luminosity_fb

            result = fisher_information(nu0, nu1)

            fisher_value = float(result["fisher_absolute"])
            combined_fisher += fisher_value

            print(
                f"  {lep_flavor:8s}: "
                f"I = {fisher_value:.6f}, "
                f"sigma = {result['sigma_c']:.6f}, "
                f"invalid bins = {result['n_invalid_bins']}"
            )

        sigma_combined = (
            1.0 / math.sqrt(combined_fisher)
            if combined_fisher > 0.0
            else math.inf
        )

        print(
            f"  combined: I = {combined_fisher:.6f}, "
            f"sigma = {sigma_combined:.6f}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--cpv-csv",
        type=Path,
        default=None,
        help="single interference baseline CSV",
    )

    parser.add_argument(
        "--sm-csv",
        type=Path,
        default=None,
        help="single SM baseline CSV",
    )

    parser.add_argument(
        "--cpv-dir",
        type=Path,
        default=None,
        help="directory containing interference chunk CSVs",
    )

    parser.add_argument(
        "--sm-dir",
        type=Path,
        default=None,
        help="directory containing SM chunk CSVs",
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="shared directory when CPV and SM CSVs are stored together",
    )

    parser.add_argument(
        "--chunks",
        default="1-79",
        help="chunk specification, e.g. 1, 1-79, 1-10,15,20-30",
    )

    parser.add_argument(
        "--bins",
        type=int,
        default=36,
        help="number of angular bins",
    )

    parser.add_argument(
        "--luminosity-fb",
        type=float,
        default=8000.0,
        help="integrated luminosity in fb^-1",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.bins <= 0:
        raise SystemExit("--bins must be positive")

    if not math.isfinite(args.luminosity_fb) or args.luminosity_fb <= 0.0:
        raise SystemExit("--luminosity-fb must be finite and positive")

    if (args.cpv_csv is None) != (args.sm_csv is None):
        raise SystemExit("--cpv-csv and --sm-csv must be provided together")

    if (args.cpv_dir is None) != (args.sm_dir is None):
        raise SystemExit("--cpv-dir and --sm-dir must be provided together")

    csv_mode = args.cpv_csv is not None
    separate_dir_mode = args.cpv_dir is not None
    shared_dir_mode = args.input_dir is not None

    if sum((csv_mode, separate_dir_mode, shared_dir_mode)) != 1:
        raise SystemExit(
            "choose exactly one input mode:\n"
            "  --cpv-csv + --sm-csv\n"
            "  --cpv-dir + --sm-dir\n"
            "  --input-dir"
        )

    edges = np.linspace(-math.pi, math.pi, args.bins + 1)

    if csv_mode:
        print("=" * 80)
        print("Single CSV-pair mode")
        print("=" * 80)

        cpv, _ = process_csv(
            args.cpv_csv,
            "interference",
            edges,
        )

        sm, _ = process_csv(
            args.sm_csv,
            "sm",
            edges,
        )

    else:
        chunks = parse_chunks(args.chunks)

        if separate_dir_mode:
            cpv_dir = args.cpv_dir
            sm_dir = args.sm_dir
        else:
            cpv_dir = args.input_dir
            sm_dir = args.input_dir

        cpv = pooled_templates(
            cpv_dir,
            chunks,
            "interference",
            edges,
        )

        sm = pooled_templates(
            sm_dir,
            chunks,
            "sm",
            edges,
        )

    evaluate_fisher(
        cpv,
        sm,
        args.luminosity_fb,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
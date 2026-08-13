#!/usr/bin/env python3
"""Combine per-chunk angular histogram templates into one pooled template,
optionally producing a 4-curve (gen/reco x CPV/SM) comparison plot.

Single-template usage:
    python3 scripts/combine_angular_templates.py \
        --pattern "outputs/angular_lr/angular/O_W/chunk1-10/O_W_all_gen_electron_chunk{chunk}_bins.csv" \
        --chunks 1-10 \
        --feature-meta-pattern "outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json" \
        --out outputs/angular_lr/angular/O_W/chunk1-10/O_W_all_gen_electron_combined_bins.csv

4-curve comparison usage:
    python3 scripts/combine_angular_templates.py \
        --chunks 1-10 \
        --compare-plot \
        --reco-cpv-csv "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_reco_electron_chunk{chunk}_bins.csv" \
        --reco-cpv-meta "outputs/angular_lr/features/chunk1-10/features_reco_higgs_rest_chunk{chunk}.meta.json" \
        --reco-sm-csv  "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_reco_electron_chunk{chunk}_bins.csv" \
        --reco-sm-meta  "outputs/angular_lr/features/chunk1-10/features_sm_reco_higgs_rest_chunk{chunk}.meta.json" \
        --gen-cpv-csv  "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_gen_electron_chunk{chunk}_bins.csv" \
        --gen-cpv-meta  "outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json" \
        --gen-sm-csv   "outputs/angular_lr/angular/O_W/chunk1-10/chunk{chunk}/O_W_all_sm_gen_electron_chunk{chunk}_bins.csv" \
        --gen-sm-meta   "outputs/angular_lr/features/chunk1-10/features_sm_gen_higgs_rest_chunk{chunk}.meta.json" \
        --out-dir outputs/angular_lr/angular/O_W \
        --tag O_W_electron
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv.histograms import SignedHistogram  # noqa: E402
from ilc_tth_cpv.io import read_table, write_table  # noqa: E402
from ilc_tth_cpv.plotting import import_plotting, plot_signed_histogram  # noqa: E402


# Chunk range parsing 
def parse_chunk_spec(spec: str) -> List[int]:
    """Take the provided (input) chunk numbers and turns it into a sorted list"""
    chunks = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low_s, high_s = part.split("-", 1)
            low, high = int(low_s), int(high_s)
            if low > high:
                raise SystemExit(f"Invalid chunk range '{part}': start > end")
            chunks.update(range(low, high + 1))
        else:
            chunks.add(int(part))
    if not chunks:
        raise SystemExit(f"No chunks parsed from --chunks '{spec}'")
    return sorted(chunks)

def get_chunk_label(chunk_ids: List[int]) -> str:
    """Format chunk list into a tag like 'chunk0-10' or 'chunk1_3_5'."""
    if len(chunk_ids) == 1:
        return f"chunk{chunk_ids[0]}"
    if chunk_ids == list(range(chunk_ids[0], chunk_ids[-1] + 1)):
        return f"chunk{chunk_ids[0]}-{chunk_ids[-1]}"
    return "chunk" + "_".join(str(c) for c in chunk_ids)


# File loading 
def meta_path_for(bins_csv_path: Path) -> Path:
    """Takes the path to a .csv file and derives the path to bins.meta.json file"""
    return Path(str(bins_csv_path).rsplit(".", 1)[0] + ".meta.json")


def load_chunk_template(pattern: str, chunk: int, feature_meta_pattern: str) -> dict:
    """Reads the csv table and json metadata for a given chunk number,
       extracts the total generator event count (n_k) and put them into dictionary"""

    bins_path = Path(pattern.format(chunk=chunk))
    if not bins_path.exists():
        raise SystemExit(f"Missing chunk {chunk} bins CSV: {bins_path}")

    bin_records = read_table(bins_path)

    # get .meta.json file from the corresponding .csv file
    bins_meta_path = meta_path_for(bins_path)
    meta = {}
    if bins_meta_path.exists():
        with bins_meta_path.open() as f:
            meta = json.load(f)
    else:
        raise SystemExit(f"Missing chunk {chunk} metadata: {bins_meta_path}")

    # Search for event counts (n_read or n_sidecar or n_write) from feature_meta.json
    n_k = None
    n_k_source = None
    
    if feature_meta_pattern:
        feature_meta_path = Path(feature_meta_pattern.format(chunk=chunk))
        if not feature_meta_path.exists():
            raise SystemExit(f"Chunk {chunk}: Missing feature metadata file at {feature_meta_path}")

        with feature_meta_path.open() as f:
            feature_meta = json.load(f)

        if "n_sidecar" in feature_meta and feature_meta["n_sidecar"]:
            n_k = feature_meta["n_sidecar"]
            n_k_source = "n_sidecar"
        elif "n_read" in feature_meta:
            n_k = feature_meta["n_read"]
            n_k_source = "n_read"
        elif "sm_normalization" in feature_meta and feature_meta["sm_normalization"] and "n_written" in feature_meta["sm_normalization"]:
            n_k = feature_meta["sm_normalization"]["n_written"]
            n_k_source = "sm_normalization.n_written"
        else:
            n_k = None
            n_k_source = None
            raise SystemExit(
                f"Chunk {chunk}: could not find an event count in {feature_meta_path}. "
                f"Tried 'n_read', 'n_sidecar', 'sm_normalization.n_written'. "
                f"Available top-level keys: {sorted(feature_meta.keys())}"
            )
            

        print(f"-> Loaded Chunk {chunk}: N_k = {int(n_k)} (from '{n_k_source}' in {feature_meta_path.name})")

    if n_k is None:
        raise SystemExit(
            f"Chunk {chunk}: could not find an event count in {feature_meta_path}. "
            f"Available top-level keys: {sorted(feature_meta.keys())}"
        )

    print(f"-> Loaded Chunk {chunk}: N_k = {int(n_k)} (from {feature_meta_path.name})")

    return {
        "chunk": chunk, 
        "bins_path": bins_path, 
        "bins_meta_path": bins_meta_path,
        "bin_records": bin_records, 
        "meta": meta, 
        "n_k": float(n_k),
        "n_k_source": n_k_source,
    }


def validate_consistent(templates: List[dict]) -> None:
    """safety check"""
    first = templates[0]
    first_meta = first["meta"]
    first_edges = edges_from_rows(first["bin_records"])
    for tpl in templates[1:]:
        meta = tpl["meta"]
        for key in ("observable", "frame", "weight_column"):
            if meta.get(key) != first_meta.get(key):
                raise SystemExit(
                    f"Chunk {tpl['chunk']} metadata mismatch on '{key}': "
                    f"{meta.get(key)!r} != {first_meta.get(key)!r}"
                )
        edges = edges_from_rows(tpl["bin_records"])
        if edges != first_edges:
            raise SystemExit(
                f"Chunk {tpl['chunk']} has different binning than "
                f"chunk {first['chunk']}"
            )


def edges_from_rows(bin_records: list) -> List[float]:
    """Reconstructs the list of bin boundary edges (x-ranges) from the csv rows"""
    edges = [float(row["bin_low"]) for row in bin_records]
    edges.append(float(bin_records[-1]["bin_high"]))
    return edges


# Combination 
def combine_templates(chunk_hists: List[dict]) -> dict:
    """Performs the mathematical pooling of per-chunk histograms into a single 
       unified template"""

    # Total number of events (n_total) for all chunks
    n_total = sum(hist_per_chunk["n_k"] for hist_per_chunk in chunk_hists)
    if n_total <= 0.0:
        raise SystemExit("N_total <= 0; cannot combine (check n_read values)")

    per_chunk_n = {hist["chunk"]: hist["n_k"] for hist in chunk_hists}

    # Get number of bins and edges from one of the chunks 
    n_bins = len(chunk_hists[0]["bin_records"])
    edges = edges_from_rows(chunk_hists[0]["bin_records"])

    # Creates empty lists for signed & absolute cross-section weights, and raw event counts 
    signed_weight_tot = [0.0] * n_bins
    abs_weight_tot    = [0.0] * n_bins
    entries_tot       = [0] * n_bins

    for hist_per_chunk in chunk_hists:
        for i, bin_data in enumerate(hist_per_chunk["bin_records"]):
            sigma_signed = float(bin_data["signed_weight_fb"]) * hist_per_chunk["n_k"]
            sigma_abs    = float(bin_data["abs_weight_fb"]) * hist_per_chunk["n_k"]

            signed_weight_tot[i] += sigma_signed / n_total
            abs_weight_tot[i]    += sigma_abs / n_total
            entries_tot[i]       += int(bin_data["entries"])

    local_signed_fraction = [
        (s / a) if a > 0.0 else 0.0
        for s, a in zip(signed_weight_tot, abs_weight_tot)
    ]

    frame = chunk_hists[0]["meta"].get("frame", "")
    observable = chunk_hists[0]["meta"].get("observable", "")

    bin_records = []
    for i in range(n_bins):
        bin_records.append({
            "frame": frame, 
            "observable": observable, 
            "bin_index": i,
            "bin_low": edges[i], 
            "bin_high": edges[i + 1],
            "bin_center": 0.5 * (edges[i] + edges[i + 1]),
            "signed_weight_fb": signed_weight_tot[i],
            "abs_weight_fb": abs_weight_tot[i],
            "local_signed_fraction": local_signed_fraction[i],
            "entries": entries_tot[i],
        })

    return {
        "bin_records": bin_records, 
        "edges": edges, 
        "signed": signed_weight_tot,
        "absw": abs_weight_tot, 
        "entries": entries_tot,
        "n_total": n_total, 
        "per_chunk_n": per_chunk_n,
        "frame": frame, 
        "observable": observable,
        "weight_column": chunk_hists[0]["meta"].get("weight_column"),
        "chunk_hists": chunk_hists,
    }


def combine_one(pattern: str, chunk_ids: List[int], feature_meta_pattern: str) -> dict:
    """Load, validate, and combine one pattern's chunks. The single-pattern
    workhorse reused by both single-output mode and --compare-plot mode."""
    templates = [load_chunk_template(pattern, c, feature_meta_pattern) for c in chunk_ids]
    validate_consistent(templates)
    return combine_templates(templates)


def write_combined(combined: dict, out_path: Path, chunk_ids: List[int], pattern: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_hists = combined.get("chunk_hists", [])

    meta = {
        "observable": combined["observable"],
        "frame": combined["frame"],
        "weight_column": combined["weight_column"],
        "combination_method": (
            "event-count-weighted average across chunks: "
            "H_i = sum_k (N_k/N_total) * H_i^(k); entries summed directly"
        ),
        "contributing_chunks": chunk_ids,
        "per_chunk_n_k": {
            f"chunk_{c['chunk']}": int(c["n_k"]) for c in chunk_hists
        },
        "per_chunk_n_sources": {
            f"chunk_{c['chunk']}": c.get("n_k_source", "unknown") for c in chunk_hists
        },
        "n_k_total": int(combined["n_total"]),
        "source_pattern": pattern,
    }

    write_table(out_path, combined["bin_records"], metadata=meta)
    print(f"bins   -> {out_path}  (N_total={combined['n_total']:.1f})")


# 4-curve comparison plot, built directly from combined in-memory data

def plot_four_curve_comparison(
    reco_cpv: dict, reco_sm: dict, gen_cpv: dict, gen_sm: dict,
    out_path: Path, observable: str, category_label: str,
) -> None:
    plt = import_plotting()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    curves = {
        "reco CPV":      (reco_cpv, "#2458a4", "-",  1.0),
        "reco SM / 10":  (reco_sm,  "#2458a4", "--", 0.1),
        "gen CPV":       (gen_cpv,  "#b34d2e", "-",  1.0),
        "gen SM / 10":   (gen_sm,   "#b34d2e", "--", 0.1),
    }

    for label, (combined, color, linestyle, scale) in curves.items():
        edges = combined["edges"]
        signed = [s * scale for s in combined["signed"]]
        ax.step(edges, signed + [signed[-1]], where="post",
                color=color, linewidth=1.4, linestyle=linestyle, label=label)

    ax.axhline(0.0, color="#222222", linewidth=0.8)
    ax.set_xlabel(f"{observable} [rad]")
    ax.set_ylabel("signed weight [fb]")
    ax.set_title(f"{observable}, {category_label}: gen vs reco, CPV vs SM "
                 f"(all chunks combined)")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"plot   -> {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--compare-plot", action="store_true",
                         help="combine 4 patterns and overlay gen/reco x CPV/SM")

    # single-template mode
    parser.add_argument("--pattern", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-plot", action="store_true")

    # compare-plot mode
    parser.add_argument(
        "--feature-meta-pattern",
        default="outputs/angular_lr/features/chunk1-10/features_gen_higgs_rest_chunk{chunk}.meta.json",
        help="Pattern for feature metadata JSON containing n_read/n_sidecar/n_written",
    )
    parser.add_argument("--reco-cpv-csv", default=None)
    parser.add_argument("--reco-cpv-meta", default=None)
    parser.add_argument("--reco-sm-csv", default=None)
    parser.add_argument("--reco-sm-meta", default=None)
    parser.add_argument("--gen-cpv-csv", default=None)
    parser.add_argument("--gen-cpv-meta", default=None)
    parser.add_argument("--gen-sm-csv", default=None)
    parser.add_argument("--gen-sm-meta", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--tag", default=None, help="filename tag, e.g. O_W_electron")

    args = parser.parse_args()
    chunk_ids = parse_chunk_spec(args.chunks)
    chunk_label = get_chunk_label(chunk_ids)
    print(f"Combining {len(chunk_ids)} chunks: {chunk_ids}")

    if args.compare_plot:
        required = {
            "--reco-cpv-csv": args.reco_cpv_csv,
            "--reco-sm-csv": args.reco_sm_csv,
            "--gen-cpv-csv": args.gen_cpv_csv,
            "--gen-sm-csv": args.gen_sm_csv,
            "--out-dir": args.out_dir,
            "--tag": args.tag,
        }
        
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise SystemExit(f"--compare-plot requires: {', '.join(missing)}")

        reco_cpv_meta = args.reco_cpv_meta or args.feature_meta_pattern
        reco_sm_meta  = args.reco_sm_meta  or args.feature_meta_pattern
        gen_cpv_meta  = args.gen_cpv_meta  or args.feature_meta_pattern
        gen_sm_meta   = args.gen_sm_meta   or args.feature_meta_pattern

        reco_cpv = combine_one(args.reco_cpv_csv, chunk_ids, reco_cpv_meta)
        reco_sm  = combine_one(args.reco_sm_csv,  chunk_ids, reco_sm_meta)
        gen_cpv  = combine_one(args.gen_cpv_csv,  chunk_ids, gen_cpv_meta)
        gen_sm   = combine_one(args.gen_sm_csv,   chunk_ids, gen_sm_meta)

        out_dir = Path(args.out_dir) / chunk_label
        full_tag = f"{args.tag}_{chunk_label}"

        write_combined(reco_cpv, out_dir / f"{full_tag}_reco_combined_bins.csv", chunk_ids, args.reco_cpv_csv)
        write_combined(reco_sm, out_dir / f"{full_tag}_sm_reco_combined_bins.csv", chunk_ids, args.reco_sm_csv)
        write_combined(gen_cpv, out_dir / f"{full_tag}_gen_combined_bins.csv", chunk_ids, args.gen_cpv_csv)
        write_combined(gen_sm, out_dir / f"{full_tag}_sm_gen_combined_bins.csv", chunk_ids, args.gen_sm_csv)

        plot_four_curve_comparison(
            reco_cpv, reco_sm, gen_cpv, gen_sm,
            out_path=out_dir / f"{full_tag}_gen_vs_reco_cpv_vs_sm_combined.png",
            observable=reco_cpv["observable"],
            category_label=f"{args.tag} ({chunk_label})",
        )
        return 0

    # single-template mode (original behavior)
    if not args.pattern or not args.out:
        raise SystemExit("Non-compare mode requires --pattern and --out")

    out_str = args.out
    if "{chunks}" in out_str:
        out_str = out_str.format(chunks=chunk_label)
    elif "{chunk_label}" in out_str:
        out_str = out_str.format(chunk_label=chunk_label)

    combined = combine_one(args.pattern, chunk_ids, args.feature_meta_pattern)
    out_path  = Path(out_str)

    # Automatically insert the chunk folder into the target path if not already present
    if chunk_label not in out_path.parts:
        out_path = out_path.parent / chunk_label / out_path.name

    write_combined(combined, out_path, chunk_ids, args.pattern)
    if not args.no_plot:
        hist = SignedHistogram(edges=combined["edges"])
        hist.signed = combined["signed"]
        hist.absw = combined["absw"]
        hist.entries = combined["entries"]
        plot_signed_histogram(
            hist, out_path.with_suffix(".png"),
            title=f"{combined['observable']} [{combined['frame']}] combined",
            xlabel=f"{combined['observable']} [rad]",
        )
        print(f"plot   -> {out_path.with_suffix('.png')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
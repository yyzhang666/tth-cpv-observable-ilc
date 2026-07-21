"""Config and event-table IO with schema validation.

CSV is the interchange format (DATA_SCHEMA.md). yaml is optional at runtime:
configs are parsed with pyyaml when available, else a minimal fallback error
is raised with instructions.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

REQUIRED_EVENT_COLUMNS = (
    "event_id",
    "sample_name",
    "process",
    "level",
    "helicity",
    "split",
)

WEIGHT_COLUMNS = (
    "weight_sm",
    "weight_interference_signed",
    "weight_interference_abs",
    "weight_quadratic",
    "weight_training",
    "weight_polarization",
    "weight_luminosity",
    "weight_template",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pyyaml is required to read configs: pip install pyyaml "
            "(see env/requirements.txt)"
        ) from exc
    with Path(path).open() as stream:
        return yaml.safe_load(stream)


def load_paths_config() -> dict:
    """paths.local.yaml if present, else paths.template.yaml."""
    root = repo_root()
    local = root / "configs" / "paths.local.yaml"
    template = root / "configs" / "paths.template.yaml"
    return load_yaml(local if local.exists() else template)


def load_analysis_config(path: Path) -> dict:
    cfg = load_yaml(path)
    for key in ("analysis", "samples", "observable", "weights"):
        if key not in cfg:
            raise ValueError(f"Analysis config {path} missing block '{key}'")
    return cfg


def resolve_gen_chunk(sample: dict, chunk: str) -> dict:
    """Resolve stdhep + sidecar paths for one generator chunk.

    Supports both sample layouts in configs/samples.yaml:
    - production layout: per-chunk stdhep under path/ with '*' chunk slot in
      file_pattern, per-chunk sidecar under sidecar_dir with '{chunk}' slot;
      alignment is accepted-event order (no skip log).
    - historical layout: single stdhep, 'sidecar' + 'physsim_log' keys
      (JSFHadronizer skip alignment needed).
    """
    base = Path(sample["path"])
    if "sidecar_dir" in sample:
        stdhep = base / sample["file_pattern"].replace("*", str(chunk))
        sidecar = Path(sample["sidecar_dir"]) / sample["sidecar_pattern"].replace(
            "{chunk}", str(chunk)
        )
        result = {"chunk": str(chunk), "stdhep": stdhep, "sidecar": sidecar,
                  "physsim_log": None}
    else:
        result = {
            "chunk": "0",
            "stdhep": base / sample["file_pattern"],
            "sidecar": base / sample["sidecar"],
            "physsim_log": base / sample["physsim_log"]
            if sample.get("physsim_log") else None,
        }
    for key in ("stdhep", "sidecar"):
        if not Path(result[key]).exists():
            raise FileNotFoundError(f"Missing {key}: {result[key]}")
    return result


def read_table(path: Path) -> List[dict]:
    with Path(path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_table(path: Path, rows: List[dict], metadata: Optional[dict] = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Refusing to write an empty table")
    columns = list(rows[0].keys())
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    if metadata is not None:
        write_metadata(path, metadata)


def write_metadata(table_path: Path, metadata: dict) -> Path:
    meta_path = Path(str(table_path).rsplit(".", 1)[0] + ".meta.json")
    payload = dict(metadata)
    payload.setdefault("table", os.path.basename(str(table_path)))
    with meta_path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, default=str)
    return meta_path


def file_sha256(path: Path, max_bytes: int = 1 << 24) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        digest.update(stream.read(max_bytes))
    return digest.hexdigest()


def validate_table(rows: List[dict], required_objects: Optional[List[str]] = None) -> dict:
    """Validate a table against DATA_SCHEMA.md. Returns a report dict."""
    problems = []
    if not rows:
        return {"ok": False, "problems": ["empty table"]}
    columns = set(rows[0].keys())
    for col in REQUIRED_EVENT_COLUMNS:
        if col not in columns:
            problems.append(f"missing required column {col}")
    for col in WEIGHT_COLUMNS:
        if col not in columns:
            problems.append(f"missing weight column {col} (fill NaN if unavailable)")
    seen_ids: Dict[str, int] = {}
    for row in rows:
        key = f"{row.get('sample_name')}:{row.get('level')}:{row.get('event_id')}"
        seen_ids[key] = seen_ids.get(key, 0) + 1
    dupes = [k for k, v in seen_ids.items() if v > 1]
    if dupes:
        problems.append(f"duplicated event ids: {dupes[:5]} ...")
    if "split" in columns:
        splits = {row["split"] for row in rows}
        unexpected = splits - {"train", "validation", "test"}
        if unexpected:
            problems.append(f"unexpected split labels: {sorted(unexpected)}")
    if required_objects:
        for obj in required_objects:
            for suffix in ("E", "theta", "phi", "mass", "valid"):
                col = f"{obj}_{suffix}"
                if col not in columns:
                    problems.append(f"missing object column {col}")
    return {"ok": not problems, "problems": problems, "n_rows": len(rows)}


def match_event_ids(gen_rows: List[dict], reco_rows: List[dict]) -> dict:
    """Gen/reco event matching report for the optional migration diagnostic.

    Returns the common id set and unmatched counts. The common pool is used for
    R_migration, not for the primary inclusive-gen/full-reco total retention.
    """
    gen_ids = {row["event_id"] for row in gen_rows}
    reco_ids = {row["event_id"] for row in reco_rows}
    common = gen_ids & reco_ids
    return {
        "n_gen": len(gen_ids),
        "n_reco": len(reco_ids),
        "n_common": len(common),
        "common_ids": common,
        "gen_only": len(gen_ids - reco_ids),
        "reco_only": len(reco_ids - gen_ids),
    }

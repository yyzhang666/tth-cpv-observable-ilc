#!/usr/bin/env bash
# Run the standard jet-assignment + kinematic-fit stage on one reco chunk.
#
# This is the ONLY supported way to produce assignment/fit results in this
# project (docs/KINFIT_JET_ASSIGNMENT.md). Physics parameters live in
# steering/tth_semilep_kinfit.xml and must not be edited.
#
# Usage:
#   bash scripts/run_kinfit_assignment.sh --config configs/analysis_ow_lr.yaml --chunk 0 --max-events 50   # smoke
#   bash scripts/run_kinfit_assignment.sh --config configs/analysis_ow_lr.yaml --chunk 0                   # full chunk
#   bash scripts/run_kinfit_assignment.sh --config configs/analysis_ow_lr.yaml --component sm --chunk 0
#   bash scripts/run_kinfit_assignment.sh --slcio /path/to/file.slcio --tag mytest --max-events 50
#
# For all 80 chunks use HTCondor: condor/README.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONFIG=""
CHUNK=""
SLCIO=""
TAG=""
MAX_EVENTS=0
OUT_DIR=""
COMPONENT="interference"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)     CONFIG="$2"; shift 2 ;;
    --chunk)      CHUNK="$2"; shift 2 ;;
    --slcio)      SLCIO="$2"; shift 2 ;;
    --tag)        TAG="$2"; shift 2 ;;
    --max-events) MAX_EVENTS="$2"; shift 2 ;;
    --out-dir)    OUT_DIR="$2"; shift 2 ;;
    --component)  COMPONENT="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if ! command -v Marlin >/dev/null 2>&1; then
  echo "Marlin not found — run: source env/setup.sh" >&2
  exit 1
fi

if [[ "$COMPONENT" != "interference" && "$COMPONENT" != "sm" ]]; then
  echo "--component must be interference or sm" >&2
  exit 1
fi

# ---- resolve input ----------------------------------------------------------
if [[ -n "$SLCIO" ]]; then
  [[ -n "$TAG" ]] || { echo "--slcio requires --tag" >&2; exit 1; }
  OUT_BASE="${OUT_DIR:-outputs/adhoc/kinfit}"
else
  [[ -n "$CONFIG" && -n "$CHUNK" ]] || { echo "Provide --config + --chunk, or --slcio + --tag" >&2; exit 1; }
  eval "$(python3 - "$CONFIG" "$CHUNK" "$COMPONENT" <<'PY'
import glob, sys
sys.path.insert(0, "src")
from ilc_tth_cpv.io import load_analysis_config, load_yaml, repo_root

cfg = load_analysis_config(sys.argv[1])
chunk = sys.argv[2]
component = sys.argv[3]
manifest = load_yaml(repo_root() / cfg["samples"]["manifest"])
sample_key = cfg["samples"]["sm_reco_sample" if component == "sm" else "reco_sample"]
sample = manifest["signals"][sample_key]
# the '*' in file_pattern is the chunk id slot
pattern = sample["file_pattern"].replace("*", chunk)
matches = sorted(glob.glob(f"{sample['path']}/{pattern}"))
if not matches:
    raise SystemExit(f"No file for chunk {chunk}: {sample['path']}/{pattern}")
print(f"SLCIO={matches[0]}")
print(f"TAG={sample_key}_chunk{chunk}")
print(f"OUT_BASE={cfg['outputs']['base_dir']}/kinfit")
PY
)"
  OUT_BASE="${OUT_DIR:-$OUT_BASE}"
fi

[[ -e "$SLCIO" ]] || { echo "Missing input: $SLCIO" >&2; exit 1; }

# make output base absolute: Marlin runs inside the job-local work dir,
# so every path handed to the steering file must be absolute
[[ "$OUT_BASE" = /* ]] || OUT_BASE="$REPO_ROOT/$OUT_BASE"

# ---- job-local working directory (parallel-safe: Marlin writes hidden
#      fixed-name files into its CWD, so every run gets its own dir) ---------
WORK_DIR="$OUT_BASE/work_$TAG"
mkdir -p "$WORK_DIR"
XML="$WORK_DIR/kinfit_$TAG.xml"
OUT_ROOT="$WORK_DIR/kinfit_$TAG.root"      # outputFilename is used verbatim
LOG="$OUT_BASE/kinfit_$TAG.log"
FINAL_ROOT="$OUT_BASE/kinfit_$TAG.root"
VALIDATION_JSON="$OUT_BASE/kinfit_$TAG.validation.json"

for f in "$FINAL_ROOT"; do
  [[ -e "$f" ]] && { echo "Refusing to overwrite $f" >&2; exit 1; }
done

sed -e "s|__INPUT_LCIO__|$SLCIO|" \
    -e "s|__MAX_RECORDS__|$MAX_EVENTS|" \
    -e "s|__OUTPUT_ROOT__|$OUT_ROOT|" \
    steering/tth_semilep_kinfit.xml > "$XML"

echo "[kinfit] input : $SLCIO"
echo "[kinfit] events: ${MAX_EVENTS} (0 = all)"
echo "[kinfit] work  : $WORK_DIR"

set +e
( cd "$WORK_DIR" && Marlin "$(basename "$XML")" ) >"$LOG" 2>&1
STATUS=$?
set -e

# Marlin finalization crashes (exit 134/139) with a valid ROOT output are
# known and accepted for this processor, but only after content validation.
if [[ -s "$OUT_ROOT" ]]; then
  python3 "$REPO_ROOT/scripts/validate_kinfit_root.py" \
    --root "$OUT_ROOT" \
    --out "$VALIDATION_JSON"
  mv "$OUT_ROOT" "$FINAL_ROOT"
  cp "$XML" "$OUT_BASE/kinfit_$TAG.xml"
  echo "[kinfit] output -> $FINAL_ROOT (marlin exit $STATUS)"
  if [[ $STATUS -ne 0 && $STATUS -ne 134 && $STATUS -ne 139 ]]; then
    echo "[kinfit] WARNING: unexpected Marlin exit $STATUS — check $LOG" >&2
    exit "$STATUS"
  fi
  exit 0
fi

echo "[kinfit] FAILED: no output ROOT produced (exit $STATUS). See $LOG" >&2
exit 1

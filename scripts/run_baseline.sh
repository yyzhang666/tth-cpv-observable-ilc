#!/usr/bin/env bash
# One-shot technical baseline for ONE generator chunk: gen inspection ->
# features -> angular template -> XGBoost -> ML observable -> Fisher.
#
# With --max-events this is a smoke test, NOT a physics result.
#
# Usage:
#   bash scripts/run_baseline.sh configs/analysis_ow_lr.yaml --max-events 500
#   bash scripts/run_baseline.sh configs/analysis_ow_lr.yaml            # full chunk 0

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 CONFIG [--max-events N]" >&2
  exit 1
fi

CONFIG="$1"
shift
MAX_EVENTS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-events) MAX_EVENTS="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# derive output dir from config (keep in sync with configs/*.yaml)
OUT_BASE="$(python3 -c "
import sys; sys.path.insert(0, 'src')
from ilc_tth_cpv.io import load_analysis_config
print(load_analysis_config('$CONFIG')['outputs']['base_dir'])
")"
FRAME="$(python3 -c "
import sys; sys.path.insert(0, 'src')
from ilc_tth_cpv.io import load_analysis_config
print(load_analysis_config('$CONFIG')['observable']['default_frame'])
")"
FEATURES="$OUT_BASE/features/features_gen_${FRAME}_chunk0.csv"

echo "== [1/6] inspect generator sample (chunk 0)"
python3 scripts/inspect_generator_event.py --config "$CONFIG" --max-events 2

echo "== [2/6] export gen features (chunk 0, max_events=$MAX_EVENTS)"
python3 scripts/export_features.py --config "$CONFIG" --level gen --chunk 0 --max-events "$MAX_EVENTS"

echo "== [3/6] angular observable template (test split)"
python3 scripts/build_angular_observable.py --config "$CONFIG" \
  --features "$FEATURES" --split test

echo "== [4/6] train XGBoost baseline"
python3 scripts/train_cpv_model.py --config "$CONFIG" --features "$FEATURES"

echo "== [5/6] ML observable template (test split)"
python3 scripts/build_ml_observable.py --config "$CONFIG" \
  --features "$FEATURES" --model "$OUT_BASE/model/cpv_xgboost.json"

echo "== [6/6] Fisher (TECHNICAL placeholder nu0; see KNOWN_ISSUES #5)"
OBS="$(python3 -c "
import sys; sys.path.insert(0, 'src')
from ilc_tth_cpv.io import load_analysis_config
print(load_analysis_config('$CONFIG')['analysis']['observable_family'])
")"
python3 scripts/evaluate_fisher.py \
  --template "$OUT_BASE/angular/$OBS/${OBS}_test_bins.csv" --nu0-from-abs
python3 scripts/evaluate_fisher.py \
  --template "$OUT_BASE/ml_observable/template_test_bins.csv" --nu0-from-abs

echo
if [[ "$MAX_EVENTS" != "0" ]]; then
  echo "NOTE: run used --max-events $MAX_EVENTS — this is a smoke test, not a physics result."
fi
echo "baseline chain complete (generator level, chunk 0). outputs under $OUT_BASE/"
echo "next steps: kinfit stage for reco level (docs/KINFIT_JET_ASSIGNMENT.md),"
echo "            all-chunk processing via HTCondor (condor/README.md)."

#!/usr/bin/env bash
# One-shot baseline for ONE generator chunk: CPV/SM features -> angular
# templates -> XGBoost -> CPV/SM ML templates -> Fisher with real SM nu0.
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
SM_FEATURES="$OUT_BASE/features/features_sm_gen_${FRAME}_chunk0.csv"
LUMI_FB="$(python3 -c "
import sys; sys.path.insert(0, 'src')
from ilc_tth_cpv.io import load_analysis_config
print(1000.0 * float(load_analysis_config('$CONFIG')['fisher']['luminosity_ab']))
")"

echo "== [1/9] inspect generator interference sample (chunk 0)"
python3 scripts/inspect_generator_event.py --config "$CONFIG" --max-events 2

echo "== [2/9] export interference gen features (chunk 0, max_events=$MAX_EVENTS)"
python3 scripts/export_features.py --config "$CONFIG" --level gen --chunk 0 --max-events "$MAX_EVENTS"

echo "== [3/9] export SM gen features (same scope)"
python3 scripts/export_features.py --config "$CONFIG" --level gen --component sm \
  --chunk 0 --max-events "$MAX_EVENTS"

echo "== [4/9] interference angular template (test split)"
python3 scripts/build_angular_observable.py --config "$CONFIG" \
  --features "$FEATURES" --split test

echo "== [5/9] SM angular nu0 template (test split)"
python3 scripts/build_angular_observable.py --config "$CONFIG" \
  --features "$SM_FEATURES" --split test --weight-column weight_sm --output-tag sm

echo "== [6/9] train XGBoost baseline on interference signs"
python3 scripts/train_cpv_model.py --config "$CONFIG" --features "$FEATURES"

echo "== [7/9] interference ML template (test split)"
python3 scripts/build_ml_observable.py --config "$CONFIG" \
  --features "$FEATURES" --model "$OUT_BASE/model/cpv_xgboost.json"

echo "== [8/9] evaluate the same ML score on SM events"
python3 scripts/build_ml_observable.py --config "$CONFIG" \
  --features "$SM_FEATURES" --model "$OUT_BASE/model/cpv_xgboost.json" \
  --weight-column weight_sm --output-tag sm

echo "== [9/9] Fisher with the binned SM nu0 (luminosity=${LUMI_FB} fb^-1)"
OBS="$(python3 -c "
import sys; sys.path.insert(0, 'src')
from ilc_tth_cpv.io import load_analysis_config
print(load_analysis_config('$CONFIG')['analysis']['observable_family'])
")"
python3 scripts/evaluate_fisher.py \
  --template "$OUT_BASE/angular/$OBS/${OBS}_test_bins.csv" \
  --sm-template "$OUT_BASE/angular/$OBS/${OBS}_test_sm_bins.csv" \
  --luminosity-scale "$LUMI_FB"
python3 scripts/evaluate_fisher.py \
  --template "$OUT_BASE/ml_observable/template_test_bins.csv" \
  --sm-template "$OUT_BASE/ml_observable/template_test_sm_bins.csv" \
  --luminosity-scale "$LUMI_FB"

echo
if [[ "$MAX_EVENTS" != "0" ]]; then
  echo "NOTE: run used --max-events $MAX_EVENTS — this is a smoke test, not a physics result."
fi
echo "baseline chain complete (generator level, chunk 0, physical SM nu0). outputs under $OUT_BASE/"
echo "next steps: kinfit stage for reco level (docs/KINFIT_JET_ASSIGNMENT.md),"
echo "            all-chunk processing via HTCondor (condor/README.md)."

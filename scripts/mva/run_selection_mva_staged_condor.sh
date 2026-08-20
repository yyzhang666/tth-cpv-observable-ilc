#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
run_id=${1:-baseline-xgboost-v1}
config=${2:-$repo_root/configs/mva_training.yaml}
workflow_dir=$repo_root/outputs/mva/condor/$run_id
model_dir=$repo_root/outputs/mva/training/$run_id
model=$model_dir/model.json
scores_dir=$repo_root/outputs/mva/scores/$run_id
evaluation=$repo_root/outputs/mva/evaluation/$run_id.json
attempt_id=$(date -u +%Y%m%dT%H%M%SZ)
log_dir=$workflow_dir/staged-$attempt_id
batch_table=$log_dir/apply-batches.txt

mkdir -p "$log_dir" "$scores_dir" "$(dirname "$evaluation")"
exec > >(tee -a "$log_dir/controller.log") 2>&1

say() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

refresh_credentials() {
  if ! klist -s; then
    say "ERROR: no valid Kerberos ticket; run kinit and aklog, then retry"
    return 1
  fi
  kinit -R >/dev/null 2>&1 || true
  aklog
  case ${KRB5CCNAME:-} in
    FILE:*) credential_file=${KRB5CCNAME#FILE:} ;;
    *)
      say "ERROR: KRB5CCNAME is not a FILE credential cache"
      return 1
      ;;
  esac
  condor_store_cred add-krb -i "$credential_file"
  condor_store_cred query-krb
}

submit_and_wait() {
  local stage=$1
  local submit_file=$2
  local event_log=$3
  shift 3
  refresh_credentials
  say "Submitting $stage"
  condor_submit -terse -batch-name "mva-$run_id-$stage" "$@" "$submit_file" | tee "$log_dir/$stage.cluster"
  say "Waiting for $stage; event log: $event_log"
  condor_wait -status "$event_log"
}

cd "$repo_root"

if [[ ! -s $workflow_dir/workflow_manifest.json ]]; then
  say "Preparing immutable job lists for $run_id"
  source env/setup.sh
  python3 scripts/mva/prepare_selection_mva_condor.py --config "$config" --run-id "$run_id"
fi

if [[ ! -s $model ]]; then
  submit_and_wait \
    train \
    "$repo_root/condor/mva/train.sub" \
    "$log_dir/train.condor.log" \
    repo_root="$repo_root" config="$config" run_id="$run_id" log_dir="$log_dir"
  if [[ ! -s $model || ! -s $model_dir/provenance.json ]]; then
    say "ERROR: TRAIN ended without a complete model; inspect $log_dir/train.err"
    exit 1
  fi
else
  say "Reusing complete model: $model"
fi

: > "$batch_table"
for job_list in "$workflow_dir"/job_lists/batch-*.txt; do
  batch_name=$(basename "$job_list" .txt)
  batch_id=${batch_name#batch-}
  printf '%s %s\n' "$batch_id" "$job_list" >> "$batch_table"
done
if [[ ! -s $batch_table ]]; then
  say "ERROR: no apply job lists found under $workflow_dir/job_lists"
  exit 1
fi

read -r expected_jobs expected_batches < <(
  python3 -c 'import json,sys; x=json.load(open(sys.argv[1])); print(x["jobs"], len(x["apply_batches"]))' \
    "$workflow_dir/workflow_manifest.json"
)

submit_and_wait \
  apply \
  "$repo_root/condor/mva/apply_all.sub" \
  "$log_dir/apply.condor.log" \
  repo_root="$repo_root" config="$config" model="$model" scores_dir="$scores_dir" \
  log_dir="$log_dir" batch_table="$batch_table"

score_count=$(find "$scores_dir" -maxdepth 1 -type f -name '*.scores.h5' | wc -l)
completion_count=$(find "$scores_dir" -maxdepth 1 -type f -name 'completion-*.json' | wc -l)
if [[ $score_count -ne $expected_jobs || $completion_count -ne $expected_batches ]]; then
  say "ERROR: APPLY incomplete: scores=$score_count/$expected_jobs completions=$completion_count/$expected_batches"
  exit 1
fi

if [[ ! -s $evaluation ]]; then
  submit_and_wait \
    evaluate \
    "$repo_root/condor/mva/evaluate.sub" \
    "$log_dir/evaluate.condor.log" \
    repo_root="$repo_root" config="$config" model="$model" scores_dir="$scores_dir" \
    evaluation="$evaluation" log_dir="$log_dir"
fi
if [[ ! -s $evaluation ]]; then
  say "ERROR: EVALUATE ended without $evaluation; inspect $log_dir/evaluate.err"
  exit 1
fi

source env/setup.sh
python3 -c 'import json,sys; x=json.load(open(sys.argv[1])); print(json.dumps({"evaluation":sys.argv[1],"threshold":x["threshold"],"threshold_status":x["threshold_status"],"test_auc":x["metrics"]["test"]["auc"],"cpv_events":x["cpv_safety"]["events"]}, indent=2))' "$evaluation"
say "FORMAL WORKFLOW COMPLETE"

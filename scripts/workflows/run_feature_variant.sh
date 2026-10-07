#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DEFAULT_ANALYSIS_ROOT="/data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable"
DEFAULT_CONFIG="${REPO_ROOT}/configs/analysis_ml_superdataset_lr_catboost_v2.yaml"
DEFAULT_CHUNKS="1-79"
DEFAULT_MODEL_TAG="catboost_d7_i1000_lr005_es50"

usage() {
    cat <<'EOF'
Run one v3 signal-only feature/model/Fisher variant.

Usage:
  run_feature_variant.sh \
    --feature-set NAME --run-name NAME --score-column NAME [options]

Required:
  --feature-set NAME     Feature set under features.sets in the YAML config
  --run-name NAME        New output directory name for this variant
  --score-column NAME    Output score column, for example q_CPV_separate_score_v0

Options:
  --config PATH          Analysis YAML (default: repository v2 CatBoost config)
  --analysis-root PATH   Root containing outputs/ (default: current zhangyuy NAF area)
  --chunks SPEC          Baseline chunks passed to both augment jobs (default: 1-79)
  --model-tag NAME       Model subdirectory tag (default: catboost_d7_i1000_lr005_es50)
  --bins N               Fisher bins (default: 20)
  --range LOW HIGH       Fisher histogram range (default: -1 1)
  --no-plot              Do not create Fisher plots
  --dry-run              Print every command; create and write nothing
  -h, --help             Show this help

The wrapper runs, in order: interference augment, SM augment, CatBoost train,
interference score, SM score, and signal-only Fisher. It never runs background
production or q_sel selection and refuses an existing run/Fisher directory.
EOF
}

feature_set=""
run_name=""
score_column=""
config="${DEFAULT_CONFIG}"
analysis_root="${DEFAULT_ANALYSIS_ROOT}"
chunks="${DEFAULT_CHUNKS}"
model_tag="${DEFAULT_MODEL_TAG}"
bins="20"
range_low="-1"
range_high="1"
plot=1
dry_run=0

while (($#)); do
    case "$1" in
        --feature-set)
            [[ $# -ge 2 ]] || { echo "error: --feature-set needs a value" >&2; exit 2; }
            feature_set="$2"; shift 2 ;;
        --run-name)
            [[ $# -ge 2 ]] || { echo "error: --run-name needs a value" >&2; exit 2; }
            run_name="$2"; shift 2 ;;
        --score-column)
            [[ $# -ge 2 ]] || { echo "error: --score-column needs a value" >&2; exit 2; }
            score_column="$2"; shift 2 ;;
        --config)
            [[ $# -ge 2 ]] || { echo "error: --config needs a value" >&2; exit 2; }
            config="$2"; shift 2 ;;
        --analysis-root)
            [[ $# -ge 2 ]] || { echo "error: --analysis-root needs a value" >&2; exit 2; }
            analysis_root="$2"; shift 2 ;;
        --chunks)
            [[ $# -ge 2 ]] || { echo "error: --chunks needs a value" >&2; exit 2; }
            chunks="$2"; shift 2 ;;
        --model-tag)
            [[ $# -ge 2 ]] || { echo "error: --model-tag needs a value" >&2; exit 2; }
            model_tag="$2"; shift 2 ;;
        --bins)
            [[ $# -ge 2 ]] || { echo "error: --bins needs a value" >&2; exit 2; }
            bins="$2"; shift 2 ;;
        --range)
            [[ $# -ge 3 ]] || { echo "error: --range needs LOW and HIGH" >&2; exit 2; }
            range_low="$2"; range_high="$3"; shift 3 ;;
        --no-plot)
            plot=0; shift ;;
        --dry-run)
            dry_run=1; shift ;;
        -h|--help)
            usage; exit 0 ;;
        *)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 2 ;;
    esac
done

[[ -n "${feature_set}" ]] || { echo "error: --feature-set is required" >&2; exit 2; }
[[ -n "${run_name}" ]] || { echo "error: --run-name is required" >&2; exit 2; }
[[ -n "${score_column}" ]] || { echo "error: --score-column is required" >&2; exit 2; }
if [[ "${run_name}" == "." || "${run_name}" == ".." || "${run_name}" == */* ]]; then
    echo "error: --run-name must be one directory name" >&2
    exit 2
fi

config="$(cd "$(dirname "${config}")" 2>/dev/null && pwd)/$(basename "${config}")"
analysis_root="${analysis_root%/}"

baseline_root="${analysis_root}/outputs/ml_superdataset/features_v3_baseline"
interference_pattern="${baseline_root}/interference_reco_lab_raw_chunks1_79_v0_20261003/features_reco_baseline_v3_interference_chunk{chunk}.csv"
sm_pattern="${baseline_root}/sm_reco_lab_raw_chunks1_79_v0_20261003/features_reco_baseline_v3_sm_chunk{chunk}.csv"

run_root="${analysis_root}/outputs/ml_superdataset/feature_trials_v3/${run_name}"
feature_dir="${run_root}/features"
model_root="${run_root}/models"
score_dir="${run_root}/scores"
fisher_dir="${analysis_root}/outputs/event_csv_fisher/${run_name}"

interference_features="${feature_dir}/interference.csv"
sm_features="${feature_dir}/sm.csv"
interference_scores="${score_dir}/interference_test.csv"
sm_scores="${score_dir}/sm_test.csv"

export_script="${REPO_ROOT}/scripts/export_features_v3.py"
train_script="${REPO_ROOT}/scripts/train_cpv_model.py"
score_script="${REPO_ROOT}/scripts/score_feature_table_v3.py"
fisher_script="${REPO_ROOT}/scripts/workflows/run_event_fisher.py"

print_command() {
    printf '  '
    printf '%q ' "$@"
    printf '\n'
}

run_stage() {
    local title="$1"
    shift
    printf '\n== %s ==\n' "${title}"
    print_command "$@"
    if ((dry_run == 0)); then
        "$@"
    fi
}

if ((dry_run == 0)); then
    for required in "${config}" "${export_script}" "${train_script}" "${score_script}" "${fisher_script}"; do
        [[ -f "${required}" ]] || { echo "error: missing required file: ${required}" >&2; exit 1; }
    done
    for component in interference sm; do
        pattern="${interference_pattern}"
        [[ "${component}" == "sm" ]] && pattern="${sm_pattern}"
        for chunk in 1 79; do
            baseline="${pattern/\{chunk\}/${chunk}}"
            [[ -f "${baseline}" ]] || { echo "error: missing representative baseline: ${baseline}" >&2; exit 1; }
        done
    done
    [[ ! -e "${run_root}" ]] || { echo "error: refusing existing run root: ${run_root}" >&2; exit 1; }
    [[ ! -e "${fisher_dir}" ]] || { echo "error: refusing existing Fisher output: ${fisher_dir}" >&2; exit 1; }
fi

printf 'Repository: %s\n' "${REPO_ROOT}"
printf 'Run root:   %s\n' "${run_root}"
printf 'Fisher:     %s\n' "${fisher_dir}"

run_stage "Prepare isolated run directory" mkdir -p "${feature_dir}" "${model_root}" "${score_dir}"
if ((dry_run == 0)); then
    cd "${run_root}"
else
    printf '  cd %q\n' "${run_root}"
fi

run_stage "1/6 augment interference" \
    python3 "${export_script}" augment \
    --config "${config}" --feature-set "${feature_set}" \
    --input-pattern "${interference_pattern}" --chunks "${chunks}" \
    --component interference --compat-policy canonical --output "${interference_features}"

run_stage "2/6 augment SM" \
    python3 "${export_script}" augment \
    --config "${config}" --feature-set "${feature_set}" \
    --input-pattern "${sm_pattern}" --chunks "${chunks}" \
    --component sm --compat-policy canonical --output "${sm_features}"

run_stage "3/6 train electron and muon models" \
    python3 "${train_script}" \
    --config "${config}" --features "${interference_features}" \
    --feature-set "${feature_set}" --version v2 \
    --out-dir "${model_root}" --tag "${model_tag}"

run_stage "4/6 score interference test rows" \
    python3 "${score_script}" score \
    --input "${interference_features}" --component interference \
    --model-root "${model_root}" --model-tag "${model_tag}" \
    --score-column "${score_column}" --output "${interference_scores}"

run_stage "5/6 score SM test rows" \
    python3 "${score_script}" score \
    --input "${sm_features}" --component sm \
    --model-root "${model_root}" --model-tag "${model_tag}" \
    --score-column "${score_column}" --output "${sm_scores}"

fisher_command=(
    python3 "${fisher_script}"
    --signal-only
    --ml-score-column "${score_column}"
    --sm-csv "${sm_scores}"
    --cpv-csv "${interference_scores}"
    --bins "${bins}"
    --range "${range_low}" "${range_high}"
    --output-dir "${fisher_dir}"
)
((plot == 0)) || fisher_command+=(--plot)
run_stage "6/6 signal-only Fisher" "${fisher_command[@]}"

printf '\nComplete.\n'
printf 'Features/models/scores: %s\n' "${run_root}"
printf 'Fisher outputs:         %s\n' "${fisher_dir}"

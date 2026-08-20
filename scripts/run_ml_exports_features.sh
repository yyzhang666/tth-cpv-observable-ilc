#!/usr/bin/env bash
set -euo pipefail

# Parse inputs
ML_MODEL="${1:-}"
VERSION="${2:-}"

# Validate ML model argument
if [[ "$ML_MODEL" != "xgboost" && "$ML_MODEL" != "catboost" ]]; then
    echo "Error: You must specify a valid ML model ('xgboost' or 'catboost')."
    echo "Usage: $0 <xgboost|catboost> [v2|\"\"]"
    exit 1
fi

# Validate version argument
if [[ "$VERSION" != "v2" && "$VERSION" != "" ]]; then
    echo "Error: Version must be either 'v2' or empty '\"\"'."
    echo "Usage: $0 <xgboost|catboost> [v2|\"\"]"
    exit 1
fi

CONFIG="../../configs/analysis_ml_superdataset_lr${VERSION}.yaml"
CHUNKS="1-79"

# Array of job tuples: "component level"
JOBS=(
    "interference gen"  # Input 1: CPV gen-level
    "sm gen"            # Input 2: SM gen-level
    "interference reco" # Input 3: CPV reco-level
    "sm reco"           # Input 4: SM reco-level
)

echo "=================================================="
echo " Starting HTCondor Submissions"
echo " ML Model: ${ML_MODEL}"
echo " Version:  ${VERSION:-'(default)'}"
echo " Config:   ${CONFIG}"
echo " Chunks:   ${CHUNKS}"
echo "=================================================="

for JOB in "${JOBS[@]}"; do
    read -r COMPONENT LEVEL <<< "$JOB"
    
    echo ""
    echo "--> Preparing: Component=${COMPONENT} | Level=${LEVEL}"
    
    # Build python command arguments array
    CMD_ARGS=(
        python3 make_arguments${VERSION}.py
        --config "${CONFIG}"
        --chunks "${CHUNKS}"
        --component "${COMPONENT}"
        --level "${LEVEL}"
        --MLmodel "${ML_MODEL}"
    )

    # Conditionally attach version flag if provided
    if [[ -n "$VERSION" ]]; then
        CMD_ARGS+=(--version "${VERSION}")
    fi

    "${CMD_ARGS[@]}"
        
    echo "--> Submitting to HTCondor..."
    condor_submit submit_export_features.sub
done

echo ""
echo "=================================================="
echo " All 4 feature export jobs submitted successfully!"
echo "=================================================="
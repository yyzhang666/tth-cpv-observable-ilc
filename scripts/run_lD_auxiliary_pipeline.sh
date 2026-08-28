#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-minimal}"
FRAME="${2:-higgs_rest}"
TAG="${3:-}"

case "${MODE}" in
    minimal|minimal_2|minimal_w2|minimal_nufit|full|wbjets|wbjets_lepton)
        ;;
    *)
        echo "Error: Invalid mode '${MODE}'. Must be one of: minimal, minimal_2, minimal_w2, minimal_nufit, full, wbjets, wbjets_lepton."
        exit 1
        ;;
esac

if [[ "${FRAME}" == "higgs_rest" ]]; then
    FRAME_SUFFIX=""
else
    FRAME_SUFFIX="_${FRAME}"
fi

CONFIG="configs/analysis_ml_superdataset_lr_catboost_v2${FRAME_SUFFIX}.yaml"
FEAT_DIR="outputs/ml_superdataset/features_v2"
MODEL_BASE="outputs/ml_superdataset/model_v2${FRAME_SUFFIX}"
OBS_BASE="outputs/ml_superdataset/ml_observable_v2${FRAME_SUFFIX}"

if [[ "${MODE}" == "wbjets" ]]; then
    MODEL_DIR="${MODEL_BASE}/lD_auxiliary_wbjets/catboost"
    TARGET_OUT="${OBS_BASE}/lD_auxiliary_wbjets/catboost"
elif [[ "${MODE}" == "wbjets_lepton" ]]; then
    MODEL_DIR="${MODEL_BASE}/lD_auxiliary_wbjets_lepton/catboost"
    TARGET_OUT="${OBS_BASE}/lD_auxiliary_wbjets_lepton/catboost"
else
    MODEL_DIR="${MODEL_BASE}/lD_auxiliary/${MODE}/catboost"
    TARGET_OUT="${OBS_BASE}/lD_auxiliary/${MODE}/catboost"
fi

# Append tag to target output directory and model path if provided
if [[ -n "${TAG}" ]]; then
    TARGET_OUT="${TARGET_OUT}/${TAG}"
    MODEL_TAG_SUFFIX="/${TAG}"
else
    MODEL_TAG_SUFFIX=""
fi

TAG_DISPLAY="${TAG:-none}"
echo "=== Running template generation in '${MODE}' mode (${FRAME} frame, tag: '${TAG_DISPLAY}') ==="

for process in sm cpv; do
    if [[ "${process}" == "sm" ]]; then
        FEAT_FILE="${FEAT_DIR}/reco_sm/features_sm_reco_${FRAME}_chunk1_79.csv"
    else
        FEAT_FILE="${FEAT_DIR}/reco_cpv/features_reco_${FRAME}_chunk1_79.csv"
    fi

    for flavor in electron muon; do
        MODEL_FILE="${MODEL_DIR}/${flavor}${MODEL_TAG_SUFFIX}/cpv_catboost.cbm"

        if [[ ! -f "${MODEL_FILE}" ]]; then
            echo "Error: Model file not found at '${MODEL_FILE}'"
            exit 1
        fi

        python3 scripts/build_ml_observable.py \
            --config "${CONFIG}" \
            --features "${FEAT_FILE}" \
            --model "${MODEL_FILE}" \
            --lepton-flavor "${flavor}" \
            --output-tag "reco_${process}" \
            --out-dir "${TARGET_OUT}" \
            --version v2
    done
done

echo "=== Running Fisher evaluation in '${MODE}' mode (${FRAME} frame, tag: '${TAG_DISPLAY}') ==="

for flavor in electron muon; do
    python3 scripts/evaluate_fisher.py \
        --template "${TARGET_OUT}/template_test_${flavor}_reco_cpv_bins.csv" \
        --sm-template "${TARGET_OUT}/template_test_${flavor}_reco_sm_bins.csv" \
        --luminosity-scale 8000
done

echo "Done! All tasks completed for '${MODE}' mode (${FRAME} frame, tag: '${TAG_DISPLAY}')."
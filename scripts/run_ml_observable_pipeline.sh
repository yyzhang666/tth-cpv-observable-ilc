#!/usr/bin/env bash
set -euo pipefail

# Level choice: reco or gen (defaults to reco)
LEVEL="${1:-reco}"

echo "=================================================================="
echo "=== Running Full ML Observables & Fisher Pipeline ==="
echo "=== Level: ${LEVEL} ==="
echo "=================================================================="

# ----------------------------------------------------------------------
# STAGE 1: Build ML Observable Templates (CPV & SM)
# ----------------------------------------------------------------------
echo ""
echo "=================================================================="
echo " STAGE 1: Building ML Observable Templates"
echo "=================================================================="

for TAG in cpv sm; do
  MODE="${LEVEL}_${TAG}"
  
  if [ "${TAG}" = "sm" ]; then
    FEATURE_TAG="sm_"
  else
    FEATURE_TAG=""
  fi

  for MODEL_TYPE in xgboost catboost; do
    for VERSION in v2 v1 v0; do
      for LEPTON in electron muon; do

        echo "--------------------------------------------------"
        echo "--> Building Template | Mode: ${MODE} | Model: ${MODEL_TYPE} | Version: ${VERSION} | Lepton: ${LEPTON}"

        # 1. Map feature directory (v2 uses features_v2, v1 & v0 use features)
        if [ "${VERSION}" = "v2" ]; then
          FEATURES_DIR="features_v2"
        else
          FEATURES_DIR="features"
        fi

        # 2. Map model directory & config naming
        if [ "${VERSION}" = "v1" ]; then
          MODEL_DIR="model"
          CFG_TAG=""
        else
          MODEL_DIR="model_${VERSION}"
          CFG_TAG="_${VERSION}"
        fi

        # 3. Construct specific config and model file paths
        if [ "${MODEL_TYPE}" = "xgboost" ]; then
          CONFIG="configs/analysis_ml_superdataset_lr${CFG_TAG}.yaml"
          MODEL="outputs/ml_superdataset/${MODEL_DIR}/lD/xgboost/${LEPTON}/cpv_xgboost.json"
        else
          CONFIG="configs/analysis_ml_superdataset_lr_catboost${CFG_TAG}.yaml"
          MODEL="outputs/ml_superdataset/${MODEL_DIR}/lD/catboost/${LEPTON}/cpv_catboost.cbm"
        fi

        FEATURES="outputs/ml_superdataset/${FEATURES_DIR}/${MODE}/features_${FEATURE_TAG}${LEVEL}_higgs_rest_chunk1_79.csv"

        python3 scripts/build_ml_observable.py \
          --config "${CONFIG}" \
          --features "${FEATURES}" \
          --model "${MODEL}" \
          --lepton-flavor "${LEPTON}" \
          --version "${VERSION}" \
          --output-tag "${MODE}"

      done
    done
  done
done

# ----------------------------------------------------------------------
# STAGE 2: Evaluate Fisher Information
# ----------------------------------------------------------------------
echo ""
echo "=================================================================="
echo " STAGE 2: Evaluating Fisher Information"
echo "=================================================================="

for MODEL_TYPE in xgboost catboost; do
  for VERSION in v2 v1 v0; do
    for LEPTON in electron muon; do

      # Map version output folder name
      if [ "${VERSION}" = "v2" ]; then
        OBS_FOLDER="ml_observable_v2"
      elif [ "${VERSION}" = "v0" ]; then
        OBS_FOLDER="ml_observable_v0"
      else
        OBS_FOLDER="ml_observable"
      fi

      OBS_DIR="outputs/ml_superdataset/${OBS_FOLDER}/${MODEL_TYPE}"
      CPV_TEMPLATE="${OBS_DIR}/template_test_${LEPTON}_${LEVEL}_cpv_bins.csv"
      SM_TEMPLATE="${OBS_DIR}/template_test_${LEPTON}_${LEVEL}_sm_bins.csv"

      echo "--------------------------------------------------"
      echo "--> Fisher Eval | Model: ${MODEL_TYPE} | Version: ${VERSION} | Lepton: ${LEPTON}"

      python3 scripts/evaluate_fisher.py \
        --template "${CPV_TEMPLATE}" \
        --sm-template "${SM_TEMPLATE}" \
        --luminosity-scale 8000

    done
  done
done

echo ""
echo "=================================================================="
echo "=== All Pipeline Steps Completed Successfully for Level: ${LEVEL} ==="
echo "=================================================================="
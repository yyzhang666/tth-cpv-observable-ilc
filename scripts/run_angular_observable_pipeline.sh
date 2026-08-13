#!/bin/bash
set -e   # stop immediately if any command fails, rather than continuing silently

# Default configuration
FRAME="${1:-higgs_rest}"  # Pass frame as argument (e.g., ./run_pipeline.sh lab), defaults to higgs_rest
CHUNK_START="${2:-0}"
CHUNK_END="${3:-0}"

# Determine directory suffix based on frame
if [ "$FRAME" = "higgs_rest" ]; then
  FEATURES_DIR="outputs/angular_lr/features"
  CONFIG="configs/analysis_angular_lr.yaml"
  OBS_BASE_DIR="outputs/angular_lr/angular"
else
  FEATURES_DIR="outputs/angular_lr_${FRAME}/features"
  CONFIG="configs/analysis_angular_lr_${FRAME}.yaml"
  OBS_BASE_DIR="outputs/angular_lr_${FRAME}/angular"
fi

for CHUNK in $(seq $CHUNK_START $CHUNK_END); do
  echo " Running Pipeline for Frame: $FRAME, Chunk: $CHUNK"
  echo " Features Directory: $FEATURES_DIR"

  # export_features.py 
  echo "--> Exporting feature CSVs..."

  python3 scripts/export_features.py --config $CONFIG --level gen --chunk $CHUNK
  python3 scripts/export_features.py --config $CONFIG --level gen --component sm --chunk $CHUNK
  python3 scripts/export_features.py --config $CONFIG --level reco --chunk $CHUNK
  python3 scripts/export_features.py --config $CONFIG --level reco --component sm --chunk $CHUNK

  # build_angular_observable.py, all 16 combinations
  echo "--> Building angular observables..."

  for observable in O_W O_lD; do
    for level in gen reco; do
      for lepton in electron muon all; do

        # Set tag names based on lepton selection
        if [ "$lepton" = "all" ]; then
          cpv_tag="${level}_chunk${CHUNK}"
          sm_tag="sm_${level}_chunk${CHUNK}"
        else
          cpv_tag="${level}_${lepton}_chunk${CHUNK}"
          sm_tag="sm_${level}_${lepton}_chunk${CHUNK}"
        fi

        # CPV
        python3 scripts/build_angular_observable.py \
          --config $CONFIG \
          --features $FEATURES_DIR/features_${level}_${FRAME}_chunk${CHUNK}.csv \
          --observable $observable \
          --split all \
          --lepton-flavor $lepton \
          --output-tag "$cpv_tag"

        # SM
        python3 scripts/build_angular_observable.py \
          --config $CONFIG \
          --features $FEATURES_DIR/features_sm_${level}_${FRAME}_chunk${CHUNK}.csv \
          --observable $observable \
          --split all \
          --weight-column weight_sm \
          --lepton-flavor $lepton \
          --output-tag "$sm_tag"

      done
    done
  done

  # Evaluate Fisher Information
  echo "--> Calculating Fisher Information..."

  for observable in O_W O_lD; do
    for level in gen reco; do
      for lepton in electron muon; do

        OBS_DIR="${OBS_BASE_DIR}/${observable}"
        TEMPLATE="${OBS_DIR}/${observable}_all_${level}_${lepton}_chunk${CHUNK}_bins.csv"
        SM_TEMPLATE="${OBS_DIR}/${observable}_all_sm_${level}_${lepton}_chunk${CHUNK}_bins.csv"

        echo "Evaluating Fisher Info: ${observable} | ${level} | ${lepton} | chunk ${CHUNK}"

        python3 scripts/evaluate_fisher.py \
          --template "$TEMPLATE" \
          --sm-template "$SM_TEMPLATE" \
          --luminosity-scale 8000

      done
    done
  done
done

echo "All chunks complete."
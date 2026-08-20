# Semileptonic ttH selection-MVA baseline v1

The frozen inputs are the 1,150 jobs listed in
`outputs/mva/weights/mva_semilep_physical_weights.json`. Never discover
training inputs by globbing `outputs/mva/datasets/export_test`: that directory
also contains smoke files.

## Physics contract

- Signal: `tth-sm` rows with `analysis_category=tth-hbb`.
- Background: `tth-nonbb`, ttZ, ttbb, 6q and 4f2l.
- CPV ttH is inference-only and never enters fitting or threshold selection.
- The model is a common-helicity XGBoost classifier. Polarization is retained
  for metrics but is not a feature.
- The 25 features and their order are frozen in `configs/mva_training.yaml`.
  The three opening-angle variables are excluded from baseline v1.
- `weight_train` balances binary class and helicity using train-split counts.
  It is unrelated to `weight_phys`.
- `weight_phys` is used only for yields and the validation-only threshold scan.
  Hbb and non-Hbb share the inclusive ttH production normalization.
- Scores are external immutable shards; frozen input HDF5 files are read-only.

## Direct smoke

Regenerate provenance only after its source/configuration changes. The full
normalization inventory performs source hashes and all-row CPV checks and is
intentionally expensive; do not rerun it before every model fit:

```bash
source env/setup.sh
python3 scripts/mva/assign_mva_splits.py --config configs/mva_semilep.yaml
python3 scripts/mva/build_physical_normalization_inventory.py
python3 scripts/mva/prepare_mva_weights.py
```

Then run a bounded model smoke:

```bash
python3 scripts/mva/train_selection_mva.py --smoke
python3 scripts/mva/apply_selection.py \
  --model outputs/mva/training/baseline-xgboost-v1-smoke/model.json \
  --output-dir outputs/mva/scores/baseline-xgboost-v1-smoke \
  --include-cpv --smoke
python3 scripts/mva/evaluate_selection.py \
  --model outputs/mva/training/baseline-xgboost-v1-smoke/model.json \
  --scores-dir outputs/mva/scores/baseline-xgboost-v1-smoke \
  --output outputs/mva/evaluation/baseline-xgboost-v1-smoke.json \
  --smoke
```

Smoke models carry `formal_use_allowed=false`. Signed CPV requests fail with
`CPV_EVENT_SIGN_JOIN_UNAVAILABLE` until the sidecar sign is joined to the
exported event order and validated separately.

## Full Condor workflow

The login node is too small for the approximately 3.12M train and 0.67M
validation rows. Prepare, inspect and submit one DAG:

```bash
source env/setup.sh
python3 scripts/mva/prepare_selection_mva_condor.py \
  --run-id baseline-xgboost-v1
condor_submit_dag outputs/mva/condor/baseline-xgboost-v1/workflow.dag
```

The DAG runs one 8-CPU/32-GB training job, disjoint 20-source-job application
batches, and evaluation only after every application batch succeeds. Outputs
are run-ID unique and refuse overwrite.

## Interpretation boundary

The nominal threshold maximizes validation `S/sqrt(S+B)` using positive
physical weights. It is recorded as
`provisional_incomplete_validation_normalization_coverage`; test data never
retune it. A later split-v2 or out-of-fold study is required before promoting
the threshold to the CP measurement.

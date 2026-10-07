# Observable workflow for ILC ttH CP studies

This branch is the maintained workflow for reconstructing, extending, training,
and diagnosing CP observables from stable event tables. The archived Nana copy
is a read-only reference; new observable work belongs here.

## Run one feature variant

On the zhangyuy NAF account:

```bash
source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh
cd /data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/worktrees/tth-cpv-observable-ilc-ozakinan-repro-20260907

bash scripts/workflows/run_feature_variant.sh \
  --feature-set lD_auxiliary_wbjets_lepton_separate_score \
  --run-name separate_score_wrapper_v1_20261007 \
  --score-column q_CPV_separate_score_v0
```

The wrapper executes one fixed five-stage signal-only chain:

```text
1. read the existing 148-column reco baselines
2. augment interference + SM feature tables
3. train electron + muon CatBoost models
4. score interference + SM test rows
5. histogram the score and calculate signal-only Fisher information
```

Outputs appear at:

```text
outputs/ml_superdataset/feature_trials_v3/<run-name>/
  features/    models/    scores/
outputs/event_csv_fisher/<run-name>/
```

Use `--dry-run` to inspect every command without writing anything and
`--help` for the small set of path/binning overrides. A real run refuses an
existing run or Fisher directory, so choose a new `--run-name` for every trial.

**NECESSITY:** the wrapper supplies one canonical command chain so manual
stage names, paths, feature sets, model tags, score columns, and Fisher inputs
cannot drift between trials.

## Architecture and sources of truth

The workflow deliberately separates expensive reconstruction primitives from
cheap, repeatable feature experiments:

1. `scripts/export_features_v3.py baseline` creates the stable **148-column
   reco lab-frame baseline** from the selected kinfit candidate. This is the
   expensive 79-chunk product.
2. `src/ilc_tth_cpv/input_features.py` is the lazy, direct-first registry. A
   finite materialized CSV column wins; otherwise the requested feature alone
   is derived from baseline primitives and cached only for that event.
3. `features.sets` in
   `configs/analysis_ml_superdataset_lr_catboost_v2.yaml` gives each model its
   ordered objects and auxiliary columns.
4. `scripts/export_features_v3.py augment` materializes only that feature set;
   `scripts/train_cpv_model.py` trains it; and
   `scripts/score_feature_table_v3.py` applies the electron/muon models.
5. `scripts/workflows/run_event_fisher.py` builds score/angle templates and
   evaluates signal-only or explicit background-plus-selection Fisher results.

Augment and score stages write a matching `.meta.json`; trained flavour models
write `model_metadata.json`; Fisher writes binned CSV/JSON summaries and,
with `--plot`, PNG figures. Treat those metadata files as part of each result.

**NECESSITY:** making this v3 baseline/registry contract the branch landing
page prevents future feature studies from falling back to duplicate parsing or
unnecessary reconstruction exports.

## What each stage consumes

The baseline already contains deterministic `train`, `validation`, and `test`
labels. Training uses `weight_training` (absolute interference magnitude,
with class balancing only inside the trainer). Scoring keeps only test rows.
For signal tables it preserves or derives

```text
weight_8ab = weight_template * 8000 / (79 * 0.2).
```

The SM template supplies the positive denominator `S0`; signed interference
weights supply `S1`. Signal-only Fisher is evaluated independently for the
electron and muon templates and then added:

```text
I_flavour = sum_bins S1_i^2 / S0_i
I_combined = I_electron + I_muon
sigma_c = 1 / sqrt(I_combined)
c95 = 1.96 * sigma_c
```

The wrapper intentionally does **not** produce or select background and does
not apply `q_sel`.

For a prepared background event CSV, run the established entry point manually
without `--signal-only`:

```bash
python3 scripts/workflows/run_event_fisher.py \
  --ml-score-column q_CPV_MODEL \
  --background-csv /PATH/background.csv \
  --sm-csv /PATH/sm_test.csv \
  --cpv-csv /PATH/interference_test.csv \
  --q-sel-threshold 0.954 \
  --background-q-sel-floor 0.954 \
  --bins 20 --range -1 1 \
  --output-dir /NEW/PATH/fisher_with_background \
  --plot
```

That mode applies strict `q_sel > threshold` event by event and uses
`S0 + B` as the denominator.

## Adding an input feature

Choose exactly one case before changing code.

### A. The column is already in the baseline

Add it to the desired YAML feature set under `objects` or `auxiliary`, then run
the wrapper with a new name. No Python change and no baseline export are needed.

YAML list items require a space:

```yaml
objects:
  lepton:
    - E
    - pt
```

`-E` is a scalar string, not the list item `E`.

### B. The value can be derived from baseline primitives

Add one focused calculator/registry route in
`src/ilc_tth_cpv/input_features.py`, add focused tests, then name the feature in
the YAML set. Run `augment` (normally through the wrapper); do **not** rerun all
79 reconstruction chunks.

For a new four-vector object:

1. Add its name to `CANONICAL_OBJECTS`.
2. Define its event-level assignment in `FeatureContext._canonical_p4` from
   existing baseline p4/indices.
3. Reuse `OBJECT_VARIABLES`; `_object_kinematics` performs the established
   Higgs-rest conversion for `E`, `pt`, `theta`, `phi`, `mass`, and `valid`.
4. Test both lepton-charge branches, invalid/zero charge, direct-first behavior,
   and the exact requested values.

For example, `lnu_fermion`/`lnu_antifermion` could map the existing lepton and
neutrino p4 according to lepton charge, analogous to the established
top/anti-top-side assignment. That example is not implemented merely by naming
it in YAML: freeze the charge mapping, register both objects, and test both
signs first.

### C. A required primitive is absent

If the baseline lacks the necessary collection, object index, raw p4, score,
or selection state—or if the reconstruction/selected-candidate contract must
change—update the baseline schema and exporter, smoke-test one small chunk,
then regenerate the affected baseline chunks before augmentation. Do not hide
a reconstruction-contract change inside a derived feature calculator.

## Focused validation checklist

Before a long variant run:

1. `python3 scripts/export_features_v3.py augment --help` and confirm the YAML
   feature-set name expands to the intended ordered columns.
2. Run the relevant `tests/test_input_features_v3.py` tests, including both
   lepton-charge branches for charge-mapped objects.
3. Run the wrapper with `--dry-run`; verify two augment commands, one training
   command, two score commands, and one `--signal-only` Fisher command.
4. Use a new run name and confirm baseline chunk 1 and 79 files exist for both
   interference and SM before the real run.
5. Inspect the two model metadata files, scored-table metadata, dropped
   non-finite counts, and per-flavour Fisher summary before comparing models.

## Repository map

```text
configs/analysis_ml_superdataset_lr_catboost_v2.yaml  ordered feature sets/model settings
src/ilc_tth_cpv/input_features.py                    lazy feature registry
src/ilc_tth_cpv/reco_baseline.py                     fixed reco baseline contract
src/ilc_tth_cpv/feature_table.py                     v3 augmentation
src/ilc_tth_cpv/model_scoring.py                     test-row model application
src/ilc_tth_cpv/event_workflow.py                    selection/templates/Fisher mechanics
scripts/export_features_v3.py                        baseline + augment CLI
scripts/train_cpv_model.py                            training CLI
scripts/score_feature_table_v3.py                     scoring CLI
scripts/workflows/run_feature_variant.sh              complete signal-only variant
scripts/workflows/run_event_fisher.py                 Fisher CLI
tests/                                                 focused regression tests
outputs/                                               untracked analysis products
```

For scientific context and frozen interfaces, see
[PROJECT_NOTE_FULL](docs/PROJECT_NOTE_FULL.md),
[observable research workflow](docs/OBSERVABLE_RESEARCH_WORKFLOW.md),
[data schema](docs/DATA_SCHEMA.md),
[MVA interface](docs/MVA_INTERFACE.md), and
[background interface](docs/BACKGROUND_INTERFACE.md). Historical production
details belong in those documents, not on this workflow landing page.

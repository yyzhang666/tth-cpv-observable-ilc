# Signal-only Fisher integration — 2026-10-07

## Contract and outcome

Integrate signal-only Fisher evaluation into the established
`scripts/workflows/run_event_fisher.py` workflow through `--signal-only`.
Signal-only mode reads only SM and CPV event CSVs, applies no `q_sel` selection,
uses `weight_8ab` directly, and computes per-flavour and combined Fisher values.
The existing background plus strict-`q_sel` workflow remains backward-compatible.
The separate signal-only entry point was removed to avoid divergent implementations.

## Changed files

- Modified `src/ilc_tth_cpv/event_workflow.py`.
- Modified `tests/test_event_csv_fisher_cli.py`.
- Deleted `scripts/workflows/run_event_fisher_signal_only.py`.

No configuration file was modified. No commit or push was performed.

## Focused validation

Environment: `source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh`.

Command:

```bash
python3 -m pytest -q tests/test_event_csv_fisher_cli.py
```

Result: `7 passed`.

The focused tests cover signal-only operation without background or `q_sel`,
and the unchanged background plus strict-`q_sel` path.

## Real-input parity

Command:

```bash
python3 scripts/workflows/run_event_fisher.py \
  --signal-only \
  --ml-score-column q_CPV_wtype_v0 \
  --sm-csv /data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/outputs/ml_superdataset/scores_v3_wtype_v0/signal_test_v0_20261006/sm_test.csv \
  --cpv-csv /data/dust/user/zhangyuy/analysis/tth/yuyang_tth_observable/outputs/ml_superdataset/scores_v3_wtype_v0/signal_test_v0_20261006/interference_test.csv \
  --bins 20 \
  --range -1 1 \
  --output-dir /tmp/tth_signal_only_integrated_20261007_sol \
  --plot
```

Observed values:

- electron Fisher: `6.44654146083`
- muon Fisher: `6.74931404842`
- combined signal-only Fisher: `13.1958555092`
- `sigma_c`: `0.275284161063`
- `c95`: `0.539556955683`

## Known doubts

- The pre-existing user modification in
  `configs/analysis_ml_superdataset_lr_catboost_v2.yaml` contains trailing
  whitespace, so an unrestricted whole-worktree `git diff --check` reports it.
  The files changed by this task pass targeted `git diff --check`.

## Optional review directions

None.

## Feature-variant wrapper and branch README — 2026-10-07

### Outcome

- Added `scripts/workflows/run_feature_variant.sh`, a single signal-only chain
  for two v3 augmentations, one electron/muon training job, two test-row scoring
  jobs, and integrated Fisher evaluation.
- Replaced the root `README.md` with a beginner-first `observable_workflow`
  guide covering the v3 baseline/registry architecture, a copy-paste
  separate-score run, signal/background Fisher entry points, and the three
  supported feature-extension cases.
- The wrapper derives its repository root from its own location, defaults to
  the current zhangyuy analysis/baseline layout, writes each trial below a new
  run name, and leaves the archived Nana copy as a read-only reference.
- No production, augmentation, training, scoring, or Fisher job was launched.

### Validation evidence

- `bash -n scripts/workflows/run_feature_variant.sh`: passed.
- `bash scripts/workflows/run_feature_variant.sh --help`: passed.
- A `--dry-run` for feature set
  `lD_auxiliary_wbjets_lepton_separate_score` printed two component-specific
  augment commands, one training command, two component-specific scoring
  commands, and one `run_event_fisher.py --signal-only` command.
- The dry-run dummy run and Fisher output directories did not exist before or
  after the check.
- Targeted `git diff --check` for the wrapper, root README, and this task
  record: passed.

### Necessity

- Wrapper: **NECESSITY:** one canonical command chain prevents manual
  stage/path drift.
- Existing-output refusal: **NECESSITY:** refusing existing run and Fisher
  directories prevents corruption or overwrite of active/previous results.
- README replacement: **NECESSITY:** the branch landing page must state the v3
  baseline/registry extension contract instead of the superseded generic
  student-project overview.

### Known doubts

- The wrapper was syntax/help/dry-run validated only; no long model variant was
  run as part of this documentation/workflow change.

### Optional review directions

None.

### Output-layout correction

- Primary inspection found that the established interactive `run_variant`
  function already writes below
  `outputs/ml_superdataset/feature_trials_v3/<run-name>`, while the first
  wrapper draft used `feature_variants_v3`.
- The wrapper and README were corrected to retain the established
  `feature_trials_v3` layout; no active output was moved or modified.
- After correction, `bash -n`, `--help`, a fresh separate-score `--dry-run`
  with before/after no-directory checks, command-sequence checks, and targeted
  `git diff --check` all passed.

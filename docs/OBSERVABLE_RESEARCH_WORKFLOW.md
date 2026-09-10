# Observable research workflow

## Scope and frozen physics contract

The maintained event-CSV path covers reconstructed semileptonic `eLpR`
events at 550 GeV and 8 ab-1.  The v0 tables contain background, SM-test, and
CPV-test events.  Selection is applied to every event with the strict
expression `q_sel > threshold` (default `0.954`).  `weight_8ab` is already an
expected 8 ab-1 yield: SM and background weights must be nonnegative, whereas
the CPV table retains both signs and supplies the interference derivative.

For each lepton flavor and bin the Fisher contribution is

```
I_bin = S1_bin**2 / (S0_bin + B_bin)
```

Electron and muon templates are never mixed before this calculation.  The
reported combined value is `I_electron + I_muon`.  Because the bundled tables
are `eLpR` only, this is not an LR+RL polarization combination.

## Environment and discoverability

On NAF:

```bash
source /data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh
python3 scripts/workflows/run_event_fisher.py --list-observables
```

The registered angles are calculated from CSV fields by
`src/ilc_tth_cpv/csv_observables.py`; no script should duplicate their wrapping
or charge-ordering rules.  Model aliases and the versioned data schema are in
`configs/workflows/observable_research_v1.yaml`.

## One-dimensional Fisher runs

Angle example:

```bash
python3 scripts/workflows/run_event_fisher.py \
  --angle O_lnu --bins 20 --q-sel-threshold 0.954 --plot \
  --output-dir outputs/event_csv_fisher/O_lnu_20bins_qsel_gt_0p954
```

Current ML-score example:

```bash
python3 scripts/workflows/run_event_fisher.py \
  --ml-model wbjets_lepton_v0 --bins 64 --q-sel-threshold 0.954 --plot \
  --output-dir outputs/event_csv_fisher/wbjets_lepton_v0_64bins_qsel_gt_0p954
```

Use all three path overrides together for a new versioned dataset:

```bash
python3 scripts/workflows/run_event_fisher.py \
  --background-csv /path/background.csv \
  --sm-csv /path/sm.csv --cpv-csv /path/cpv.csv \
  --angle O_lD --bins 36 --q-sel-threshold 0.954 --plot \
  --output-dir outputs/event_csv_fisher/O_lD_new_dataset
```

The background v0 CSV only covers `q_sel >= 0.954`; requesting a lower
threshold fails unless a background CSV with that coverage is supplied and
its floor is passed explicitly.  Each output directory contains the exact bin
table, summary, input/output SHA256 values, event accounting, runtime, and Git
state.  A non-finite observable removes only that event from that observable;
it does not create a file-level veto.

## CP-aware three-class observable

The three targets are always `CPV- / neutral / CPV+`.  The two controlled
schemes differ only in the neutral training population:

- `--neutral-class sm`: SM is neutral; background is retained for test scoring
  and Fisher but has `training_include=0`.
- `--neutral-class sm-plus-background`: SM and background share target 0 and
  both participate in training.  Their separate `source_role` values survive
  so the Fisher denominator still uses distinct S0 and B templates.

Prepare either scheme from three normalized event tables:

```bash
python3 scripts/workflows/prepare_multiclass_dataset.py \
  --background-csv /path/full_background.csv \
  --sm-csv /path/full_sm.csv --cpv-csv /path/full_cpv.csv \
  --neutral-class sm \
  --analysis-config configs/analysis_ml_superdataset_lr_catboost_v2.yaml \
  --feature-set lD_auxiliary_wbjets_lepton \
  --q-sel-threshold 0.954 \
  --test-weights-already-8ab \
  --output outputs/threeclass/sm/events.csv
```

For the second scheme, run the same command with
`--neutral-class sm-plus-background` and write to (for example)
`outputs/threeclass/sm_plus_background/events.csv`.  Keep every other option,
input, feature, seed, and test event identical for a controlled comparison.
The builder preserves authoritative splits or hashes `split_group`/job/chunk;
it never splits individual rows independently.  It uses absolute CPV template
weights and nonnegative SM/background template weights for training, while
the signed CPV `template_weight` remains untouched.

`--test-weights-already-8ab` is an explicit assertion that every role/flavor
test subset already represents 8 ab-1; it is not inferred from the column
name.  If the input weights instead represent all splits together, replace
that flag with six explicit factors, for example
`--test-weight-scale sm:electron=6.67`, repeated for background/SM/CPV and
electron/muon.  The builder preserves both `source_template_weight` and the
factor, and the trainer refuses an unrecorded projection.  This prevents a
15% held-out split from being reported as the full 8 ab-1 exposure.

Train and score both lepton channels:

```bash
python3 scripts/workflows/train_threeclass_model.py \
  --dataset outputs/threeclass/sm/events.csv \
  --out-dir outputs/threeclass/sm/model --plot
```

The trainer equalizes total train weight among the three target classes within
each lepton flavor, without changing the SM:background mixture inside neutral.
It writes `scores/{background,sm,cpv}_scores.csv`; the observable is
`q_threeclass = p_plus - p_minus`.  Evaluate it with the unchanged Fisher
workflow:

```bash
python3 scripts/workflows/run_event_fisher.py \
  --background-csv outputs/threeclass/sm/model/scores/background_scores.csv \
  --sm-csv outputs/threeclass/sm/model/scores/sm_scores.csv \
  --cpv-csv outputs/threeclass/sm/model/scores/cpv_scores.csv \
  --ml-score-column q_threeclass --bins 20 --range -1 1 \
  --q-sel-threshold 0.954 --plot \
  --output-dir outputs/threeclass/sm/fisher
```

The bundled v0 signal CSVs contain only the old test split.  They may exercise
the builder with `--allow-test-only-v0`, but the trainer always rejects that
output as non-trainable.  The implementation contract and focused test record
are in `docs/THREECLASS_WORKFLOW_VALIDATION_20260910.md`.

## Directory policy

- `src/ilc_tth_cpv/`: reusable physics and workflow functions.
- `scripts/workflows/`: maintained thin commands.
- `scripts/diagnostics/`: one-question audits and historical investigations.
- `outputs/`: generated products, never source code.
- `data/event_csv/<version>/`: immutable, versioned small event tables.

The original root entry points remain available for compatibility; new work
should call the maintained commands above.

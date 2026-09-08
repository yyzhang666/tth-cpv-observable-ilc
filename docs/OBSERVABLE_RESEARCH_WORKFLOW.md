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

## Future three-class input

This command prepares a uniform table but deliberately does not train:

```bash
python3 scripts/workflows/prepare_multiclass_dataset.py \
  --background-csv /path/full_background.csv \
  --sm-csv /path/full_sm.csv --cpv-csv /path/full_cpv.csv \
  --feature-column q_CPV_wbjets_lepton \
  --feature-column O_lnu \
  --q-sel-threshold 0.954 \
  --cpv-training-weight-policy unit \
  --output outputs/multiclass/v1/events.csv
```

The output has stable role-prefixed event IDs, deterministic
train/validation/test assignments, a nonnegative `training_weight`, and a
separate `template_weight`.  CPV `template_weight` may be signed for physics
templates, but signed interference is forbidden as a classification-loss
weight.  The bundled v0 signal files are test-only; their use is blocked by
default and `--allow-test-only-v0` exists only for a schema smoke test.

## Directory policy

- `src/ilc_tth_cpv/`: reusable physics and workflow functions.
- `scripts/workflows/`: maintained thin commands.
- `scripts/diagnostics/`: one-question audits and historical investigations.
- `outputs/`: generated products, never source code.
- `data/event_csv/<version>/`: immutable, versioned small event tables.

The original root entry points remain available for compatibility; new work
should call the maintained commands above.

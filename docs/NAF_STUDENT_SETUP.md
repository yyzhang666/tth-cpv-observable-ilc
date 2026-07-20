# NAF Student Setup

The repository is meant to run directly from a writable NAF working copy. The
large input samples stay in the shared production directories listed in
`configs/samples.yaml`; student outputs are written under this repo's
`outputs/` directory.

## Writable Working Copy

```bash
mkdir -p /data/dust/user/$USER/analysis
cd /data/dust/user/$USER/analysis
cp -a /data/dust/user/zhangyuy/analysis/ilc-tth-cpv-v2 ./ilc-tth-cpv-v2
cd ilc-tth-cpv-v2
source env/setup.sh
bash env/check_environment.sh
bash env/check_environment.sh --data
```

`env/setup.sh` sources the analysis-side ZHH stack by default:

```text
/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh
```

That stack provides `pyLCIO`, `ROOT`, `Marlin`, and the
`TTHSemiLepKinFit` processor used by `scripts/run_kinfit_assignment.sh`.

## First Smoke Path

Start with a generator-only smoke:

```bash
bash scripts/run_baseline.sh configs/analysis_ow_lr.yaml --max-events 500
```

Then smoke-test the reconstruction path on one chunk:

```bash
bash scripts/run_kinfit_assignment.sh \
  --config configs/analysis_ow_lr.yaml --chunk 0 --max-events 50
```

The runner writes the exact XML, ROOT output, log, and validation JSON under
`outputs/<analysis>/kinfit/`. Do not submit all 80 chunks until the smoke job
has a valid ROOT tree and the expected branches.

## Dependency Checks

```bash
python3 scripts/check_model_profile.py
python3 scripts/check_model_profile.py --profile marlin_kinfit
```

Use `--strict` in batch wrappers when a missing dependency should stop the job.

# NAF Student Setup

The repository is meant to run directly from a writable working copy in the
student's own DUST area, not in AFS. The large input samples stay read-only in
the supervisor's shared production directories listed in
`configs/samples.yaml`; student outputs are written under the DUST clone's
`outputs/` directory.

## Writable Working Copy

```bash
mkdir -p /data/dust/user/$USER/analysis
cd /data/dust/user/$USER/analysis
# Fork the GitHub repository first, then use the student's account here.
git clone git@github.com:YOUR_GITHUB_ACCOUNT/tth-cpv-observable-ilc.git
cd tth-cpv-observable-ilc
source env/setup.sh
bash env/check_environment.sh
bash env/check_environment.sh --data
```

With this layout, large products go to
`/data/dust/user/$USER/analysis/tth-cpv-observable-ilc/outputs/`. Do not copy
the shared event samples and do not write analysis products into the
supervisor's `events_physsim` or `events_whizard` trees.

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
  --config configs/analysis_ow_lr.yaml \
  --chunk 0 \
  --max-events 50 \
  --out-dir outputs/ow_lr/kinfit_smoke
```

The runner writes the exact XML, ROOT output, log, and validation JSON under
`outputs/ow_lr/kinfit_smoke/`. A complete chunk uses the canonical
`outputs/<analysis>/kinfit/` directory. Do not submit all 80 chunks until the
smoke job has a valid ROOT tree and the expected branches.

## Dependency Checks

```bash
python3 scripts/check_model_profile.py
python3 scripts/check_model_profile.py --profile marlin_kinfit
```

Use `--strict` in batch wrappers when a missing dependency should stop the job.

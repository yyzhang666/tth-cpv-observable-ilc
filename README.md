# ilc-tth-cpv

Unified entry point for the ILC/LCF `e+e- -> ttH` CP-violation summer-student
project on the DESY NAF.

Supervisor reference copy on NAF: `ilc-tth-cpv-v2`.
GitHub mirror: `git@github.com:yyzhang666/tth-cpv-observable-ilc.git`.

## What this repository studies

```
e+e- -> ttH            sqrt(s) = 550 GeV
semileptonic channel   H -> bbar b
CP-violating top-Higgs coupling (kappa_t, kappa~_t)
angular observables and ML-learned observables
generator-to-reconstruction information loss
```

The full scientific programme: [docs/PROJECT_NOTE_FULL.md](docs/PROJECT_NOTE_FULL.md)
(student-facing full project guide) and
[docs/PROJECT_NOTE.md](docs/PROJECT_NOTE.md) (short chapter map).

## Current project status

- There is **no completed angular–ML baseline**. Building, validating, and
  documenting the first baseline is the first scientific result.
- **Signal samples are produced**: 1M CPV events per polarization
  (`eL.pR`, `eR.pL`), 80 chunks each, from Physsim through SGV to
  kinfit-ready complete reconstruction, with per-chunk CPV weight sidecars
  ([configs/samples.yaml](configs/samples.yaml)). Generator physics and
  production validation are complete; see
  [docs/SAMPLE_PROVENANCE.md](docs/SAMPLE_PROVENANCE.md).
- **Jet assignment + kinematic fit** is a standard, frozen pipeline stage
  ([docs/KINFIT_JET_ASSIGNMENT.md](docs/KINFIT_JET_ASSIGNMENT.md));
  production final selection uses `FinalSelectionMode=logchi2_plus_flavor`
  with `FlavorWeight=0.3`, and all reco-level observables use that selected
  candidate.
- The event-selection MVA and the background tables are prepared by the
  supervisor in parallel; the interfaces here are frozen but currently
  `enabled: false` ([docs/MVA_INTERFACE.md](docs/MVA_INTERFACE.md),
  [docs/BACKGROUND_INTERFACE.md](docs/BACKGROUND_INTERFACE.md)).
- Everything blocking or ambiguous is tracked in
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md). Read it before trusting any convention.

## Clone on the NAF: use your own DUST

Do not clone the working repository into AFS (`/afs/desy.de/user/...`). The
kinfit ROOT files, feature tables, models, and plots are written below the
working copy, so the clone itself must live in the student's DUST area:

```bash
mkdir -p /data/dust/user/$USER/analysis
cd /data/dust/user/$USER/analysis

# After forking on GitHub, replace YOUR_GITHUB_ACCOUNT with the student's account.
git clone git@github.com:YOUR_GITHUB_ACCOUNT/tth-cpv-observable-ilc.git
cd tth-cpv-observable-ilc
```

The large input samples remain read-only in the supervisor's
`events_physsim/production` tree through [configs/samples.yaml](configs/samples.yaml);
they are not copied. All student products then stay under
`/data/dust/user/$USER/analysis/tth-cpv-observable-ilc/outputs/`. Do not put
derived student products inside the shared `events_physsim` or
`events_whizard` production trees.

## Quick start

```bash
cd /data/dust/user/$USER/analysis/tth-cpv-observable-ilc
source env/setup.sh
bash env/check_environment.sh
bash env/check_environment.sh --data

# look at generator events (chunk 0)
python3 scripts/inspect_generator_event.py --config configs/analysis_ow_lr.yaml --max-events 3

# look at a reconstructed event
python3 scripts/inspect_reco_event.py --config configs/analysis_ow_lr.yaml --max-events 1

# generator-level baseline chain on a few hundred events (NOT a physics result)
bash scripts/run_baseline.sh configs/analysis_ow_lr.yaml --max-events 500

# kinfit + jet assignment smoke test on one chunk
bash scripts/run_kinfit_assignment.sh \
  --config configs/analysis_ow_lr.yaml \
  --chunk 0 \
  --max-events 50 \
  --out-dir outputs/ow_lr/kinfit_smoke
```

The 50-event kinfit output is deliberately isolated from the canonical
full-chunk directory. The standard reco feature exporter reads only a validated
full-chunk ROOT; follow PROJECT_NOTE_FULL.md Chapter 3 for the one-chunk
HTCondor gate and reco export.

## Inspect event files directly

These LCIO command-line tools are useful for building intuition about what is
actually stored in event files. They are inspection/debug tools, not the
production analysis workflow.

```bash
source env/setup.sh

# summarize an SLCIO file: events, collections, collection types, parameters
anajob /path/to/file.slcio

# dump the n-th event in an SLCIO file
dumpevent /path/to/file.slcio 0

# dump one specific run/event pair
dumpevent /path/to/file.slcio <runNum> <evtNum>

# restrict the dump to selected collections
LCIO_READ_COL_NAMES="MCParticle RefinedJets6 OutputErrorFlowJets6" dumpevent /path/to/file.slcio 0

# convert stdhep -> SLCIO for inspection; maxEvt=-1 means all events
stdhepjob_new /path/to/input.stdhep /tmp/stdhep_subset.slcio 100
```

Use real sample paths from [configs/samples.yaml](configs/samples.yaml).
For reconstructed analysis inputs, inspect the `complete_reco_kinfit_ready`
`.slcio` files; for generator-only checks, use
`scripts/inspect_generator_event.py` or first convert a small subset with
`stdhepjob_new`.

## The pipeline

```
generator stdhep + sidecar        (produced; per chunk)
        |
SGV -> complete_reco_kinfit_ready (produced; per chunk)
        |
kinfit + jet assignment           scripts/run_kinfit_assignment.sh   <- YOU run this
        |                         (all 80 chunks: HTCondor, condor/README.md)
feature export                    scripts/export_features.py
        |
angular template  +  ML model     scripts/build_angular_observable.py
        |                         scripts/train_cpv_model.py
ML observable                     scripts/build_ml_observable.py
        |
Fisher / likelihood               scripts/evaluate_fisher.py
        |
selection MVA + backgrounds       (interfaces frozen, deliveries pending)
LCF polarisation combination      scripts/apply_polarization_weights.py
```

## Where things are

- Sample manifest (the ONLY place with data paths):
  [configs/samples.yaml](configs/samples.yaml)
- Sample history / validation state: [docs/SAMPLE_PROVENANCE.md](docs/SAMPLE_PROVENANCE.md)
- Where every reused piece of code came from: [docs/CODE_PROVENANCE.md](docs/CODE_PROVENANCE.md)
- Student setup notes: [docs/NAF_STUDENT_SETUP.md](docs/NAF_STUDENT_SETUP.md)
- Dependency/model policy: [docs/DEPENDENCY_AND_MODEL_POLICY.md](docs/DEPENDENCY_AND_MODEL_POLICY.md)
- Machine-specific paths: copy `configs/paths.template.yaml` to
  `configs/paths.local.yaml` (gitignored) and edit.
- Batch processing: [condor/README.md](condor/README.md)

## Repository layout

```
configs/     sample manifest, per-analysis configs, polarisation scenario
docs/        schema, conventions, provenance, interfaces, kinfit stage
env/         setup + environment check
steering/    frozen Marlin steering (kinfit + jet assignment)
condor/      HTCondor rules + working example (submit/wrapper/arguments)
src/         ilc_tth_cpv python package (shared physics library)
scripts/     runnable entry points (kinfit, export, train, histogram, Fisher)
templates/   commented reader/training/Fisher walk-throughs for the student
tests/       pure-python unit tests
notebooks/   scratch notebooks
outputs/     all products (gitignored)
```

## Rules that protect the physics

1. All paths come from configs. The only external paths anywhere are the
   large data samples and the ZHH software setup.
2. One shared frame/angle implementation:
   [src/ilc_tth_cpv/frames.py](src/ilc_tth_cpv/frames.py) and
   [src/ilc_tth_cpv/angles.py](src/ilc_tth_cpv/angles.py) — import it
   everywhere.
3. ML inputs are **raw variables** (E, theta, phi, masses, scores), exactly
   as exported (frozen decision; see `docs/DATA_SCHEMA.md`).
4. Training weights and physics-template weights live in separate columns;
   each output uses its own kind ([docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md)).
5. Reco-level observables come from the production kinfit selected candidate:
   `FinalSelectionMode=logchi2_plus_flavor`, `FlavorWeight=0.3`, and
   `accepted=1 && fit_success=1`
   ([docs/KINFIT_JET_ASSIGNMENT.md](docs/KINFIT_JET_ASSIGNMENT.md)).
6. Debug runs (`--max-events`, split files) are for pipeline validation;
   physics numbers come from full-sample runs.
7. Every result directory contains the config and metadata that produced it.

## Checks the student is expected to do

- verify collection names against the actual SLCIO files (`inspect_*` scripts);
- verify event counts and paths in `configs/samples.yaml`;
- verify all input files are readable (`env/check_environment.sh --data`);
- verify the default model profile (`python3 scripts/check_model_profile.py`);
- smoke-test ONE condor job end-to-end before submitting 80;
- check every trained model for overtraining (train vs validation curves);
- check sidecar/event alignment and record gen-only, reco-only, and overlapping
  event counts (do not intersect IDs for the total-retention result);
- check normalization of every histogram output;
- check the deterministic train/validation/test split for overlap.

# Environment notes

## Stack layout on the NAF — zero installs required

A fresh NAF account gets everything from `source env/setup.sh`:

- ILCSoft / key4hep stack from cvmfs: pyLCIO, Marlin, ROOT, and the
  `TTHSemiLepKinFit` processor (via the ZHH software setup; path in
  `configs/paths.template.yaml: external.zhh_setup` — the only software path
  outside this repository);
- the key4hep python3 already ships with `pyyaml`, `numpy`, `matplotlib`,
  `scikit-learn`, `xgboost`, and `torch`. The baseline classifier is
  **XGBoost** for exactly this reason — the whole pipeline runs without any
  pip install.
- the core library `src/ilc_tth_cpv` uses only the python standard library,
  so the unit tests run with any python3.

## Optional extra packages (e.g. catboost)

When an extra package is wanted, create a venv once on a login node (login
nodes have network access) under the repository on /data/dust (ample quota),
inheriting the cvmfs packages:

```bash
source env/setup.sh
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install catboost
```

Batch jobs then activate the same venv after `env/setup.sh`. The `.venv/`
directory is gitignored.

## Known quirks

- The ZHH setup script is not `set -u`-clean; `env/setup.sh` relaxes `-u`
  around the source call.
- matplotlib on batch nodes needs writable cache dirs; the plotting module
  sets `XDG_CACHE_HOME` / `MPLCONFIGDIR` under `/tmp` automatically.
- Marlin writes hidden fixed-name files into its working directory; all
  wrappers in this repo therefore run Marlin in job-local work directories.
  Keep that pattern in anything you add (condor/README.md rule 1).
- `TTHSemiLepKinFit` may crash in finalization (exit 134/139) after writing a
  valid output ROOT file; wrappers accept these exits only with a non-empty
  output (KNOWN_ISSUES #9).
- GPU is not required for the CatBoost baseline. Weaver/ParT retraining
  (optional extension) is out of scope for this repo.

## Batch usage

- Anything beyond a few chunks runs on HTCondor: see `condor/README.md` and
  the working example in `condor/example/`.
- Keep condor logs under `outputs/` or the example dir — both gitignored.

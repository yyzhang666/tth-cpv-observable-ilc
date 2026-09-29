# ilc-miner

A general-purpose machine-learning observable package for ILC analyses, starting
with CP-violation classification and local Fisher-information evaluation.

The aim is to configure a dataset, features, a learning target, a model and
experimental conditions once, then run feature preparation, training, observable
construction and evaluation through a shared Python API or command-line entry
point. The API organization is inspired by
[MadMiner](https://arxiv.org/abs/1907.10621); this is an independent project.

## Development status

This branch is a **development foundation, not a working analysis pipeline**.
It currently contains an installable `ilc_miner` namespace, general provenance
utilities, their tests and the [workflow design](docs/ILC_MINER_DESIGN.md).

The feature registry, metadata-driven normalization, training interfaces,
observable registry, templates, Fisher evaluation and analysis CLI are **not
implemented yet**. Commands in the design document are proposed interfaces.

Historical analysis scripts, teaching material, fixed-sample configurations,
tracked datasets, reports and generated outputs have been removed from this
branch. There is no legacy compatibility layer. They remain recoverable from
[the pre-cleanup commit](https://github.com/yyzhang666/tth-cpv-observable-ilc/tree/476383ddf2f4179150c681eed4eec00797c10a48)
and the existing analysis branches.

## Design commitments

- Define a feature once; export, training and evaluation share its implementation.
  Missing features are computed from declared dependencies and traceable sources.
- Compute physical weights from source metadata, generation statistics, cross
  sections, luminosity and polarization at run time, with explicit overrides.
- Keep physical sample roles, training labels, training weights and template
  weights separate.
- Support binary and three-class CPV targets; class 2 represents SM or
  SM plus background.
- Register ML observables independently of models. The default is
  `P(plus) - P(minus)`; three-class ratios are explicit alternatives.
- Keep process-specific selections and ILC input adapters outside the generic
  analysis core.
- Track definitions, dependencies, class mappings and normalization alongside
  artifacts; validate numerical and physics closure before reporting results.

The first end-to-end implementation will target CPV. Other processes can reuse
the infrastructure with suitable inputs and targets. Local-score regression is
a future extension requiring appropriate derivative supervision, not just a
different list of features.

## Develop locally

Python 3.9 or newer is required. From this checkout:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

The current utilities use only the Python standard library. No ROOT, LCIO or ML
backend is required for these tests. Installation does not provide an analysis
command yet.

## Current repository layout

```text
docs/ILC_MINER_DESIGN.md   Physics contracts, intended interfaces and roadmap
src/ilc_miner/            Package namespace and provenance utilities
tests/                   Tests of the retained utilities
pyproject.toml           Minimal package/build configuration
LICENSE                  Unchanged license-pending declaration
```

## License

An open-source license has not yet been selected. The existing
[license declaration](LICENSE) is unchanged; the project is not currently
offered under an open-source license.

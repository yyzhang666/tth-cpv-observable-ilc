# Maintained observable workflows

This directory contains the small, supported command-line surface for new
observable studies.  Shared selection, observable, Fisher, I/O, and provenance
logic lives in `src/ilc_tth_cpv/`; entry points here should stay thin.

- `run_event_fisher.py`: read background/SM/CPV event CSVs, apply the strict
  per-event `q_sel > threshold` selection, histogram one registered angle or
  ML score, and calculate `sum S1^2/(S0+B)` separately for electron and muon
  before adding their likelihood information.
- `prepare_multiclass_dataset.py`: make a validated unified
  background/SM/CPV table for future three-class training.  It does not train
  a model and never uses the signed CPV interference weight as a loss weight.

See `docs/OBSERVABLE_RESEARCH_WORKFLOW.md` for runnable commands and physics
contracts.

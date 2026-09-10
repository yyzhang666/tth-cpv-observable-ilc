# Maintained observable workflows

This directory contains the small, supported command-line surface for new
observable studies.  Shared selection, observable, Fisher, I/O, and provenance
logic lives in `src/ilc_tth_cpv/`; entry points here should stay thin.

- `run_event_fisher.py`: read background/SM/CPV event CSVs, apply the strict
  per-event `q_sel > threshold` selection, histogram one registered angle or
  ML score, and calculate `sum S1^2/(S0+B)` separately for electron and muon
  before adding their likelihood information.
- `prepare_multiclass_dataset.py`: build the CP-aware three-class table
  `CPV- / neutral / CPV+`.  `--neutral-class sm` excludes background from
  training but retains it for scoring; `sm-plus-background` trains it together
  with SM as neutral.  Explicit inputs must also declare whether test weights
  are already projected to 8 ab-1 or provide six role/flavor scale factors.
- `train_threeclass_model.py`: train independent electron/muon CatBoost
  `MultiClass` models, derive `q_threeclass=P(+)-P(-)`, and write separate
  background/SM/CPV test-score CSVs ready for the Fisher command.

See `docs/OBSERVABLE_RESEARCH_WORKFLOW.md` for runnable commands and physics
contracts.

# PROJECT_NOTE

Start with [PROJECT_NOTE_FULL.md](PROJECT_NOTE_FULL.md). It is now the
student-facing full project guide and the main scientific roadmap for this
repository. This file is only a short chapter map.

## One-Sentence Programme

Build and validate the first gen/reco angular-vs-ML CP-observable baseline for
semileptonic `e+e- -> ttH`, then measure what information is lost through
reconstruction, selection, backgrounds, observable fusion, and the physical LCF
polarisation mixture.

## Required Result Path

1. Complete the guided event inspection and one-chunk gen/reco validation,
   producing the first labelled `O_W` distributions.
2. Complete the full `O_W` angular-vs-ML baseline at gen and reco level.
3. Reuse that machinery for `O_b`, `O_lnu`, and `O_top`.
4. Add the supervisor-provided event-selection MVA and backgrounds.
5. Fuse `O_W` with one secondary observable.
6. Convert pure `LR/RL` samples to the physical LCF polarisation scenario.
7. Add the minimal supervisor-approved generator-to-SMEFT conversion.

Optional extensions live in Chapter 10 of the full guide; opening none of them
is acceptable.

## Chapter Prompts

| Chapter | What the student should understand or do | Repo entry point |
|---|---|---|
| 1 | Know the physics question, starting conditions, deliverables, and non-goals. Negative results are valid. | [README.md](../README.md), [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) |
| 2 | Learn the concepts: signed interference weights, CP-odd angles, frames, ML observables, Fisher information, and polarisation. | `src/ilc_tth_cpv/weights.py`, `angles.py`, `frames.py`, `fisher.py`, `polarization.py` |
| 3 | Follow the first-run workflow: inspect real events, validate a generator table, smoke-test kinfit, complete one HTCondor chunk, export reco features, and preserve labelled gen/reco `O_W` examples before scaling out. | [DATA_SCHEMA.md](DATA_SCHEMA.md), `scripts/inspect_generator_event.py`, `scripts/inspect_reco_event.py`, `scripts/run_kinfit_assignment.sh`, `condor/README.md` |
| 4 | Main milestone: full `O_W` angular-vs-ML comparison at gen and reco level, including frame and model checks. | `configs/analysis_ow_lr.yaml`, `configs/analysis_ow_rl.yaml`, `scripts/run_baseline.sh`, `scripts/train_cpv_model.py` |
| 5 | Fast secondary baselines by reuse, not reinvention: `O_b`, `O_lnu`, `O_top`. | same feature/export/train/histogram tools as Chapter 4 |
| 6 | Integrate the delivered event-selection MVA and backgrounds; measure selection-induced CP-information loss. | [MVA_INTERFACE.md](MVA_INTERFACE.md), [BACKGROUND_INTERFACE.md](BACKGROUND_INTERFACE.md), `scripts/join_selection_mva.py` |
| 7 | Compare fusion strategies for `O_W + X`: early fusion, late fusion, or a 2D likelihood. | `scripts/build_ml_observable.py`, `scripts/evaluate_fisher.py` |
| 8 | Convert pure `LR/RL` results into the physical LCF running scenario without using polarisation weights as ML features. | `configs/lcf_polarization.yaml`, `scripts/apply_polarization_weights.py` |
| 9 | Apply only the supervisor-approved one-parameter generator-to-SMEFT conversion. | full guide Chapter 9 |
| 10 | Optional extensions, opened only after required results are frozen. | full guide Chapter 10 |
| 11 | Final checklist: scientific outputs, technical outputs, summary table/figure, quote-readiness. | full guide Chapter 11 and Appendix A |
| 12 | Suggested reading and bookkeeping templates. | full guide Chapter 12 and Appendices |

## Reconstruction Rule

Reco-level observables use the production kinfit selected candidate, not raw
jets and not offline re-ranking:
[KINFIT_JET_ASSIGNMENT.md](KINFIT_JET_ASSIGNMENT.md),
`steering/tth_semilep_kinfit.xml`, and
`scripts/run_kinfit_assignment.sh`.

## Current Feature Policy

The guide explains transformed ML inputs such as `log(E/E0)`, `cos(theta)`,
`sin(phi)`, and `cos(phi)` as useful concepts. The current frozen project
decision is to start from **raw variables** (`E`, `theta`, `phi`, masses, and
scores) as exported; see [DATA_SCHEMA.md](DATA_SCHEMA.md) and
[../KNOWN_ISSUES.md](../KNOWN_ISSUES.md).

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
| 1 | Separate what is already provided from what the student must produce; understand the five questions, six required deliverables, non-goals, and why a negative result can still be complete. | [README.md](../README.md), [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) |
| 2 | Understand sidecar-to-event alignment, signed template weights versus optimizer weights, CP-odd object ordering, the fixed-lab and Ma frame conventions, total gen-to-reco retention, Fisher information, polarisation, and the local SMEFT conversion. | [DATA_SCHEMA.md](DATA_SCHEMA.md), [PHYSICS_CONVENTIONS.md](PHYSICS_CONVENTIONS.md), `src/ilc_tth_cpv/weights.py`, `angles.py`, `frames.py`, `fisher.py`, `polarization.py` |
| 3 | Follow the first-run workflow in order: inspect real events, validate the generator table, isolate a kinfit smoke test, complete one HTCondor chunk, export reco features, and preserve labelled gen/reco `O_W` examples before scaling out. | [NAF_STUDENT_SETUP.md](NAF_STUDENT_SETUP.md), [DATA_SCHEMA.md](DATA_SCHEMA.md), `scripts/inspect_generator_event.py`, `scripts/inspect_reco_event.py`, `scripts/run_kinfit_assignment.sh`, `scripts/validate_kinfit_root.py`, `scripts/export_features.py`, `scripts/build_angular_observable.py`, `condor/README.md` |
| 4 | Produce the main `O_W` result matrix: frame study, angle versus ML, minimal versus extended features, model cross-check, pure LR/RL comparison, and inclusive-gen/full-reco information retention. | `configs/analysis_ow_lr.yaml`, `configs/analysis_ow_rl.yaml`; `scripts/run_baseline.sh` for the generator starting chain; then the export, angular-template, training, ML-template, and Fisher scripts listed in the full guide |
| 5 | Reuse the frozen Chapter 4 recipe for `O_b`, `O_lnu`, and `O_top`; compare Fisher strength and correlation with `O_W`, then select one complementary branch for fusion. | the same export/train/template tools as Chapter 4; full guide §5.4–§5.5 |
| 6 | Only after the frozen inputs arrive, join the event-selection MVA and backgrounds, quantify selection loss and background dilution, and compare the nominal 1D result with the optional 2D purity diagnostic. | [MVA_INTERFACE.md](MVA_INTERFACE.md), [BACKGROUND_INTERFACE.md](BACKGROUND_INTERFACE.md), `scripts/join_selection_mva.py` |
| 7 | Implement and compare early fusion, late fusion, and a 2D likelihood for `O_W + X`; report the conditional information gain rather than only classifier performance. | reuse `scripts/build_ml_observable.py` and `scripts/evaluate_fisher.py`; no frozen fusion driver exists yet |
| 8 | Start from frozen pure-LR/RL results, construct the four physical run categories, apply luminosity and helicity factors only as weights, run the closure test, and combine per-category likelihoods. | `configs/lcf_polarization.yaml`, `scripts/apply_polarization_weights.py`, Appendix B |
| 9 | After the likelihood is stable, apply only the supervisor-approved local one-parameter conversion to `C^I_tphi/Lambda^2`, recording sign, units, and convention; do not present a multi-operator fit. | full guide §2.14 and Chapter 9 |
| 10 | Open at most one optional extension, and only after the required results are frozen; state its prerequisite and information-based deliverable before starting. | full guide Chapter 10 |
| 11 | Assemble the exact scientific and technical outputs, one summary figure/table, and every quote-readiness check before reporting a number. | full guide Chapter 11 and Appendix A |
| 12 | Read the minimum theory/software references and use the appendices for the result matrix, polarisation closure test, and decision log. | full guide Chapter 12 and Appendices A–C |

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

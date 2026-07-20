# PROJECT_NOTE

The authoritative project description is included in this repository:
[PROJECT_NOTE_FULL.md](PROJECT_NOTE_FULL.md) (supervisor's project note,
copied verbatim; the supervisor's working copy is the master version).

This file only summarises the structure so the repository is self-navigable.

## Programme (summary)

- Channel: semileptonic `e+e- -> ttH`, `H -> bb`, sqrt(s) = 550 GeV.
- Coupling: `L = -(m_t/v) H tbar (kappa_t + i kappa~_t gamma5) t`; local linear
  parameter `c` with `dsigma/dx = f0 + c f1 (+ c^2 f2 optional)`.
- Required scope (note ch. 1.4):
  1. complete gen/reco angular–ML baseline for `O_W`;
  2. integrate the supervisor's event-selection MVA; first S and S+B result;
  3. quick baselines for `O_b`, `O_lnu`, `O_top`;
  4. fusion of `O_W` with one secondary observable;
  5. physical LCF polarisation combination;
  6. minimal supervisor-approved generator->SMEFT conversion.
- Optional extensions (at most one; ch. 10): hadronic-tau category, W-pairing
  optimisation, quadratic EFT term, wider fusion.
- Scope-control: negative results are valid results (ch. 1.6).

## Where reconstruction-level objects come from

Reconstructed events go through the **kinfit + jet assignment stage** before
any observable is built: see
[KINFIT_JET_ASSIGNMENT.md](KINFIT_JET_ASSIGNMENT.md). Students use the
selected candidate of that stage (jet slots `W1, W2, b_had, b_lep, H_b1,
H_b2` plus the fitted lepton/neutrino), not raw jets.

## Chapter map of the note

| Note chapter | Topic | Repo entry point |
|---|---|---|
| 2.2 | signed interference weights | `src/ilc_tth_cpv/weights.py` |
| 2.3 | angular observables | `src/ilc_tth_cpv/angles.py` |
| 2.4 | reference frames | `src/ilc_tth_cpv/frames.py` |
| 2.5–2.6 | ML inputs / ML observables | `src/ilc_tth_cpv/features.py`, `scripts/train_cpv_model.py` |
| 2.8 | gen/reco matching | `docs/DATA_SCHEMA.md`, `tests/test_event_matching.py` |
| 2.9 | selection MVA & backgrounds | `docs/MVA_INTERFACE.md`, `docs/BACKGROUND_INTERFACE.md` |
| 2.10–2.12 | Fisher, limits, retention | `src/ilc_tth_cpv/fisher.py`, `scripts/evaluate_fisher.py` |
| 2.13 | polarisation | `src/ilc_tth_cpv/polarization.py`, `configs/lcf_polarization.yaml` |
| 3 | common baseline layer | `src/ilc_tth_cpv/` |
| 4 | O_W baseline | `configs/analysis_ow_lr.yaml`, `scripts/run_baseline.sh` |
| — | jet assignment + kinfit | `docs/KINFIT_JET_ASSIGNMENT.md`, `steering/`, `scripts/run_kinfit_assignment.sh` |
| — | batch processing | `condor/README.md` |

Note: the project note (§2.5) discusses transformed ML inputs such as
`log(E/E0), cos theta, sin phi, cos phi`. The current supervisor decision is
to start from **raw variables** (`E, theta, phi`, masses, scores) without any
transformation; see docs/DATA_SCHEMA.md and KNOWN_ISSUES.

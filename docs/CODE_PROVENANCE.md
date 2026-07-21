# CODE_PROVENANCE

Every physics-relevant implementation in this repository is ported from an
existing, validated implementation in the supervisor's working areas. Nothing
was rewritten from memory.

Everything required for the student project is inside this repository.
Original locations are recorded generically (script name + area); the
supervisor holds the master copies.

Legend for "mode": `copied` (verbatim), `wrapped` (thin wrapper),
`ported` (re-typed with identical logic, cosmetic changes only),
`adapted` (simplified/parametrised for student use, physics unchanged).

## Generator / CP weights

| repo file | origin (supervisor area) | mode |
|---|---|---|
| `src/ilc_tth_cpv/angles.py::wrap_phi` | theory-study script `compute_tthcpv_ma2018_observables.py` | ported |
| `src/ilc_tth_cpv/frames.py::boost_to_rest`, `make_frame`, `BasisQuality`, `find_electron_beam_direction` | same script | ported |
| `src/ilc_tth_cpv/weights.py::read_sidecar`, `parse_skipped_events_from_log` | same script | ported |
| hadronic-W analyzer PDG sets in `src/ilc_tth_cpv/objects.py` | theory-study script `compute_tthcpv_ma2018_hadronic_w_observables.py` | ported |
| signed/abs/entries histogram triple in `src/ilc_tth_cpv/histograms.py` | theory-study script `summarize_tthcpv_phi_sensitivity.py` | ported |
| `docs/PROJECT_NOTE_FULL.md` | student-facing project guide, rewritten from the supervisor's project note | adapted |

Why authoritative: these scripts produced the validated generator observable
theory-study report on the 12500-event validation sample and are the official
rerun commands of that study.

## Kinfit + jet assignment

| repo file | origin | mode |
|---|---|---|
| `steering/tth_semilep_kinfit.xml` | XML emitted by the supervisor's canonical kinfit runner (`run_tth_semilep_canonical_kinfit_20260707.py` + `run_kinfit_calibration_matrix.py::make_xml`), canonical Top10 / sigma-angle-2.6 / `logchi2_plus_flavor_x0p3` configuration | adapted (parameters identical, paths templated) |
| `scripts/run_kinfit_assignment.sh` | new student wrapper around the same Marlin call | new |
| `scripts/validate_kinfit_root.py` | content-validation guardrail from `AI_PIPELINES` rules: file existence is not success | new |
| `docs/KINFIT_JET_ASSIGNMENT.md` | supervisor's final kinfit & jet assignment scheme note plus `20260720_tth_semilep_logchi2_flavor_production_update.md` | adapted |

The `TTHSemiLepKinFit` Marlin processor itself is part of the ZHH software
stack loaded by `env/setup.sh`. On 2026-07-22 its best tree output was extended
to persist the already-fitted `FitOutcome.nuAfter` as
`nu_fit_{E,px,py,pz}`. This was output plumbing only; fit logic and candidate
selection were unchanged.

## Reconstruction reading

| repo file | origin | mode |
|---|---|---|
| collection contract in `templates/reco_reader_template.py` | production `complete_reco_kinfit_ready` steering + kinfit scheme note | documented |
| `src/ilc_tth_cpv/slcio.py` reader pattern | supervisor's MVA-inputs LCIO helper module | ported |
| `src/ilc_tth_cpv/flavor.py::orient_w_pair` | frozen supervisor rule using Weaver signed light-flavour probabilities within the selected W pair | new, tested |
| sample weight rule `xsec*lumi/n_gen` | same module | ported |

## ML observable

| repo item | origin | mode |
|---|---|---|
| score convention `P(+)-P(-)`, class labels resolved by value | supervisor's ZH CPV sensitivity package (`catboost_observable.py`) | ported |
| training/template weight separation | ZH CPV conventions + project note §2.2 | ported |
| **raw-feature policy** (no log/sin/cos transforms) | supervisor decision 2026-07-20 | frozen |
| `configs/model_profiles.yaml`, `scripts/check_model_profile.py` | student-onboarding dependency guardrail | new |

## Histograms / Fisher / likelihood

| repo item | origin | mode |
|---|---|---|
| Fisher `I = sum nu1^2/nu0`, shape-only subtraction | project note §2.10 (formula) | new, toy-tested |
| Poisson Asimov likelihood scan | project note §2.10–2.11; ZH CPV standard | new, toy-tested |

## Batch processing (HTCondor)

| repo item | origin | mode |
|---|---|---|
| `condor/` examples and rules | supervisor's NAF Physsim workflow conventions + a colleague's ZHH condor workflow template | adapted |

## Authoritative sources, complete list

The tables above are the complete list of authoritative sources for this
project. For anything that seems missing, ask the supervisor — they maintain
the master copies and will point to or import the right implementation.

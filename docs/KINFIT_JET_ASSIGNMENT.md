# KINFIT_JET_ASSIGNMENT

The standard jet-assignment + kinematic-fit stage for the semileptonic
`ttH, H->bb` analysis. **Every reconstruction-level observable in this project
is built from the selected candidate of this stage.**

This page describes the one runnable standard flow. Calibration history and
diagnostic variants are supervisor material and live outside this repo.

## One-sentence version

```
RefinedJets6 Weaver/signed-flavor information pre-selects TopN=10 jet assignments
  -> each of the 10 base assignments is fitted with TTHSemiLepKinFit using
     OutputErrorFlowJets6 jet four-momenta + covariances
  -> fit uses fullMass4C + soft mass constraints + SLD/neutrino enumeration
  -> after preferring successful fits, the fitted candidate/subsolution with
     the smallest
     log(1 + fit_chi2) + 0.3*signed_flavor_NLL is the production result
```

## Collection contract (fixed)

Each collection has exactly one role. The two easiest mistakes in this
workflow are swapping the two jet collections and letting truth into the
reco-level selection — keep this table at hand:

| Collection | Role |
|---|---|
| `OutputErrorFlowJets6` | jet four-momentum + covariance INTO the fit (kinematics only) |
| `RefinedJets6` | Weaver flavour tags, signed-flavor TopN pre-selection, ymerge from ParticleID algorithm `yth` (flavour only) |
| `ISOElectrons`, `ISOMuons` | isolated lepton into the fit |
| `JetSLDLink6`, `SLDNuLink6` | semi-leptonic heavy-flavour decay / neutrino links |
| `JetsPreFitTTHSemiLep` / `JetsKinFitTTHSemiLep` | optional pre/post-fit jet states; pre/post-fit comparisons require these to be saved |
| `TrueJets` / truth links / `MCParticlesSkimmed` | validation, accuracy, pulls — truth stays out of the reco-level selection |

## Jet slots of one assignment

```
W1, W2      light jets of the hadronic W
b_had       b of the hadronic top
b_lep       b of the leptonic top
H_b1, H_b2  Higgs b pair
```

The signed-flavor pre-selection ranks all base assignments by how well the
Weaver flavour information matches this hypothesis and keeps the best 10.
The kinematic fit then selects the final candidate among those 10 (including
SLD/neutrino sub-solutions) with the production combined score.

Selection rule:

```
1. Prefer fit_success=true over fit_success=false.
2. If success status is the same, choose smaller final_selection_score.
3. If tied, choose larger fitprob.
4. If tied, choose smaller fitchi2.
5. If tied, choose smaller combo id.
```

## Canonical parameters (frozen)

```
JetCollectionName        = OutputErrorFlowJets6
FlavorJetCollectionName  = RefinedJets6
TopN                     = 10
ConstraintMode           = fullMass4C
includeISR               = true
EnableSLDNeutrinoEnumeration = true
UseSoftMassConstraints   = true
UseJetCovarianceOffDiagonal = false     # diagonal covariance is the standard
FinalSelectionMode       = logchi2_plus_flavor
FlavorWeight             = 0.3
SigmaEnergyScaleFactor   = 1.6
SigmaAnglesScaleFactor   = 2.6          # sigma multiplier, not variance
SigmaInvPtScaleFactor    = 1.1
ECM = 550, WMass = 80.4, TopMass = 172.5, HMass = 125.0
```

These are wired into [steering/tth_semilep_kinfit.xml](../steering/tth_semilep_kinfit.xml).
They come from a dedicated calibration campaign; changes go through the
supervisor.

## How to run

```bash
source env/setup.sh

# smoke test: one chunk, 50 events
bash scripts/run_kinfit_assignment.sh \
    --config configs/analysis_ow_lr.yaml --chunk 0 --max-events 50

# one full chunk (~12.5k events)
bash scripts/run_kinfit_assignment.sh \
    --config configs/analysis_ow_lr.yaml --chunk 0

# the matching SM denominator uses the identical processor/selection
bash scripts/run_kinfit_assignment.sh \
    --config configs/analysis_ow_lr.yaml --component sm --chunk 0

# all 80 chunks: use HTCondor, see condor/README.md
```

Output per chunk (under `outputs/<analysis>/kinfit/`):

- `kinfit_<sample>_<chunk>.root` — the `TTHSemiLepKinFit` tree with the
  selected candidate, and per-candidate debug entries;
- `kinfit_<sample>_<chunk>.xml` — the exact steering used (provenance);
- `kinfit_<sample>_<chunk>.log` — Marlin log.
- `kinfit_<sample>_<chunk>.validation.json` — ROOT content validation
  produced by `scripts/validate_kinfit_root.py`.

CPV and SM outputs coexist because their filenames contain different sample
keys (`tthcpv_reco_*` versus `tth_sm_reco_*`). Use `--component sm` in both
the runner and the Condor argument generator; this changes only the input
sample, never the fit configuration.

## Which events count

For physics selections use only:

```
accepted   = 1
fit_success = 1
```

The fit tree records at least `fit_success, fit_status, fitchi2, ndof, fitprob`,
the selected base-combo id, the SLD/neutrino sub-solution id, and the final
selection bookkeeping:

```
final_selection_mode
flavor_weight
final_selection_score
final_fit_score
final_flavor_score
nu_fit_E
nu_fit_px
nu_fit_py
nu_fit_pz
lepton_charge
```

For the canonical mode:

```
final_fit_score       = log(1 + fit_chi2)
final_flavor_score    = signed_flavor_NLL = best_preselect_score
final_selection_score = final_fit_score + 0.3 * final_flavor_score
```

`fitprob` is still stored as the p-value of (`fitchi2`, `ndof`), but it is no
longer the default final selection criterion. It remains available as a control
mode in the processor.

## Reco-level observables from the selected candidate

Kinfit supplies the selected slots for the CP observables:

```
O_W  : selected W1/W2 pair, oriented after selection by the feature exporter
O_b  : selected slots b_had - b_lep
```

The processor enumerates `W1/W2` in source-index order and scores their pair
symmetrically. `export_features.py` then computes each selected jet's
`P(q)` and `P(qbar)` from the Weaver u/d/s/c and anti-u/d/s/c probabilities.
Opposite preferences are used directly. For two q-like jets, larger `P(q)` is
q; for two qbar-like jets, larger `P(qbar)` is qbar. b probabilities are
ignored for this orientation. The rule, scores, decision margin, and
same-sign/tie status are persisted in the feature table. This is an
orientation of the selected pair, not an offline reranking of kinfit
candidates.

The best tree also stores the selected fit's `nu_fit_{E,px,py,pz}`. These
branches and `lepton_charge` are required by the validator/exporter so reco
`O_lnu` can use the same charge-dependent ordering as generator level. The
`b_had/b_lep` and hadronic/leptonic top sides remain selected slots until their
charge ordering is implemented and checked in Chapter 4.

One entry per selected event passing `accepted=1 && fit_success=1`.
Truth-oriented variants remain separate diagnostics with their own denominator.

## Out of scope for the student baseline

- The sigma scale factors and the covariance treatment are calibration
  results — use them as given.
- The old fitprob/chi2-only selection is no longer the production standard. It
  remains only as a configurable control mode for supervisor comparisons.
- The pre-implementation diagnostic headline numbers motivated the
  `logchi2_plus_flavor` production mode, but they are not post-implementation
  performance measurements. Quote new production accuracy only from samples
  rerun with this library and XML.
- Off-diagonal jet covariance is a supervisor-side backup study.

## MVA variables from this stage (for later chapters)

When exporting event tables for the selection MVA / CP studies, take from the
selected event: `y45, y56, y67` (from `RefinedJets6` ParticleID `yth`),
highest Weaver `b/bbar/c/cbar` tags, `m_H, m_W, m_t`, `fitchi2, fitprob`,
`final_selection_score`, `final_fit_score`, `final_flavor_score`,
Higgs-pair `cos(theta_bb)`, `cos(theta_H_hadtop)`,
`cos(theta_H_leptop_visible)`, `E_vis`, `|P_missing|`, thrust, and the
selected-pair delta-phi variables — always with the status columns.

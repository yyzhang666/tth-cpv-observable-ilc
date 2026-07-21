# KNOWN_ISSUES

Unresolved decisions and known limitations. Do not silently resolve any item
here; every resolution needs supervisor sign-off and a dated note.

## Open physics decisions (supervisor)

1. **Reco-level quark/antiquark mapping for O_W.** The generator-level
   ordering is frozen from the theory study:
   `O_W = wrap(phi_quark - phi_antiquark)` (particle − antiparticle). At
   reconstruction level the mapping from the selected kinfit slots `W1/W2`
   onto quark/antiquark uses the signed ParT/Weaver charge information; the
   exact recipe needs supervisor confirmation before the first reco O_W
   result. See docs/PHYSICS_CONVENTIONS.md §4, §10.
2. **phi wrap boundary.** The project note writes `(-pi, pi]`, but the
   authoritative theory-study implementation returns values in `[-pi, pi)`.
   This repo freezes the **code** convention `[-pi, pi)` because all
   validated results were produced with it. The boundary set has measure
   zero but affects exact-boundary tests.
3. **O_top and O_lnu exact definitions** are supervisor-approved placeholders;
   the definitions in configs are drafts.
4. **Generator physics validation** of the CPV production is pending. The
   2026-07-20 production passed all *technical* validation gates (file
   counts, event counts, sidecar alignment), but the samples stay
   `method-development-ready` / `physics-validation-pending` in
   `configs/samples.yaml` until the supervisor signs off the physics.
5. **SM weight bookkeeping.** SM ttH reco productions exist, but the
   cross-section / n_generated bookkeeping for `weight_sm` yield templates is
   not yet frozen. Until then absolute Fisher numbers use the documented
   technical placeholder (`evaluate_fisher.py --nu0-from-abs`) and are NOT
   physics results.
6. **Generator-to-SMEFT conversion factor K** must be supplied by the
   supervisor (docs/PROJECT_NOTE.md ch. 9).
7. **Generator cross-section spin-averaging convention** must be checked
   before applying the LCF a/b polarisation factors to yields
   (docs/PHYSICS_CONVENTIONS.md §7).

## Kinfit / jet assignment stage

8. **Post-implementation kinfit performance tables pending.** As of
   2026-07-20, the production `TTHSemiLepKinFit` final selection uses
   `FinalSelectionMode=logchi2_plus_flavor` and `FlavorWeight=0.3`, i.e.
   `log(1+fit_chi2) + 0.3*signed_flavor_NLL`. The old fitprob/chi2-only
   selection is now only a configurable control mode. New official accuracy,
   recovered/destroyed, mass, delta-phi, and MVA-variable tables require
   rerunning the standard SLCIO samples with the new library and XML
   (docs/KINFIT_JET_ASSIGNMENT.md).
9. **Marlin finalization exits 134/139.** The kinfit processor may crash in
   finalization after writing a valid ROOT output. The wrapper accepts these
   exit codes only when the output is non-empty and
   `scripts/validate_kinfit_root.py` confirms the expected tree/branches.
10. **Reco feature neutrino p4.** `export_features.py --level reco` reads the
    selected `TTHSemiLepKinFit` best tree plus the matching SLCIO input. The
    best tree does not store the fitted neutrino four-vector, so reco neutrino
    columns are `NaN` and the leptonic-top composite is visible-only until the
    processor persists that p4.

## Interface placeholders

11. **Event-selection MVA** not yet delivered. `selection.enabled: false` in
    all analysis configs. Interface frozen in docs/MVA_INTERFACE.md.
12. **Backgrounds**: ttZ reco production directories exist but no background
    event table has been delivered; ttbb and other 6f are pending. Interface
    frozen in docs/BACKGROUND_INTERFACE.md.

## Technical limitations

13. `scripts/split_slcio.sh` / `merge_slcio.sh` need pyLCIO from the ZHH
    stack; if unavailable, use `--max-events` early stopping instead.
14. Fisher intervals from `scripts/evaluate_fisher.py` are local Gaussian
    approximations; a likelihood scan (`src/ilc_tth_cpv/likelihood.py`) is
    required for final intervals (conditions in PROJECT_NOTE §2.11).
15. **Feature policy**: ML inputs are raw variables only (E, theta, phi,
    masses, scores). The transformed encodings discussed in the project note
    §2.5 are explicitly NOT used at this stage (supervisor decision
    2026-07-20); revisiting them requires a config-level change request.

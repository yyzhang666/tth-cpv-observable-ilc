# KNOWN_ISSUES

Only unresolved limitations that can change a result belong here. Frozen
conventions are documented in `docs/PHYSICS_CONVENTIONS.md`; completed sample
validation is documented in `docs/SAMPLE_PROVENANCE.md`.

## Kinfit / jet assignment stage

1. **Post-implementation kinfit performance tables pending.** As of
   2026-07-20, the production `TTHSemiLepKinFit` final selection uses
   `FinalSelectionMode=logchi2_plus_flavor` and `FlavorWeight=0.3`, i.e.
   `log(1+fit_chi2) + 0.3*signed_flavor_NLL`. The old fitprob/chi2-only
   selection is now only a configurable control mode. New official accuracy,
   recovered/destroyed, mass, delta-phi, and MVA-variable tables require
   rerunning the standard SLCIO samples with the new library and XML
   (`docs/KINFIT_JET_ASSIGNMENT.md`).

2. **Marlin finalization exits 134/139.** The kinfit processor may crash in
   finalization after writing a valid ROOT output. The wrapper accepts these
   exit codes only when the output is non-empty and
   `scripts/validate_kinfit_root.py` confirms the expected tree and branches.

## External inputs not delivered

3. **Event-selection MVA** not yet delivered. `selection.enabled: false` in
   all analysis configs. Interface frozen in `docs/MVA_INTERFACE.md`.
4. **Background tables** not yet delivered. ttZ reco production directories
   exist, while ttbb and other 6f are pending. Interface frozen in
   `docs/BACKGROUND_INTERFACE.md`.

## Technical limitations

5. `scripts/split_slcio.sh` and `scripts/merge_slcio.sh` need pyLCIO from the
   ZHH stack; if unavailable, use `--max-events` early stopping instead.
6. Fisher intervals from `scripts/evaluate_fisher.py` are local Gaussian
   approximations; a likelihood scan (`src/ilc_tth_cpv/likelihood.py`) is
   required for final intervals under the conditions in Project Note section
   2.11.
7. **Near-beam Ma-frame conditioning.** For the Ma production-plane basis,
   `frames.make_frame` rejects a collinear system when the beam-transverse x
   vector has norm at most `1e-12`. Stability just above that threshold is not
   yet covered by an automated toy test. This does not affect the current
   fixed-`lab_axes` baseline, but any Ma-style result must report frame
   failures and test the system-to-beam-angle dependence; see
   `docs/PROJECT_NOTE_FULL.md` section 2.4.

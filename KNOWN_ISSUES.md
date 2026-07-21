# KNOWN_ISSUES

Only unresolved limitations that can change a result belong here. Frozen
conventions are documented in `docs/PHYSICS_CONVENTIONS.md`; completed sample
validation is documented in `docs/SAMPLE_PROVENANCE.md`.

## Physics-template blockers

1. **Reco signed-object ordering is not implemented yet.** Generator-level
   definitions are frozen, but the current reco exporter does not reproduce all
   of their particle-antiparticle orderings:

   - the kinfit enumerates `W1/W2` in ascending source-jet index and scores the
     two W slots symmetrically; signed flavor helps select the W pair and orient
     the top-side b jets, but it does not identify W1 as quark and W2 as
     antiquark;
   - the exporter currently aliases `W1/W2` to
     `wjet_quark/wjet_antiquark`, so reco `O_W = W1-W2` is a technical
     slot-order diagnostic, not yet the physical quark-antiquark observable;
   - `O_b` and `O_top` must use the isolated-lepton charge to decide whether the
     hadronic or leptonic side is the top; the current exporter does not perform
     that swap;
   - reco `O_lnu` is unavailable because the fitted neutrino four-vector is not
     persisted in the kinfit best tree.

   Do not quote a headline reco signed-angle or gen-to-reco retention result
   until these reco mappings are implemented and validated. Generator-level
   results are unaffected. See `docs/PHYSICS_CONVENTIONS.md` sections 4 and 10.

2. **The SM denominator template is not wired into this repository.** The SM
   ttH productions exist, but `configs/samples.yaml` does not yet record the
   pure-LR/RL SM cross sections and actual written-event totals, and
   `export_features.py` currently exports only the CPV-interference samples and
   writes `weight_sm = NaN`. Therefore `evaluate_fisher.py --nu0-from-abs` uses
   the absolute-interference histogram as a plumbing-only stand-in for
   `nu0`; it is not an SM prediction or a physics Fisher result.

## Kinfit / jet assignment stage

3. **Post-implementation kinfit performance tables pending.** As of
   2026-07-20, the production `TTHSemiLepKinFit` final selection uses
   `FinalSelectionMode=logchi2_plus_flavor` and `FlavorWeight=0.3`, i.e.
   `log(1+fit_chi2) + 0.3*signed_flavor_NLL`. The old fitprob/chi2-only
   selection is now only a configurable control mode. New official accuracy,
   recovered/destroyed, mass, delta-phi, and MVA-variable tables require
   rerunning the standard SLCIO samples with the new library and XML
   (`docs/KINFIT_JET_ASSIGNMENT.md`).

4. **Marlin finalization exits 134/139.** The kinfit processor may crash in
   finalization after writing a valid ROOT output. The wrapper accepts these
   exit codes only when the output is non-empty and
   `scripts/validate_kinfit_root.py` confirms the expected tree and branches.

## External inputs not delivered

5. **Event-selection MVA** not yet delivered. `selection.enabled: false` in
   all analysis configs. Interface frozen in `docs/MVA_INTERFACE.md`.
6. **Background tables** not yet delivered. ttZ reco production directories
   exist, while ttbb and other 6f are pending. Interface frozen in
   `docs/BACKGROUND_INTERFACE.md`.

## Technical limitations

7. `scripts/split_slcio.sh` and `scripts/merge_slcio.sh` need pyLCIO from the
   ZHH stack; if unavailable, use `--max-events` early stopping instead.
8. Fisher intervals from `scripts/evaluate_fisher.py` are local Gaussian
   approximations; a likelihood scan (`src/ilc_tth_cpv/likelihood.py`) is
   required for final intervals under the conditions in Project Note section
   2.11.
9. **Near-beam Ma-frame conditioning.** For the Ma production-plane basis,
   `frames.make_frame` rejects a collinear system when the beam-transverse x
   vector has norm at most `1e-12`. Stability just above that threshold is not
   yet covered by an automated toy test. This does not affect the current
   fixed-`lab_axes` baseline, but any Ma-style result must report frame
   failures and test the system-to-beam-angle dependence; see
   `docs/PROJECT_NOTE_FULL.md` section 2.4.

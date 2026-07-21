# SAMPLE_PROVENANCE

History and validation state of every registered sample. Machine-readable
fields live in `configs/samples.yaml`; this file carries the narrative.

## Production tree (2026-07-20)

All current samples live under one production root (path in
`configs/samples.yaml: meta.production_root`), organised as

```
production/<process>/<polarization>/<run_id>/
    generator/stdhep/       per-chunk .stdhep
    generator/sidecars/     per-chunk CPV weight sidecar CSV (CPV only)
    sgv/                    SGV common-baseline .slcio
    complete_reco/          kinfit-ready complete reco .slcio   <- analysis input
    manifests/  condor/  logs_and_dumps/  aida/
```

with `<process>` in `cpv_tth, sm_tth, sm_ttz` and `<polarization>` in
`eL.pR, eR.pL`. The CPV samples contain 80 chunks of 12500 sidecar events per
polarization. The 80 SM generator logs record 11505 written events in every LR
chunk (920400 total) and 11515 in every RL chunk (921200 total).

## ttH CPV |interference| production (primary signal sample)

- 1,000,000 generated events per polarization (80 chunks x 12500).
- Chain: Physsim stdhep -> SGV -> `complete_reco_kinfit_ready` slcio.
- Production validation (2026-07-20): all 80 chunks per polarization passed
  the kinfit-ready validator with 12499 usable events per chunk; zero missing,
  empty, or symlinked outputs. A small number of Marlin finalisation
  crashes (exit 134/139) are accepted because outputs validated and jobs
  returned 0.
- **Sidecar**: the CPV sidecar is a full event-level record (not only a sign):
  matrix elements (`me2_*`), differential pieces (`dsg_*`, `func_*`),
  validation angles, QED/phase weights, and kinematics (`shat, mtt, mt, mh,
  cos_h, phi_h, ...`). Column list: `configs/samples.yaml: meta.sidecar_columns`.
- **Alignment convention**: accepted-event-order matching — sidecar row i is
  the i-th usable LCIO event of the same chunk. Weights are kept external to
  the LCIO files. Spot checks confirmed `accepted_order_match=true` and
  `sidecar_covers_lcio=true` for SGV and complete reco.
- Generator physics validation is complete. The 2026-05-04 validation checked
  event accounting, sign balance, the signed integral, non-negative component
  weights, the matrix-element Cauchy bound, the finite-mixing-angle identity,
  and sidecar ordering. The 2026-07-20 production validation then checked both
  million-event helicity samples through SGV and complete reconstruction. The
  registered CPV samples are `physics-validated`.

## SM ttH and ttZ productions

The same chain and layout exist under `sm_tth/` and `sm_ttz/`. The SM event
count audit is complete: `N_written=920400` for LR and `921200` for RL. The
accepted LR BASES integration log
`TTHStudy_first_run/bases.tth_example_vtx_patched_1000.out` reports

```text
Total Cross section = 2.96055 +/- 0.00581374 fb
PolElectron=-1, PolPositron=+1, Ecm=550 GeV
```

No matching accepted SM eR.pL BASES integration was found. This matters
because the production guardrail requires a polarization-matched BASES
template/integration before an eR.pL production is normalised.

The complete-reco LCIO parameters are not authoritative cross-section
provenance. A checked LR file and a checked RL file both carry
`crossSection=296.0`, `beamPol1=-1`, and `beamPol2=+1`; the RL metadata are
therefore demonstrably generic, and 296.0 is inconsistent with the accepted LR
BASES result. The standard `stdhepjob_new` conversion exposes event IDs and
unit event weights but does not copy a cross section into LCIO run parameters;
direct extraction of the raw STDHEP/HEPRUP run record remains a valid audit.

For an unweighted SM sample, the exported per-event cross-section weight is

```math
w_{\mathrm{SM}}^{\mathrm{base}}=
\frac{\sigma_{\mathrm{SM}}}{N_{\mathrm{written}}}.
```

Luminosity and later polarization factors multiply this base weight when the
yield template is evaluated. `export_features.py --component sm` now exports
SM generator/reco kinematics and the angular/ML builders evaluate the same
observable/model on them. LR therefore provides a physical binned `nu0`. RL
exports `weight_sm_shape=1/N_written` but keeps `weight_sm=NaN` until its cross
section is frozen. The Fisher script requires a real SM template and has no
`|f1|` fallback.

Each chunk is an independent full-cross-section MC estimate. A one-chunk
template uses `sigma/N_written_chunk`; multiple chunk templates must be
averaged, not summed. Equivalently, concatenate all chunks only after changing
the event weight to `sigma/N_written_total`. ttZ is the first background
(interface: `docs/BACKGROUND_INTERFACE.md`).

## Kinfit + jet assignment stage

The `complete_reco` files are "kinfit-ready": they carry
`OutputErrorFlowJets6`, `RefinedJets6`, isolated leptons, and the SLD links
required by the `TTHSemiLepKinFit` processor. The assignment/fit stage is part
of THIS repository's pipeline — see docs/KINFIT_JET_ASSIGNMENT.md — and its
outputs live under `outputs/<analysis>/kinfit/`.

On 2026-07-22 the processor best tree was extended with
`nu_fit_{E,px,py,pz}` from the already fitted `FitOutcome.nuAfter`. The fit,
constraints, candidate ranking, and final score did not change. ROOT files
made before this update are rejected by the current validator and must be
regenerated for reco `O_lnu`.

## Historical validation sample

`tthcpv_absint_val_12500` (12500 events, single stdhep + 5-column sidecar) is
the sample behind the original generator observable theory study. It is
`superseded` for production work but remains the reference for cross-checking
the ported frame/angle/weight implementations. Its alignment needs the
physsim-log skip list (`requested the event N to be skipped`), which the
`ilc_tth_cpv.weights` module handles.

## Event counting rule

Every analysis records the bookkeeping chain

```
N_generated -> N_isolated_lepton -> N_valid_reconstruction
            -> N_kinfit_selected (accepted=1, fit_success=1)
            -> N_MVA_selected
```

and stores it in the output metadata.

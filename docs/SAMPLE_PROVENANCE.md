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

with `<process>` in `cpv_tth, sm_tth, sm_ttz`, `<polarization>` in
`eL.pR, eR.pL`, and 80 chunks of 12500 generated events each.

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
- Generator **physics** validation is still pending (KNOWN_ISSUES); the
  production is `method-development-ready`.

## SM ttH and ttZ productions

Same chain and layout under `sm_tth/` and `sm_ttz/`. The SM ttH samples will
provide the `weight_sm` yield templates; ttZ is the first background
(interface: docs/BACKGROUND_INTERFACE.md).

## Kinfit + jet assignment stage

The `complete_reco` files are "kinfit-ready": they carry
`OutputErrorFlowJets6`, `RefinedJets6`, isolated leptons, and the SLD links
required by the `TTHSemiLepKinFit` processor. The assignment/fit stage is part
of THIS repository's pipeline — see docs/KINFIT_JET_ASSIGNMENT.md — and its
outputs live under `outputs/<analysis>/kinfit/`.

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

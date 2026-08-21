# KinFit 全量生产与 MVA 接入 handoff（2026-08-04）

NECESSITY: 这份单一 handoff 固定 path、denominator、stage 和 fail-closed
join 合同，避免把不同生产分支、候选层级或旧 flat layout 混在一起。

## 1. 正式状态与 denominator

唯一正式 manifest 是：

```text
/afs/desy.de/user/z/zhangyuy/condorworkflow_kinfit_mva_inputs_20260731/parameters/job_plan.jsonl
```

workflow root 与两个正式 ROOT root：

```text
/afs/desy.de/user/z/zhangyuy/condorworkflow_kinfit_mva_inputs_20260731
/data/dust/user/zhangyuy/analysis/tth/events_physsim/kinfit/mva_inputs_20260731
/data/dust/user/zhangyuy/analysis/tth/events_whizard/kinfit/mva_inputs_20260731
```

Physsim 四组是 all-channel complete-reco；Whizard 两组使用已经经过
`nIso=1` 的 reco skim denominator。比例定义为
`accepted/input`、`fit_success/input`、`fit_success/accepted`。

| group | files | input | accepted | fit_success | accepted/input | fit_success/input | fit_success/accepted |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tth-sm`（Physsim all-channel） | 158 | 1,974,649 | 734,477 | 734,443 | 0.371953 | 0.371936 | 0.999954 |
| `tth-cpv`（Physsim all-channel） | 160 | 1,999,840 | 744,618 | 744,578 | 0.372339 | 0.372319 | 0.999946 |
| `ttz`（Physsim all-channel） | 158 | 1,974,702 | 671,065 | 671,005 | 0.339831 | 0.339801 | 0.999911 |
| `ttbb`（Physsim all-channel） | 145 | 1,812,137 | 661,289 | 661,139 | 0.364922 | 0.364839 | 0.999773 |
| `6q`（Whizard `nIso=1`） | 179 | 17,412 | 17,412 | 17,396 | 1.000000 | 0.999081 | 0.999081 |
| `4q2l`（Whizard `nIso=1`） | 350 | 2,429,494 | 2,429,490 | 2,427,720 | 0.999998 | 0.999270 | 0.999271 |
| **total** | **1,150** | **10,208,234** | **5,258,351** | **5,256,281** | **0.515109** | **0.514906** | **0.999606** |

## 2. 输入、输出与文件身份

Physsim source directories are the four reviewed branches
`sm_tth/`, `cpv_tth/`, `sm_ttz/`, and `ttbb/`, with polarization
`eL.pR` or `eR.pL`. The complete absolute input patterns are:

```text
/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/<pol>/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Ptth.Gphyssim.<pol>.I01234_0.<chunk>_sgv.slcio
/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/cpv_tth/<pol>/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Ptthcpv.Gphyssim.<pol>.I01234_0.<chunk>_sgv.slcio
/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_ttz/<pol>/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Pttz.Gphyssim.<pol>.I01234_0.<chunk>_sgv.slcio
/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/ttbb/<pol>/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Pttbb.Gphyssim.<pol>.I01234_0.<chunk>_sgv.slcio
```

Their output is:

```text
events_physsim/kinfit/mva_inputs_20260731/
  {tth-sm,tth-cpv,ttz,ttbb}/{eL.pR,eR.pL}/<job_key>/kinfit_<job_key>.root
```

The corresponding XML, log, validation JSON and provenance JSON form the
five-file set; the 24 controlled recoveries additionally have
`kinfit_<job_key>.pathology-override.json`. Do not infer identity from a flat
`chunkN` filename.

Whizard 的 `nIso=1` reco skim denominator 使用以下 source branches：

```text
/data/dust/user/zhangyuy/analysis/tth/events_whizard/production/6f_niso1_workflow/complete_reco/
  complete_reco_6f_niso1_E550-TDR_ws.P6f_<mask>.Gwhizard-3_1_5.<pol>.I<process>.<shard>[_partN].slcio

/data/dust/user/zhangyuy/analysis/tth/events_whizard/production/6f_niso1_workflow/complete_reco_no_truejet/
  complete_reco_6f_niso1_no_truejet_E550-TDR_ws.P6f_<mask>.Gwhizard-3_1_5.<pol>.I<process>.<shard>[_partN].slcio
```

The output pattern is:

```text
events_whizard/kinfit/mva_inputs_20260731/{6q,4q2l}/<job_key>/kinfit_<job_key>.root
```

The manifest/job key uses `4f2l`, while the output directory is deliberately
`4q2l`; this is an adapter mapping, not a new physics label. The logical shard
`I410035.0` is represented by `_part1` and `_part2`; they remain one logical
shard for split and weight bookkeeping, while their physical files and event
ranges are distinct.

## 3. Frozen physics and tree roles

- Fit kinematics/covariance: `OutputErrorFlowJets6`.
- Flavor ranking: `RefinedJets6`.
- Exactly one isolated electron or muon; then TopN=10 base assignments with SLD
  enumeration.
- Constraint mode: `fullMass4C`; final score:
  `log1p(chi2) + 0.3 * signed_flavor_NLL`.
- `accepted` is the processor's event-level best-selection entry after the
  six-jet/single-lepton/assignment gate; `fit_success` requires fitter error
  zero plus finite, non-negative fit probability. It is a technical status,
  not a physical mass or fit-quality acceptance gate.
- Best tree is one selected row per accepted event. Candidate tree retains the
  persisted TopN/SLD candidate pool and is for candidate diagnostics, not a
  second event denominator.

## 4. Issues and evidence boundaries

**CONFIRMED**

- The 24 legacy failures were controlled float32 validator false rejections:
  old absolute `|E²-p²|` shell threshold, no ROOT/XML rewrite, explicit
  override/provenance, retained failed attempts.
- A: 24 recovered jobs are the validator false-rejection set; this is a file
  count, not an event count.
- B: 34 / 5,256,281 selected `accepted && fit_success` events are the
  high-energy diagnostic set; 25 of those 34 are in the 24 override jobs.
  The strata include the combined `tth-sm+tth-cpv` diagnostic `4 / 1,479,021`
  (SM `1 / 734,443`, CPV `3 / 744,578`) and Whizard `6q` `10 / 17,396`.
  The baseline training signal remains SM `tth` only; these are diagnostics,
  not formal cuts.
- C: within the persisted formal TopN=10 + SLD candidate pool, 24/34 events
  have no successful candidate with `0 < E <= 550`, while 10/34 have a
  low-energy successful candidate but the formal score selects the high-energy
  row. This statement does not cover assignments outside that persisted pool.
- `fit_success` is a loose technical gate; the best tree contains only accepted
  events. Exit 134/139 is accepted only after processed-count, schema, tree and
  provenance checks prove a complete output.

**UNRESOLVED**

- The hashed production `.so` has been audited for path/hash, but its runtime
  binding to the inspected private-source build is not proven. No private
  library is part of the production contract.
- The end-to-end exporter/MVA adapter and one-to-one event join remain
  unverified.

## 5. MVA readiness

Remote repository `HEAD` is
`94cfc854216d055503603e7c252b126d283d6383`, and
`scripts/link_kinfit_inputs.sh` is tracked by that commit and correctly links
the two formal ROOT roots. In the current worktree, however,
`scripts/mva/`, `configs/mva_samples.yaml`, and `configs/mva_semilep.yaml` are
uncommitted changes; `analysis_olD_lr.yaml` is additionally untracked. A clean
checkout at that HEAD does not contain these MVA files, so they cannot be
attributed to the commit. The MVA feature pipeline is therefore not yet a
committed implementation.

The existing remote `scripts/export_features.py` is branch/tree-compatible,
but hard-codes old flat `kinfit_<sample>_chunkN.root` names and a signal/chunk
model. It cannot directly consume the 1,150 nested directories above. A
manifest-driven path adapter is required before production MVA extraction.

Join contract:

1. Every ROOT is joined to its original manifest `input_path`; never infer the
   LCIO input from a basename.
2. Use ROOT `event_index`, not best-tree ordinal. Existing `event_number`
   mismatch is currently counted but must become fail-closed.
3. A global event ID must include `generator/sample/polarization/job_key/
   physical_part/event_index`; `chunk * 1e6 + local` can collide.
4. Apply manifest `4f2l -> 4q2l` only at the output-path adapter.
5. Split by logical shard; `_part1` and `_part2` of `I410035.0` cannot leak
   across train/validation/test.

Feature stage and first model:

- The exporter combines raw/prefit `OutputErrorFlowJets6` jets/lepton with
  fitted `nu_fit_*`: this is a hybrid stage, not an all-postfit feature set.
- First MVA version: best-tree `accepted && fit_success` only. Candidate tree
  remains diagnostic.
- Keep fit probability, chi2 and neutrino energy as diagnostics. If `E_nu` is
  used in the model, use a robust/log transform and report sensitivity with and
  without the 34 events; do not create a formal energy cut.

## 6. Classes, weights and CP safety

- SM `tth` is the signal class. CPV is not mixed into the training signal; it is
  a separate CP-safety or parameterized-model study.
- Backgrounds: `ttz`, `ttbb`, Whizard `6q`, and Whizard `4q2l`.
- Preserve the Physsim all-channel versus Whizard `nIso=1` denominator split.
- `weight_phys` belongs to the future MVA manifest and is not currently
  implemented in the production `job_plan`. Define it as
  `weight_phys = xsec * L / Ngen`, where `L` is helicity-specific integrated
  luminosity and `Ngen` is the corresponding generated-sample denominator
  before any reco `nIso`, accepted, fit-success, split or skim selection (use
  an explicit generator-denominator field when available). Keep physical
  weights separate from class/helicity-balanced `weight_train`; never use a
  training-balancing weight as a physics yield.
- Preserve logical-shard split bookkeeping and do not double count physical
  parts.
- Signed CP observables are excluded from the baseline classifier. Report model
  behavior by helicity, lepton flavor and domain (Physsim/Whizard).

## 7. Minimum integration acceptance checklist

- [ ] One path smoke for each of the six groups, using the exact manifest row.
- [ ] Manifest has 1,150 unique `job_key` rows and exactly one physical path per
      row (with explicit `_partN` rows and logical-shard identity).
- [ ] ROOT/SLcio join passes one-to-one on `event_index`; event-ID duplicate
      count is zero and mismatches fail closed.
- [ ] Required tree/schema checks pass; all exported features are finite.
- [ ] Train/validation/test overlap by logical shard is zero, including
      `I410035.0_part1/part2` handling.
- [ ] Weighted totals close to `σ × L` by class, polarization and domain
      using the future MVA manifest's `weight_phys`; this is not a claim that
      the current production `job_plan` contains or reproduces those weights.
- [ ] MVA sensitivity is reported with and without the 34-event diagnostic
      subset; this is not a formal selection.
- [ ] Join score is one-to-one for every exported `accepted && fit_success`
      best-tree row; fit-fail rows are not exported and candidate rows are not
      silently added to the event denominator.

## 8. Existing evidence and paths

- Production contract and six-group accounting:
  [`20260731_all_complete_reco_kinfit_production.md`](../work_remote_edit/20260731_kinfit_mva_inputs/20260731_all_complete_reco_kinfit_production.md)
- Production issues and validator/recovery closure:
  [`20260731_kinfit_all_complete_reco_issues.md`](../work_remote_edit/20260731_kinfit_mva_inputs/20260731_kinfit_all_complete_reco_issues.md)
- Neutrino pathology report:
  [`kinfit_neutrino_pathology_investigation_20260804.md`](kinfit_neutrino_pathology_investigation_20260804.md)
- Final remote global summary outputs:

```text
/data/dust/user/zhangyuy/analysis/AI_PIPELINES/20260803_neutrino_pathology/global_summary/
  global_summary.json
  global_summary_groups.csv
  global_summary_jobs.csv
  global_summary.md
```

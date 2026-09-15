# Generator $m_{t\bar t}$ run record — 2026-09-12

Status: **completed diagnostic; immutable output recorded; lepton-finder outputs recorded**. This record
captures the externally verifiable framework and supplied results of the
generator comparison run. It is not a production or formal physics-result
claim beyond the checks listed here.

## Inputs and frozen analysis

- Physsim input (chunk 1, STDHEP):
  `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/generator/stdhep/E550-Test.Ptth.Gphyssim.eL.pR.I01234_0.1.stdhep`
- Whizard input (chunk 0, physical LCIO file):
  `/pnfs/desy.de/ilc/prod/ilc/mc-2025/generated/550-TDR_ws/8f/E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_0.0.slcio`
- Input manifest:
  `/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/records/input_manifest/generator_chunk1_vs_chunk0.json`
- Stage/readers: generator-level `pyLCIO.UTIL.LCStdHepRdr` for Physsim and
  explicit `MCParticle` collection for Whizard; no fallback reader or
  collection.
- Observable: hard-pair $m_{t\bar t}$, 50 bins from 340 to 425 GeV.
  Normalization uses each sample's accumulated raw in-window histogram
  integral, with the sample cross section divided by that integral.
- Code commit: `e2d8558` on branch `reco_performance`.

## Command and runtime shape

The command sourced `/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh`,
prepended the `root-config` libdir and repository `src` to `PYTHONPATH`, and
then ran `compare_generator_mtt.py`. The exact shell transcript/environment
was not supplied in this record. A malformed `~/.bashrc` export warning was
observed and is unrelated to the run.

## Result

Successful immutable run ID/path:

`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/generator_mtt/20260912_physsim_chunk1_whizard_chunk0_r3`

| sample | processed / with $m_{t\bar t}$ | raw in-window | sigma / normalized area |
|---|---:|---:|---:|
| Physsim chunk 1 | 12498 / 12498 | 11946 | 2.96055314955 fb |
| Whizard chunk 0 | 12500 / 12500 | 12499 | 2.206536 fb |

Output artifact types: PNG, PDF, ROOT, raw CSV, normalized CSV, and counters
JSON. Visual inspection of the PNG passed. A local mirror is present at:

`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/generator_mtt/20260912_physsim_chunk1_whizard_chunk0_r3`

The study manifest now also records the Whizard event-metadata integration
uncertainty, `0.0009175807936117053 fb`. Future plots display both cross
sections with their MC integration uncertainties and uncertainty-based
precision. The ROOT legend strings use TLatex `#pm` so they render visually as
`Physsim (2.9606 ± 0.0058 fb)` and `Whizard (2.20654 ± 0.00092 fb)`.
This display-only follow-up does not
change the full-precision normalization or regenerate the immutable r3
artifacts above.

### Final generator MC-error plot

The final MC-error plot is recorded at
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/generator_mtt/20260912_physsim_chunk1_whizard_chunk0_mc_errors_r2`
with local mirror
`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/generator_mtt/20260912_physsim_chunk1_whizard_chunk0_mc_errors_r2`.
Visual QA passed. Labels render with TLatex `#pm` as
`Physsim (2.9606 ± 0.0058 fb)` and `Whizard (2.20654 ± 0.00092 fb)`.
The full-precision areas remain 2.96055314955 fb and 2.206536 fb, with
processed counts 12498 and 12500. Source evidence is
`configs/mva_normalization_sources.yaml` (Physsim 2.96055 ± 0.00581374;
source `/data/dust/user/zhangyuy/analysis/physsim/run/canonical_sm_tth/bases.root`)
and first-event metadata in `I410213_0.0.slcio` (Whizard
`crossSection=2.206536054611206`,
`crossSectionError=0.0009175807936117053`). The relevant code commits are
`1da8488` and `a3236ab`.

## Failed attempts and correction

Two immutable attempts were empty: the original `20260911` output path failed
because a STDHEP EOF exposed a false null proxy; `20260912` revision `r2`
failed because a Whizard EOF exposed a false null proxy. The one-line EOF/null
predicates were corrected in commits `2e5a650` and `e2d8558`. Focused tests
covered two passes after the first correction and four passes after the second.
These failures are recorded as one causal issue, not as separate attempts.

## Validation, residual risk, and review target

- Source-confirmed result facts are the paths, counters, areas, binning,
  artifact types, visual inspection, commits, and test-pass counts above.
- Interpretation: the matching normalized areas and full hard-pair counters
  support the intended single-sample normalization and reader guards.
- No raw command transcript, runtime manifest, file hashes, or test log path
  was supplied; those remain the primary reproducibility gap.
- Review target: confirm the immutable output contents against the manifest,
  verify the 50-bin 340–425 GeV axis and area checks from the counters/ROOT
  artifacts, and retain the failed-attempt diagnosis as a candidate issue
  record for reviewer confirmation.

NECESSITY: The explicit input paths, manifest, reader/collection, denominator,
and immutable run ID prevent a successful-looking comparison from being
reproduced with substituted samples or changed normalization semantics.

NECESSITY: Recording the EOF/null-proxy correction and focused-test counts
prevents the two empty immutable attempts from being mistaken for valid zero-
event results.

## Lepton Finder Condor

Source-confirmed run: Condor cluster `5109135`, 10 jobs, submitted at commit
`546bf2d`, with run root
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260912_finder_chunks1_10`.
All Marlin runtime manifests report exit `-6` (known accepted tail abort),
while physical LCIO outputs exist with exact event counts for chunks 1..10:
`12498, 12499, 12498, 12499, 12498, 12498, 12499, 12499, 12499, 12495`.
Each chunk passed a separate
`validate_lepton_branch.py --max-events 20` check for exact event keys,
required collections, and PFO fingerprints; records are at
`finder_chunk_i_run/pfo_validation_20.json`. Condor history exit `1` was from
the post-Marlin in-process validator failing to import pyLCIO under
`getenv=false`; this is not classified as reconstruction failure. Runtime
manifest `output_validation` fields are absent, so external counts plus the
20-event semantic checks are the available output evidence.

## Whizard reconstruction smoke

The retained log `/tmp/reco_perf_whizard_reco_smoke_20260911/run_0/marlin.log`
shows SIGSEGV at `SLDCorrection::end()` line 3711 after processing/output,
not mid-event. The output contains 4 events for `max_records=5`, consistent
with the observed N→N−1 boundary. `source/build/lib` and `source/lib` ZHH
processor hashes are both `d50ef394...`, ruling out library divergence for
this run. `AI_PIPELINES/RUNNING_STACK.md` already records the same
post-output tail crash (`corrupted size` / segmentation) on the accepted
lepton workflow; the previous summary calling this an unexplained new bug
was incorrect because that record was not consulted in time. The current-SGV
input differs from the irrecoverable historical SGV, but the observed stack
point is the already-recorded finalizer crash. No Marlin rerun is required for
the accepted files.

## Physsim lepton efficiency/purity tables — 10 chunks

This is the completed 10-chunk Physsim eL.pR lepton-table run. The contract
keeps the historical selection and counting semantics unchanged and joins the
complete-reco and Finder branches by `(source_file_id, run, event)`.

- Complete-reco inputs (chunks 1..10):
  `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/complete_reco/complete_reco_kinfit_ready_E550-Test.Ptth.Gphyssim.eL.pR.I01234_0.{chunk}_sgv.slcio`.
- Finder inputs (chunks 1..10):
  `/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260912_finder_chunks1_10/finder_chunk_{chunk}.slcio`.
- Source IDs were `physsim_chunk_1` through `physsim_chunk_10`.
- Tagger collections: `ISOElectrons`, `ISOMuons`; Finder collection:
  `Isolep`. The four frozen legacy selection/counting implementations were
  reused unchanged from `reco_performance_study/legacy`:
  `isolepton_eff_purity_v2077.py`, `isolepton_finder_eff_purity_v2077.py`,
  `count_hbb_ttbar_had_iso_pass.py`, and
  `count_hbb_ttbar_dilep_pass.py`.
- Code-side recovery: commit `4f318bc` explicitly reuses frozen legacy
  stdout. The first full joined scan reached EOF but produced zero Finder/DI/MU
  denominators and no derived outputs. Audit showed `other_pid/unknown`
  overwrote the MU state (and could silently pollute SEMI/MU); commit
  `445371e` fixes the state parser. Fifteen focused tests passed, and parser
  smoke matched all four Finder blocks. A second `nohup` recovery (PID
  `3724125`) completed and generated the formal outputs.
- Events processed: `124982`.

Raw failed-recovery evidence is at
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10/recovery_failed_parser.log`;
successful-recovery evidence is at
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10/recovery.log`.
The local mirror contains the corresponding files at
`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10/recovery_failed_parser.log`
and
`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10/recovery.log`.
The attempts remain part of this continuous record, not separate task records.

### Formal outputs

Remote output directory:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10`.
Local mirror:
`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10`.
The seven nonempty formal artifacts are `tagger_stdout.txt`,
`finder_stdout.txt`, `lepton_counts.json`, `lepton_purity.csv`,
`lepton_multiplicity.csv`, `semileptonic_lepton_table.png`, and
`dileptonic_lepton_table.png`; associated recovery logs are kept alongside
the run outputs.

Purity raw counts/denominators:

| branch/category | denominator | from_topW | from_tau | from_hadron |
|---|---:|---:|---:|---:|
| Tagger SEMI EL | 11727 | 10122 | 1432 | 173 |
| Tagger SEMI MU | 11233 | 9897 | 1143 | 193 |
| Tagger DI EL | 5514 | 4793 | 668 | 53 |
| Tagger DI MU | 5485 | 4890 | 533 | 62 |
| Finder SEMI EL | 10619 | 9693 | 876 | 50 |
| Finder SEMI MU | 10455 | 9613 | 804 | 38 |
| Finder DI EL | 5026 | 4623 | 383 | 20 |
| Finder DI MU | 5152 | 4750 | 387 | 15 |

Multiplicity denominators: `HBB had=32752`, `semileptonic_e=10611`,
`semileptonic_mu=10569`, `semileptonic_tau=10513`, `DI NO_TAU=3393`, and
`HAS_TAU=4174`. Derived percentages are in the CSV/PNG outputs; each purity
category row sums to its denominator.

### Validation and operating policy

- All seven formal targets were present and nonempty; JSON reports
  `events_processed=124982`.
- All eight purity denominators were positive and origin sums equal their
  denominators. Both PNGs were visually readable. Remote-to-local `rsync`
  completed for the small formal output directory.
- The parser-overwrite failure did not change physics selections, collections,
  join key, denominators, or frozen legacy logic in the corrected run.
- Future large-sample work follows the user's policy: perform only a smoke
  test, then deliver the script and complete command; do not run large samples
  without explicit authorization.

NECESSITY: Recording exact inputs, source IDs, collections, join key, frozen
scripts, and denominators prevents silent branch mixing or changed physics
definitions.

NECESSITY: Recording the parser-overwrite failure and focused validation
prevents zero-denominator output from being mistaken for a physical result.

## Delivery state

The terminal was intentionally left open during delivery. No further job
monitoring was done after the completion checks.

Known doubts: runtime manifests lack `output_validation`; the current-SGV
Whizard input is not the irrecoverable historical SGV; exact command
transcripts/file hashes are not retained in this record.

Optional review directions: source the ZHH environment before launching the
Python validator in future Condor submissions; teach the Whizard wrapper to
accept `-11` only after explicit output/event/collection validation. No review
is required for this record, and no further direction applies.

## 2026-09-13 whole-chunk Whizard reco submission and TopN follow-up

The corrected contract uses whole input chunks; the obsolete 6000+6500 split
is not used. Current production does not run kinfit. The canonical future
kinfit variant is `steering/tth_semilep_kinfit.xml` with TopN10,
`RefinedJets6` flavor, and `OutputErrorFlowJets6` fit output; historical
Top180 is only a later scan control. Local code commits are `7efeb78` and
`d1a3c56`; remote commits are `bb63e9b` and `8e14626`. Manifest validation
passed. The 19-event smoke passed SGV/XML/output, nine required collections,
ordered unique event keys, and runtime XML-library-hash checks. Marlin's
`-11` occurs at `SLDCorrection::end()` after output and is accepted only after
content validation. The first validator attempt failed because a pyLCIO banner
contaminated stdout before JSON parsing; a minimal sentinel fix plus a new run
ID passed, and the old attempt was rejected.

DAGMan cluster `5111722` failed because `KRB5CCNAME` was not inherited by the
scheduler universe: four SGV nodes each exhausted six retries, four reco nodes
were futile, no compute node queued, DAG status was 1, and `rescue001` remains.
Four authorized direct-chain jobs were submitted as cluster `5111735`; each
does whole SGV then validated whole reco. At 12:52:48 all four were Running
(QDate 12:50:37), with zero Idle/Held/Removed and empty stdout/err. Monitoring
stopped after two minutes as requested. Run root:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_flavor/20260913_whizard_direct_chain_4x12500_8e14626`.

The TopN figure's original scripts are
`scripts/run_weekly_ppt_0608_kinfit_controls_20260625.py` and
`scripts/make_weekly_ppt_0608_assets_20260625.py`, with CSV
`topn_extended_accuracy_runtime_wide_with_top1_top5_20260626.csv`. It used
full6000 and accuracy denominator830 (`sa3.6`), so it is a low-statistics
historical reference. After reco completion, redo it over four chunks with a
common-event denominator and canonical Top10 settings.

Known doubts: only the two-minute Running checkpoint is recorded; no job
completion is claimed. Optional review directions: none.

## 2026-09-13 truth composition after one-lepton selection

Completed on the common 124,982-event, 10-chunk Physsim eL.pR complete-reco sample after truth `H_to_bb`. Tagger is `n(ISOElectrons)+n(ISOMuons)==1`; Finder is `Isolep==1` from the existing validated `lepton_counts.json`. Percentages use a separate selected four-class denominator per method.

| method | direct semilep e/μ | semilep τ | fully hadronic | dileptonic | selected total |
|---|---:|---:|---:|---:|---:|
| Tagger | 19,798 (76.792987%) | 2,622 (10.170280%) | 380 (1.473954%) | 2,981 (11.562779%) | 25,781 |
| Finder | 18,696 (70.834281%) | 2,969 (11.248769%) | 1,720 (6.516633%) | 3,009 (11.400318%) | 26,394 |

Inputs are the ten `complete_reco_kinfit_ready_...{1..10}_sgv.slcio` files under `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/complete_reco/`; Finder counts came from `/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260912_lepton_tables_chunks1_10/lepton_counts.json` (SHA-256 `cb6d476f5be25e0df42a980bea46d7518faddd37498b6e71fa9846672d5d9fd3`). The frozen truth/counting implementation is `reco_performance_study/legacy/count_hbb_ttbar_had_iso_pass.py` (SHA-256 `93ecaaf863890d73ce6741cc97946451904b3dc0cc7f254ac104a62a2374d7e2`); local code commit is `5fabb29`, remote execution snapshot/output tag is `e45b62f`.

Authoritative NAF output: `/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260913_lepton_truth_composition_chunks1_10_e45b62f_r2/result/`; local mirror: `/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/physsim_leptons/20260913_lepton_truth_composition_chunks1_10_e45b62f_r2/result/`. CSV SHA-256 `a9be5abf4b3fb0ddee118e5c65fd259a9069b4479fe0455cc57e1d1db4ab859e`; JSON SHA-256 `2587eb2a9139ad8791cdb1783c35b8c96266d25bac7bdd746db05d84a571859a`; remote/local hashes agree.

The ≤20-event smoke was Condor cluster `5114852`, output root `/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/physsim_leptons/20260913_lepton_truth_composition_condor_smoke20_e45b62f`, and passed bounded output/JSON checks. Formal Condor cluster `5114858` submitted at 21:52:05, executed at 21:52:27, terminated normally with return value 0 at 21:59:38; `job.err` was empty. Setup-wrapper cluster `5111742` failed before usable output because nounset rejected an environment variable during ZHH setup. The minimal correction was no-nounset setup sourcing, validated in local commit `d95a579`; physics selections, collections, denominators, and truth functions were unchanged.

Validation: `events_processed=124982`; Tagger closure is true and its four counts sum to 25,781; Finder four counts sum to 26,394 and percentages sum to 100%; `semilep_lep=0` in both methods. `unclassified` is not independently recorded by the Finder source JSON. NECESSITY: Separate method denominators and frozen truth functions prevent a selection/provenance change from masquerading as a composition difference.

Known doubts: Finder unclassified selected-event count is not recorded by the source JSON. Optional review directions: none.
## 2026-09-14 historical assignment-mass overlay

Request: compare `Price2014 + signed flavor` PREFIT with `kinfit + signed
flavor` POSTFIT in the same W/top/H figure. The large-data version is
deferred until the new jet figures are available.

- Input: local archived mirror
  `/Users/tdbrylf/Documents/NAF_tth/TRASH_NONCANONICAL_LOCAL_20260704/local_dirs/naf_outputs/kinfit_softmass_sld_on_full6000_20260618/assignment_accuracy/kinfit_flavor_rerank_selected.csv`, SHA-256 `c58e7e...`. The NAF original was not rehashed because the SSH control socket lacked permission.
- Entry point: `scripts/reco_performance/plot_historical_assignment_masses.py`; focused tests are in the corresponding `tests/` file. Contract is `source_mode=sld_enumeration`, exactly two methods/columns, strict common `event_index` (830 events), 60 bins, W 40–130, top 100–240, H 40–210, weight `1/830`. This is an offline rerank diagnostic, not canonical Top10; distinct candidate methods are allowed.
- Output: `/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/jet_assignment_masses/20260914_historical830_price_prefit_vs_kinfit_postfit_r2/` (PNG/PDF/summary/manifest). The initial unsuffixed directory is an empty preserved failed attempt caused by missing matplotlib. The final script uses existing gnuplot; no dependency was installed.
- Validation: common 830/830, all finite, combo differs 325; W under/in/over is 9/815/6 vs 19/800/11; top is 1/829/0 vs 0/830/0; H is 0/830/0 for both; all closure values are 1.0. Three tests, `py_compile`, diff-check, and visual QA passed.
- Artifact hashes: PNG `79114260...`, PDF `782aae7d...`, summary `17bde26f...`, manifest `a73569bb...`.

NECESSITY: The dedicated entry point prevents the old same-selection pre/post function from being misused for a cross-method/cross-stage diagnostic.

## 2026-09-14 Physsim 1k assignment-mass diagnostic

This follows the historical Whizard-830 overlay. Input was old Physsim chunk0:
first 1000 events, filtered truth 159, candidate ROOT rows 4380. The initial
run incorrectly used the assignment truth map as an attach gate, leaving only
3 common events; it produced no formal plot. NAF failed log:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/jet_assignment_masses/20260914_physsim1k_price_prefit_vs_kinfit_postfit_truth.run.log`
(SHA prefix `8d63d5a...6359`).

The frozen recovery used a presence-only assignment map with status
`not_evaluated_for_mass_plot`, and reused legacy
`load_price2014/build_flavor_prior_map/attach_scores_and_truth/select_best_by_mode`.
No `truth_match_*` fields were generated and no assignment-accuracy result is
claimed. Final NAF output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/jet_assignment_masses/20260914_physsim1k_price_prefit_vs_kinfit_postfit_truth`; local mirror:
`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/jet_assignment_masses/20260914_physsim1k_price_prefit_vs_kinfit_postfit_truth`.

Counts: truth 159; candidates 4380; presence 150 events/1500 pairs; attach
4380; flavor prior 4380 rows/150 events with ROOT fallback 0; Price selected
150 (fit success 146, failed 4); kinfit selected 150 (failed 0); common 150;
combo differs 55. The joined 150 source-aware keys were unique; rerank rows
300; no truth-match fields. Nine histogram closures were 150/150. Truth
medians were W=80.4114, top=170.5541, H=125 GeV.

Entry point: `scripts/reco_performance/plot_physsim1k_assignment_masses.py`;
tests: `tests/test_physsim1k_assignment_masses.py`. Final `run.log` SHA prefix
`cf374d3...308f`. Five focused tests, `py_compile`, `git diff --check`, and
PNG visual QA passed.

NECESSITY: Source-aware joining prevents filtered-LCIO/ROOT index drift.

NECESSITY: The truth parent-p4 curve prevents a nominal reference from being
mislabeled as truth.

NECESSITY: Presence-only assignment removes the irrelevant accuracy gate while
preserving exact scores and tie-breaking.

Known doubts: this is a historical small sample, not canonical large
production; assignment truth was intentionally not evaluated. Optional review
direction: redo this frozen diagnostic on large production candidate outputs
when available.

Known doubts: the remote NAF original was not rehashed. The large-data version is intentionally deferred. Optional review directions: none.

## 2026-09-14 Physsim ten-chunk mass comparison and Whizard truth-match gate

The Physsim large-sample mass plot was produced by direct reuse of the ten
existing ROOT inputs; SGV, complete reco, truth filtering, and kinfit were not
rerun. Inputs are the ten ROOT/provenance pairs under
`/data/dust/user/zhangyuy/analysis/tth/events_physsim/kinfit/mva_inputs_20260731/tth-sm/eL.pR/physsim__tth-sm__eL.pR__I01234_0_{1..10}`.
The entry point is `scripts/reco_performance/plot_physsim10_assignment_masses.py`
(SHA-256 prefix `b1ebfd2d...`). The authoritative formal POSTFIT curve is read
from the best tree; the offline PREFIT curve is the legacy mass-constraint-only
plus signed-flavor rerank. No truth line or assignment-accuracy claim is made.

| quantity | value |
|---|---:|
| authoritative best rows | 46,415 |
| fit-success rows | 46,414 |
| candidate rows | 1,099,930 |
| common denominator | 46,414 |
| failed source event | chunk8, run1, event6976 (index6976) |
| key policy | source-aware key |
| histogram closure checks | 6 |
| smoke validation | 20 events |

Final NAF output is
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/jet_assignment_masses/20260914_physsim_chunks1_10_existing_root_b1ebfd2d`;
local mirror is
`/Users/tdbrylf/Documents/NAF_tth/naf_outputs/reco_performance_study/outputs/jet_assignment_masses/20260914_physsim_chunks1_10_existing_root_b1ebfd2d`.
Eight focused tests, `py_compile`, diff-check, and visual QA passed. Superseded
attempts are retained only as evidence: `3d199445` heterogeneous CSV failure,
`77e82cdf` ambiguous diagnostic, and `31082e57` stopped before output.

The old 21 mismatch was not reproduced: exact-double mass-row/SLD56 and
persisted-float187 comparisons gave zero combo mismatches. This is a known
diagnostic doubt; the formal curve is unaffected.

Whizard recovery files are structurally valid at 4x12,500 and were not
rerun. Source audit confirmed that missing `TrueJetPFOLink` collections are
skipped and counted, while a present-but-empty collection yields all-zero Dice
overlaps and is accepted by the legacy `min_dice=0.0` condition. The user
approved an atomic event gate requiring all six Dice matches to satisfy
`Dice>0`, for both `RefinedJets6` confusion-matrix matching and
`OutputErrorFlowJets6` assignment truth matching. Rejected events will be
counted separately; this changes the truth-matched denominator and must not be
silently folded into the result. Whizard analysis has not yet been submitted;
Top10 only, never Top180.

NECESSITY: Direct ROOT reuse preserves the established production products and
avoids an unnecessary reco/kinfit rerun.

NECESSITY: The source-aware key prevents cross-chunk event-index collisions.

NECESSITY: The all-six positive-Dice gate prevents arbitrary zero-overlap
permutations from entering truth-labelled accuracy or confusion denominators.

Known doubts: the old 21-mismatch diagnostic discrepancy remains unexplained;
the Whizard analysis is pending submission. Optional review directions: none.

## 2026-09-14 Whizard positive-Dice gate, submission, and local consolidation

Source-confirmed implementation commit: `ec727b412c5e55c9606eb17697b8ecf946e841ae`.
Changed surfaces are `report_whizard_jet_cm.py`,
`report_whizard_assignment_common.py`, and `test_whizard_jet_analysis.py`.
The event identity is the four-field key
`(source_file_id, local_event_index, run, event)`.  The independent atomic
gate requires all six assigned Dice values to be strictly positive, separately
for `RefinedJets6` confusion-matrix matching and `OutputErrorFlowJets6`
assignment matching; zero-Dice permutations are rejected and counted rather
than entering a truth denominator.

Validation was source-confirmed: 10/10 focused tests, `py_compile`, and
`git diff --check` passed.  Relation smoke output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_flavor/20260914_whizard_positive_dice_smoke_4field_14cd253`;
accepted=2, CM events=2, CM jets=12; summary SHA-256
`60924855ce36ace56f211bc498aeee0036a4ed5c45db27a02845ac200731ed14`.
Top10 smoke output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_assignment/20260914_whizard_top10_positive_dice_smoke20_84cbb7d`;
processed=19, best=7, candidates=110, successful=106; validated ROOT SHA-256
`c2784feba3dfa53dcfc692889f079a6bc86fcd3c6b6452ad59f99088f5bfce8f`.

The four whole-chunk canonical Top10 processes were submitted as Condor
cluster `5121180`, run root
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_assignment/20260914_whizard_top10_4x12500_posdice_039354d`.
The submission command reconstructed from the generated `submit.sub` and
runtime manifest was (the original interactive shell transcript was not
retained):

```sh
condor_submit /data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_assignment/20260914_whizard_top10_4x12500_posdice_039354d/condor/submit.sub \
  -append repo_root=/data/dust/user/zhangyuy/tth-cpv-observable-ilc-reco-performance \
  -append reco_root=/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_flavor/20260913_whizard_reco_recovery_4x12500_36f05b6/reco \
  -append run_root=/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_assignment/20260914_whizard_top10_4x12500_posdice_039354d \
  -terse
```

At the two-minute checkpoint all four were `Running` (about 134 s), stderr was
empty, and no job was Held.  Monitoring stopped at the user's requested
checkpoint.  These candidates are still running; no completion or final
physics result is claimed.

The local consolidation is
`/Users/tdbrylf/Documents/NAF_tth/plots_ild_cern_version`, including
`PRODUCT_INDEX.md`, the full 54 MB Physsim10 `selected_rows` CSV, outputs,
scripts, tests, and the mirrored record.  The Whizard formal products and
final CM/accuracy/mass figures remain pending until cluster `5121180`
completes.

The local `reco_performance` branch was pushed non-forcibly to
`git@github.com:yyzhang666/tth-cpv-observable-ilc.git`; the remote branch
contains implementation commit `ec727b4` and this continuous study record.

NECESSITY: The four-field key prevents cross-file/local-index collisions in
the recovered multi-chunk sample.

NECESSITY: The all-six positive-Dice gate prevents zero-overlap arbitrary
permutations from inflating truth-labelled CM and assignment denominators.

Known doubts: cluster `5121180` completion and its final readable products
remain pending. Optional review directions: none.

## 2026-09-14 Whizard phase-1 formal products and wrapper ABI incident

Phase-1 Whizard products are complete. The four-source input ceiling was
4x12,500 readable events; assignment ROOT validation reached 4x12,499. The
all-six assigned-Dice `>0` gate was applied atomically to both
`RefinedJets6`/`TrueJets` confusion matching and `OutputErrorFlowJets6`/`TrueJets`
assignment matching, using `(source_file_id, local_index, run_number,
event_number)` keys.

CM output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_flavor/20260914_whizard_cm_4x12500_posdice_cf291a8`.

| events analyzed/read | truth selected | relation eligible | nonpositive Dice | accepted six-positive | CM jets |
|---:|---:|---:|---:|---:|---:|
| 50,000 | 12,839 | 9,252 | 1,728 | 7,524 | 45,144 |

Assignment output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_assignment/20260914_whizard_accuracy_4x12499_posdice_cf291a8`.
The common denominator is 4,730 source-aware events.

| method | W | top | H | all |
|---|---:|---:|---:|---:|
| mass-constraint-only | 0.820930 | 0.553066 | 0.465751 | 0.396406 |
| kinfit-only | 0.821353 | 0.578224 | 0.526427 | 0.465751 |
| mass-constraint-only + signed flavor | 0.844820 | 0.612262 | 0.514165 | 0.464059 |
| kinfit + signed flavor | 0.849683 | 0.630444 | 0.571882 | 0.521776 |

The selected common-event CSV SHA-256 is
`885a86c45f0ce64255af5edb60c9148ffc0bcfdd2813234b6c13d7bde7dbc540`.

Mass overlay output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/jet_assignment_masses/20260914_whizard_4x12499_common4730_cf291a8`.
It uses the separate 4,730-event denominator and compares
mass-constraint-only + signed flavor PREFIT with authoritative kinfit + signed
flavor POSTFIT; no truth curve is claimed.

| object | prefit mean [GeV] | postfit mean [GeV] |
|---|---:|---:|
| W | 80.7241 | 80.4878 |
| top | 167.6137 | 166.6739 |
| H | 121.0997 | 119.1855 |

Exact commands, schema, input/output hashes, and scripts are retained in the
CM/assignment/mass manifests. Local mirrors are under
`/Users/tdbrylf/Documents/NAF_tth/plots_ild_cern_version`.

Confirmed wrapper ABI bug: under Condor `getenv=false`, system-Python PyROOT
was imported before setup, causing `libcppyy.so: undefined symbol:
PyObject_Vectorcall`. The correction was an explicitly sourced py311/root
validation child. No release/resubmit was made; legacy cluster `5121180`
remains Held by design. Evidence: focused pytest 38, NAF unittest 13,
clean-environment smoke best 7/candidates 110, and primary visual inspection
of all three PNGs. Commit/push was
`cf291a801cf7ebb9013573d20920155b76d51ba7` on `reco_performance`; worktree
clean. Homebrew Python lacked pytest, so primary local pytest was unavailable;
this is an environment limitation, not a code failure.

NECESSITY: The explicit py311/root child prevents system-Python PyROOT ABI
contamination from invalidating post-processing validation.

Known doubts: CM and assignment intentionally differ in collections, input
ceilings and denominators; `setup.sh` is nonzero in strict shell mode but the
explicit runtime was validated. Phase-2 Top1/5/10 has not started and no
active analysis process remains. Optional review directions: none.

External validation details: the four reco inputs were
`.../whizard_I410213_{0,1,2,3}_complete_reco.slcio` under
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_flavor/20260913_whizard_reco_recovery_4x12500_36f05b6/reco`;
the four validated ROOT inputs are under
`.../whizard_top10_4x12500_posdice_039354d/root` and each has expected event
count 12,499. Their SHA-256 prefixes/full values retained by the manifest are:
`fc8c6c25a56bfad225e91978cbc1aa75de0c274e5f6e5f6701a6204a047b74e4`,
`b9af8d31f7ded8c6ae53e32876b1525f659be962c1ed56f9a14c8010400969fd`,
`eab734d92abd4b01d2f9a922b4abfac557cf9e0026823208958a40df0a2eb9ca`,
`51edffbadd9a86b818e1c360ee5b6037fbd79998068f519e9441f20713048afe`.
The assignment script hash is
`e2845dd0d7472fc30507a75f54ca6192c5576ddfe26fc85f49855adfc7c73d1f`; the
legacy CM and rerank hashes are
`e54d3103c5e1dbb9edcf060b65b87923cab53dd54762f035d5ec57409f2555dd` and
`e3ee6146ec3b9eb8b0f9628cf8f66fcacca0611c3dffb5eb17ea4c50e3e42dd3`.
The CM script hash is
`1a8c6e30dd24caf6494e0118b8617ac75cff42cb623e594c3b29f61121d66f14`; CM
summary hash is `920e27a3d968940768ea209ca0f16ae892abab6f06947b4f61d8e5930decd744`.

## 2026-09-14 assignment-accuracy pool/label contract correction (resolved 2026-09-15)

Historical common830 used full180 base-combo+SLD, `sa3.6`, and legacy `min_dice=0`; its mass-only and kinfit-only values were respectively `0.2494/0.1675/0.2434/0.1253` and `0.2795/0.2012/0.2759/0.1602` for W/top/H/all. Current common4730 used RefinedJets6 signed-flavor-preselected Top10+SLD, `sa2.6`, and all-six `Dice>0`, so its `0.8209/0.5531/0.4658/0.3964` and `0.8214/0.5782/0.5264/0.4658` values are within-signed-flavor-Top10 diagnostics, not flavor-free methods or a same-method large-stat replacement. Truth direct matcher orientation/index audit found no bug. The correction is complete in new immutable output `20260914_whizard_full180_first2_common4730_sa2p6_v1` (commit `b7d2717`): only the first two bars were recomputed from full180; the last two were copied byte-for-value from the Top10 diagnostic. Counts, validation, and paths are recorded in the completion section below. The obsolete Top1/5/10 runtime phase was canceled and not submitted. Known doubts: positive-Dice and sample/SA effects are not separately quantified, and the historical vintage used different SA/Dice settings. Optional review direction: none.

## 2026-09-15 Whizard full180 correction — completed

The requested correction is complete under implementation commit `b7d2717`.
Only the first two bars were recomputed, using all 180 base assignments plus
SLD for the immutable common set of 4,730 source-aware event keys. The final
two bars were copied byte-for-value from the validated signed-flavor Top10
result; they were not reranked. This is a new output and does not overwrite
the earlier diagnostic.

| display label | internal mode | candidate pool/stage | W | top | H | all |
|---|---|---|---:|---:|---:|---:|
| mass constraint-only [full180] | `price2014_prefit` | full180 base+SLD, prefit | 0.316068 | 0.226850 | 0.305497 | 0.162791 |
| kinfit-only [full180] | `kinfit_chi2_only` | full180 base+SLD, successful fit | 0.338055 | 0.261734 | 0.370613 | 0.220719 |
| mass constraint-only + q_flavor minimize [signed-flavor-preselected Top10] | `price2014_prefit_bcharge1p00` | signed-flavor Top10, prefit | 0.844820 | 0.612262 | 0.514165 | 0.464059 |
| q_reco minimize [signed-flavor-preselected Top10] | `kinfit_flavor_rerank` | signed-flavor Top10, postfit | 0.849683 | 0.630444 | 0.571882 | 0.521776 |

Numerator counts for the four rows are respectively `(1495,1073,1445,770)`,
`(1599,1238,1753,1044)`, `(3996,2896,2432,2195)`, and
`(4019,2982,2705,2468)` for W/top/H/all. Exact source filter counts were
1,168/1,168/1,168/1,226. The ≤20-event smoke processed 19 events, found 180
unique combinations per event, and had 19/19 first-ten overlap with the
existing Top10 workflow. Four formal Condor jobs were cluster `5125333`, all
exited 0; formal first-ten overlap was 4,730/4,730.

Authoritative NAF output:
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/whizard_jet_assignment/20260914_whizard_full180_first2_common4730_sa2p6_v1`

Local mirror:
`/Users/tdbrylf/Documents/NAF_tth/plots_ild_cern_version/jet_assignment_accuracy/whizard4x12499_full180_first2_common4730_sa2p6_v1`

Validation evidence: 44 focused tests passed; `py_compile` and
`git diff --check` passed; image visual QA passed. The executed authority XML
is preserved in the output and differs from the repository XML only by a
trailing blank line. The `.bashrc` invalid-export warning was external and
had no effect. The obsolete Top1/5/10 runtime phase was canceled and no such
jobs were submitted.

NECESSITY: Recomputing only the mislabeled first two bars over full180 fixes
the candidate-pool contract without changing the frozen signed-flavor
reference bars or overwriting prior evidence.

Known doubts: the full180 rows use the current SA2.6 and positive-Dice/common-
key contract, while the historical 830-event reference used older SA3.6 and
min-Dice-zero settings; they are therefore a controlled correction, not an
identical vintage reproduction. Optional review directions: none.

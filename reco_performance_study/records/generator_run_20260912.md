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

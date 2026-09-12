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

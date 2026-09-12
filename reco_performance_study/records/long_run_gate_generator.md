# Generator $m_{t\bar t}$ long-run gate

Status: **NAF diagnostic**.  This record authorizes only the generator full
analysis.  It does not authorize Finder, SGV, reco, or kinfit production.
Formal output is planned on NAF; local files are only a dereferenced mirror.

## Current Long-Run Gate (seven questions)

1. **What exact input enters?**

   Physsim input is canonical raw STDHEP chunk 1 (~12500 events):
   `/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/generator/stdhep/E550-Test.Ptth.Gphyssim.eL.pR.I01234_0.1.stdhep`.
   Whizard input is physical file chunk 0 (12500 events):
   `/pnfs/desy.de/ilc/prod/ilc/mc-2025/generated/550-TDR_ws/8f/E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_0.0.slcio`.
   The formal run must fail on a missing or unreadable input; no input
   substitution is allowed.

2. **What reader, stage, and source definition are frozen?**

   Physsim is read directly with `pyLCIO.UTIL.LCStdHepRdr` at generator
   stage.  Whizard is read through the explicit `MCParticle` collection at
   generator stage.  There is no fallback reader or collection.  The hard
   particle-pair rule is frozen from the old script:
   `pdg_exact_no_same_pdg_parent_prefer_parents_minus11_plus11_then_daughters_then_first`.
   No generator-status filter is applied.

3. **What observable, axis, and denominator are used?**

   The observable is hard-pair $m_{t\bar t}$, with the old script's hard
   `±6` rule and 50 bins spanning 340--425 GeV.  Raw entries are accumulated
   across the chosen file of each physical sample before one normalization per
   sample.  The width-scaled normalization uses the accumulated raw histogram
   integral inside 340--425 GeV (`sigma / hist.Integral()`); it is not
   normalized by all processed events.  `n_processed` and `n_with_mtt` remain
   separate completeness counters, and out-of-window events are excluded from
   that histogram integral.

4. **What normalization and validation target must hold?**

   The exact cross sections are Physsim `2.96055314955 fb` and Whizard
   `2.206536 fb`.  The normalized, width-integrated histogram areas must equal
   those values exactly for each chosen physical sample.  The formal
   comparison uses one file per sample.
   Smoke evidence at
   `/tmp/reco_perf_generator_smoke_20260911/output` records the relevant
   chosen-file subset as 5/5 events with $m_{t\bar t}$ for each file.  Visual
   smoke inspection was okay.

5. **What is produced, and where is the authoritative output?**

   This is a read-only analysis producing ROOT/CSV/PNG/PDF/JSON.  The planned
   authoritative NAF directory is
   `/data/dust/user/zhangyuy/analysis/tth/reco_performance_study/outputs/generator_mtt/20260911_physsim_chunk1_whizard_chunk0`;
   immutable records live under the study's `records` directory.  A run ID
   directory and its record must not be overwritten.  Local output is only a
   dereferenced mirror and is not physics truth.

6. **What producer/consumer collections or libraries are involved?**

   Producer/consumer collection questions are **N/A**: this is not a Marlin
   collection chain.  Consumed generator structures are the direct STDHEP
   records through `LCStdHepRdr` and the explicit Whizard `MCParticle`
   collection; no LCIO output collection is produced.  Runtime library scope
   is pyLCIO/ROOT from `/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh`.
   No ZHH processor library is involved.  The formal run must record the
   exact sourced environment, `root-config --libdir`, `PYTHONPATH` (with the
   root libdir prepended while preserving its existing value), and loaded
   library hashes.  Smoke evidence confirms that root-config libdir prepending
   while preserving `PYTHONPATH` was required; an exact formal environment
   manifest has not yet been captured because no formal run was executed.

7. **What falsifies or invalidates the run, and what does this gate permit?**

   Invalidate on any non-full hard-pair success without classification, wrong
   or fallback MC collection, normalized areas different from the exact
   single-sample sigmas (including an erroneous `Nchunk×sigma` result), the old `3.1137` label, missing/unreadable
   inputs or outputs, bin-axis mismatch, or output/record overwrite.  These
   are hard failures, independent of fraction.  The gate permits only the
   this one-file-per-sample generator diagnostic after the formal run records its exact runtime and
   immutable run directory; it does not promote the smoke to a formal result.

## Implementation and evidence identity

- Code branch: `reco_performance`; code commit currently documented as
  `7c94185d27bffa42a9cd961d8b61a1f473070244`; generator implementation commit
  `319ae7f`.
- Frozen observable source: old generator comparison script
  `compare_mtt_from_two_slcio_xsec.py` (the study input manifest records its
  SHA-256).
- Evidence actually available before this record: the bounded smoke summary
  above.  No formal NAF job, output, or environment capture was run while
  writing this gate.

NECESSITY: The seven-question gate prevents a statistics-heavy generator run
from silently changing input completeness, truth reader/collection,
denominator, normalization, runtime library, output identity, or diagnostic
versus formal-result status.

## Residual risk / review target

The formal as-run runtime manifest, exact output file list, hashes, and final
chunk-1/chunk-0 event counters remain to be captured during the authorized run.
Reviewer should confirm those artifacts and the exact area/bin-axis checks
before treating the comparison as a formal result.

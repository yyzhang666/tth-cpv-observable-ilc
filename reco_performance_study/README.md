# Reco performance study contract

This branch owns a reproducible refresh of four established diagnostics.  It
does not redefine their physics selections.  The authoritative input contract
is `study_inputs.json`.

## Frozen scope

- Generator comparison: canonical Physsim `eL.pR` STDHEP chunks 1--10 versus
  the four Whizard `I410213_{0,1,2,3}.0` files.  The readers are respectively
  `UTIL.LCStdHepRdr` and the explicit `MCParticle` collection.  There is no
  generator-status cut.  The hard-top rule and 50 bins over [340, 425] GeV are
  frozen.  The complete file list is accumulated before applying exactly one
  cross-section normalization per physical sample.
- Leptons: Physsim complete-reco chunks 1--10 contain 124982 events.  Tagger
  collections are `ISOElectrons` and `ISOMuons`.  The study-owned Finder branch
  must start from the matching SGV file, reproduce the complete-reco upstream
  PFO/track/cluster/MC-relation prefix, and align results by
  `(source_file_id, run, event)`.  The four historical truth/denominator scripts
  remain separate and are never silently unified.
- Jet flavor: predicted rows, true columns, energy-Dice one-to-one TrueJet
  matching, and column normalization.  The frozen collections are
  `MCParticlesSkimmed`, `RefinedJets6`, `TrueJets`, and `TrueJetPFOLink`.
- Jet assignment: preserve the historical TopN180 base-combo pool, SLD/neutrino
  enumeration, fullMass4C/ISR/soft-mass settings, `require_converged=False`,
  `truejet_direct` truth, and `log1p(max(0,chi2))+0.3*flavor` score.

Current SGV is explicitly a controlled variant; the exact executable that made
the 2025 reference file is not recoverable.  No output from the current SGV may
be labelled an exact reproduction of that historical sample.

## Directory interface

On NAF the study root is
`/data/dust/user/zhangyuy/analysis/tth/reco_performance_study`.  The fixed layout
contains `scripts`, `functions`, `steering/{generator,sgv,reco,kinfit}`,
`outputs/{generator_mtt,physsim_leptons,whizard_jet_flavor,whizard_jet_assignment}`,
and `records/{contract,input_manifest,runtime_manifest,xml_diff,validation,handoff}`.
Scripts and common pure functions link to the clean `reco_performance` repo
worktree.  Steering files are immutable task-owned snapshots, not links to
shared XML.

## Gate status

Only pure-function regression tests and a bounded generator smoke may run
before the long-run gate is recorded.  Finder/SGV/reco/kinfit production and
all runs above 1000 events remain pending explicit gate review.

## Lepton branch execution

`steering/physsim_finder_branch.xml` is generated from the byte-identical
reference snapshots.  It preserves the current complete-reco prefix through
PFO corrections, overlay removal, and TrueJet; it then uses the old
`MyFastJetProcessor` and `MyIsolatedLeptonFinderProcessor` definitions.  A
bounded smoke exposed that the legacy Finder omitted `JetCollection` and thus
requested its unavailable default `JetsForIsolation`; the generated XML adds
the single explicit producer/consumer adapter `JetCollection=JetsForIsolep`.
Its
input, output, maximum-record, and skip values are mandatory render tokens;
the output mode is `WRITE_NEW`.

`run_finder_branch.py` sources
`/data/dust/user/zhangyuy/analysis/tth/ZHH/setup.sh`, records setup/template/as-run
XML and loaded `MARLIN_DLL` hashes, and refuses existing outputs.  With the
Python 3.11 venv, the directory returned by `root-config --libdir` must be
prepended to `PYTHONPATH`, followed by this repository's `src`, while retaining
the setup-provided path.  Before the long-run gate the wrapper permits at most
20 events unless the caller explicitly records and supplies the long-run
override.

The post-run validator checks every required collection for each bounded event
and compares a deterministic numeric/object-count fingerprint of
`PFOsWithoutOverlayCheated` against complete-reco.  The analysis joins the two
branches only by `(source_file_id, run, event)`, invokes the four frozen legacy
truth/counting implementations separately, accumulates integer counts, and
only then calculates table percentages.

## Whizard replay scaffold

The Whizard replay uses the four complete physical files
`I410213_{0,1,2,3}.0`.  SGV runs one whole file at a time with `N_SKIP=0`, its
actual full count, the unchanged default RNG settings, a copied local steer and
local `fort.17`, a unique working directory, and a serial lock.  It is labelled
`current-SGV controlled variant`; it is not an exact reproduction of the
irrecoverable historical SGV runtime.

Complete reco is rendered only from the frozen 2026-06-16 XML and split as
`skip=0,max=6000` plus `skip=6000,max=actual_count-6000`.  Kinfit is rendered
only from the frozen 2026-06-18 XML and keeps TopN180, fullMass4C, ISR 125.6,
SLD enumeration, soft mass, diagonal covariance, and scale factors 1.6/3.6/1.1.
Each replay uses a new job-local directory, XML, log, runtime manifest, and
output.  A kinfit exit 134 can only be accepted when the explicit override is
present, both required ROOT trees exist with nonzero counters, and the
candidate tree contains at least one `fit_success==1` row.

## Necessity statements

- NECESSITY: immutable steering snapshots prevent a later shared-XML edit from
  changing the documented as-run configuration.
- NECESSITY: refusing to replace existing study links prevents this setup step
  from overwriting user-owned study files.
- NECESSITY: manifest validation prevents accidental chunk, cross-section, join
  key, or runtime-hash drift before an expensive run.
- NECESSITY: the explicit Whizard `MCParticle` lookup prevents collection
  fallback from silently changing the generator truth definition.
- NECESSITY: the 20-event default execution gate prevents an unreviewed XML
  variant from becoming a production Marlin run.
- NECESSITY: event-key and upstream-PFO equality checks prevent combining
  Finder and Tagger values from different events or preprocessing branches.
- NECESSITY: explicitly binding Finder `JetCollection` to the FastJet output
  prevents the observed `DataNotAvailableException` for `JetsForIsolation`.
- NECESSITY: whole-file SGV plus a serial job-local steer prevents shared-steer
  races and RNG restarts caused by splitting a physical input.
- NECESSITY: allowed-diff XML rendering prevents a replay shard from silently
  adopting current TopN10 or angle-scale 2.6 production settings.
- NECESSITY: validated exit-134 handling prevents treating a crashed or empty
  kinfit ROOT file as a successful shard.

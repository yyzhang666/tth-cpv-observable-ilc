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

## Necessity statements

- NECESSITY: immutable steering snapshots prevent a later shared-XML edit from
  changing the documented as-run configuration.
- NECESSITY: refusing to replace existing study links prevents this setup step
  from overwriting user-owned study files.
- NECESSITY: manifest validation prevents accidental chunk, cross-section, join
  key, or runtime-hash drift before an expensive run.
- NECESSITY: the explicit Whizard `MCParticle` lookup prevents collection
  fallback from silently changing the generator truth definition.

# Reserved diagnostic: selected kinfit pair with truth q/qbar orientation

This is intentionally not implemented yet.

## Question

Keep the production-selected `idx_W1/idx_W2` pair and the reconstructed jet
four-momenta, but replace the Weaver orientation with a validated truth
quark/antiquark label. Compare that result with the current Weaver-oriented
distribution.

## Why it is reserved

The Physsim SLCIO files contain potentially useful collections including
`TrueJets`, `TrueJetMCParticleLink`, `TrueJetPFOLink`, `RecoMCTruthLink`, and
`MCParticlesSkimmed`. Existing project guardrails explicitly say that Physsim
TrueJet truth is sample-dependent and must be validated before use. A direct
`TrueJetMCParticleLink` ancestry vote must not silently be treated as a correct
signed label.

## Proposed validation sequence

1. Verify that `OutputErrorFlowJets6[i]` and `RefinedJets6[i]` refer to the same
   physical jet for every selected event.
2. Establish a reco-jet to truth-parton association using PFO overlap or a
   validated `RecoMCTruthLink` aggregation.
3. Require the selected pair to match the two direct daughters of the same
   hadronic W.
4. Read the signed direct daughter PDG IDs to assign q versus qbar.
5. Report separately:
   - selected-pair truth purity;
   - truth-orientation efficiency;
   - Weaver orientation accuracy among truth-valid selected pairs;
   - sign-flip rate and its dependence on `w_orientation_status` and margin.
6. Rebuild only the matched-event migration diagnostic. Do not replace the
   inclusive-gen/full-reco total-retention metric with this matched subset.

Implementation should start only after a few dumped Physsim events establish
that the chosen truth relation is reliable.

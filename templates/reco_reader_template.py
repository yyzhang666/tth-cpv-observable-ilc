#!/usr/bin/env python3
"""TEMPLATE — how to read a kinfit-ready reconstructed event, step by step.

The analysis input is the `complete_reco_kinfit_ready` SLCIO production
(configs/samples.yaml). The collection contract is FIXED
(docs/KINFIT_JET_ASSIGNMENT.md):

    OutputErrorFlowJets6   jet p4 + covariance  (kinematics INTO the fit)
    RefinedJets6           Weaver flavor tags + ymerge (ParticleID 'yth')
    ISOElectrons/ISOMuons  isolated lepton
    JetSLDLink6/SLDNuLink6 SLD / neutrino links
    MCParticlesSkimmed     truth (validation ONLY)

Jet assignment + kinematic fit is NOT done here — it is the standard
TTHSemiLepKinFit stage (scripts/run_kinfit_assignment.sh). Observables use
that stage's logchi2_plus_flavor_x0p3 selected candidate. This template only
shows where the raw reco information lives.

Run (needs pyLCIO -> source env/setup.sh first):
    python3 templates/reco_reader_template.py --slcio /path/to/complete_reco_kinfit_ready_*.slcio
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv import frames
from ilc_tth_cpv.slcio import (
    four_momentum,
    get_collection,
    get_pid_parameters,
    iter_slcio_events,
    list_collections,
    pdg,
)

FIT_JETS = "OutputErrorFlowJets6"     # kinematics for the fit
FLAVOR_JETS = "RefinedJets6"          # Weaver flavor / ymerge source
ISO_LEPTONS = ("ISOMuons", "ISOElectrons")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slcio", required=True)
    parser.add_argument("--max-events", type=int, default=2)
    args = parser.parse_args()

    for i, evt in enumerate(iter_slcio_events([Path(args.slcio)],
                                              max_events=args.max_events)):
        # -------------------------------------------------------------------
        # Step 1: event identity. Gen/reco matching uses accepted-event-order
        # alignment with the sidecar of the SAME chunk (docs/SAMPLE_PROVENANCE.md):
        # the i-th usable event here corresponds to sidecar row i+1.
        # -------------------------------------------------------------------
        print(f"\n=== usable event #{i} run={evt.getRunNumber()} event={evt.getEventNumber()}")

        # Step 2: list collections — first thing to do on any new file.
        print("collections:", ", ".join(list_collections(evt)))

        # -------------------------------------------------------------------
        # Step 3: isolated lepton (semileptonic selection requires exactly
        # one; flavour/charge feed the O_b conventions).
        # -------------------------------------------------------------------
        for name in ISO_LEPTONS:
            col = get_collection(evt, name)
            if col is None:
                continue
            for k in range(col.getNumberOfElements()):
                lep = col.getElementAt(k)
                p4 = four_momentum(lep)
                print(f"  {name}: E={p4[0]:.2f} GeV charge={lep.getCharge():+.0f}")

        # -------------------------------------------------------------------
        # Step 4: fit-input jets. p4 + covariance come from FIT_JETS ONLY.
        # -------------------------------------------------------------------
        fit_jets = get_collection(evt, FIT_JETS)
        if fit_jets is None:
            print(f"  {FIT_JETS} missing — wrong input file?")
            continue
        for k in range(fit_jets.getNumberOfElements()):
            jet = fit_jets.getElementAt(k)
            p4 = four_momentum(jet)
            print(f"  fit jet {k}: E={p4[0]:7.2f} m={frames.invariant_mass(p4):6.2f}")

        # -------------------------------------------------------------------
        # Step 5: flavor information. Weaver scores (incl. signed b/bbar)
        # come from FLAVOR_JETS via the 'weaver' PID algorithm; ymerge values
        # (y45, y56, y67 ...) via the 'yth' PID algorithm. NEVER read these
        # from OutputErrorFlowJets6.
        # -------------------------------------------------------------------
        weaver = get_pid_parameters(evt, FLAVOR_JETS, "weaver")
        for k, scores in enumerate(weaver):
            top3 = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
            print(f"  flavor jet {k}: " + " ".join(f"{n}={v:.3f}" for n, v in top3))
        yth = get_pid_parameters(evt, FLAVOR_JETS, "yth")
        if yth and yth[0]:
            interesting = {k: v for k, v in yth[0].items() if k in ("y45", "y56", "y67")}
            print(f"  ymerge (yth): {interesting}")

        # -------------------------------------------------------------------
        # Step 6: jet assignment + kinematic fit -> NOT here.
        # Run: bash scripts/run_kinfit_assignment.sh --config ... --chunk N
        # Then read the TTHSemiLepKinFit tree (selected candidate, fitchi2,
        # fitprob, final_selection_score, fit_success, slots
        # W1/W2/b_had/b_lep/H_b1/H_b2) and require accepted=1 &&
        # fit_success=1 for physics.
        # -------------------------------------------------------------------

        # -------------------------------------------------------------------
        # Step 7: truth (validation only — never in reco-level selection).
        # -------------------------------------------------------------------
        mc = get_collection(evt, "MCParticlesSkimmed")
        if mc is not None:
            n_top = sum(1 for k in range(mc.getNumberOfElements())
                        if abs(pdg(mc.getElementAt(k)) or 0) == 6)
            print(f"  MCParticlesSkimmed present, top-like entries: {n_top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""TEMPLATE — how to read a generator event, step by step.

This is a commented walk-through for the student. It re-uses the shared
library (src/ilc_tth_cpv); do NOT copy-paste physics code out of here —
import it. The authoritative origins of every step are listed in
docs/CODE_PROVENANCE.md.

Run (needs pyLCIO -> source env/setup.sh first):
    python3 templates/generator_reader_template.py --max-events 5
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ilc_tth_cpv import angles, frames, weights
from ilc_tth_cpv.histograms import SignedHistogram
from ilc_tth_cpv.objects import identify_semileptonic_truth
from ilc_tth_cpv.slcio import four_momentum, open_stdhep

# ---------------------------------------------------------------------------
# Step 0: sample paths. In real analysis code these ALWAYS come from
# configs/samples.yaml — hardcoded here (one production chunk) only so the
# template is standalone. Large-data paths are the only external paths
# allowed in this repository.
# ---------------------------------------------------------------------------
PROD = Path(
    "/data/dust/user/zhangyuy/analysis/tth/events_physsim/production/"
    "cpv_tth/eL.pR/I01234_0/generator"
)
CHUNK = 0
STDHEP = PROD / "stdhep" / f"E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.{CHUNK}.stdhep"
SIDECAR = PROD / "sidecars" / f"E550-Test.Ptthcpv.Gphyssim.eL.pR.I01234_0.{CHUNK}.tthcpv_me.csv"
PHYSSIM_LOG = None  # production sidecars are accepted-event-order aligned; no skip log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-events", type=int, default=5)
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Step 1: read the CPV weight sidecar for this chunk.
    # Production convention: sidecar row i corresponds to the i-th usable
    # event (accepted-event-order matching). The historical validation sample
    # additionally needs the JSFHadronizer skip list from the physsim log —
    # parse_skipped_events_from_log handles that case.
    # -----------------------------------------------------------------------
    sidecar = weights.read_sidecar(SIDECAR)
    skipped = weights.parse_skipped_events_from_log(PHYSSIM_LOG)
    aligned = weights.align_sidecar_to_stdhep(sidecar, skipped)
    print(f"sidecar={len(sidecar)} skipped={len(skipped)} aligned={len(aligned)}")

    # Always validate before use: sign consistency, |w| = sigma/n, etc.
    report = weights.validate_signed_weights(aligned)
    assert report["ok"], report["problems"]

    # -----------------------------------------------------------------------
    # Step 2: open the stdhep file and loop events.
    # -----------------------------------------------------------------------
    reader = open_stdhep(STDHEP)
    hist_ow = SignedHistogram.phi_binning(36)  # theory-study binning

    for i, row in enumerate(aligned):
        if i >= args.max_events:
            break
        col = reader.readEvent()
        if col is None:
            break
        mc_list = [col.getElementAt(k) for k in range(col.getNumberOfElements())]

        # -------------------------------------------------------------------
        # Step 3: identify the hard-process particles.
        # Rules (ported from the theory study): first non-self-parented
        # particle of the target PDG; direct children for decays; W daughters
        # follow self-links and generator-internal codes (91-99).
        # -------------------------------------------------------------------
        truth = identify_semileptonic_truth(mc_list)
        # truth.higgs / top / antitop / top_b / antitop_bbar
        # truth.wjet_quark / wjet_antiquark  (light quark / antiquark, same W)
        # truth.lepton / neutrino            (leptonic W side)

        # -------------------------------------------------------------------
        # Step 4: build the frame. Choices: "lab", "higgs_rest", "ttbar_rest".
        # Delta-phi observables use the LAB-AXES basis (theory-study primary
        # convention): boost, then phi = atan2(py, px) against the fixed lab
        # axes. The production-plane basis (frames.make_frame) is reserved
        # for the Ma2018 sign observables.
        # -------------------------------------------------------------------
        rest_p4 = frames.rest_p4_for_frame(
            "higgs_rest",
            four_momentum(truth.top),
            four_momentum(truth.antitop),
            four_momentum(truth.higgs),
        )
        if rest_p4 is None:
            continue

        # -------------------------------------------------------------------
        # Step 5: boost + evaluate (E, cos_theta, phi) for the two W
        # daughters, then the signed angle
        #   O_W = wrap(phi_quark - phi_antiquark)   (particle - antiparticle).
        # -------------------------------------------------------------------
        q_p4 = four_momentum(truth.wjet_quark)
        qbar_p4 = four_momentum(truth.wjet_antiquark)
        if q_p4 is None or qbar_p4 is None:
            continue  # event has a leptonic W on both sides
        q = frames.boost_only_angles(q_p4, rest_p4)
        qbar = frames.boost_only_angles(qbar_p4, rest_p4)
        if q is None or qbar is None:
            continue
        o_w = angles.delta_phi(q[2], qbar[2])

        # -------------------------------------------------------------------
        # Step 6: fill the SIGNED histogram with event_weight_signed.
        # Theory-study normalisation: signed bin contents in fb; the
        # |w| histogram and per-bin signed fraction come for free.
        # -------------------------------------------------------------------
        w_signed = row["event_weight_signed"]
        hist_ow.fill(o_w, w_signed)
        print(f"event {row['event']}: O_W={o_w:+.4f} rad  w={w_signed:+.4g} fb "
              f"E_q={q[0]:.1f} E_qbar={qbar[0]:.1f}")

    # -----------------------------------------------------------------------
    # Step 7: inspect the result. For plots use ilc_tth_cpv.plotting
    # (line-only style, matching the theory-study galleries).
    # -----------------------------------------------------------------------
    print(f"\nsigned integral = {hist_ow.integral_signed():+.6g} fb")
    print(f"abs integral    = {hist_ow.integral_abs():.6g} fb")
    fractions = hist_ow.local_signed_fraction()
    print(f"max |local signed fraction| = {max(abs(f) for f in fractions):.3f}")
    print("\nangle sanity: wrap(pi) =", angles.wrap_phi(math.pi), "(equals -pi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

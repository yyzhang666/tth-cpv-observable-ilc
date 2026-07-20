"""Physics object identification in generator MCParticle lists.

PDG navigation logic ported from the theory-study scripts. Object naming
follows docs/DATA_SCHEMA.md.

Pair-ordering convention (theory-study "Original Phi" family, frozen in
docs/PHYSICS_CONVENTIONS.md §4): pairs are ordered particle - antiparticle.
For the hadronic W this means the light QUARK (PDG > 0) versus the light
ANTIQUARK (PDG < 0) from the same W decay — matching the strongest
theory-study observable `delta_phi_light_quark_antiquark`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .slcio import pdg, vec_to_list

LIGHT_PDGS = {1, 2, 3, 4, -1, -2, -3, -4}
LIGHT_QUARKS = {1, 2, 3, 4}
LIGHT_ANTIQUARKS = {-1, -2, -3, -4}
CHARGED_LEPTONS = {11, 13, -11, -13}
NEUTRINOS = {12, 14, -12, -14}
GENERATOR_INTERNAL = {90, 91, 92, 93, 94, 95, 96, 97, 98, 99}

# Ma2018 hadronic-W analyzer sets (sign-observable study only):
WPLUS_DOWNTYPE_ANALYZER = {-1, -3}   # dbar, sbar from W+
WMINUS_DOWNTYPE_ANALYZER = {1, 3}    # d, s from W-


def parents(mc) -> list:
    try:
        return vec_to_list(mc.getParents())
    except Exception:
        return []


def daughters(mc) -> list:
    try:
        return vec_to_list(mc.getDaughters())
    except Exception:
        return []


def has_parent_with_pdg(mc, target_pdg: int) -> bool:
    return any(pdg(parent) == target_pdg for parent in parents(mc))


def find_hard_particle(mc_list: Iterable, target_pdg: int):
    """First non-self-parented particle of target_pdg (theory-study rule)."""
    candidates = []
    for idx, mc in enumerate(mc_list):
        if pdg(mc) != target_pdg:
            continue
        if has_parent_with_pdg(mc, target_pdg):
            continue
        candidates.append((idx, mc))
    if not candidates:
        return None
    with_daughters = [(idx, mc) for idx, mc in candidates if daughters(mc)]
    return (with_daughters or candidates)[0][1]


def choose_direct_child(parent, target_pdg: int):
    if parent is None:
        return None
    children = [child for child in daughters(parent) if pdg(child) == target_pdg]
    if not children:
        return None
    with_daughters = [child for child in children if daughters(child)]
    return (with_daughters or children)[0]


def w_direct_final_daughters(w) -> list:
    """Follow W self-links and generator-internal codes to the real daughters."""
    if w is None:
        return []
    out = []
    for child in daughters(w):
        child_pdg = pdg(child)
        if child_pdg is None:
            continue
        if abs(child_pdg) in GENERATOR_INTERNAL:
            out.extend(w_direct_final_daughters(child))
        elif child_pdg == pdg(w):
            out.extend(w_direct_final_daughters(child))
        else:
            out.append(child)
    return out


def choose_w_daughter(w, allowed_pdgs: set):
    candidates = [
        child for child in w_direct_final_daughters(w) if pdg(child) in allowed_pdgs
    ]
    return candidates[0] if candidates else None


@dataclass
class SemileptonicTruth:
    """Truth objects of one semileptonic ttH event (None when absent)."""

    higgs: object = None
    top: object = None
    antitop: object = None
    top_b: object = None
    antitop_bbar: object = None
    w_plus: object = None
    w_minus: object = None
    wjet_quark: object = None       # light quark (PDG > 0) from the hadronic W
    wjet_antiquark: object = None   # light antiquark (PDG < 0) from the same W
    lepton: object = None
    neutrino: object = None


def identify_semileptonic_truth(mc_list: list) -> SemileptonicTruth:
    """Identify H, t, tbar, b, bbar, W daughters, lepton, neutrino.

    Uses the theory-study navigation rules. The hadronic W is whichever W has
    light-quark daughters; the leptonic W provides lepton+neutrino. The W-jet
    pair is ordered quark (PDG>0) / antiquark (PDG<0), matching the frozen
    particle-antiparticle convention.
    """
    truth = SemileptonicTruth()
    truth.higgs = find_hard_particle(mc_list, 25)
    truth.top = find_hard_particle(mc_list, 6)
    truth.antitop = find_hard_particle(mc_list, -6)
    truth.top_b = choose_direct_child(truth.top, 5)
    truth.antitop_bbar = choose_direct_child(truth.antitop, -5)
    truth.w_plus = choose_direct_child(truth.top, 24)
    truth.w_minus = choose_direct_child(truth.antitop, -24)

    for w in (truth.w_plus, truth.w_minus):
        if w is None:
            continue
        finals = w_direct_final_daughters(w)
        final_pdgs = {pdg(child) for child in finals}
        if final_pdgs & LIGHT_PDGS:
            truth.wjet_quark = choose_w_daughter(w, LIGHT_QUARKS)
            truth.wjet_antiquark = choose_w_daughter(w, LIGHT_ANTIQUARKS)
        elif final_pdgs & CHARGED_LEPTONS:
            truth.lepton = choose_w_daughter(w, CHARGED_LEPTONS)
            truth.neutrino = choose_w_daughter(w, NEUTRINOS)
    return truth

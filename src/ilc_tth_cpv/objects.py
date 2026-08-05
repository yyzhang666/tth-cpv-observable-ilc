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

W_QUARKS = {
    1, 2, 3, 4, 5,
    -1, -2, -3, -4, -5,
}

W_EMU_LEPTONS = {
    11, 13,
    -11, -13,
}

W_TAU_LEPTONS = {
    15, -15,
}

W_NEUTRINOS = {
    12, 14, 16,
    -12, -14, -16,
}

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


def physical_children(parent, max_depth: int = 40) -> list:
    """Return physical daughters after skipping self-copies and generator nodes."""
    if parent is None:
        return []

    root_pdg = pdg(parent)
    output = []
    stack = [(parent, 0)]
    seen = set()

    while stack:
        node, depth = stack.pop()
        if node is None or depth > max_depth:
            continue

        for child in daughters(node):
            child_id = id(child)
            if child_id in seen:
                continue
            seen.add(child_id)

            child_pdg = pdg(child)
            if child_pdg is None:
                continue

            node_pdg = pdg(node)
            is_generator_internal = abs(child_pdg) in GENERATOR_INTERNAL
            is_self_copy = (
                child_pdg == node_pdg
                or child_pdg == root_pdg
            )

            if is_generator_internal or is_self_copy:
                stack.append((child, depth + 1))
            else:
                output.append(child)

    return output


def choose_physical_child(parent, target_pdg: int):
    """Choose a physical daughter after skipping self-copies/internal nodes."""
    candidates = [
        child
        for child in physical_children(parent)
        if pdg(child) == target_pdg
    ]
    if not candidates:
        return None

    with_daughters = [
        child for child in candidates
        if daughters(child)
    ]
    return (with_daughters or candidates)[0]


def w_direct_final_daughters(w) -> list:
    """Follow W self-links and generator-internal codes to physical daughters."""
    return physical_children(w)


def choose_w_daughter(w, allowed_pdgs: set):
    candidates = [
        child for child in w_direct_final_daughters(w) if pdg(child) in allowed_pdgs
    ]
    return candidates[0] if candidates else None


def classify_higgs_decay(mc_list: list) -> str:
    """Classify the physical Higgs decay mode."""
    higgs = find_hard_particle(mc_list, 25)

    if higgs is None:
        return "H->none"

    child_pdgs = [
        pdg(child)
        for child in physical_children(higgs)
        if pdg(child) is not None
    ]

    abs_child_pdgs = [abs(value) for value in child_pdgs]

    # Physsim STDHEP may encode a two-body decay as
    # H -> H copy -> one decay seed -> generator node 94 -> both daughters.
    # The absolute PDG of the first physical seed therefore identifies the
    # mode even when only one member of the pair is directly visible here.
    if 5 in abs_child_pdgs:
        return "H->bb"

    if 24 in abs_child_pdgs:
        return "H->WW"

    if 15 in abs_child_pdgs:
        return "H->tautau"

    if 21 in abs_child_pdgs:
        return "H->gg"

    return "H->other"


def classify_w_decay(w) -> str:
    """Classify W as hadronic, direct e/mu, tau, or unknown."""
    if w is None:
        return "unknown"

    final_pdgs = {
        pdg(child)
        for child in physical_children(w)
        if pdg(child) is not None
    }

    n_quarks = sum(
        1 for value in final_pdgs
        if value in W_QUARKS
    )

    has_any_charged_lepton = bool(
        final_pdgs & (W_EMU_LEPTONS | W_TAU_LEPTONS)
    )
    has_any_neutrino = bool(final_pdgs & W_NEUTRINOS)

    if (
        n_quarks >= 2
        and not has_any_charged_lepton
        and not has_any_neutrino
        ):
        return "hadronic"

    w_pdg = pdg(w)

    if w_pdg == 24:
        # W+ -> l+ nu, where l+ has negative PDG code.
        has_emu = bool(final_pdgs & {-11, -13})
        has_tau = -15 in final_pdgs
        has_matching_neutrino = bool(final_pdgs & {12, 14, 16})

    elif w_pdg == -24:
        # W- -> l- anti-nu, where l- has positive PDG code.
        has_emu = bool(final_pdgs & {11, 13})
        has_tau = 15 in final_pdgs
        has_matching_neutrino = bool(final_pdgs & {-12, -14, -16})

    else:
        return "unknown"

    if has_emu and has_matching_neutrino:
        return "leptonic_emu"

    if has_tau and has_matching_neutrino:
        return "leptonic_tau"

    return "unknown"


def classify_ttbar_decay(mc_list: list) -> str:
    """Classify the ttbar decay topology."""
    top = find_hard_particle(mc_list, 6)
    antitop = find_hard_particle(mc_list, -6)

    if top is None or antitop is None:
        return "ttbar_unknown"

    w_plus = choose_physical_child(top, 24)
    w_minus = choose_physical_child(antitop, -24)

    w_plus_mode = classify_w_decay(w_plus)
    w_minus_mode = classify_w_decay(w_minus)

    modes = {w_plus_mode, w_minus_mode}

    if "unknown" in modes:
        return "ttbar_unknown"

    if w_plus_mode == "hadronic" and w_minus_mode == "hadronic":
        return "hadronic"

    if (w_plus_mode.startswith("leptonic_")
        and w_minus_mode.startswith("leptonic_")
        ):
        return "dileptonic"

    if modes == {"hadronic", "leptonic_emu"}:
        return "semileptonic_emu"

    if modes == {"hadronic", "leptonic_tau"}:
        return "semileptonic_tau"

    return "ttbar_unknown"


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

    # New topology and analyser information
    truth_topology: str = "invalid"
    hadronic_w_pdg: int | None = None
    lepton_pdg: int | None = None
    lepton_flavour: str | None = None
    down_type_daughter: object = None


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
    truth.top_b = choose_physical_child(truth.top, 5)
    truth.antitop_bbar = choose_physical_child(truth.antitop, -5)
    truth.w_plus = choose_physical_child(truth.top, 24)
    truth.w_minus = choose_physical_child(truth.antitop, -24)

    # number of hadronic W decays and number of direct electron/muon W decays
    n_hadronic_w = 0
    n_leptonic_w = 0

    for w in (truth.w_plus, truth.w_minus):
        if w is None:
            continue
            
        finals = w_direct_final_daughters(w)
        final_pdgs = {pdg(child) for child in finals}

        # Hadronic Decay (if final_pdgs contain light quarks pdgs)
        if final_pdgs & LIGHT_PDGS:
            n_hadronic_w += 1
            truth.wjet_quark = choose_w_daughter(w, LIGHT_QUARKS)      
            truth.wjet_antiquark = choose_w_daughter(w, LIGHT_ANTIQUARKS) 
            truth.hadronic_w_pdg = pdg(w)

            # Check W+- Decay
            if truth.hadronic_w_pdg == 24:
                # W+ -> U Dbar
                if truth.wjet_antiquark and pdg(truth.wjet_antiquark) in WPLUS_DOWNTYPE_ANALYZER:
                    truth.down_type_daughter = truth.wjet_antiquark
            elif truth.hadronic_w_pdg == -24:
                # W- -> D Ubar
                if truth.wjet_quark and pdg(truth.wjet_quark) in WMINUS_DOWNTYPE_ANALYZER:
                    truth.down_type_daughter = truth.wjet_quark
            
        # Leptonic Decay
        elif final_pdgs & CHARGED_LEPTONS:
            n_leptonic_w += 1
            truth.lepton = choose_w_daughter(w, CHARGED_LEPTONS)
            truth.neutrino = choose_w_daughter(w, NEUTRINOS)

            if truth.lepton is None:
                continue
            
            truth.lepton_pdg = pdg(truth.lepton)

            # Store lepton flavour info
            if abs(truth.lepton_pdg) == 11:
                truth.lepton_flavour = "e"
            elif abs(truth.lepton_pdg) == 13:
                truth.lepton_flavour = "mu"

    h_daughters = physical_children(truth.higgs) if truth.higgs else []
    h_bb = (classify_higgs_decay(mc_list) == "H->bb")


    # Confirm the decay is semileptonic
    is_semileptonic = (
        h_bb
        and n_hadronic_w == 1                     # Exactly one hadronic W
        and n_leptonic_w == 1                     # Exactly one leptonic W
        and truth.lepton_flavour in ("e", "mu")   # lepton is e or mu
        and truth.wjet_quark is not None          # W -> q
        and truth.wjet_antiquark is not None      # w -> q-
    )

    if is_semileptonic:
        truth.truth_topology = "semileptonic_e" if truth.lepton_flavour == "e" else "semileptonic_mu"
    else:
        truth.truth_topology = "invalid"

    return truth

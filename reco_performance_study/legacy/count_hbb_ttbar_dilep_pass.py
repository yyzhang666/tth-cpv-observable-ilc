#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from collections import Counter, defaultdict
from pyLCIO import IOIMPL


# ----------------------------
# LCIO helpers (same style)
# ----------------------------
def get_collection_names(evt):
    try:
        return set(list(evt.getCollectionNames()))
    except Exception:
        return set()


def get_col(evt, name):
    try:
        return evt.getCollection(name)
    except Exception:
        return None


def pick_collection(evt, preferred, fallbacks):
    names = get_collection_names(evt)
    if preferred and preferred in names:
        return preferred
    for c in fallbacks:
        if c in names:
            return c
    return None


def get_n_reco(evt, preferred, fallbacks, require_type="ReconstructedParticle"):
    """
    Return (name_used, n) if collection exists and has required type,
    else return (None, None).
    """
    name = pick_collection(evt, preferred, fallbacks)
    if name is None:
        return None, None
    c = get_col(evt, name)
    if c is None:
        return None, None
    try:
        if require_type is not None:
            if str(c.getTypeName()) != require_type:
                return None, None
        return name, int(c.getNumberOfElements())
    except Exception:
        return None, None


# ----------------------------
# Truth helpers (copied logic)
# ----------------------------
def first_physical_children(p, max_depth=20):
    """
    Flatten technical nodes (91/92/94) and self-copies:
    return first-layer 'physical' children.
    """
    out = []
    stack = [(p, 0)]
    seen = set()
    while stack:
        node, depth = stack.pop()
        if node is None or depth > max_depth:
            continue
        try:
            ds = node.getDaughters()
        except Exception:
            continue
        for d in ds:
            if d is None:
                continue
            oid = id(d)
            if oid in seen:
                continue
            seen.add(oid)
            try:
                apdg = abs(d.getPDG())
                pdg = d.getPDG()
            except Exception:
                continue
            # flatten technical nodes and self-copies
            if apdg in (91, 92, 94) or pdg == node.getPDG():
                stack.append((d, depth + 1))
            else:
                out.append(d)
    return out


def get_top_W(top):
    kids = first_physical_children(top, max_depth=10)
    for k in kids:
        try:
            if abs(k.getPDG()) == 24:
                return k
        except Exception:
            pass
    return None


def W_has_direct_tau(W):
    if W is None:
        return False
    kids = first_physical_children(W, max_depth=10)
    for k in kids:
        try:
            if abs(k.getPDG()) == 15:
                return True
        except Exception:
            continue
    return False


def classify_W_mode(W):
    """
    Return one of:
      - "had"
      - "e" / "mu" / "tau"   (leptonic flavour by direct W daughter)
      - "lep"               (leptonic but flavour ambiguous)
      - "unk"
    Uses first-layer physical daughters.
    """
    if W is None:
        return "unk"
    kids = first_physical_children(W, max_depth=10)
    apdgs = []
    for k in kids:
        try:
            apdgs.append(abs(k.getPDG()))
        except Exception:
            continue

    has_ch = any(x in (11, 13, 15) for x in apdgs)
    has_nu = any(x in (12, 14, 16) for x in apdgs)
    n_q = sum(1 for x in apdgs if x in (1, 2, 3, 4, 5))

    if n_q >= 2 and (not has_ch) and (not has_nu):
        return "had"

    if has_ch and has_nu:
        if 15 in apdgs and 16 in apdgs:
            return "tau"
        if 11 in apdgs and 12 in apdgs:
            return "e"
        if 13 in apdgs and 14 in apdgs:
            return "mu"
        return "lep"

    return "unk"


def truth_h_to_bb(evt, colMC="MCParticlesSkimmed"):
    cMCP = get_col(evt, colMC)
    if cMCP is None:
        return None
    H = None
    for i in range(cMCP.getNumberOfElements()):
        p = cMCP.getElementAt(i)
        try:
            if p.getPDG() == 25:
                H = p
                break
        except Exception:
            continue
    if H is None:
        return None
    kids = first_physical_children(H, max_depth=10)
    nb = 0
    for k in kids:
        try:
            if abs(k.getPDG()) == 5:
                nb += 1
        except Exception:
            continue
    return nb >= 2


def truth_ttbar_channel_and_tau(evt, colMC="MCParticlesSkimmed"):
    """
    Return:
      (channel, tau_direct_flag)

    channel in:
      - "had"
      - "semilep_e" / "semilep_mu" / "semilep_tau" / "semilep_lep"
      - "dilep"
      - None  (if cannot classify)

    tau_direct_flag:
      True if any W has direct tau daughter (15 in first-layer physical daughters).
    """
    cMCP = get_col(evt, colMC)
    if cMCP is None:
        return None, False

    top_p = None
    top_m = None
    for i in range(cMCP.getNumberOfElements()):
        p = cMCP.getElementAt(i)
        try:
            if p.getPDG() == 6 and top_p is None:
                top_p = p
            elif p.getPDG() == -6 and top_m is None:
                top_m = p
        except Exception:
            continue

    if top_p is None or top_m is None:
        return None, False

    Wp = get_top_W(top_p)
    Wm = get_top_W(top_m)

    mp = classify_W_mode(Wp)
    mm = classify_W_mode(Wm)

    if mp == "unk" or mm == "unk":
        return None, False

    tau_direct = W_has_direct_tau(Wp) or W_has_direct_tau(Wm)

    def is_lep(m):
        return m in ("e", "mu", "tau", "lep")

    if mp == "had" and mm == "had":
        return "had", False

    if (mp == "had" and is_lep(mm)) or (mm == "had" and is_lep(mp)):
        lep_mode = mm if mp == "had" else mp
        if lep_mode == "e":
            return "semilep_e", tau_direct
        if lep_mode == "mu":
            return "semilep_mu", tau_direct
        if lep_mode == "tau":
            return "semilep_tau", tau_direct
        return "semilep_lep", tau_direct

    if is_lep(mp) and is_lep(mm):
        return "dilep", tau_direct

    return None, tau_direct


# ----------------------------
# Stats accumulator (dilep-only)
# ----------------------------
def init_stat():
    return {
        "n": 0,
        "pass": Counter(),
        "miss": Counter(),
        "used": Counter(),
        "dist_mu": Counter(),
        "dist_el": Counter(),
        "dist_iso": Counter(),
    }


def update_stat(S, nmu_name, nmu, nel_name, nel, niso_name, niso):
    S["n"] += 1

    if nmu_name is None:
        S["miss"]["missing_ISOMuons_collection"] += 1
    else:
        S["used"][f"MU:{nmu_name}"] += 1
        S["dist_mu"][nmu] += 1

    if nel_name is None:
        S["miss"]["missing_ISOElectrons_collection"] += 1
    else:
        S["used"][f"EL:{nel_name}"] += 1
        S["dist_el"][nel] += 1

    if niso_name is None:
        S["miss"]["missing_Isolep_collection"] += 1
    else:
        S["used"][f"ISO:{niso_name}"] += 1
        S["dist_iso"][niso] += 1

    # ---- Your requested "require" counts (STRICT) ----
    # Tagger-side
    if nmu_name is not None and nel_name is not None:
        if (nmu == 0 and nel == 0):
            S["pass"]["MU0_EL0"] += 1
        if (nmu + nel == 1):
            S["pass"]["MUEL_SUM1"] += 1
        if (nmu + nel == 2):
            S["pass"]["MUEL_SUM2"] += 1

    # Isolep-side
    if niso_name is not None:
        if (niso == 0):
            S["pass"]["ISOLEP0"] += 1
        if (niso == 1):
            S["pass"]["ISOLEP1"] += 1
        if (niso == 2):
            S["pass"]["ISOLEP2"] += 1

    # Joint consistency (Tagger vs Isolep)
    if nmu_name is not None and nel_name is not None and niso_name is not None:
        if (nmu == 0 and nel == 0 and niso == 0):
            S["pass"]["MU0_EL0_AND_ISO0"] += 1
        if (nmu + nel == 1 and niso == 1):
            S["pass"]["SUM1_AND_ISO1"] += 1
        if (nmu + nel == 2 and niso == 2):
            S["pass"]["SUM2_AND_ISO2"] += 1


def print_dist(title, dist, max_k=6):
    print(f"\n{title}")
    if not dist:
        print("  (none)")
        return
    for x in sorted(dist.keys()):
        if x <= max_k:
            print(f"  n={x:2d} : {dist[x]}")
    tail = sum(v for k, v in dist.items() if k > max_k)
    if tail > 0:
        print(f"  n>{max_k} : {tail}")


def print_summary(label, S):
    print(f"\n==================== {label} ====================")
    print(f"Events in this category (H->bb truth, ttbar dilep): {S['n']}")

    keys = [
        "MU0_EL0",
        "ISOLEP0",
        "MU0_EL0_AND_ISO0",
        "MUEL_SUM1",
        "ISOLEP1",
        "SUM1_AND_ISO1",
        "MUEL_SUM2",
        "ISOLEP2",
        "SUM2_AND_ISO2",
    ]
    print("\nPass counts (STRICT: needed collections exist):")
    for k in keys:
        print(f"  {k:20s} : {S['pass'].get(k, 0)}")

    if S["miss"]:
        print("\nMissing-collection diagnostics (within this category):")
        for k, v in S["miss"].most_common():
            print(f"  {k:35s} : {v}")

    if S["used"]:
        print("\nWhich collection names were used (within this category):")
        for k, v in S["used"].most_common():
            print(f"  {k:20s} : {v}")

    print_dist("ISOMuons multiplicity", S["dist_mu"])
    print_dist("ISOElectrons multiplicity", S["dist_el"])
    print_dist("Isolep multiplicity", S["dist_iso"])


# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slcio")
    ap.add_argument("--maxEvents", type=int, default=-1)
    ap.add_argument("--colMC", default="MCParticlesSkimmed")

    ap.add_argument("--colIsolep", default="Isolep")
    ap.add_argument("--colMu", default="ISOMuons")
    ap.add_argument("--colEl", default="ISOElectrons")
    args = ap.parse_args()

    isolep_fallbacks = [args.colIsolep, "Isolep", "IsolatedLeptons", "IsolatedLepton", "Leptons"]
    mu_fallbacks = [args.colMu, "ISOMuons", "IsolatedMuons"]
    el_fallbacks = [args.colEl, "ISOElectrons", "IsolatedElectrons"]

    stats = defaultdict(init_stat)
    truth_cnt = Counter()

    reader = IOIMPL.LCFactory.getInstance().createLCReader()
    reader.open(args.slcio)

    n_evt = 0
    while True:
        try:
            evt = reader.readNextEvent()
        except Exception:
            evt = None
        if evt is None:
            break
        if args.maxEvents >= 0 and n_evt >= args.maxEvents:
            break

        chan, tau_direct = truth_ttbar_channel_and_tau(evt, colMC=args.colMC)
        if chan != "dilep":
            n_evt += 1
            continue

        hbb = truth_h_to_bb(evt, colMC=args.colMC)
        if hbb is not True:
            n_evt += 1
            continue

        # Split by tau-direct flag (your only requested split)
        cls = "HAS_TAU" if tau_direct else "NO_TAU"
        truth_cnt[f"dilep_hbb_{cls}"] += 1
        truth_cnt["dilep_hbb_all"] += 1

        # reco counts
        nmu_name, nmu = get_n_reco(evt, args.colMu, mu_fallbacks)
        nel_name, nel = get_n_reco(evt, args.colEl, el_fallbacks)
        niso_name, niso = get_n_reco(evt, args.colIsolep, isolep_fallbacks)

        update_stat(stats[cls], nmu_name, nmu, nel_name, nel, niso_name, niso)

        n_evt += 1

    reader.close()

    print("\n==================== Global summary (dilep-only, H->bb truth) ====================")
    print(f"Processed events (file looped): {n_evt}")
    print(f"Dilep + H->bb truth (all): {truth_cnt.get('dilep_hbb_all', 0)}")
    print(f"  NO_TAU  : {truth_cnt.get('dilep_hbb_NO_TAU', 0)}")
    print(f"  HAS_TAU : {truth_cnt.get('dilep_hbb_HAS_TAU', 0)}")

    print_summary("DILEP + HBB + NO_TAU (no W->tau directly)", stats["NO_TAU"])
    print_summary("DILEP + HBB + HAS_TAU (>=1 W->tau directly)", stats["HAS_TAU"])


if __name__ == "__main__":
    main()
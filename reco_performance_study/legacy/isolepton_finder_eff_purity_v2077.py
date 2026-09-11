#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import math
from collections import deque, defaultdict, Counter

# ============================================================
# LCIO import
# ============================================================
def import_lcio():
    try:
        from pyLCIO import IOIMPL, UTIL
        return IOIMPL, UTIL
    except Exception:
        try:
            import lcio  # noqa: F401
            from lcio import IOIMPL, UTIL
            return IOIMPL, UTIL
        except Exception as e:
            print("[ERROR] Cannot import pyLCIO/lcio. Did you source your ILCSoft environment?", file=sys.stderr)
            print(f"        Import error: {e}", file=sys.stderr)
            sys.exit(2)

IOIMPL, UTIL = import_lcio()

def open_reader(fn: str):
    r = IOIMPL.LCFactory.getInstance().createLCReader()
    r.open(fn)
    return r

# ============================================================
# Collection helpers
# ============================================================
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

def get_reco_list(evt, preferred, fallbacks, require_type="ReconstructedParticle"):
    name = pick_collection(evt, preferred, fallbacks)
    if name is None:
        return None, []
    c = get_col(evt, name)
    if c is None:
        return None, []
    try:
        if require_type is not None and str(c.getTypeName()) != require_type:
            return name, []
        n = int(c.getNumberOfElements())
        return name, [c.getElementAt(i) for i in range(n)]
    except Exception:
        return name, []

# ============================================================
# Robust vector -> list
# ============================================================
def vec_to_list(v):
    if v is None:
        return []
    try:
        n = int(v.size())
        return [v[i] for i in range(n)]
    except Exception:
        pass
    try:
        return list(v)
    except Exception:
        return []

# ============================================================
# Basic object helpers
# ============================================================
def obj_uid(obj):
    if obj is None:
        return None
    try:
        return int(obj.id())
    except Exception:
        return id(obj)

def pdg(obj):
    try:
        return int(obj.getPDG())
    except Exception:
        return None

def abs_pdg(obj):
    p = pdg(obj)
    return abs(p) if p is not None else None

def p_mag(obj):
    try:
        px, py, pz = obj.getMomentum()
        return math.sqrt(float(px)**2 + float(py)**2 + float(pz)**2)
    except Exception:
        return 0.0

def iter_daughters(mc):
    try:
        return vec_to_list(mc.getDaughters())
    except Exception:
        return []

def iter_parents(mc):
    try:
        return vec_to_list(mc.getParents())
    except Exception:
        return []

# ============================================================
# Generator artifacts: PDG 90-99
# ============================================================
def is_gen_artifact(pdg_abs: int):
    return (pdg_abs is not None) and (90 <= pdg_abs <= 99)

# ============================================================
# Physics traversal: first-layer physical daughters
# - expand 90-99
# - expand self-copies
# ============================================================
def physical_daughters_first_layer(parent, max_expand=20000):
    if parent is None:
        return []
    out = []
    stack = list(iter_daughters(parent))
    steps = 0
    parent_abs = abs_pdg(parent)
    while stack and steps < max_expand:
        steps += 1
        ch = stack.pop()
        if ch is None:
            continue
        a = abs_pdg(ch)
        if a is None:
            continue
        if is_gen_artifact(a):
            stack.extend(iter_daughters(ch))
            continue
        if parent_abs is not None and a == parent_abs:
            stack.extend(iter_daughters(ch))
            continue
        out.append(ch)
    return out

# ============================================================
# H -> bb strict
# ============================================================
def is_higgs_to_bb_strict(h):
    if h is None or abs_pdg(h) != 25:
        return False
    D = physical_daughters_first_layer(h)
    pdgs = []
    abs_pdgs = []
    for x in D:
        p = pdg(x)
        if p is None:
            continue
        pdgs.append(p)
        abs_pdgs.append(abs(p))
    if any(a in (24, 23, 15) for a in abs_pdgs):
        return False
    return (5 in pdgs) and (-5 in pdgs)

def has_higgs_parent(m):
    q = deque([m])
    seen = set([obj_uid(m)])
    while q:
        x = q.popleft()
        for par in iter_parents(x):
            if par is None:
                continue
            uid = obj_uid(par)
            if uid in seen:
                continue
            seen.add(uid)
            a = abs_pdg(par)
            if a is None:
                continue
            if is_gen_artifact(a):
                q.append(par)
                continue
            if a == 25:
                return True
    return False

def find_higgs_hbb(mc_list):
    candidates = [m for m in mc_list if abs_pdg(m) == 25 and is_higgs_to_bb_strict(m)]
    if not candidates:
        return None
    roots = [h for h in candidates if not has_higgs_parent(h)]
    return roots[0] if roots else candidates[0]

# ============================================================
# Root tops + W finder
# ============================================================
def is_root_top(t):
    if t is None or abs_pdg(t) != 6:
        return False
    q = deque([t])
    seen = set([obj_uid(t)])
    while q:
        x = q.popleft()
        for par in iter_parents(x):
            if par is None:
                continue
            uid = obj_uid(par)
            if uid in seen:
                continue
            seen.add(uid)
            a = abs_pdg(par)
            if a is None:
                continue
            if is_gen_artifact(a):
                q.append(par)
                continue
            if a == 6:
                return False
    return True

def find_root_tops(mc_list):
    tops = [m for m in mc_list if abs_pdg(m) == 6]
    roots = [t for t in tops if is_root_top(t)]
    roots = sorted(roots, key=lambda x: -p_mag(x))
    return roots[:2]

def find_W_from_top(top):
    if top is None or abs_pdg(top) != 6:
        return None
    D = physical_daughters_first_layer(top)
    Ws = [x for x in D if abs_pdg(x) == 24]
    if Ws:
        return max(Ws, key=lambda x: p_mag(x))
    q = deque()
    for ch in iter_daughters(top):
        q.append((ch, 1))
    seen = set()
    while q:
        node, d = q.popleft()
        if node is None or d > 60:
            continue
        uid = obj_uid(node)
        if uid in seen:
            continue
        seen.add(uid)
        a = abs_pdg(node)
        if a is None:
            continue
        if is_gen_artifact(a):
            for g in iter_daughters(node):
                q.append((g, d + 1))
            continue
        if a == 24:
            return node
        for g in iter_daughters(node):
            q.append((g, d + 1))
    return None

# ============================================================
# W mode classification (tau-inclusive)
# ============================================================
def classify_W_mode(W):
    if W is None or abs_pdg(W) != 24:
        return "unk"
    D = physical_daughters_first_layer(W)
    apdgs = [abs_pdg(x) for x in D if abs_pdg(x) is not None]
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

def classify_ttbar_channel_tauincl(mc_list):
    tops = find_root_tops(mc_list)
    if len(tops) < 2:
        return False, "UNCLASS"
    W1 = find_W_from_top(tops[0])
    W2 = find_W_from_top(tops[1])
    if W1 is None or W2 is None:
        return False, "UNCLASS"
    m1 = classify_W_mode(W1)
    m2 = classify_W_mode(W2)
    lep_modes = set(["e", "mu", "tau", "lep"])
    if m1 == "had" and m2 == "had":
        return True, "HAD"
    if (m1 == "had" and m2 in lep_modes) or (m2 == "had" and m1 in lep_modes):
        return True, "SEMI"
    if (m1 in lep_modes and m2 in lep_modes):
        return True, "DI"
    return True, "OTHER"

# ============================================================
# Ancestor queries for origin
# ============================================================
def has_tau_ancestor(mc, max_depth=200):
    if mc is None:
        return False
    q = deque([(mc, 0)])
    seen = set([obj_uid(mc)])
    a0 = abs_pdg(mc)
    while q:
        node, d = q.popleft()
        if node is None or d >= max_depth:
            continue
        for par in iter_parents(node):
            if par is None:
                continue
            uid = obj_uid(par)
            if uid in seen:
                continue
            seen.add(uid)
            ap = abs_pdg(par)
            if ap is None:
                continue
            if is_gen_artifact(ap):
                q.append((par, d + 1))
                continue
            if a0 is not None and ap == a0:
                q.append((par, d + 1))
                continue
            if ap == 15:
                return True
            q.append((par, d + 1))
    return False

def closest_nonself_ancestor(mc, max_steps=200):
    if mc is None:
        return None
    a0 = abs_pdg(mc)
    cur = mc
    seen = set([obj_uid(cur)])
    for _ in range(max_steps):
        ps = []
        for p in iter_parents(cur):
            if p is None:
                continue
            ap = abs_pdg(p)
            if ap is None:
                continue
            if is_gen_artifact(ap):
                continue
            ps.append(p)
        if not ps:
            return None
        p_best = max(ps, key=lambda x: p_mag(x))
        uid = obj_uid(p_best)
        if uid in seen:
            return None
        seen.add(uid)
        ap = abs_pdg(p_best)
        if a0 is not None and ap == a0:
            cur = p_best
            continue
        return p_best
    return None

def first_W_ancestor(mc, max_depth=200):
    if mc is None:
        return None
    q = deque([(mc, 0)])
    seen = set([obj_uid(mc)])
    a0 = abs_pdg(mc)
    while q:
        node, d = q.popleft()
        if node is None or d >= max_depth:
            continue
        for par in iter_parents(node):
            if par is None:
                continue
            uid = obj_uid(par)
            if uid in seen:
                continue
            seen.add(uid)
            ap = abs_pdg(par)
            if ap is None:
                continue
            if is_gen_artifact(ap):
                q.append((par, d + 1))
                continue
            if a0 is not None and ap == a0:
                q.append((par, d + 1))
                continue
            if ap == 24:
                return par
            q.append((par, d + 1))
    return None

def has_top_ancestor(mc, max_depth=300):
    if mc is None:
        return False
    q = deque([(mc, 0)])
    seen = set([obj_uid(mc)])
    while q:
        node, d = q.popleft()
        if node is None or d >= max_depth:
            continue
        for par in iter_parents(node):
            if par is None:
                continue
            uid = obj_uid(par)
            if uid in seen:
                continue
            seen.add(uid)
            ap = abs_pdg(par)
            if ap is None:
                continue
            if is_gen_artifact(ap):
                q.append((par, d + 1))
                continue
            if ap == 6:
                return True
            q.append((par, d + 1))
    return False

def classify_origin_only(mc_match):
    if mc_match is None:
        return "no_mc"
    if has_tau_ancestor(mc_match):
        return "from_tau"
    anc = closest_nonself_ancestor(mc_match)
    if anc is not None:
        ap = abs_pdg(anc)
        if ap is not None and ap >= 100:
            return "from_hadron"
    W = first_W_ancestor(mc_match)
    if W is not None and has_top_ancestor(W):
        return "from_topW"
    return "other"

# ============================================================
# Relation navigators + fallback matching (Reco -> Track -> Cluster)
# ============================================================
def make_nav(evt, rel_name):
    try:
        rel_col = evt.getCollection(rel_name)
        return UTIL.LCRelationNavigator(rel_col)
    except Exception:
        return None

def best_related(nav, obj):
    if nav is None or obj is None:
        return None, -1.0
    best, best_w = None, -1.0
    try:
        objs = nav.getRelatedToObjects(obj)
        ws = nav.getRelatedToWeights(obj)
        for o, w in zip(objs, ws):
            ww = float(w)
            if ww > best_w:
                best, best_w = o, ww
    except Exception:
        pass
    try:
        objs = nav.getRelatedFromObjects(obj)
        ws = nav.getRelatedFromWeights(obj)
        for o, w in zip(objs, ws):
            ww = float(w)
            if ww > best_w:
                best, best_w = o, ww
    except Exception:
        pass
    return best, best_w

def match_reco_to_mc_any_with_fallback(rp, nav_reco, nav_track, nav_cluster):
    best_mc = None
    best_w = -1.0
    best_src = None

    mc, w = best_related(nav_reco, rp)
    if mc is not None and float(w) > best_w:
        best_mc, best_w, best_src = mc, float(w), "reco"

    try:
        trks = vec_to_list(rp.getTracks())
    except Exception:
        trks = []
    for t in trks:
        mc2, w2 = best_related(nav_track, t)
        if mc2 is not None and float(w2) > best_w:
            best_mc, best_w, best_src = mc2, float(w2), "track"

    try:
        cls = vec_to_list(rp.getClusters())
    except Exception:
        cls = []
    for c in cls:
        mc3, w3 = best_related(nav_cluster, c)
        if mc3 is not None and float(w3) > best_w:
            best_mc, best_w, best_src = mc3, float(w3), "cluster"

    if best_mc is None:
        return None, None, None, None
    return best_mc, abs_pdg(best_mc), best_w, best_src

# ============================================================
# Reco-side PID tagging for Isolep entries (YOUR REQUEST)
#   Electron: R_cal > 0.9
#   Muon:     total cal energy < 5
# ============================================================
def get_cal_energy_ecal_hcal(rp):
    """
    Sum subdetector energies over clusters.
    Same convention as your working script:
      ECAL = sub[0]+sub[3], HCAL = sub[1]+sub[4]
    """
    ecal = 0.0
    hcal = 0.0
    try:
        clusters = vec_to_list(rp.getClusters())
    except Exception:
        clusters = []
    for cl in clusters:
        try:
            sub = cl.getSubdetectorEnergies()
            ecal += float(sub[0] + sub[3])
            hcal += float(sub[1] + sub[4])
        except Exception:
            continue
    return ecal, hcal

def tag_isolep_pid(rp, rcal_ele_min=0.90, calE_mu_max=5.0, mu_first=True):
    """
    Return (pid_tag, R_cal, Ecal, Hcal, Ecal+Hcal)
      pid_tag in {"e_like","mu_like","other_pid","unknown"}
    """
    ecal, hcal = get_cal_energy_ecal_hcal(rp)
    cal = ecal + hcal
    if cal <= 0.0:
        return "unknown", 0.0, ecal, hcal, cal
    rcal = ecal / cal

    # priority choice:
    if mu_first:
        if cal < calE_mu_max:
            return "mu_like", rcal, ecal, hcal, cal
        if rcal > rcal_ele_min:
            return "e_like", rcal, ecal, hcal, cal
    else:
        if rcal > rcal_ele_min:
            return "e_like", rcal, ecal, hcal, cal
        if cal < calE_mu_max:
            return "mu_like", rcal, ecal, hcal, cal

    return "other_pid", rcal, ecal, hcal, cal

# ============================================================
# Stats
# ============================================================
def init_stat():
    return {
        "n_evt": 0,
        "dist_isolep": Counter(),
        "used_isolep_name": Counter(),

        # entry-level (SEMI/DI only)
        "n_entries": 0,
        "pid_cnt": Counter(),          # pid_tag counts
        "pid_origin": Counter(),       # key: f"{pid}|{origin}"
        "pid_no_mc": Counter(),        # no_mc per pid
        "pid_src": Counter(),          # key: f"{pid}|src"
        "pid_apdg": Counter(),         # key: f"{pid}|absPDG"
    }

def safe_div(n, d):
    return (float(n) / float(d)) if d else 0.0

def pdg_name(abs_code: int):
    m = {11:"e", 13:"mu", 15:"tau", 22:"gamma", 211:"pi", 321:"K", 2212:"p"}
    return m.get(abs_code, "")

# ============================================================
# Main
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--max-events", type=int, default=-1)

    ap.add_argument("--mc-col", default="MCParticlesSkimmed")
    ap.add_argument("--isolep-col", default="Isolep")
    ap.add_argument("--require-type", default="ReconstructedParticle")

    # PID tag params
    ap.add_argument("--rcal-ele-min", type=float, default=0.90)
    ap.add_argument("--calE-mu-max", type=float, default=5.0)
    ap.add_argument("--pid-mu-first", action="store_true",
                    help="If set, apply mu_like (cal<mu_max) before e_like (Rcal>ele_min). "
                         "Default is True in code; use --pid-mu-first to be explicit.")
    ap.add_argument("--pid-ele-first", action="store_true",
                    help="If set, apply e_like before mu_like (overrides --pid-mu-first).")

    ap.add_argument("--topN-pdg", type=int, default=12)
    args = ap.parse_args()

    mu_first = True
    if args.pid_ele_first:
        mu_first = False

    mc_fallbacks = [args.mc_col, "MCParticlesSkimmed", "MCParticles", "MCParticle"]
    isolep_fallbacks = [args.isolep_col, "Isolep", "IsolatedLeptons", "IsolatedLepton", "Leptons"]

    reco_mc_rel = "RecoMCTruthLink"
    track_mc_rel = "TrackMCTruthLink"
    cluster_mc_rel = "ClusterMCTruthLink"

    stats = defaultdict(init_stat)

    n_processed = 0
    for fn in args.inputs:
        reader = open_reader(fn)
        while True:
            if args.max_events >= 0 and n_processed >= args.max_events:
                break
            try:
                evt = reader.readNextEvent()
            except Exception:
                evt = None
            if evt is None:
                break
            n_processed += 1

            mc_name = pick_collection(evt, args.mc_col, mc_fallbacks)
            if mc_name is None:
                iso_name, iso_list = get_reco_list(evt, args.isolep_col, isolep_fallbacks, require_type=args.require_type)
                S = stats["ALL|UNCLASS"]
                S["n_evt"] += 1
                S["used_isolep_name"][str(iso_name)] += 1
                S["dist_isolep"][len(iso_list)] += 1
                continue

            mc_col = get_col(evt, mc_name)
            try:
                nmc = int(mc_col.getNumberOfElements())
                mc_list = [mc_col.getElementAt(i) for i in range(nmc)]
            except Exception:
                continue

            is_hbb = (find_higgs_hbb(mc_list) is not None)
            ok, ch = classify_ttbar_channel_tauincl(mc_list)
            ch = ch if ok else "UNCLASS"

            iso_name, iso_list = get_reco_list(evt, args.isolep_col, isolep_fallbacks, require_type=args.require_type)

            nav_reco = make_nav(evt, reco_mc_rel)
            nav_track = make_nav(evt, track_mc_rel)
            nav_cluster = make_nav(evt, cluster_mc_rel)

            for sel in (["ALL"] + (["HBB"] if is_hbb else [])):
                key = f"{sel}|{ch}"
                S = stats[key]
                S["n_evt"] += 1
                S["used_isolep_name"][str(iso_name)] += 1
                S["dist_isolep"][len(iso_list)] += 1

                if ch not in ("SEMI", "DI"):
                    continue

                S["n_entries"] += len(iso_list)

                for rp in iso_list:
                    pid_tag, rcal, ecal, hcal, cal = tag_isolep_pid(
                        rp,
                        rcal_ele_min=args.rcal_ele_min,
                        calE_mu_max=args.calE_mu_max,
                        mu_first=mu_first
                    )
                    S["pid_cnt"][pid_tag] += 1

                    mc_match, ap, w, src = match_reco_to_mc_any_with_fallback(rp, nav_reco, nav_track, nav_cluster)
                    origin = classify_origin_only(mc_match)

                    S["pid_origin"][f"{pid_tag}|{origin}"] += 1

                    if mc_match is None:
                        S["pid_no_mc"][pid_tag] += 1
                        continue

                    if ap is None:
                        ap = 0
                    S["pid_src"][f"{pid_tag}|{src}"] += 1
                    S["pid_apdg"][f"{pid_tag}|{ap}"] += 1

        reader.close()

    # ============================================================
    # Print
    # ============================================================
    print("\n" + "=" * 120)
    print("SUMMARY: Isolep entry origin-only diagnostics in tau-inclusive SEMI/DI, split by reco PID tags")
    print("=" * 120)
    print(f"Files: {len(args.inputs)}")
    print(f"Events processed: {n_processed}")
    print(f"PID tag rules: e_like if Rcal>={args.rcal_ele_min:.3f}; mu_like if Ecal+Hcal<{args.calE_mu_max:.3f}; "
          f"priority={'mu_first' if mu_first else 'e_first'}")

    def print_dist(dist, max_k=6):
        if not dist:
            print("  (none)")
            return
        for x in sorted(dist.keys()):
            if x <= max_k:
                print(f"  n={x:2d} : {dist[x]}")
        tail = sum(v for k, v in dist.items() if k > max_k)
        if tail > 0:
            print(f"  n>{max_k} : {tail}")

    def print_block(sel, ch):
        key = f"{sel}|{ch}"
        S = stats.get(key, None)
        if S is None or S["n_evt"] == 0:
            return

        print(f"\n==================== {sel} | {ch} ====================")
        print(f"Events: {S['n_evt']}")
        print("Isolep multiplicity:")
        print_dist(S["dist_isolep"])
        if ch not in ("SEMI", "DI"):
            return

        tot = S["n_entries"]
        if tot == 0:
            print("\nNo Isolep entries in this block.")
            return

        pid_tags = ["e_like", "mu_like", "other_pid", "unknown"]
        origins = ["from_topW", "from_tau", "from_hadron", "other", "no_mc"]

        print("\nOrigin-only diagnostics over ALL Isolep entries (split by reco PID tag):")
        for pid in pid_tags:
            n_pid = S["pid_cnt"].get(pid, 0)
            if n_pid == 0:
                continue
            print(f"\n-- PID = {pid:9s}  entries={n_pid}  frac_in_block={safe_div(n_pid, tot):.4f}")
            for org in origins:
                v = S["pid_origin"].get(f"{pid}|{org}", 0)
                print(f"   {org:12s}: {v:6d}   frac_in_pid={safe_div(v, n_pid):.4f}")

            matched = n_pid - S["pid_no_mc"].get(pid, 0)
            if matched > 0:
                print("   match sources:")
                for src in ("reco", "track", "cluster"):
                    v = S["pid_src"].get(f"{pid}|{src}", 0)
                    if v:
                        print(f"     {src:7s}: {v}")

                # top absPDG for this pid
                items = []
                for k2, v2 in S["pid_apdg"].items():
                    if not k2.startswith(pid + "|"):
                        continue
                    try:
                        ap = int(k2.split("|")[1])
                    except Exception:
                        ap = -1
                    items.append((ap, v2))
                items.sort(key=lambda x: -x[1])
                if items:
                    print(f"   matched abs(PDG) top{args.topN_pdg}:")
                    for ap, v2 in items[:args.topN_pdg]:
                        nm = pdg_name(ap)
                        nm = f" ({nm})" if nm else ""
                        print(f"     absPDG={ap:6d}{nm:8s}: {v2}")

    for sel in ("ALL", "HBB"):
        print("\n" + "-" * 120)
        print(f"Selection: {sel}")
        print("-" * 120)
        for ch in ("HAD", "SEMI", "DI", "OTHER", "UNCLASS"):
            print_block(sel, ch)

    print("\n" + "=" * 120)


if __name__ == "__main__":
    main()
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

def get_collection_names(evt):
    try:
        return set(list(evt.getCollectionNames()))
    except Exception:
        return set()

def pick_collection(evt, preferred, fallbacks):
    names = get_collection_names(evt)
    if preferred and preferred in names:
        return preferred
    for c in fallbacks:
        if c in names:
            return c
    return None

# ============================================================
# Robust vector -> list
# ============================================================
def vec_to_list(v):
    if v is None:
        return []
    try:
        n = int(v.size())
        out = []
        for i in range(n):
            out.append(v[i])
        return out
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

def gen_status(obj, default=None):
    try:
        return int(obj.getGeneratorStatus())
    except Exception:
        return default

def p_mag(obj):
    try:
        px, py, pz = obj.getMomentum()
        return math.sqrt(float(px) ** 2 + float(py) ** 2 + float(pz) ** 2)
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
# Generator artifacts: skip abs(pdg) in [90,99]
# ============================================================
def is_gen_artifact(pdg_abs: int):
    return (pdg_abs is not None) and (90 <= pdg_abs <= 99)

# ============================================================
# Physics traversal: first-layer physical daughters (EXPAND artifacts & self-copies)
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

        # expand self-copy (same abs PDG as parent)
        if parent_abs is not None and a == parent_abs:
            stack.extend(iter_daughters(ch))
            continue

        out.append(ch)
    return out

# ============================================================
# Keep self-copies (for last-gen tracking)
# ============================================================
def physical_daughters_keep_self(parent, max_expand=20000):
    if parent is None:
        return []
    out = []
    stack = list(iter_daughters(parent))
    steps = 0

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
        out.append(ch)
    return out

def last_generation_selfcopy_down(mc, max_steps=500):
    if mc is None:
        return None
    try:
        pdg0 = int(mc.getPDG())
    except Exception:
        return mc

    cur = mc
    seen = set([obj_uid(cur)])

    for _ in range(max_steps):
        ds = physical_daughters_keep_self(cur)
        same = []
        for d in ds:
            try:
                if int(d.getPDG()) == pdg0:
                    same.append(d)
            except Exception:
                continue
        if not same:
            return cur
        nxt = max(same, key=lambda x: p_mag(x))
        uid = obj_uid(nxt)
        if uid in seen:
            return cur
        seen.add(uid)
        cur = nxt
    return cur

def lastgen_key(mc):
    end = last_generation_selfcopy_down(mc)
    return obj_uid(end) if end is not None else None

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

    # extra safety: reject if direct W/Z/tau
    if any(a in (24, 23, 15) for a in abs_pdgs):
        return False
    has_b = any(p == 5 for p in pdgs)
    has_bbar = any(p == -5 for p in pdgs)
    return has_b and has_bbar

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
# Root tops
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

# ============================================================
# Find W from top
# ============================================================
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
    """
    Return: "had", "e", "mu", "tau", "lep", "unk"
    Uses first-layer physical daughters (expand artifacts & self-copies).
    """
    if W is None or abs_pdg(W) != 24:
        return "unk"
    D = physical_daughters_first_layer(W)
    apdgs = []
    for x in D:
        a = abs_pdg(x)
        if a is not None:
            apdgs.append(a)

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

def pick_direct_child(parent, abs_pdg_target):
    D = physical_daughters_first_layer(parent)
    cands = [x for x in D if abs_pdg(x) == abs_pdg_target]
    if not cands:
        return None
    return max(cands, key=lambda x: p_mag(x))

def W_direct_emu_lastgen(W, require_status1=False):
    """If W has direct e/mu, return (lastgen_lepton, flavor) else (None, None)."""
    if W is None or abs_pdg(W) != 24:
        return None, None
    D = physical_daughters_first_layer(W)
    cands = []
    for x in D:
        a = abs_pdg(x)
        if a in (11, 13):
            if require_status1:
                st = gen_status(x, default=None)
                if st is not None and st != 1:
                    continue
            cands.append(x)
    if not cands:
        return None, None
    lep0 = max(cands, key=lambda x: p_mag(x))
    lep_end = last_generation_selfcopy_down(lep0)
    flv = "e" if abs_pdg(lep0) == 11 else "mu"
    return lep_end, flv

def tau_to_emu_lastgen(tau):
    """
    If tau decays leptonically (tau -> e/mu + nus), return (lastgen_lepton, flavor).
    Otherwise (None, None).
    """
    if tau is None or abs_pdg(tau) != 15:
        return None, None
    tau_end = last_generation_selfcopy_down(tau)
    D = physical_daughters_first_layer(tau_end)
    cands = [x for x in D if abs_pdg(x) in (11, 13)]
    if not cands:
        return None, None
    lep0 = max(cands, key=lambda x: p_mag(x))
    lep_end = last_generation_selfcopy_down(lep0)
    flv = "e" if abs_pdg(lep0) == 11 else "mu"
    return lep_end, flv

# ============================================================
# Ancestor queries (diagnostics)
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
            # skip lepton self-copies upward
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
        parents = iter_parents(cur)
        ps = []
        for p in parents:
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

def origin_label(mc):
    """
    Priority:
      - origin_from_tau
      - origin_from_hadron (closest nonself ancestor abs(pdg) >= 100)
      - origin_from_topW   (has W ancestor AND that W has top ancestor)
      - origin_other
    """
    if mc is None:
        return "no_mc"
    if has_tau_ancestor(mc):
        return "origin_from_tau"
    anc = closest_nonself_ancestor(mc)
    if anc is not None:
        ap = abs_pdg(anc)
        if ap is not None and ap >= 100:
            return "origin_from_hadron"
    W = first_W_ancestor(mc)
    if W is not None and has_top_ancestor(W):
        return "origin_from_topW"
    return "origin_other"

# ============================================================
# Reco-MC relation navigator
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
    # To
    try:
        objs = nav.getRelatedToObjects(obj)
        ws = nav.getRelatedToWeights(obj)
        for o, w in zip(objs, ws):
            ww = float(w)
            if ww > best_w:
                best, best_w = o, ww
    except Exception:
        pass
    # From
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

# ============================================================
# Event classification (tau-inclusive) + truth e/mu list (incl. W->tau->e/mu)
# ============================================================
def classify_ttbar_event(mc_list, require_status1=False):
    """
    Return:
      ok (bool)   : whether we can find 2 root tops and 2 Ws
      ch (str)    : "HAD", "SEMI", "DI", "OTHER"
      truth_emu   : list of MCParticle (e/mu only; includes W direct e/mu and W->tau->e/mu)
      dbg_modes   : tuple(m1,m2) W modes
    """
    tops = find_root_tops(mc_list)
    if len(tops) < 2:
        return False, "UNCLASS", [], ("unk", "unk")

    W1 = find_W_from_top(tops[0])
    W2 = find_W_from_top(tops[1])
    if W1 is None or W2 is None:
        return False, "UNCLASS", [], ("unk", "unk")

    m1 = classify_W_mode(W1)
    m2 = classify_W_mode(W2)

    lep_modes = set(["e", "mu", "tau", "lep"])
    if m1 == "had" and m2 == "had":
        ch = "HAD"
    elif (m1 == "had" and m2 in lep_modes) or (m2 == "had" and m1 in lep_modes):
        ch = "SEMI"
    elif (m1 in lep_modes and m2 in lep_modes):
        ch = "DI"
    else:
        ch = "OTHER"

    # Build truth e/mu list (tau-inclusive via tau->e/mu)
    truth_emu = []

    def add_truth_from_W(W, mode):
        if mode in ("e", "mu"):
            lep, _flv = W_direct_emu_lastgen(W, require_status1=require_status1)
            if lep is not None and abs_pdg(lep) in (11, 13):
                truth_emu.append(lep)
            return

        if mode == "tau":
            tau0 = pick_direct_child(W, 15)
            if tau0 is None:
                return
            lep, _flv = tau_to_emu_lastgen(tau0)
            if lep is not None and abs_pdg(lep) in (11, 13):
                truth_emu.append(lep)
            return

        if mode == "lep":
            # best-effort: try direct e/mu first, else try tau->e/mu
            lep, _flv = W_direct_emu_lastgen(W, require_status1=require_status1)
            if lep is not None and abs_pdg(lep) in (11, 13):
                truth_emu.append(lep)
                return
            tau0 = pick_direct_child(W, 15)
            if tau0 is not None:
                lep2, _ = tau_to_emu_lastgen(tau0)
                if lep2 is not None and abs_pdg(lep2) in (11, 13):
                    truth_emu.append(lep2)
            return

    add_truth_from_W(W1, m1)
    add_truth_from_W(W2, m2)

    return True, ch, truth_emu, (m1, m2)

# ============================================================
# Helpers for printing
# ============================================================
def safe_div(n, d):
    return (float(n) / float(d)) if d else 0.0

def fmt_frac(n, d):
    if d == 0:
        return "0/0 (nan)"
    return f"{n}/{d} ({safe_div(n,d):.4f})"

def pdg_name(abs_code: int):
    m = {
        11: "e",
        13: "mu",
        15: "tau",
        22: "gamma",
        12: "nu_e",
        14: "nu_mu",
        16: "nu_tau",
        211: "pi",
        321: "K",
        130: "K0L",
        310: "K0S",
        2212: "p",
        2112: "n",
        111: "pi0",
    }
    return m.get(abs_code, "")

# ============================================================
# Stats containers
# ============================================================
def init_block():
    return {
        "n_evt": 0,
        "ch_cnt": Counter(),

        # multiplicities
        "dist_el": Counter(),
        "dist_mu": Counter(),
        "dist_sum": Counter(),
        "dist_isolep": Counter(),

        # pass counts
        "pass": Counter(),

        # efficiency: truth e/mu (incl tau->e/mu) in SEMI/DI
        "truth_emu": 0,
        "match_emu": 0,
        "truth_emu_fromtau": 0,   # optional debug
        "match_emu_fromtau": 0,   # optional debug
    }

def inc_dist(dist: Counter, x: int):
    dist[int(x)] += 1

# ============================================================
# Main
# ============================================================
def main():
    ap = argparse.ArgumentParser(
        description="Tau-inclusive (W direct tau included) H->bb(strict) + ttbar channel classification. "
                    "Diagnostics count mis-ID origins for ISOElectrons/ISOMuons (and Isolep) without restricting to truth=e/mu samples. "
                    "Also prints Isolep multiplicities + Tagger multiplicities jointly."
    )
    ap.add_argument("inputs", nargs="+", help="Input .slcio file(s)")
    ap.add_argument("--max-events", type=int, default=-1, help="Max events TOTAL across all files (default -1 = no limit)")
    ap.add_argument("--mc-col", default="MCParticlesSkimmed")
    ap.add_argument("--iso-e-col", default="ISOElectrons")
    ap.add_argument("--iso-mu-col", default="ISOMuons")
    ap.add_argument("--isolep-col", default="Isolep")
    ap.add_argument("--require-status1", action="store_true",
                    help="Require GeneratorStatus==1 for W direct lepton selection (usually unnecessary)")
    ap.add_argument("--topN-wrongpdg", type=int, default=10, help="Top-N wrong-PDG actual abs(PDG) to print per block")
    args = ap.parse_args()

    mc_fallbacks = [args.mc_col, "MCParticlesSkimmed", "MCParticles", "MCParticle"]
    iso_e_fallbacks = [args.iso_e_col, "ISOElectrons", "IsolatedElectrons"]
    iso_mu_fallbacks = [args.iso_mu_col, "ISOMuons", "IsolatedMuons"]
    isolep_fallbacks = [args.isolep_col, "Isolep", "IsolatedLeptons", "IsolatedLepton", "Leptons"]

    reco_mc_rel_names = ["RecoMCTruthLink", "MCTruthRecoLink", "MCTruthRecoLinkSkimmed"]

    # blocks: selection in {ALL, HBB}, channel in {HAD, SEMI, DI, OTHER, UNCLASS}
    blocks = defaultdict(init_block)

    # mis counters:
    # key examples:
    #   f"{sel}|{ch}|EL|total"
    #   f"{sel}|{ch}|EL|no_mc"
    #   f"{sel}|{ch}|EL|tag_correct|origin_from_tau"
    #   f"{sel}|{ch}|EL|tag_wrong|origin_from_hadron"
    mis = Counter()
    wrongpdg_abs = Counter()  # f"{sel}|{ch}|EL|abs{apdg}"

    used_rel_any = None

    def update_multiplicity(sel, ch, nel, nmu, niso):
        B = blocks[f"{sel}|{ch}"]
        B["n_evt"] += 1
        B["ch_cnt"][ch] += 1

        inc_dist(B["dist_el"], nel)
        inc_dist(B["dist_mu"], nmu)
        inc_dist(B["dist_sum"], nel + nmu)
        inc_dist(B["dist_isolep"], niso)

        # requested pass counters (0/1/2) + joint consistency
        s = nel + nmu
        if s == 0:
            B["pass"]["SUM0"] += 1
        if s == 1:
            B["pass"]["SUM1"] += 1
        if s == 2:
            B["pass"]["SUM2"] += 1

        if niso == 0:
            B["pass"]["ISO0"] += 1
        if niso == 1:
            B["pass"]["ISO1"] += 1
        if niso == 2:
            B["pass"]["ISO2"] += 1

        if s == 0 and niso == 0:
            B["pass"]["SUM0_ISO0"] += 1
        if s == 1 and niso == 1:
            B["pass"]["SUM1_ISO1"] += 1
        if s == 2 and niso == 2:
            B["pass"]["SUM2_ISO2"] += 1

    def update_eff(sel, ch, truth_emu, reco_set_e, reco_set_mu):
        # only meaningful for SEMI/DI
        if ch not in ("SEMI", "DI"):
            return
        B = blocks[f"{sel}|{ch}"]

        # truth sets
        truth_e = set()
        truth_mu = set()
        truth_tauflag = {}  # key -> bool (from tau chain) for debug

        for tl in truth_emu:
            k = lastgen_key(tl)
            if k is None:
                continue
            a = abs_pdg(tl)
            if a == 11:
                truth_e.add(k)
                truth_tauflag[k] = has_tau_ancestor(tl)
            elif a == 13:
                truth_mu.add(k)
                truth_tauflag[k] = has_tau_ancestor(tl)

        # matches
        me = sum(1 for k in truth_e if k in reco_set_e)
        mm = sum(1 for k in truth_mu if k in reco_set_mu)

        B["truth_emu"] += (len(truth_e) + len(truth_mu))
        B["match_emu"] += (me + mm)

        # optional debug: tau-sourced truth e/mu
        n_fromtau = sum(1 for k, v in truth_tauflag.items() if v)
        m_fromtau = 0
        for k, v in truth_tauflag.items():
            if not v:
                continue
            # choose correct reco set by checking if key belongs to truth_e or truth_mu
            if k in truth_e and k in reco_set_e:
                m_fromtau += 1
            if k in truth_mu and k in reco_set_mu:
                m_fromtau += 1
        B["truth_emu_fromtau"] += n_fromtau
        B["match_emu_fromtau"] += m_fromtau

    def update_mis(sel, ch, tag, matches, target_abs=None):
        """
        tag: "EL", "MU", "ISO" (Isolep)
        matches: list of (rp, mc_match, w)
        For EL/MU: define tag_correct vs tag_wrong by target_abs (11/13).
        For ISO: no tag_correct/wrong; only record actual abs(PDG) groups + origin.
        """
        base = f"{sel}|{ch}|{tag}"
        mis[f"{base}|total"] += len(matches)

        for _rp, mc_match, _w in matches:
            if mc_match is None:
                mis[f"{base}|no_mc"] += 1
                continue

            ap = abs_pdg(mc_match)
            org = origin_label(mc_match)

            if target_abs is None:
                # Isolep: record composition by actual apdg bucket
                bucket = "is_emu" if ap in (11, 13) else ("is_tau" if ap == 15 else "is_other")
                mis[f"{base}|{bucket}|{org}"] += 1
                continue

            # ISOElectrons/ISOMuons: tag correctness
            tagcls = "tag_correct" if ap == target_abs else "tag_wrong"
            mis[f"{base}|{tagcls}|total"] += 1
            mis[f"{base}|{tagcls}|{org}"] += 1

            if tagcls == "tag_wrong":
                # store what it actually is
                if ap is None:
                    ap = 0
                wrongpdg_abs[f"{base}|abs{ap}"] += 1

    # ============================
    # Loop files/events
    # ============================
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

            # --- MC collection ---
            mc_name = pick_collection(evt, args.mc_col, mc_fallbacks)
            if mc_name is None:
                # still count as UNCLASS at ALL level (no MC)
                blocks["ALL|UNCLASS"]["n_evt"] += 1
                blocks["ALL|UNCLASS"]["ch_cnt"]["UNCLASS"] += 1
                continue

            try:
                mc_col = evt.getCollection(mc_name)
                nmc = int(mc_col.getNumberOfElements())
                mc_list = [mc_col.getElementAt(i) for i in range(nmc)]
            except Exception:
                blocks["ALL|UNCLASS"]["n_evt"] += 1
                blocks["ALL|UNCLASS"]["ch_cnt"]["UNCLASS"] += 1
                continue

            # --- selection HBB? ---
            h = find_higgs_hbb(mc_list)
            is_hbb = (h is not None)

            # --- relation navigator ---
            nav = None
            used_rel = None
            for rn in reco_mc_rel_names:
                nav_try = make_nav(evt, rn)
                if nav_try is not None:
                    nav = nav_try
                    used_rel = rn
                    used_rel_any = rn
                    break

            # --- ISO collections ---
            iso_e_name = pick_collection(evt, args.iso_e_col, iso_e_fallbacks)
            iso_mu_name = pick_collection(evt, args.iso_mu_col, iso_mu_fallbacks)
            isolep_name = pick_collection(evt, args.isolep_col, isolep_fallbacks)

            iso_e_list, iso_mu_list, isolep_list = [], [], []

            if iso_e_name is not None:
                try:
                    c = evt.getCollection(iso_e_name)
                    iso_e_list = [c.getElementAt(i) for i in range(int(c.getNumberOfElements()))]
                except Exception:
                    iso_e_list = []

            if iso_mu_name is not None:
                try:
                    c = evt.getCollection(iso_mu_name)
                    iso_mu_list = [c.getElementAt(i) for i in range(int(c.getNumberOfElements()))]
                except Exception:
                    iso_mu_list = []

            if isolep_name is not None:
                try:
                    c = evt.getCollection(isolep_name)
                    isolep_list = [c.getElementAt(i) for i in range(int(c.getNumberOfElements()))]
                except Exception:
                    isolep_list = []

            # --- match lists ---
            def match_list(rps):
                out = []
                if nav is None:
                    for rp in rps:
                        out.append((rp, None, -1.0))
                    return out
                for rp in rps:
                    mc_match, w = best_related(nav, rp)
                    out.append((rp, mc_match, w))
                return out

            iso_e_matches = match_list(iso_e_list)
            iso_mu_matches = match_list(iso_mu_list)
            isolep_matches = match_list(isolep_list)

            # --- build reco sets for efficiency matching (correct flavor only) ---
            reco_set_e = set()
            for _rp, mc_match, _w in iso_e_matches:
                if mc_match is None:
                    continue
                if abs_pdg(mc_match) != 11:
                    continue
                k = lastgen_key(mc_match)
                if k is not None:
                    reco_set_e.add(k)

            reco_set_mu = set()
            for _rp, mc_match, _w in iso_mu_matches:
                if mc_match is None:
                    continue
                if abs_pdg(mc_match) != 13:
                    continue
                k = lastgen_key(mc_match)
                if k is not None:
                    reco_set_mu.add(k)

            # --- truth channel classification (tau-inclusive) ---
            ok_tt, ch, truth_emu, dbg_modes = classify_ttbar_event(mc_list, require_status1=args.require_status1)

            # for ALL selection: if cannot classify, use UNCLASS
            ch_all = ch if ok_tt else "UNCLASS"
            # update multiplicities for ALL|ch
            update_multiplicity("ALL", ch_all, len(iso_e_list), len(iso_mu_list), len(isolep_list))
            # update efficiency for ALL|SEMI/DI
            update_eff("ALL", ch_all, truth_emu, reco_set_e, reco_set_mu)

            # update mis only for SEMI/DI (most relevant)
            if ch_all in ("SEMI", "DI"):
                update_mis("ALL", ch_all, "EL", iso_e_matches, target_abs=11)
                update_mis("ALL", ch_all, "MU", iso_mu_matches, target_abs=13)
                update_mis("ALL", ch_all, "ISO", isolep_matches, target_abs=None)

            # for HBB selection
            if is_hbb:
                ch_hbb = ch if ok_tt else "UNCLASS"
                update_multiplicity("HBB", ch_hbb, len(iso_e_list), len(iso_mu_list), len(isolep_list))
                update_eff("HBB", ch_hbb, truth_emu, reco_set_e, reco_set_mu)
                if ch_hbb in ("SEMI", "DI"):
                    update_mis("HBB", ch_hbb, "EL", iso_e_matches, target_abs=11)
                    update_mis("HBB", ch_hbb, "MU", iso_mu_matches, target_abs=13)
                    update_mis("HBB", ch_hbb, "ISO", isolep_matches, target_abs=None)

        reader.close()

    # ============================================================
    # Printing
    # ============================================================
    def print_block_summary(sel, ch):
        B = blocks[f"{sel}|{ch}"]
        print(f"\n==================== {sel} | {ch} ====================")
        print(f"Events: {B['n_evt']}")

        # multiplicity pass
        print("Multiplicity pass counts:")
        keys = ["SUM0", "SUM1", "SUM2", "ISO0", "ISO1", "ISO2", "SUM0_ISO0", "SUM1_ISO1", "SUM2_ISO2"]
        for k in keys:
            print(f"  {k:10s} : {B['pass'].get(k, 0)}")

        # efficiency (only meaningful for SEMI/DI)
        if ch in ("SEMI", "DI"):
            print("Truth e/mu (incl. W->tau->e/mu) reconstruction efficiency (correct flavor match):")
            print(f"  match/truth : {fmt_frac(B['match_emu'], B['truth_emu'])}")
            # debug tau-sourced
            print(f"  (tau-sourced truth e/mu) match/truth : {fmt_frac(B['match_emu_fromtau'], B['truth_emu_fromtau'])}")

        # small multiplicity dist print
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

        print_dist("ISOElectrons multiplicity", B["dist_el"])
        print_dist("ISOMuons multiplicity", B["dist_mu"])
        print_dist("Tagger SUM (EL+MU) multiplicity", B["dist_sum"])
        print_dist("Isolep multiplicity", B["dist_isolep"])

    def print_mis_table(sel, ch, tag, topN=10):
        base = f"{sel}|{ch}|{tag}"
        tot = mis.get(f"{base}|total", 0)
        if tot == 0:
            print(f"\n[{sel}|{ch}] {tag}: total=0")
            return

        print(f"\n[{sel}|{ch}] {tag}  total={tot}")
        print(f"  no_mc: {mis.get(f'{base}|no_mc', 0)}  frac={safe_div(mis.get(f'{base}|no_mc', 0), tot):.4f}")

        if tag in ("EL", "MU"):
            c_tot = mis.get(f"{base}|tag_correct|total", 0)
            w_tot = mis.get(f"{base}|tag_wrong|total", 0)
            print(f"  tag_correct: {c_tot}  frac={safe_div(c_tot, tot):.4f}")
            for org in ("origin_from_topW", "origin_from_tau", "origin_from_hadron", "origin_other"):
                v = mis.get(f"{base}|tag_correct|{org}", 0)
                print(f"    {org:18s} : {v:6d}  frac_in_correct={safe_div(v, c_tot):.4f}")

            print(f"  tag_wrong:   {w_tot}  frac={safe_div(w_tot, tot):.4f}")
            for org in ("origin_from_topW", "origin_from_tau", "origin_from_hadron", "origin_other"):
                v = mis.get(f"{base}|tag_wrong|{org}", 0)
                print(f"    {org:18s} : {v:6d}  frac_in_wrong={safe_div(v, w_tot):.4f}")

            # what they actually are
            items = []
            for k, v in wrongpdg_abs.items():
                if not k.startswith(base + "|abs"):
                    continue
                # parse abs code
                try:
                    abs_code = int(k.split("|abs")[-1])
                except Exception:
                    abs_code = -1
                items.append((abs_code, v))
            items.sort(key=lambda x: -x[1])

            if items:
                print(f"  tag_wrong actual abs(PDG) top{topN}:")
                for abs_code, v in items[:topN]:
                    nm = pdg_name(abs_code)
                    nm = f" ({nm})" if nm else ""
                    print(f"    absPDG={abs_code:6d}{nm:8s} : {v}")

        else:
            # Isolep: show composition buckets
            for bucket in ("is_emu", "is_tau", "is_other"):
                bsum = 0
                for org in ("origin_from_topW", "origin_from_tau", "origin_from_hadron", "origin_other"):
                    bsum += mis.get(f"{base}|{bucket}|{org}", 0)
                print(f"  {bucket:8s} : {bsum:6d}  frac={safe_div(bsum, tot):.4f}")
                for org in ("origin_from_topW", "origin_from_tau", "origin_from_hadron", "origin_other"):
                    v = mis.get(f"{base}|{bucket}|{org}", 0)
                    print(f"    {org:18s} : {v:6d}  frac_in_bucket={safe_div(v, bsum):.4f}")

    print("\n" + "=" * 120)
    print("SUMMARY: Tau-inclusive channel definition + ISO diagnostics (HBB and ALL)")
    print("=" * 120)
    print(f"Files: {len(args.inputs)}")
    print(f"Events processed (TOTAL): {n_processed}")
    if used_rel_any is None:
        print("[WARN] No reco-mc relation collection found. All matching-based results become meaningless.")
    else:
        print(f"[INFO] Used reco-mc relation: {used_rel_any}")

    # print blocks for BOTH selections
    for sel in ("ALL", "HBB"):
        print("\n" + "-" * 120)
        print(f"Selection: {sel}")
        print("-" * 120)
        for ch in ("HAD", "SEMI", "DI", "OTHER", "UNCLASS"):
            print_block_summary(sel, ch)

        # mis tables only for SEMI/DI (user focus)
        print("\n" + "-" * 120)
        print(f"Mis-ID / origin diagnostics (subset = {sel} | SEMI/DI)")
        print("-" * 120)
        for ch in ("SEMI", "DI"):
            print_mis_table(sel, ch, "EL", topN=args.topN_wrongpdg)
            print_mis_table(sel, ch, "MU", topN=args.topN_wrongpdg)
            print_mis_table(sel, ch, "ISO", topN=args.topN_wrongpdg)

    print("\n" + "=" * 120)

if __name__ == "__main__":
    main()
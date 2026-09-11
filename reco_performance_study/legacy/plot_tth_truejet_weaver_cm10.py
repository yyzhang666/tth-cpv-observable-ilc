#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import glob
import itertools
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pyLCIO import IOIMPL, UTIL


# ============================================================
# User-tunable constants
# ============================================================

# IMPORTANT:
# This order is taken from your current RefinedJets6 dump:
#   mc_b, mc_bbar, mc_c, mc_cbar, mc_d, mc_dbar, mc_g, mc_s, mc_sbar, mc_u, mc_ubar
# If another file has a different ParameterNames_weaver order, update this list.
WEAVER_ORDER = [
    "mc_b", "mc_bbar",
    "mc_c", "mc_cbar",
    "mc_d", "mc_dbar",
    "mc_g",
    "mc_s", "mc_sbar",
    "mc_u", "mc_ubar",
]

# 10 quark classes only, for a 10x10 matrix
CLASS_ORDER = [
    "b", "bbar",
    "c", "cbar",
    "s", "sbar",
    "u", "ubar",
    "d", "dbar",
]

DISPLAY_LABELS = [
    r"$b$", r"$\bar b$",
    r"$c$", r"$\bar c$",
    r"$s$", r"$\bar s$",
    r"$u$", r"$\bar u$",
    r"$d$", r"$\bar d$",
]


# ============================================================
# Basic helpers
# ============================================================

def expand_inputs(patterns):
    out = []
    for p in patterns:
        matches = sorted(glob.glob(p))
        if matches:
            out.extend(matches)
        else:
            out.append(p)

    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def v2list(v):
    return [v[i] for i in range(v.size())]


def get_col(evt, name):
    try:
        return evt.getCollection(name)
    except Exception:
        return None


def obj_id(obj):
    """
    Return a stable LCObject ID if available.
    """
    for name in ("id", "getObjectID", "getID"):
        try:
            f = getattr(obj, name)
            if callable(f):
                return int(f())
        except Exception:
            pass
    raise RuntimeError("Cannot obtain LCObject ID")


def pdg_to_label(pdg):
    if pdg == 5:
        return "b"
    if pdg == -5:
        return "bbar"
    if pdg == 4:
        return "c"
    if pdg == -4:
        return "cbar"
    if pdg == 3:
        return "s"
    if pdg == -3:
        return "sbar"
    if pdg == 2:
        return "u"
    if pdg == -2:
        return "ubar"
    if pdg == 1:
        return "d"
    if pdg == -1:
        return "dbar"
    return None


# ============================================================
# Truth selection: H->bb + semileptonic ttbar
# ============================================================

def first_physical_children(p, max_depth=20):
    """
    Flatten technical nodes (91/92/94) and self-copies.
    Return first-layer physical daughters.
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

            oid = obj_id(d)
            if oid in seen:
                continue
            seen.add(oid)

            try:
                apdg = abs(int(d.getPDG()))
                pdg = int(d.getPDG())
            except Exception:
                continue

            if apdg in (91, 92, 94) or pdg == int(node.getPDG()):
                stack.append((d, depth + 1))
            else:
                out.append(d)

    return out


def get_top_W(top):
    kids = first_physical_children(top, max_depth=10)
    for k in kids:
        try:
            if abs(int(k.getPDG())) == 24:
                return k
        except Exception:
            pass
    return None


def classify_W_mode(W):
    if W is None:
        return "unk"

    kids = first_physical_children(W, max_depth=10)
    apdgs = []
    for k in kids:
        try:
            apdgs.append(abs(int(k.getPDG())))
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


def truth_ttbar_channel(evt, colMC="MCParticlesSkimmed"):
    cMCP = get_col(evt, colMC)
    if cMCP is None:
        return None

    top_p = None
    top_m = None

    for i in range(cMCP.getNumberOfElements()):
        p = cMCP.getElementAt(i)
        try:
            pdg = int(p.getPDG())
        except Exception:
            continue

        if pdg == 6 and top_p is None:
            top_p = p
        elif pdg == -6 and top_m is None:
            top_m = p

    if top_p is None or top_m is None:
        return None

    Wp = get_top_W(top_p)
    Wm = get_top_W(top_m)

    mp = classify_W_mode(Wp)
    mm = classify_W_mode(Wm)

    if mp == "unk" or mm == "unk":
        return None

    def is_lep(m):
        return m in ("e", "mu", "tau", "lep")

    if mp == "had" and mm == "had":
        return "had"

    if (mp == "had" and is_lep(mm)) or (mm == "had" and is_lep(mp)):
        lep_mode = mm if mp == "had" else mp
        if lep_mode == "e":
            return "semilep_e"
        if lep_mode == "mu":
            return "semilep_mu"
        if lep_mode == "tau":
            return "semilep_tau"
        return "semilep_lep"

    if is_lep(mp) and is_lep(mm):
        return "dilep"

    return None


def truth_h_to_bb(evt, colMC="MCParticlesSkimmed"):
    cMCP = get_col(evt, colMC)
    if cMCP is None:
        return None

    H = None
    for i in range(cMCP.getNumberOfElements()):
        p = cMCP.getElementAt(i)
        try:
            if int(p.getPDG()) == 25:
                H = p
                break
        except Exception:
            continue

    if H is None:
        return False

    kids = first_physical_children(H, max_depth=10)
    nb = 0
    for k in kids:
        try:
            if abs(int(k.getPDG())) == 5:
                nb += 1
        except Exception:
            continue

    return (nb >= 2)


def keep_semilep_channel(chan, semilep_mode):
    if semilep_mode == "all":
        return chan in ("semilep_e", "semilep_mu", "semilep_tau", "semilep_lep")
    if semilep_mode == "emu":
        return chan in ("semilep_e", "semilep_mu")
    if semilep_mode == "emu_tau":
        return chan in ("semilep_e", "semilep_mu", "semilep_tau")
    raise RuntimeError(f"Unknown semilep_mode: {semilep_mode}")


# ============================================================
# TrueJet helpers
# ============================================================

def get_truejet_quark_pdg(truejet):
    """
    Read the quark PDG from TrueJet particle IDs.
    We pick the first ParticleID entry whose PDG is a quark.
    """
    try:
        pids = v2list(truejet.getParticleIDs())
    except Exception:
        return None

    for pid in pids:
        try:
            pdg = int(pid.getPDG())
        except Exception:
            continue
        if abs(pdg) in (1, 2, 3, 4, 5):
            return pdg

    return None


def collect_truejet_quark_jets(truejets_col):
    """
    Return the 6 quark-like TrueJets and their labels.
    """
    out = []
    for i in range(truejets_col.getNumberOfElements()):
        tj = truejets_col.getElementAt(i)
        pdg = get_truejet_quark_pdg(tj)
        if pdg is None:
            continue

        label = pdg_to_label(pdg)
        if label is None:
            continue

        out.append({
            "obj": tj,
            "id": obj_id(tj),
            "pdg": pdg,
            "label": label,
        })

    return out


def build_truejet_pfo_map(truejet_quarks, nav_tj_pfo):
    """
    For each TrueJet, build:
      - set of constituent PFO IDs
      - total constituent energy
    """
    tj_map = {}

    for item in truejet_quarks:
        tj = item["obj"]
        tjid = item["id"]

        try:
            pfos = v2list(nav_tj_pfo.getRelatedToObjects(tj))
        except Exception:
            pfos = []

        pfo_ids = set()
        energy_sum = 0.0

        for p in pfos:
            try:
                pid = obj_id(p)
                en = float(p.getEnergy())
            except Exception:
                continue
            pfo_ids.add(pid)
            energy_sum += en

        tj_map[tjid] = {
            "label": item["label"],
            "pdg": item["pdg"],
            "pfo_ids": pfo_ids,
            "energy": energy_sum,
        }

    return tj_map


def build_reco_jet_pfo_map(reco_jets_col):
    """
    For each reco jet, build:
      - set of constituent PFO IDs
      - dict pfo_id -> energy
      - total jet energy
    """
    out = []

    for i in range(reco_jets_col.getNumberOfElements()):
        jet = reco_jets_col.getElementAt(i)

        pfo_ids = set()
        pfo_e = {}
        jet_e = 0.0

        try:
            parts = v2list(jet.getParticles())
        except Exception:
            parts = []

        for p in parts:
            try:
                pid = obj_id(p)
                en = float(p.getEnergy())
            except Exception:
                continue
            pfo_ids.add(pid)
            pfo_e[pid] = en
            jet_e += en

        out.append({
            "obj": jet,
            "id": obj_id(jet),
            "pfo_ids": pfo_ids,
            "pfo_energy": pfo_e,
            "energy": jet_e,
        })

    return out


# ============================================================
# Matching helpers
# ============================================================

def shared_energy(reco_info, true_info):
    """
    Shared PFO energy between one reco jet and one TrueJet.
    """
    e = 0.0
    common = reco_info["pfo_ids"] & true_info["pfo_ids"]
    for pid in common:
        e += reco_info["pfo_energy"].get(pid, 0.0)
    return e


def dice_score(e_shared, e_reco, e_true):
    denom = e_reco + e_true
    if denom <= 0.0:
        return 0.0
    return 2.0 * e_shared / denom


def best_assignment(score_mat):
    """
    Exhaustive search over 6! permutations.
    score_mat[i, a] = score between reco jet i and true jet a.
    """
    n = score_mat.shape[0]
    best_perm = None
    best_val = -1.0

    for perm in itertools.permutations(range(n)):
        s = 0.0
        for i in range(n):
            s += score_mat[i, perm[i]]
        if s > best_val:
            best_val = s
            best_perm = perm

    return best_perm, best_val


# ============================================================
# Weaver helpers
# ============================================================

def get_weaver_alg_id(jets_col, weaver_name="weaver"):
    pid_handler = UTIL.PIDHandler(jets_col)
    return pid_handler.getAlgorithmID(weaver_name), pid_handler


def get_pid_for_alg(jet, alg_id):
    try:
        pids = v2list(jet.getParticleIDs())
    except Exception:
        return None

    for pid in pids:
        try:
            if int(pid.getAlgorithmType()) == int(alg_id):
                return pid
        except Exception:
            continue

    return None


def get_weaver_pred_label_quark10(jet, alg_id):
    """
    Return predicted label among 10 quark classes only.
    We intentionally exclude gluon for a 10x10 matrix.
    """
    pid = get_pid_for_alg(jet, alg_id)
    if pid is None:
        return None, None

    try:
        pars = [float(x) for x in v2list(pid.getParameters())]
    except Exception:
        return None, None

    if len(pars) < len(WEAVER_ORDER):
        return None, None

    # Build score dict from the current file's known order
    score_dict = {}
    for name, val in zip(WEAVER_ORDER, pars[:len(WEAVER_ORDER)]):
        score_dict[name] = val

    # Keep only 10 quark classes
    quark_names = [
        "mc_b", "mc_bbar",
        "mc_c", "mc_cbar",
        "mc_s", "mc_sbar",
        "mc_u", "mc_ubar",
        "mc_d", "mc_dbar",
    ]

    best_name = None
    best_val = -1.0
    for name in quark_names:
        val = score_dict.get(name, -999.0)
        if val > best_val:
            best_val = val
            best_name = name

    if best_name is None:
        return None, score_dict

    label = best_name.replace("mc_", "")
    return label, score_dict


# ============================================================
# Matrix helpers
# ============================================================

def init_matrix():
    return np.zeros((len(CLASS_ORDER), len(CLASS_ORDER)), dtype=np.int64)


def fill_matrix(mat, pred_label, true_label):
    i = CLASS_ORDER.index(pred_label)
    j = CLASS_ORDER.index(true_label)
    mat[i, j] += 1


def normalize_by_true_columns(mat):
    out = np.zeros_like(mat, dtype=float)
    for j in range(mat.shape[1]):
        s = mat[:, j].sum()
        if s > 0:
            out[:, j] = mat[:, j] / float(s)
    return out


def save_csv(path, counts, norm):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["pred\\true"] + CLASS_ORDER
        w.writerow(header)
        for i, pred in enumerate(CLASS_ORDER):
            w.writerow([pred] + [f"{norm[i, j]:.6f}" for j in range(len(CLASS_ORDER))])

        w.writerow([])
        w.writerow(["raw_counts"])
        w.writerow(header)
        for i, pred in enumerate(CLASS_ORDER):
            w.writerow([pred] + [str(int(counts[i, j])) for j in range(len(CLASS_ORDER))])


def plot_confusion(norm, out_png, title):
    fig, ax = plt.subplots(figsize=(10.5, 8.3), dpi=180)

    vmax = max(0.7, float(np.max(norm)) if norm.size > 0 else 0.7)
    im = ax.imshow(norm, origin="upper", aspect="auto", vmin=0.0, vmax=vmax, cmap="cividis")

    ax.set_xticks(range(len(CLASS_ORDER)))
    ax.set_xticklabels(DISPLAY_LABELS, fontsize=14)
    ax.set_yticks(range(len(CLASS_ORDER)))
    ax.set_yticklabels(DISPLAY_LABELS, fontsize=14)

    ax.set_xlabel("True flavor", fontsize=20)
    ax.set_ylabel("Predicted flavor", fontsize=20)
    ax.set_title(title, fontsize=20)

    for i in range(norm.shape[0]):
        for j in range(norm.shape[1]):
            ax.text(j, i, f"{norm[i, j]:.3f}", ha="center", va="center", fontsize=9, color="black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=12)

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)


# ============================================================
# Main event loop
# ============================================================

def main():
    ap = argparse.ArgumentParser(
        description=(
            "Build a TrueJet-based Weaver 10x10 confusion matrix for tth samples, "
            "restricted to truth H->bb and semileptonic ttbar events. "
            "Reco jets are RefinedJets6, truth jets are the 6 quark-like TrueJets. "
            "Reco-True matching is done by constituent-PFO energy overlap."
        )
    )
    ap.add_argument("inputs", nargs="+", help="input slcio file(s) or glob pattern(s)")
    ap.add_argument("--colMC", default="MCParticlesSkimmed")
    ap.add_argument("--reco-jets", default="RefinedJets6")
    ap.add_argument("--truejets", default="TrueJets")
    ap.add_argument("--truejet-pfo-link", default="TrueJetPFOLink")
    ap.add_argument("--semilep-mode", choices=["all", "emu", "emu_tau"], default="all")
    ap.add_argument("--weaver-name", default="weaver")
    ap.add_argument("--min-dice", type=float, default=0.0,
                    help="minimum Dice score required for every matched pair in an event")
    ap.add_argument("--maxEvents", type=int, default=-1)
    ap.add_argument("--out-prefix", default="tth_truejet_weaver_cm10")
    args = ap.parse_args()

    files = expand_inputs(args.inputs)

    reader = IOIMPL.LCFactory.getInstance().createLCReader()

    counts = init_matrix()
    summary = Counter()

    processed = 0
    consecutive_read_errors = 0

    for path in files:
        summary["files"] += 1

        try:
            reader.open(path)
        except Exception as e:
            print(f"[WARN] cannot open {path}: {e}")
            summary["file_open_fail"] += 1
            continue

        while True:
            if args.maxEvents >= 0 and processed >= args.maxEvents:
                break

            try:
                evt = reader.readNextEvent()
                consecutive_read_errors = 0
            except Exception as e:
                summary["read_errors"] += 1
                print(f"[WARN] readNextEvent() failed at processed={processed}: {e}")
                consecutive_read_errors += 1
                if consecutive_read_errors >= 3:
                    print("[WARN] consecutive read errors >= 3, stop reading this file.")
                    break
                continue

            if evt is None:
                break

            processed += 1
            summary["events_total"] += 1

            # ---------- truth event selection ----------
            chan = truth_ttbar_channel(evt, colMC=args.colMC)
            if chan is None:
                summary["skip_bad_truth_chan"] += 1
                continue
            summary[f"truth_{chan}"] += 1

            if not keep_semilep_channel(chan, args.semilep_mode):
                summary["skip_non_semilep"] += 1
                continue

            hbb = truth_h_to_bb(evt, colMC=args.colMC)
            if hbb is None:
                summary["missing_mc"] += 1
                continue
            if hbb is not True:
                summary["skip_non_hbb"] += 1
                continue

            summary["events_selected"] += 1

            # ---------- collections ----------
            reco_col = get_col(evt, args.reco_jets)
            if reco_col is None:
                summary["missing_reco_jets"] += 1
                continue

            truejet_col = get_col(evt, args.truejets)
            if truejet_col is None:
                summary["missing_truejets"] += 1
                continue

            tj_pfo_link = get_col(evt, args.truejet_pfo_link)
            if tj_pfo_link is None:
                summary["missing_truejet_pfo_link"] += 1
                continue

            if reco_col.getNumberOfElements() != 6:
                summary[f"skip_reco_njet_{reco_col.getNumberOfElements()}"] += 1
                continue

            # ---------- select 6 quark-like TrueJets ----------
            truejet_quarks = collect_truejet_quark_jets(truejet_col)
            summary[f"truejet_quark_mult_{len(truejet_quarks)}"] += 1

            if len(truejet_quarks) != 6:
                summary["skip_bad_truejet_quark_mult"] += 1
                continue

            # ---------- build overlap structures ----------
            nav_tj_pfo = UTIL.LCRelationNavigator(tj_pfo_link)
            tj_map = build_truejet_pfo_map(truejet_quarks, nav_tj_pfo)
            reco_infos = build_reco_jet_pfo_map(reco_col)

            # Order TrueJets deterministically
            tj_ids = sorted(tj_map.keys())

            # ---------- build 6x6 score matrix ----------
            score_mat = np.zeros((6, 6), dtype=float)
            shared_mat = np.zeros((6, 6), dtype=float)

            for i in range(6):
                reco_i = reco_infos[i]
                for a in range(6):
                    tj_info = tj_map[tj_ids[a]]
                    e_shared = shared_energy(reco_i, tj_info)
                    shared_mat[i, a] = e_shared
                    score_mat[i, a] = dice_score(e_shared, reco_i["energy"], tj_info["energy"])

            # ---------- one-to-one optimal matching ----------
            perm, best_sum = best_assignment(score_mat)
            if perm is None:
                summary["skip_no_assignment"] += 1
                continue

            # ---------- event-level quality cut ----------
            bad_quality = False
            for i in range(6):
                if score_mat[i, perm[i]] < args.min_dice:
                    bad_quality = True
                    break
            if bad_quality:
                summary["skip_low_dice_event"] += 1
                continue

            # ---------- predicted labels from Weaver ----------
            try:
                alg_id, pid_handler = get_weaver_alg_id(reco_col, weaver_name=args.weaver_name)
            except Exception:
                summary["missing_weaver_algo"] += 1
                continue

            event_ok = True
            for i in range(6):
                reco_jet = reco_infos[i]["obj"]
                pred_label, score_dict = get_weaver_pred_label_quark10(reco_jet, alg_id)
                if pred_label is None:
                    event_ok = False
                    summary["missing_weaver_pid"] += 1
                    break

                # Optional diagnostic: count how often full 11-way argmax is gluon
                if score_dict is not None:
                    full_best = max(score_dict.items(), key=lambda kv: kv[1])[0]
                    if full_best == "mc_g":
                        summary["jets_full_argmax_g"] += 1

                tj_info = tj_map[tj_ids[perm[i]]]
                true_label = tj_info["label"]

                fill_matrix(counts, pred_label, true_label)

            if not event_ok:
                continue

            summary["events_used"] += 1

        try:
            reader.close()
        except Exception:
            pass

        if args.maxEvents >= 0 and processed >= args.maxEvents:
            break

    # ---------- outputs ----------
    norm = normalize_by_true_columns(counts)

    np.savez(
        f"{args.out_prefix}.npz",
        counts=counts,
        norm=norm,
        class_order=np.array(CLASS_ORDER, dtype=object),
        display_labels=np.array(DISPLAY_LABELS, dtype=object),
    )
    save_csv(f"{args.out_prefix}.csv", counts, norm)
    plot_confusion(norm, f"{args.out_prefix}.png",
                   title=r"$t\bar t H,\ H\to b\bar b,\ \mathrm{semileptonic}$" + "\nTrueJet overlap matched, Weaver 10x10")

    with open(f"{args.out_prefix}.summary.txt", "w", encoding="utf-8") as f:
        f.write("=== tth TrueJet-based Weaver 10x10 confusion matrix ===\n")
        f.write(f"files               : {summary['files']}\n")
        f.write(f"events_total        : {summary['events_total']}\n")
        f.write(f"events_selected     : {summary['events_selected']}\n")
        f.write(f"events_used         : {summary['events_used']}\n")
        f.write(f"min_dice            : {args.min_dice}\n")
        f.write(f"semilep_mode        : {args.semilep_mode}\n\n")

        for key in sorted(summary.keys()):
            if key in ("files", "events_total", "events_selected", "events_used"):
                continue
            f.write(f"{key:24s}: {summary[key]}\n")

    print(f"Processed events      : {processed}")
    print(f"Selected events       : {summary['events_selected']}")
    print(f"Used events           : {summary['events_used']}")
    print(f"Saved                 : {args.out-prefix if False else ''}")
    print(f"PNG                   : {args.out_prefix}.png")
    print(f"CSV                   : {args.out_prefix}.csv")
    print(f"NPZ                   : {args.out_prefix}.npz")
    print(f"SUMMARY               : {args.out_prefix}.summary.txt")

    print("\nDiagnostics:")
    for key in sorted(summary.keys()):
        if key in ("files", "events_total", "events_selected", "events_used"):
            continue
        print(f"  {key:24s}: {summary[key]}")


if __name__ == "__main__":
    main()
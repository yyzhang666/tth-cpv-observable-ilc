#!/usr/bin/env python3
"""Plot frozen mass selections from ten existing Physsim ROOT files."""
from __future__ import annotations

import argparse, csv, hashlib, importlib.util, json, math, sys
from pathlib import Path

CHUNKS = tuple(range(1, 11))
PRICE_MODE = "price2014_prefit_bcharge1p00"
KINFIT_MODE = "logchi2_plus_flavor_x0p3"
BINS = 60
EXPECTED = {"best_rows": 46415, "best_success_rows": 46414, "candidate_rows": 1099930, "common_rows": 46414}
EXPECTED_FAILED_BEST = {(8, 1, 6976, 6976)}
EXPECTED_LIBRARY_SHA256 = "d50ef394d7cda39e5304fd6a89d0f7e677e29556c12213c6405c4520ed6120cd"
DISPLAY = {
    PRICE_MODE: {"label": "mass-constraint-only + signed flavor (PREFIT)", "color": "#2364aa", "columns": {"W": "mW_had_prefit", "top": "mt_had_prefit", "H": "mH_prefit"}},
    KINFIT_MODE: {"label": "kinfit + signed flavor (POSTFIT)", "color": "#d95f02", "columns": {"W": "mW_had_postfit", "top": "mt_had_postfit", "H": "mH_postfit"}},
}
OBJECTS = {"W": {"range": (40., 130.), "reference": 80.4}, "top": {"range": (100., 240.), "reference": 172.5}, "H": {"range": (40., 210.), "reference": 125.}}
TOP_REQUIRED = {"accepted", "best_combo_id", "event_index", "event_number", "final_fit_score", "final_flavor_score", "final_selection_mode", "final_selection_score", "fit_success", "flavor_jet_collection_name", "flavor_weight", "jet_collection_name", "mH_postfit", "mW_had_postfit", "mt_had_postfit", "run_number", "top_n"}
CANDIDATE_REQUIRED = {"candidate_rank", "combo_id", "event_index", "event_number", "final_fit_score", "final_flavor_score", "final_selection_mode", "final_selection_score", "fit_success", "fitchi2", "flavor_jet_collection_name", "flavor_weight", "jet_collection_name", "mH_prefit", "mW_had_prefit", "mt_had_prefit", "mH_postfit", "mW_had_postfit", "mt_had_postfit", "run_number"}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def assert_new_output_dir(path: Path) -> None:
    if path.exists() or path.is_symlink(): raise RuntimeError(f"refusing to reuse output directory: {path}")

def load_legacy(path: Path, chi2_dir: Path):
    sys.path.insert(0, str(chi2_dir.resolve(strict=True)))
    spec = importlib.util.spec_from_file_location("frozen_physsim10_rerank", path.resolve(strict=True))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def branch_signature(tree) -> tuple:
    out = []
    for b in tree.GetListOfBranches():
        leaf = b.GetLeaf(b.GetName()); out.append((str(b.GetName()), str(b.GetClassName()), str(leaf.GetTypeName()) if leaf else ""))
    return tuple(sorted(out))

def root_and_provenance(run_root: Path, chunk: int) -> tuple[Path, Path, Path]:
    key = f"physsim__tth-sm__eL.pR__I01234_0_{chunk}"; stem = run_root / key / f"kinfit_{key}"
    return Path(f"{stem}.root"), Path(f"{stem}.provenance.json"), Path(f"{stem}.xml")

def validate_provenance(root: Path, provenance: Path, xml: Path, chunk: int, verify_content: bool = True) -> tuple[dict, str, str]:
    p = json.loads(provenance.read_text())
    if p.get("job_key") != f"physsim__tth-sm__eL.pR__I01234_0_{chunk}": raise RuntimeError(f"job_key mismatch chunk {chunk}")
    if p.get("processor_library_sha256") != EXPECTED_LIBRARY_SHA256: raise RuntimeError(f"library mismatch chunk {chunk}")
    recorded = p.get("sha256", {})
    validated = []
    for path in (root, xml):
        expected = recorded.get(path.name) or recorded.get(str(path))
        if not expected: raise RuntimeError(f"content hash absent: {path}")
        if verify_content and sha256(path) != expected: raise RuntimeError(f"content hash mismatch: {path}")
        validated.append(expected)
    return p, validated[0], validated[1]

def validate_mode_fields(row, context: str) -> None:
    if str(row.final_selection_mode) != "logchi2_plus_flavor": raise RuntimeError(f"mode mismatch at {context}")
    if hasattr(row, "top_n") and int(row.top_n) != 10: raise RuntimeError(f"TopN mismatch at {context}")
    if not math.isclose(float(row.flavor_weight), .3, abs_tol=2e-7): raise RuntimeError(f"weight mismatch at {context}")
    if str(row.jet_collection_name) != "OutputErrorFlowJets6" or str(row.flavor_jet_collection_name) != "RefinedJets6": raise RuntimeError(f"collection mismatch at {context}")
    fit_score = math.log1p(max(0., float(row.fitchi2))) if hasattr(row, "fitchi2") else float(row.final_fit_score)
    expected = fit_score + .3 * float(row.final_flavor_score)
    if not math.isclose(float(row.final_selection_score), expected, rel_tol=2e-6, abs_tol=2e-5): raise RuntimeError(f"formula mismatch at {context}")

def candidate_payload(row, legacy, price: dict) -> dict:
    validate_mode_fields(row, f"candidate event={int(row.event_index)} rank={int(row.candidate_rank)}")
    p = {"event_index": int(row.event_index), "run_number": int(row.run_number), "event_number": int(row.event_number), "candidate_rank": int(row.candidate_rank), "combo_id": int(row.combo_id), "fit_success": int(row.fit_success), "fitchi2": float(row.fitchi2), "flavor_score": float(row.final_flavor_score), "final_selection_score": float(row.final_selection_score), "mW_had_prefit": float(row.mW_had_prefit), "mt_had_prefit": float(row.mt_had_prefit), "mH_prefit": float(row.mH_prefit), "mW_had_postfit": float(row.mW_had_postfit), "mt_had_postfit": float(row.mt_had_postfit), "mH_postfit": float(row.mH_postfit)}
    if not all(math.isfinite(x) for x in p.values() if isinstance(x, float)): raise RuntimeError(f"nonfinite candidate event={p['event_index']}")
    mass = legacy.price2014_score(p, price); p["price2014_prefit"] = mass; p[PRICE_MODE] = mass + p["flavor_score"]; p["kinfit_log1pchi2"] = math.log1p(max(0., p["fitchi2"])); return p

def best_payload(row, chunk: int, source_id: str, input_path: str) -> dict:
    validate_mode_fields(row, f"best chunk={chunk} event={int(row.event_index)}")
    return {"chunk": chunk, "source_id": source_id, "input_path": input_path, "run_number": int(row.run_number), "event_number": int(row.event_number), "event_index": int(row.event_index), "combo_id": int(row.best_combo_id), "accepted": int(row.accepted), "fit_success": int(row.fit_success), "final_fit_score": float(row.final_fit_score), "final_flavor_score": float(row.final_flavor_score), "final_selection_score": float(row.final_selection_score), "mW_had_postfit": float(row.mW_had_postfit), "mt_had_postfit": float(row.mt_had_postfit), "mH_postfit": float(row.mH_postfit)}

def source_key(row: dict) -> tuple: return (row["source_id"], int(row["run_number"]), int(row["event_number"]), int(row["event_index"]))

def diagnostic_combo_mismatch(best: dict, diagnostic: dict | None) -> bool:
    if best["fit_success"] != 1: return False
    if diagnostic is None: raise RuntimeError("successful authoritative best has no diagnostic kinfit winner")
    return int(diagnostic["combo_id"]) != int(best["combo_id"])

def diagnostic_mass_row_mismatch(best: dict, diagnostic: dict | None) -> bool:
    if best["fit_success"] != 1: return False
    if diagnostic is None: raise RuntimeError("successful authoritative best has no diagnostic kinfit winner")
    return any(float(diagnostic[k]) != float(best[k]) for k in ("mW_had_postfit", "mt_had_postfit", "mH_postfit"))

def histogram_accounting(values, low, high, bins, denominator):
    counts = [0] * bins; width = (high-low)/bins; under = over = 0
    for value in values:
        if value < low: under += 1
        elif value > high: over += 1
        else: counts[bins-1 if value == high else int((value-low)/width)] += 1
    closure = under + sum(counts) + over
    if closure != len(values) or closure != denominator: raise RuntimeError("histogram closure failed")
    return {"counts": counts, "edges": [low+i*width for i in range(bins+1)], "underflow": under, "in_range": sum(counts), "overflow": over, "closure_count": closure, "closure_fraction": closure/denominator}

def csv_field_union(rows):
    fields=[]; seen=set()
    for row in rows:
        for field in row:
            if field not in seen: seen.add(field); fields.append(field)
    return fields

def write_csv(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_field_union(rows)); w.writeheader(); w.writerows(rows)

def render_plot(png, pdf, indexed, common):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.8))
    for ax, (obj, spec) in zip(axes, OBJECTS.items()):
        for mode in (PRICE_MODE, KINFIT_MODE):
            vals = [float(indexed[mode][k][DISPLAY[mode]["columns"][obj]]) for k in common]
            ax.hist(vals, bins=BINS, range=spec["range"], weights=[1/len(common)]*len(vals), histtype="step", linewidth=2, color=DISPLAY[mode]["color"], label=DISPLAY[mode]["label"])
        ax.axvline(spec["reference"], color="black", linestyle=":", linewidth=1.5, label="constraint reference, not MC truth")
        ax.set(xlabel=f"{obj} mass [GeV]", ylabel="fraction of common events / bin"); ax.grid(alpha=.22); ax.legend(fontsize=8)
    fig.suptitle("Physsim eL.pR chunks 1–10: selected assignment masses\nexisting TopN10, SLD1, SA2.6 ROOT outputs")
    fig.tight_layout(); fig.savefig(png, dpi=180); fig.savefig(pdf); plt.close(fig)

def process(args, chunks, smoke=False):
    legacy = load_legacy(args.legacy, args.chi2_dir); price = legacy.load_price2014(str(args.model_bundle))
    selected = {PRICE_MODE: [], KINFIT_MODE: []}; records=[]; schema_ref=None; failed=set(); cand_total=best_total=success_total=mismatches=mass_mismatches=persisted_combo_mismatches=persisted_mass_mismatches=0
    for chunk in chunks:
        root_path, prov_path, xml_path = root_and_provenance(args.run_root, chunk); prov, root_hash, xml_hash = validate_provenance(root_path, prov_path, xml_path, chunk, verify_content=not smoke)
        source_id, input_path = str(prov["job_key"]), str(prov["input_path"]); rf=legacy.ROOT.TFile.Open(str(root_path))
        if not rf or rf.IsZombie(): raise RuntimeError(f"cannot open {root_path}")
        try:
            top, candidates = rf.Get("TTHSemiLepKinFit"), rf.Get("TTHSemiLepKinFit_candidates")
            if not top or not candidates: raise RuntimeError(f"missing trees chunk {chunk}")
            tn, cn = legacy.branch_names(top), legacy.branch_names(candidates)
            if TOP_REQUIRED-tn or CANDIDATE_REQUIRED-cn: raise RuntimeError(f"schema missing chunk {chunk}: {sorted(TOP_REQUIRED-tn)} {sorted(CANDIDATE_REQUIRED-cn)}")
            sig={"top":branch_signature(top), "candidates":branch_signature(candidates)}
            if schema_ref is None: schema_ref=sig
            elif sig != schema_ref: raise RuntimeError(f"schema signature differs chunk {chunk}")
            best={}; limit=args.smoke_rows if smoke else None
            for i,row in enumerate(top):
                if limit is not None and i>=limit: break
                p=best_payload(row,chunk,source_id,input_path); ei=p["event_index"]
                if ei in best or p["accepted"] != 1: raise RuntimeError(f"invalid best row chunk {chunk} event {ei}")
                best[ei]=p; best_total+=1
                if p["fit_success"]==1: success_total+=1; selected[KINFIT_MODE].append(p)
                else: failed.add((chunk,p["run_number"],p["event_number"],ei))
            current=None; rows=[]; done=0
            def finish():
                nonlocal mismatches,mass_mismatches,persisted_combo_mismatches,persisted_mass_mismatches,done
                if not rows:return
                ei=rows[0]["event_index"]
                if ei not in best:
                    if smoke:return
                    raise RuntimeError(f"candidate event absent from best chunk {chunk}: {ei}")
                win=legacy.select_best_by_mode(rows,[PRICE_MODE],require_converged=False).get(PRICE_MODE)
                if win is None: raise RuntimeError(f"no prefit winner chunk {chunk} event {ei}")
                win.update({"chunk":chunk,"source_id":source_id,"input_path":input_path}); selected[PRICE_MODE].append(win)
                diagnostic=legacy.select_best_by_mode(rows,[KINFIT_MODE],require_converged=False).get(KINFIT_MODE)
                if diagnostic_combo_mismatch(best[ei], diagnostic): mismatches+=1
                if diagnostic_mass_row_mismatch(best[ei], diagnostic): mass_mismatches+=1
                successful=[row for row in rows if row["fit_success"]==1 and math.isfinite(row["final_selection_score"])]
                persisted=min(successful,key=lambda row:row["final_selection_score"]) if successful else None
                if diagnostic_combo_mismatch(best[ei], persisted): persisted_combo_mismatches+=1
                if diagnostic_mass_row_mismatch(best[ei], persisted): persisted_mass_mismatches+=1
                done+=1
            for row in candidates:
                ei=int(row.event_index)
                if smoke and ei not in best:
                    if best and ei > max(best):
                        finish(); rows=[]; break
                    continue
                if current is None: current=ei
                if ei != current:
                    finish()
                    if smoke and done>=args.smoke_rows: rows=[]; break
                    if ei<current: raise RuntimeError(f"unordered candidates chunk {chunk}")
                    current=ei; rows=[]
                p=candidate_payload(row,legacy,price); rows.append(p); cand_total+=1
            else: finish()
            records.append({"chunk":chunk,"source_id":source_id,"input_path":input_path,"root_path":str(root_path),"provenance_path":str(prov_path),"xml_path":str(xml_path),"root_sha256":root_hash,"provenance_sha256":sha256(prov_path),"xml_sha256":xml_hash,"best_rows":len(best),"best_success_rows":sum(x["fit_success"]==1 for x in best.values()),"processor_library":prov["processor_library"],"processor_library_sha256":prov["processor_library_sha256"]})
        finally: rf.Close()
    indexed={}
    for mode, values in selected.items():
        mapping={}
        for row in values:
            key=source_key(row)
            if key in mapping: raise RuntimeError(f"duplicate source key {mode}: {key}")
            mapping[key]=row
        indexed[mode]=mapping
    common=sorted(set(indexed[PRICE_MODE])&set(indexed[KINFIT_MODE]))
    counts={"best_rows":best_total,"best_success_rows":success_total,"candidate_rows":cand_total,"common_rows":len(common),"exact_double_candidate_argmin_combo_mismatches":mismatches,"exact_double_candidate_argmin_mass_row_mismatches":mass_mismatches,"persisted_float_stable_argmin_combo_mismatches":persisted_combo_mismatches,"persisted_float_stable_argmin_mass_row_mismatches":persisted_mass_mismatches}
    if not smoke:
        if {k:counts[k] for k in EXPECTED} != EXPECTED: raise RuntimeError(f"count mismatch {counts}")
        if failed != EXPECTED_FAILED_BEST: raise RuntimeError(f"failed-best mismatch {failed}")
        if any(indexed[KINFIT_MODE][k]["fit_success"]!=1 for k in common): raise RuntimeError("failed fit in postfit denominator")
    return {"indexed":indexed,"common":common,"chunk_records":records,"counts":counts,"failed_best":sorted(failed),"schema_signature":schema_ref}

def run(args):
    assert_new_output_dir(args.output_dir); r=process(args,CHUNKS); indexed,common=r["indexed"],r["common"]; hist={}; summary=[]; joined=[]; selected=[]
    for key in common:
        p,k=indexed[PRICE_MODE][key],indexed[KINFIT_MODE][key]
        joined.append({"source_id":key[0],"run_number":key[1],"event_number":key[2],"event_index":key[3],"chunk":p["chunk"],"mass_constraint_combo_id":p["combo_id"],"kinfit_combo_id":k["combo_id"],"mass_constraint_fit_success":p["fit_success"],"kinfit_fit_success":k["fit_success"],"mW_had_prefit":p["mW_had_prefit"],"mt_had_prefit":p["mt_had_prefit"],"mH_prefit":p["mH_prefit"],"mW_had_postfit":k["mW_had_postfit"],"mt_had_postfit":k["mt_had_postfit"],"mH_postfit":k["mH_postfit"]})
        selected += [{"mode_internal":PRICE_MODE,"mode_display":DISPLAY[PRICE_MODE]["label"],**p},{"mode_internal":KINFIT_MODE,"mode_display":DISPLAY[KINFIT_MODE]["label"],**k}]
    for mode in (PRICE_MODE,KINFIT_MODE):
        for obj,spec in OBJECTS.items():
            vals=[float(indexed[mode][k][DISPLAY[mode]["columns"][obj]]) for k in common]; a=histogram_accounting(vals,*spec["range"],BINS,len(common)); hist[f"{mode}:{obj}"]=a
            summary.append({"mode_internal":mode,"mode_display":DISPLAY[mode]["label"],"object":obj,"stage":"prefit" if mode==PRICE_MODE else "postfit","denominator":len(common),"underflow":a["underflow"],"in_range":a["in_range"],"overflow":a["overflow"],"mean_GeV":sum(vals)/len(vals),"constraint_reference_GeV":spec["reference"]})
    args.output_dir.mkdir(parents=True); png=args.output_dir/"physsim_chunks1_10_mass_constraint_prefit_vs_kinfit_postfit.png"; pdf=args.output_dir/"physsim_chunks1_10_mass_constraint_prefit_vs_kinfit_postfit.pdf"
    joined_path=args.output_dir/"joined_common_events.csv"; selected_path=args.output_dir/"selected_rows.csv"; summary_path=args.output_dir/"summary.csv"
    render_plot(png,pdf,indexed,common); write_csv(joined_path,joined); write_csv(selected_path,selected); write_csv(summary_path,summary)
    command=" ".join([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:]])
    manifest={"status":"NAF diagnostic; deterministic aggregation of existing formal workflow ROOT outputs","truth_evaluated":False,"assignment_accuracy_claim":False,"denominator":{"definition":"source-aware intersection of offline prefit and accepted fit-success authoritative postfit selections","events":len(common)},"source_key":["provenance.job_key","run_number","event_number","event_index"],"modes":{PRICE_MODE:{"display":DISPLAY[PRICE_MODE]["label"],"stage":"prefit","candidate_pool":"persisted TopN10/SLD1 candidate tree; no fit_success cut","formula":"sum_obj((m_obj_prefit-M_obj)/sigma_obj)^2 + final_flavor_score","tie_break":"(score, 0, candidate_rank, combo_id)","implementation":"legacy price2014_score + select_best_by_mode"},KINFIT_MODE:{"display":DISPLAY[KINFIT_MODE]["label"],"stage":"postfit","source":"authoritative TTHSemiLepKinFit; accepted=1, fit_success=1","formula_validation":"final_selection_score == log1p(max(0,fitchi2)) + 0.3*final_flavor_score","warning":"not reconstructed by candidate argmin"}},"objects":OBJECTS,"bins":BINS,"normalization":"each common event has weight 1/N_common","constraint_reference_note":"constraint references, not MC truth","model_bundle":str(args.model_bundle),"model_bundle_sha256":sha256(args.model_bundle),"legacy_script":str(args.legacy),"legacy_script_sha256":sha256(args.legacy),"script":str(Path(__file__).resolve()),"script_sha256":sha256(Path(__file__).resolve()),"command":command,"counts":r["counts"],"failed_authoritative_best_rows":r["failed_best"],"chunk_inputs":r["chunk_records"],"schema_signature":r["schema_signature"],"histograms":hist}
    mp=args.output_dir/"manifest.json"; mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    outputs={p.name:sha256(p) for p in (png,pdf,joined_path,selected_path,summary_path,mp)}; log=args.output_dir/"run.log"; log.write_text(json.dumps({"command":command,"counts":r["counts"],"output_sha256":outputs},indent=2,sort_keys=True)+"\n")
    return {"counts":r["counts"],"outputs":outputs|{log.name:sha256(log)}}

def parse_args():
    p=argparse.ArgumentParser(); p.add_argument("--run-root",type=Path,required=True); p.add_argument("--legacy",type=Path,required=True); p.add_argument("--chi2-dir",type=Path,required=True); p.add_argument("--model-bundle",type=Path,required=True); p.add_argument("--output-dir",type=Path); p.add_argument("--smoke",action="store_true"); p.add_argument("--smoke-rows",type=int,default=10); a=p.parse_args()
    if not a.smoke and a.output_dir is None:p.error("--output-dir required unless --smoke")
    return a

def main():
    a=parse_args()
    if a.smoke:
        r=process(a,(1,2),smoke=True); print(json.dumps({"smoke":True,"chunks":[1,2],"counts":r["counts"]},sort_keys=True))
    else: print(json.dumps(run(a),indent=2,sort_keys=True))

if __name__ == "__main__": main()

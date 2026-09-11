#!/usr/bin/env python3
"""Compare canonical Physsim STDHEP and Whizard LCIO m_ttbar spectra."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from ilc_tth_cpv.reco_performance import find_hard_particle, invariant_mass


def collection_items(collection):
    return [collection.getElementAt(index) for index in range(collection.getNumberOfElements())]


def particle_four_vector(particle):
    momentum = particle.getMomentum()
    return float(momentum[0]), float(momentum[1]), float(momentum[2]), float(particle.getEnergy())


def event_mtt(particles):
    _, top = find_hard_particle(particles, 6)
    _, antitop = find_hard_particle(particles, -6)
    if top is None or antitop is None:
        return None
    return invariant_mass(particle_four_vector(top), particle_four_vector(antitop))


def fill_stdhep(paths, histogram, max_events_per_file):
    from pyLCIO import UTIL

    records = []
    for path in paths:
        reader = UTIL.LCStdHepRdr(path)
        processed = selected = 0
        while max_events_per_file < 0 or processed < max_events_per_file:
            collection = reader.readEvent()
            if collection is None:
                break
            processed += 1
            mass = event_mtt(collection_items(collection))
            if mass is not None:
                histogram.Fill(mass)
                selected += 1
        records.append({"path": path, "events_processed": processed, "events_with_mtt": selected})
    return records


def fill_whizard(paths, histogram, max_events_per_file):
    from pyLCIO import IOIMPL

    records = []
    for path in paths:
        reader = IOIMPL.LCFactory.getInstance().createLCReader()
        reader.open(path)
        processed = selected = 0
        try:
            while max_events_per_file < 0 or processed < max_events_per_file:
                event = reader.readNextEvent()
                if event is None:
                    break
                processed += 1
                # Deliberately no fallback: the contract fixes Whizard to MCParticle.
                collection = event.getCollection("MCParticle")
                mass = event_mtt(collection_items(collection))
                if mass is not None:
                    histogram.Fill(mass)
                    selected += 1
        finally:
            reader.close()
        records.append({"path": path, "events_processed": processed, "events_with_mtt": selected})
    return records


def scale_once(raw_histogram, name, cross_section_fb):
    normalized = raw_histogram.Clone(name)
    normalized.SetDirectory(0)
    integral = normalized.Integral()
    if integral <= 0.0:
        raise RuntimeError(f"cannot normalize empty histogram: {raw_histogram.GetName()}")
    normalized.Scale(float(cross_section_fb) / integral, "width")
    return normalized


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-events-per-file", type=int, default=-1)
    args = parser.parse_args()

    import ROOT

    ROOT.gROOT.SetBatch(True)
    ROOT.TH1.AddDirectory(False)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    contract = manifest["generator_mtt"]
    binning = contract["binning"]
    phy = contract["physsim"]
    whi = contract["whizard"]
    phy_paths = [phy["path_template"].format(chunk=chunk) for chunk in phy["chunks"]]
    whi_paths = list(whi["files"])
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    h_phy_raw = ROOT.TH1D("h_mtt_physsim_raw", "", binning["bins"], binning["minimum_gev"], binning["maximum_gev"])
    h_whi_raw = ROOT.TH1D("h_mtt_whizard_raw", "", binning["bins"], binning["minimum_gev"], binning["maximum_gev"])
    phy_records = fill_stdhep(phy_paths, h_phy_raw, args.max_events_per_file)
    whi_records = fill_whizard(whi_paths, h_whi_raw, args.max_events_per_file)
    h_phy = scale_once(h_phy_raw, "h_mtt_physsim_dsigma_dm", phy["cross_section_fb"])
    h_whi = scale_once(h_whi_raw, "h_mtt_whizard_dsigma_dm", whi["cross_section_fb"])

    raw_fields = ["bin_low_gev", "bin_high_gev", "physsim_raw", "whizard_raw"]
    normalized_fields = [
        "bin_low_gev",
        "bin_high_gev",
        "physsim_dsigma_dm_fb_per_gev",
        "whizard_dsigma_dm_fb_per_gev",
    ]
    with (output / "mtt_raw_counts.csv").open("w", newline="", encoding="utf-8") as raw_stream, (
        output / "mtt_normalized.csv"
    ).open("w", newline="", encoding="utf-8") as normalized_stream:
        raw_writer = csv.DictWriter(raw_stream, fieldnames=raw_fields)
        normalized_writer = csv.DictWriter(normalized_stream, fieldnames=normalized_fields)
        raw_writer.writeheader()
        normalized_writer.writeheader()
        for index in range(1, h_phy.GetNbinsX() + 1):
            edges = {
                "bin_low_gev": h_phy.GetXaxis().GetBinLowEdge(index),
                "bin_high_gev": h_phy.GetXaxis().GetBinUpEdge(index),
            }
            raw_writer.writerow(
                {
                    **edges,
                    "physsim_raw": int(h_phy_raw.GetBinContent(index)),
                    "whizard_raw": int(h_whi_raw.GetBinContent(index)),
                }
            )
            normalized_writer.writerow(
                {
                    **edges,
                    "physsim_dsigma_dm_fb_per_gev": h_phy.GetBinContent(index),
                    "whizard_dsigma_dm_fb_per_gev": h_whi.GetBinContent(index),
                }
            )

    root_file = ROOT.TFile(str(output / "mtt_comparison.root"), "RECREATE")
    h_phy_raw.Write()
    h_whi_raw.Write()
    h_phy.Write()
    h_whi.Write()
    root_file.Close()

    h_phy.SetLineColor(ROOT.kBlue + 1)
    h_whi.SetLineColor(ROOT.kRed + 1)
    for histogram in (h_phy, h_whi):
        histogram.SetLineWidth(2)
        histogram.SetStats(0)
    h_phy.SetTitle("Generator-level m_{t#bar{t}} comparison;m_{t#bar{t}} [GeV];d#sigma/dm [fb/GeV]")
    canvas = ROOT.TCanvas("c_mtt", "c_mtt", 1000, 760)
    maximum = max(h_phy.GetMaximum(), h_whi.GetMaximum())
    h_phy.SetMaximum(1.25 * maximum)
    h_phy.Draw("HIST")
    h_whi.Draw("HIST SAME")
    legend = ROOT.TLegend(0.56, 0.72, 0.88, 0.87)
    legend.AddEntry(h_phy, f"Physsim ({phy['cross_section_fb']:.6f} fb)", "l")
    legend.AddEntry(h_whi, f"Whizard ({whi['cross_section_fb']:.6f} fb)", "l")
    legend.Draw()
    canvas.SaveAs(str(output / "mtt_comparison.png"))
    canvas.SaveAs(str(output / "mtt_comparison.pdf"))

    counters = {
        "manifest": str(args.manifest.resolve()),
        "max_events_per_file": args.max_events_per_file,
        "normalization": "one scaling per physical sample after accumulating all listed files",
        "physsim": {"cross_section_fb": phy["cross_section_fb"], "files": phy_records, "raw_histogram_integral": h_phy_raw.Integral()},
        "whizard": {"cross_section_fb": whi["cross_section_fb"], "files": whi_records, "raw_histogram_integral": h_whi_raw.Integral()},
    }
    (output / "mtt_counters.json").write_text(json.dumps(counters, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

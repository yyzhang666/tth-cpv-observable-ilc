#!/usr/bin/env python3
"""Build the study-owned Finder XML from frozen current/legacy snapshots."""

from __future__ import annotations

import argparse
import copy
import xml.etree.ElementTree as ET
from pathlib import Path


PREFIX_PROCESSORS = (
    "MyAIDAProcessor",
    "InitDD4hep",
    "MyStatusmonitor",
    "MyAddNeutralPFOCovMatLite",
    "MyChargedPFOCorrection",
    "MySwitchCovMat",
    "MyPatchCollections",
    "MyCheatedMCOverlayRemoval",
    "MyTrueJet",
)


def processor(root, name):
    matches = root.findall(f"./processor[@name='{name}']")
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one processor {name}, found {len(matches)}")
    return matches[0]


def build(current_path: Path, legacy_path: Path) -> ET.Element:
    current = ET.parse(current_path).getroot()
    legacy = ET.parse(legacy_path).getroot()
    root = ET.Element("marlin", current.attrib)
    for library in current.findall("./library"):
        root.append(copy.deepcopy(library))
    root.append(copy.deepcopy(current.find("./constants")))

    execute = ET.SubElement(root, "execute")
    for name in PREFIX_PROCESSORS:
        if name in ("MySwitchCovMat", "MyPatchCollections"):
            continue
        ET.SubElement(execute, "processor", {"name": name})
        if name == "MyChargedPFOCorrection":
            conditional = ET.SubElement(execute, "if", {"condition": "${IsFastSim}"})
            ET.SubElement(conditional, "processor", {"name": "MySwitchCovMat"})
            ET.SubElement(conditional, "processor", {"name": "MyPatchCollections"})
    ET.SubElement(execute, "processor", {"name": "MyFastJetProcessor"})
    ET.SubElement(execute, "processor", {"name": "MyIsolatedLeptonFinderProcessor"})
    ET.SubElement(execute, "processor", {"name": "LCIOOutput"})

    global_element = copy.deepcopy(current.find("./global"))
    for parameter in global_element.findall("./parameter"):
        if parameter.get("name") == "LCIOInputFiles":
            parameter.clear()
            parameter.set("name", "LCIOInputFiles")
            parameter.text = "__INPUT_FILE__"
        elif parameter.get("name") == "MaxRecordNumber":
            parameter.set("value", "__MAX_RECORDS__")
        elif parameter.get("name") == "SkipNEvents":
            parameter.set("value", "__SKIP_EVENTS__")
    root.append(global_element)

    for name in PREFIX_PROCESSORS:
        root.append(copy.deepcopy(processor(current, name)))
    root.append(copy.deepcopy(processor(legacy, "MyFastJetProcessor")))
    finder = copy.deepcopy(processor(legacy, "MyIsolatedLeptonFinderProcessor"))
    if finder.find("./parameter[@name='JetCollection']") is not None:
        raise RuntimeError("legacy Finder unexpectedly already defines JetCollection")
    ET.SubElement(
        finder,
        "parameter",
        {"name": "JetCollection", "type": "string", "lcioInType": "ReconstructedParticle"},
    ).text = "JetsForIsolep"
    root.append(finder)
    output = copy.deepcopy(processor(current, "LCIOOutput"))
    output_file = output.find("./parameter[@name='LCIOOutputFile']")
    write_mode = output.find("./parameter[@name='LCIOWriteMode']")
    if output_file is None or write_mode is None:
        raise RuntimeError("current LCIOOutput lacks LCIOOutputFile/LCIOWriteMode")
    output_file.text = "__OUTPUT_FILE__"
    write_mode.text = "WRITE_NEW"
    root.append(output)
    ET.indent(root, space="  ")
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise RuntimeError(f"refusing to overwrite steering: {args.output}")
    root = build(args.current, args.legacy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(args.output, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()

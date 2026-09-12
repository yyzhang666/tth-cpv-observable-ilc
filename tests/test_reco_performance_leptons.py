"""Static and parser tests for the frozen lepton study workflow."""

import hashlib
import importlib.util
import json
import copy
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load("finder_builder", ROOT / "scripts/reco_performance/build_finder_steering.py")
analysis = load("lepton_analysis", ROOT / "scripts/reco_performance/analyze_leptons.py")
validator = load("lepton_validator", ROOT / "scripts/reco_performance/validate_lepton_branch.py")
runner = load("finder_runner", ROOT / "scripts/reco_performance/run_finder_branch.py")


def canonical(element):
    element = copy.deepcopy(element)
    for node in element.iter():
        node.tail = None
        if node.text is not None and not node.text.strip():
            node.text = None
    return ET.tostring(element)


def test_frozen_snapshots_match_recorded_naf_hashes():
    manifest = json.loads((ROOT / "reco_performance_study/snapshot_manifest.json").read_text())
    for relative, record in manifest.items():
        assert hashlib.sha256((ROOT / "reco_performance_study" / relative).read_bytes()).hexdigest() == record["sha256"]


def test_generated_finder_xml_matches_builder_and_frozen_processor_definitions():
    current_path = ROOT / "reco_performance_study/steering/reference/complete_reco_kinfit_ready.xml"
    legacy_path = ROOT / "reco_performance_study/steering/reference/lepton_reco.xml"
    generated_path = ROOT / "reco_performance_study/steering/physsim_finder_branch.xml"
    expected = builder.build(current_path, legacy_path)
    generated = ET.parse(generated_path).getroot()
    assert ET.tostring(generated) == ET.tostring(expected)

    current = ET.parse(current_path).getroot()
    legacy = ET.parse(legacy_path).getroot()
    for name in builder.PREFIX_PROCESSORS:
        assert canonical(builder.processor(generated, name)) == canonical(builder.processor(current, name))
    assert canonical(builder.processor(generated, "MyFastJetProcessor")) == canonical(builder.processor(legacy, "MyFastJetProcessor"))


def test_finder_xml_execution_and_output_contract():
    root = ET.parse(ROOT / "reco_performance_study/steering/physsim_finder_branch.xml").getroot()
    execute = root.find("./execute")
    flat = []
    for child in execute:
        if child.tag == "processor":
            flat.append(child.get("name"))
        elif child.tag == "if":
            flat.extend(processor.get("name") for processor in child.findall("./processor"))
    assert flat == [
        "MyAIDAProcessor", "InitDD4hep", "MyStatusmonitor", "MyAddNeutralPFOCovMatLite",
        "MyChargedPFOCorrection", "MySwitchCovMat", "MyPatchCollections",
        "MyCheatedMCOverlayRemoval", "MyTrueJet", "MyFastJetProcessor",
        "MyIsolatedLeptonFinderProcessor", "LCIOOutput",
    ]
    finder = builder.processor(root, "MyIsolatedLeptonFinderProcessor")
    values = {parameter.get("name"): (parameter.text or "").strip() for parameter in finder.findall("./parameter")}
    assert values["InputCollection"] == "${PFOsWithoutOverlayCollection}"
    assert values["OutputCollectionIsolatedLeptons"] == "Isolep"
    assert values["OutputCollectionWithoutIsolatedLepton"] == "PFOsAfterIso"
    assert values["IsolationPolynomialCutA"] == "0"
    assert values["IsolationPolynomialCutB"] == "6"
    assert values["IsolationPolynomialCutC"] == "-90"
    assert values["IsolationMinimumTrackEnergy"] == "15"
    assert values["UseJetIsolation"] == "true"
    assert values["UsePID"] == "false"
    assert values["UseImpactParameter"] == "true"
    assert values["ImpactParameterMaxD0"] == values["ImpactParameterMaxZ0"] == values["ImpactParameterMax3D"] == "0.05"
    fastjet = builder.processor(root, "MyFastJetProcessor")
    jet_output = fastjet.find("./parameter[@name='jetOut']").text.strip()
    assert jet_output == values["JetCollection"] == "JetsForIsolep"
    output = builder.processor(root, "LCIOOutput")
    assert output.find("./parameter[@name='LCIOOutputFile']").text == "__OUTPUT_FILE__"
    assert output.find("./parameter[@name='LCIOWriteMode']").text == "WRITE_NEW"


def test_origin_parsers_keep_integer_counts_before_division():
    tagger_text = """
[HBB|SEMI] EL  total=10
  tag_correct: 9  frac=0.9
    origin_from_topW   : 7 frac=0.7
    origin_from_tau    : 1 frac=0.1
    origin_from_hadron : 1 frac=0.1
  tag_wrong: 1 frac=0.1
"""
    finder_text = """
==================== HBB | SEMI ====================
-- PID = e_like     entries=10 frac_in_block=1
   from_topW   : 7 frac_in_pid=.7
   from_tau    : 2 frac_in_pid=.2
   from_hadron : 1 frac_in_pid=.1
"""
    tagger = analysis.parse_tagger_origins(tagger_text)
    finder = analysis.parse_finder_origins(finder_text)
    assert tagger[("SEMI", "EL")]["origins"] == {"from_topW": 7, "from_tau": 1, "from_hadron": 1}
    assert finder[("SEMI", "EL")]["origins"] == {"from_topW": 7, "from_tau": 2, "from_hadron": 1}


def test_finder_runner_persists_combined_marlin_log():
    source = (ROOT / "scripts/reco_performance/run_finder_branch.py").read_text()
    assert 'run_dir / "marlin.log"' in source
    assert "stderr=subprocess.STDOUT" in source
    assert '.open("xb")' in source


def test_finder_condor_submit_freezes_canonical_chunk_boundaries():
    submit = (
        ROOT / "condor/reco_performance/physsim_finder_branch.sub"
    ).read_text(encoding="utf-8")
    arguments = next(line for line in submit.splitlines() if line.startswith("arguments = "))
    assert "$(REPO_ROOT)/scripts/reco_performance/run_finder_branch.py" in arguments
    assert "$(REPO_ROOT)/reco_performance_study/steering/physsim_finder_branch.xml" in arguments
    assert "--input /data/dust/user/zhangyuy/analysis/tth/events_physsim/production/sm_tth/eL.pR/I01234_0/sgv/E550-Test.Ptth.Gphyssim.eL.pR.I01234_0.$(chunk)_sgv.slcio" in arguments
    assert "--output $(RUN_ROOT)/finder_chunk_$(chunk).slcio" in arguments
    assert "--run-dir $(RUN_ROOT)/finder_chunk_$(chunk)_run" in arguments
    assert "--max-records $(max_records) --expected-output-events $(expected)" in arguments
    assert "--skip-events 0 --allow-long-run --accept-validated-exit-134" in arguments
    assert "should_transfer_files = NO" in submit
    assert "on_exit_remove = true" in submit
    for stream in ("out", "err", "log"):
        assert f"$(RUN_ROOT)/condor/chunk_$(chunk).{stream}" in submit
    queue = submit.split("queue chunk,max_records,expected from (\n", 1)[1].split("\n)", 1)[0]
    assert [tuple(map(int, row.split(","))) for row in queue.splitlines()] == [
        (1, 12499, 12498),
        (2, 12500, 12499),
        (3, 12499, 12498),
        (4, 12500, 12499),
        (5, 12499, 12498),
        (6, 12499, 12498),
        (7, 12500, 12499),
        (8, 12500, 12499),
        (9, 12500, 12499),
        (10, 12496, 12495),
    ]


class PointerLike:
    def __init__(self, values, expose_size):
        self.values = values
        self.expose_size = expose_size

    def __getitem__(self, index):
        return self.values[index]

    def __iter__(self):
        raise AssertionError("generic iteration must never be attempted")

    def size(self):
        if not self.expose_size:
            raise AttributeError("no size")
        return len(self.values)


def test_validator_reads_fixed_momentum_indices_without_iteration():
    assert validator.fixed_vector3(PointerLike([1, 2, 3], False), "momentum") == [1.0, 2.0, 3.0]


def test_validator_requires_size_for_variable_payloads():
    assert validator.sized_vector(PointerLike([1, 2], True), "cov") == [1.0, 2.0]
    with pytest.raises(RuntimeError, match="no valid size"):
        validator.sized_vector(PointerLike([1, 2], False), "cov")


class Event:
    def __init__(self, collections):
        self.collections = collections

    def getCollectionNames(self):
        return list(self.collections)


class Reader:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = False

    def open(self, _path):
        return None

    def readNextEvent(self):
        return next(self.events, None)

    def close(self):
        self.closed = True


def test_joined_multiplicity_handles_false_eof_and_rejects_one_sided_end(monkeypatch):
    class FalseNullProxy:
        def __bool__(self):
            return False

        def getRunNumber(self):
            raise AssertionError("EOF proxy must not be dereferenced")

    legacy = type("Legacy", (), {"init_stat": staticmethod(dict)})
    monkeypatch.setattr(analysis, "load_module", lambda name, path: legacy)

    synchronized = [Reader([FalseNullProxy()]), Reader([FalseNullProxy()])]
    synchronized_readers = iter(synchronized)
    monkeypatch.setattr(analysis, "open_reader", lambda path: next(synchronized_readers))
    result = analysis.joined_multiplicity(
        ["complete.slcio"], ["finder.slcio"], ["chunk1"], Path("legacy"), -1
    )
    assert result["events_processed"] == 0
    assert all(reader.closed for reader in synchronized)

    mismatched = [Reader([FalseNullProxy()]), Reader([object()])]
    mismatched_readers = iter(mismatched)
    monkeypatch.setattr(analysis, "open_reader", lambda path: next(mismatched_readers))
    with pytest.raises(RuntimeError, match="branch length mismatch for chunk1"):
        analysis.joined_multiplicity(
            ["complete.slcio"], ["finder.slcio"], ["chunk1"], Path("legacy"), -1
        )
    assert all(reader.closed for reader in mismatched)


def test_finder_output_validation_requires_exact_count_and_collections(tmp_path):
    required = {"MCParticlesSkimmed", "PFOsWithoutOverlayCheated", "Isolep", "PFOsAfterIso"}
    report = runner.validate_finder_output(tmp_path / "out.slcio", 2, lambda: Reader([Event(required), Event(required)]))
    assert report["events"] == 2
    with pytest.raises(RuntimeError, match="event count"):
        runner.validate_finder_output(tmp_path / "out.slcio", 2, lambda: Reader([Event(required)]))
    with pytest.raises(RuntimeError, match="missing collections"):
        runner.validate_finder_output(tmp_path / "out.slcio", 1, lambda: Reader([Event(required - {"Isolep"})]))


def test_finder_runner_freezes_observed_marlin_boundary_contract(tmp_path, monkeypatch):
    input_path = tmp_path / "input.slcio"
    input_path.write_bytes(b"input")
    template = ROOT / "reco_performance_study/steering/physsim_finder_branch.xml"
    monkeypatch.setattr(
        __import__("sys"),
        "argv",
        [
            "run_finder_branch.py", "--template", str(template), "--input", str(input_path),
            "--output", str(tmp_path / "output.slcio"), "--run-dir", str(tmp_path / "run"),
            "--max-records", "10", "--expected-output-events", "10", "--skip-events", "0", "--prepare-only",
        ],
    )
    with pytest.raises(ValueError, match=r"max-records = expected-output-events \+ 1"):
        runner.main()


def test_exit_134_requires_explicit_validation_path():
    assert not runner.accepted_exit_134(134, False)
    assert not runner.accepted_exit_134(-6, False)
    assert runner.accepted_exit_134(134, True)
    assert runner.accepted_exit_134(-6, True)
    assert not runner.accepted_exit_134(1, True)

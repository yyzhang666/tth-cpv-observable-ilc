"""Static contracts for guarded Whizard SGV/reco/kinfit replay."""

import copy
import importlib.util
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sgv = load("whizard_sgv", ROOT / "scripts/reco_performance/run_whizard_sgv.py")
marlin = load("whizard_marlin", ROOT / "scripts/reco_performance/run_whizard_marlin.py")
generator_mtt = load("generator_mtt", ROOT / "scripts/reco_performance/compare_generator_mtt.py")


def canonical(element):
    element = copy.deepcopy(element)
    for node in element.iter():
        node.tail = None
        if node.text is not None and not node.text.strip():
            node.text = None
    return ET.tostring(element)


def test_stdhep_false_null_proxy_terminates_before_dereference(monkeypatch):
    class FalseNullProxy:
        def __bool__(self):
            return False

        def getNumberOfElements(self):
            raise AssertionError("EOF proxy must not be dereferenced")

    events = iter((types.SimpleNamespace(getNumberOfElements=lambda: 0), FalseNullProxy()))
    reader = types.SimpleNamespace(readEvent=lambda: next(events))
    fills = []
    histogram = types.SimpleNamespace(Fill=fills.append)
    monkeypatch.setitem(
        sys.modules,
        "pyLCIO",
        types.SimpleNamespace(UTIL=types.SimpleNamespace(LCStdHepRdr=lambda path: reader)),
    )
    monkeypatch.setattr(generator_mtt, "event_mtt", lambda particles: 350.0)

    records = generator_mtt.fill_stdhep(["input.stdhep"], histogram, -1)

    assert records == [{"path": "input.stdhep", "events_processed": 1, "events_with_mtt": 1}]
    assert fills == [350.0]


def test_stdhep_read_event_exception_propagates(monkeypatch):
    class ReadError(RuntimeError):
        pass

    def fail_read():
        raise ReadError("read failed")

    monkeypatch.setitem(
        sys.modules,
        "pyLCIO",
        types.SimpleNamespace(
            UTIL=types.SimpleNamespace(
                LCStdHepRdr=lambda path: types.SimpleNamespace(readEvent=fail_read)
            )
        ),
    )

    with pytest.raises(ReadError, match="read failed"):
        generator_mtt.fill_stdhep(["input.stdhep"], object(), -1)


def test_sgv_accepts_only_four_whole_physical_files_and_labels_variant():
    for index in range(4):
        path = f"E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_{index}.0.slcio"
        assert sgv.sample_index(path) == index
    with pytest.raises(ValueError):
        sgv.sample_index("E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_4.0.slcio")
    assert sgv.VARIANT_LABEL == "current-SGV controlled variant"
    source = (ROOT / "scripts/reco_performance/run_whizard_sgv.py").read_text()
    assert '"0", str(args.event_count), "LCIO"' in source
    assert '(run_dir / "fort.17").symlink_to("sgv.steer")' in source
    assert "shutil.copy2(SGV_HOME / \"sgv.steer\", local_steer)" in source
    assert "fcntl.LOCK_EX" in source
    assert "refusing to reuse SGV run directory" in source
    assert "DSEED" not in source and "GSEED" not in source


def test_reco_shards_are_6000_plus_actual_remainder():
    assert marlin.shard_bounds(12500, 0) == (0, 6000)
    assert marlin.shard_bounds(12500, 1) == (6000, 6500)
    assert marlin.shard_bounds(12001, 1) == (6000, 6001)
    with pytest.raises(ValueError):
        marlin.shard_bounds(5000, 1)


def test_reco_render_changes_only_input_output_and_range(tmp_path):
    authority = ROOT / "reco_performance_study/steering/reference/whizard_complete_reco_20260616.xml"
    original = ET.parse(authority).getroot()
    rendered, skip, maximum = marlin.render_reco(authority, Path("/input.slcio"), tmp_path / "out.slcio", 12500, 1)
    assert (skip, maximum) == (6000, 6500)
    for xpath in (
        "./global/parameter[@name='LCIOInputFiles']",
        "./global/parameter[@name='MaxRecordNumber']",
        "./global/parameter[@name='SkipNEvents']",
        "./constants/constant[@name='OutputDirectory']",
        "./constants/constant[@name='OutputBaseName']",
    ):
        rendered_node = marlin.one(rendered, xpath)
        original_node = marlin.one(original, xpath)
        rendered_node.attrib.clear()
        rendered_node.attrib.update(original_node.attrib)
        rendered_node.text = original_node.text
    assert canonical(rendered) == canonical(original)


def test_kinfit_render_changes_only_input_output_and_range(tmp_path):
    authority = ROOT / "reco_performance_study/steering/reference/whizard_kinfit_20260618.xml"
    original = ET.parse(authority).getroot()
    rendered, skip, maximum = marlin.render_kinfit(authority, Path("/reco.slcio"), tmp_path / "fit.root", 6500)
    assert (skip, maximum) == (0, 6500)
    for xpath in (
        "./global/parameter[@name='LCIOInputFiles']",
        "./global/parameter[@name='MaxRecordNumber']",
        "./global/parameter[@name='SkipNEvents']",
        "./processor[@name='MyTTHSemiLepKinFit']/parameter[@name='outputFilename']",
    ):
        rendered_node = marlin.one(rendered, xpath)
        original_node = marlin.one(original, xpath)
        rendered_node.attrib.clear()
        rendered_node.attrib.update(original_node.attrib)
        rendered_node.text = original_node.text
    assert canonical(rendered) == canonical(original)


def test_kinfit_authority_keeps_frozen_physics_settings():
    root = ET.parse(ROOT / "reco_performance_study/steering/reference/whizard_kinfit_20260618.xml").getroot()
    processor = marlin.one(root, "./processor[@name='MyTTHSemiLepKinFit']")
    values = {item.get("name"): (item.text or "").strip() for item in processor.findall("./parameter")}
    assert values["JetCollectionName"] == "OutputErrorFlowJets6"
    assert values["ElectronCollectionName"] == "ISOElectrons"
    assert values["MuonCollectionName"] == "ISOMuons"
    assert values["JetSLDLinkCollectionName"] == "JetSLDLink6"
    assert values["SLDNuLinkCollectionName"] == "SLDNuLink6"
    assert values["TopN"] == "180"
    assert values["ConstraintMode"] == "fullMass4C"
    assert values["includeISR"] == "true" and values["ISRPzMax"] == "125.6"
    assert values["EnableSLDNeutrinoEnumeration"] == "true"
    assert values["UseSoftMassConstraints"] == "true"
    assert values["UseJetCovarianceOffDiagonal"] == "false"
    assert (values["SigmaEnergyScaleFactor"], values["SigmaAnglesScaleFactor"], values["SigmaInvPtScaleFactor"]) == ("1.6", "3.6", "1.1")


def test_wrappers_refuse_existing_output_before_runtime(tmp_path, monkeypatch):
    input_path = tmp_path / "E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_0.0.slcio"
    input_path.write_bytes(b"input")
    output = tmp_path / "exists.slcio"
    output.write_bytes(b"existing")
    monkeypatch.setattr(sys, "argv", ["run_whizard_sgv.py", "--input", str(input_path), "--output", str(output), "--run-dir", str(tmp_path / "run"), "--lock-file", str(tmp_path / "lock"), "--event-count", "20", "--prepare-only"])
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        sgv.main()
    authority = ROOT / "reco_performance_study/steering/reference/whizard_complete_reco_20260616.xml"
    monkeypatch.setattr(sys, "argv", ["run_whizard_marlin.py", "reco", "--authority", str(authority), "--input", str(input_path), "--output", str(output), "--run-dir", str(tmp_path / "reco_run"), "--event-count", "20", "--shard-index", "0", "--prepare-only"])
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        marlin.main()

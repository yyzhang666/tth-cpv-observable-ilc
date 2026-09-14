"""Static contracts for guarded Whizard SGV/reco/kinfit replay."""

import copy
import importlib.util
import json
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
dag = load(
    "whizard_replay_dag",
    ROOT / "condor/reco_performance/prepare_whizard_replay_dag.py",
)


def canonical(element):
    element = copy.deepcopy(element)
    for node in element.iter():
        node.tail = None
        if node.text is not None and not node.text.strip():
            node.text = None
    return ET.tostring(element)


def test_generator_cross_section_uncertainties_and_display_precision():
    contract = json.loads(
        (ROOT / "reco_performance_study/study_inputs.json").read_text(encoding="utf-8")
    )["generator_mtt"]
    physsim = contract["physsim"]
    whizard = contract["whizard"]
    assert physsim["cross_section_uncertainty_fb"] == 0.00581374326
    assert whizard["cross_section_uncertainty_fb"] == 0.0009175807936117053
    assert generator_mtt.cross_section_label(
        "Physsim", physsim["cross_section_fb"], physsim["cross_section_uncertainty_fb"]
    ) == "Physsim (2.9606 #pm 0.0058 fb)"
    assert generator_mtt.cross_section_label(
        "Whizard", whizard["cross_section_fb"], whizard["cross_section_uncertainty_fb"]
    ) == "Whizard (2.20654 #pm 0.00092 fb)"


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


def test_whizard_false_null_proxy_terminates_before_dereference(monkeypatch):
    class FalseNullProxy:
        def __bool__(self):
            return False

        def getCollection(self, name):
            raise AssertionError("EOF proxy must not be dereferenced")

    class Reader:
        def __init__(self):
            collection = types.SimpleNamespace(getNumberOfElements=lambda: 0)
            event = types.SimpleNamespace(getCollection=lambda name: collection)
            self.events = iter((event, FalseNullProxy()))
            self.closed = False

        def open(self, path):
            pass

        def readNextEvent(self):
            return next(self.events)

        def close(self):
            self.closed = True

    reader = Reader()
    factory = types.SimpleNamespace(createLCReader=lambda: reader)
    ioimpl = types.SimpleNamespace(
        LCFactory=types.SimpleNamespace(getInstance=lambda: factory)
    )
    monkeypatch.setitem(sys.modules, "pyLCIO", types.SimpleNamespace(IOIMPL=ioimpl))
    monkeypatch.setattr(generator_mtt, "event_mtt", lambda particles: 350.0)
    fills = []

    records = generator_mtt.fill_whizard(
        ["input.slcio"], types.SimpleNamespace(Fill=fills.append), -1
    )

    assert records == [{"path": "input.slcio", "events_processed": 1, "events_with_mtt": 1}]
    assert fills == [350.0]
    assert reader.closed


def test_whizard_read_event_exception_propagates(monkeypatch):
    class ReadError(RuntimeError):
        pass

    class Reader:
        def open(self, path):
            pass

        def readNextEvent(self):
            raise ReadError("read failed")

        def close(self):
            pass

    factory = types.SimpleNamespace(createLCReader=Reader)
    ioimpl = types.SimpleNamespace(
        LCFactory=types.SimpleNamespace(getInstance=lambda: factory)
    )
    monkeypatch.setitem(sys.modules, "pyLCIO", types.SimpleNamespace(IOIMPL=ioimpl))

    with pytest.raises(ReadError, match="read failed"):
        generator_mtt.fill_whizard(["input.slcio"], object(), -1)


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


def test_reco_is_one_whole_file_with_boundary_record():
    assert marlin.whole_file_bounds(12500) == (0, 12501)
    with pytest.raises(ValueError):
        marlin.whole_file_bounds(0)


def test_reco_render_changes_only_input_output_and_range(tmp_path):
    authority = ROOT / "reco_performance_study/steering/reference/whizard_complete_reco_20260616.xml"
    original = ET.parse(authority).getroot()
    rendered, skip, maximum = marlin.render_reco(authority, Path("/input.slcio"), tmp_path / "out.slcio", 12500)
    assert (skip, maximum) == (0, 12501)
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
    authority = ROOT / "steering/tth_semilep_kinfit.xml"
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


def test_kinfit_authority_is_current_canonical_top10():
    root = ET.parse(ROOT / "steering/tth_semilep_kinfit.xml").getroot()
    processor = marlin.one(root, "./processor[@name='MyTTHSemiLepKinFit']")
    values = {item.get("name"): (item.text or "").strip() for item in processor.findall("./parameter")}
    assert values["JetCollectionName"] == "OutputErrorFlowJets6"
    assert values["FlavorJetCollectionName"] == "RefinedJets6"
    assert values["ElectronCollectionName"] == "ISOElectrons"
    assert values["MuonCollectionName"] == "ISOMuons"
    assert values["JetSLDLinkCollectionName"] == "JetSLDLink6"
    assert values["SLDNuLinkCollectionName"] == "SLDNuLink6"
    assert values["TopN"] == "10"
    assert values["ConstraintMode"] == "fullMass4C"
    assert values["includeISR"] == "true" and values["ISRPzMax"] == "125.6"
    assert values["EnableSLDNeutrinoEnumeration"] == "true"
    assert values["UseSoftMassConstraints"] == "true"
    assert values["UseJetCovarianceOffDiagonal"] == "false"
    assert (values["SigmaEnergyScaleFactor"], values["SigmaAnglesScaleFactor"], values["SigmaInvPtScaleFactor"]) == ("1.6", "2.6", "1.1")


def test_historical_top180_kinfit_authority_is_rejected(tmp_path):
    authority = ROOT / "reco_performance_study/steering/reference/whizard_kinfit_20260618.xml"
    with pytest.raises(RuntimeError, match="non-canonical kinfit authority"):
        marlin.render_kinfit(authority, Path("/reco.slcio"), tmp_path / "fit.root", 20)


class FakeEvent:
    def __init__(self, key, collections=marlin.REQUIRED_RECO_COLLECTIONS):
        self.key = key
        self.collections = collections

    def getRunNumber(self):
        return self.key[0]

    def getEventNumber(self):
        return self.key[1]

    def getCollectionNames(self):
        return self.collections


class FakeReader:
    def __init__(self, events):
        self.events = iter(events)

    def open(self, path):
        pass

    def readNextEvent(self):
        return next(self.events, None)

    def close(self):
        pass


def reader_factory_pair(input_events, output_events):
    readers = iter((FakeReader(input_events), FakeReader(output_events)))
    return lambda: next(readers)


def test_reco_validation_requires_exact_count_collections_and_ordered_unique_keys():
    events = [FakeEvent((1, 7)), FakeEvent((1, 8))]
    result = marlin.validate_reco_output(
        "input.slcio", "output.slcio", 2, reader_factory_pair(events, events)
    )
    assert result["events"] == 2
    assert result["ordered_event_keys_match"] is True
    assert result["unique_event_keys"] is True


@pytest.mark.parametrize(
    "input_events,output_events,expected,message",
    [
        ([FakeEvent((1, 7))], [], 1, "different event counts"),
        ([FakeEvent((1, 7))], [FakeEvent((1, 8))], 1, "ordered event-key mismatch"),
        ([FakeEvent((1, 7)), FakeEvent((1, 7))], [FakeEvent((1, 7)), FakeEvent((1, 7))], 2, "duplicate SGV input"),
        ([FakeEvent((1, 7))], [FakeEvent((1, 7), ())], 1, "missing collections"),
        ([FakeEvent((1, 7))], [FakeEvent((1, 7))], 2, "event count 1 != expected 2"),
    ],
)
def test_reco_validation_rejects_incomplete_or_mismatched_outputs(
    input_events, output_events, expected, message
):
    with pytest.raises(RuntimeError, match=message):
        marlin.validate_reco_output(
            "input.slcio",
            "output.slcio",
            expected,
            reader_factory_pair(input_events, output_events),
        )


def test_tail_segv_signature_is_specific_to_sldcorrection_end(tmp_path):
    good = tmp_path / "good.log"
    good.write_text(
        "*** Break *** segmentation violation\n"
        "#6 in SLDCorrection::end (this=x) at /src/SLDCorrection/src/SLDCorrection.cc:3711\n"
        "#8 in marlin::ProcessorMgr::end()\n"
    )
    bad = tmp_path / "bad.log"
    bad.write_text(
        "*** Break *** segmentation violation\n"
        "#6 in SLDCorrection::processEvent at /src/SLDCorrection/src/SLDCorrection.cc:1200\n"
        "#8 in marlin::ProcessorMgr::processEvent()\n"
    )
    assert marlin.has_sldcorrection_end_signature(good)
    assert not marlin.has_sldcorrection_end_signature(bad)
    assert marlin.accepted_reco_tail_segv(139, True, good)
    assert marlin.accepted_reco_tail_segv(-11, True, good)
    assert not marlin.accepted_reco_tail_segv(139, False, good)
    assert not marlin.accepted_reco_tail_segv(1, True, good)
    assert not marlin.accepted_reco_tail_segv(139, True, bad)


def test_xml_library_hashes_actual_library_path(tmp_path):
    library = tmp_path / "libProcessor.so"
    library.write_bytes(b"actual runtime library")
    root = ET.fromstring(f'<marlin><execute><library path="{library}"/></execute></marlin>')
    assert marlin.xml_library_hashes(root) == [
        {"path": str(library), "sha256": marlin.sha256(library)}
    ]


def test_runtime_validator_uses_prefixed_json_amid_pylcio_banner(monkeypatch):
    validation = {"events": 19, "ordered_event_keys_match": True}
    completed = types.SimpleNamespace(
        stdout=(
            "Loading LCIO ROOT dictionaries ...\n"
            + marlin.VALIDATION_JSON_PREFIX
            + json.dumps(validation)
            + "\n"
        )
    )
    monkeypatch.setattr(marlin.subprocess, "run", lambda *args, **kwargs: completed)
    assert marlin.runtime_validate_reco(
        ROOT, {"pythonpath_prefix": "/runtime"}, "/input", "/output", 19
    ) == validation


def test_kinfit_runtime_validator_uses_explicit_compatible_child(monkeypatch):
    validation = {"expected_input_events": 12499, "candidate_top10_rank_combo_alignment": True}
    observed = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["env"] = kwargs["env"]
        return types.SimpleNamespace(
            stdout=marlin.KINFIT_VALIDATION_JSON_PREFIX + json.dumps(validation) + "\n"
        )

    monkeypatch.setattr(marlin.subprocess, "run", fake_run)
    assert marlin.runtime_validate_kinfit(
        ROOT, {"pythonpath_prefix": "/runtime"}, "/output.root", 12499
    ) == validation
    assert str(marlin.KINFit_VALIDATION_PYTHON) in observed["command"]
    assert observed["command"][-1] == "12499"
    assert set(observed["env"]) == {"HOME", "PATH"}


def test_kinfit_schema_contract_includes_alignment_payload():
    assert {"top_combo_ids", "top_n", "best_combo_id"} <= marlin.BEST_TREE_REQUIRED_BRANCHES
    assert {"candidate_rank", "combo_id", "fit_success"} <= marlin.CANDIDATE_TREE_REQUIRED_BRANCHES


def test_condor_dag_is_four_whole_sgv_then_reco_jobs_without_kinfit():
    rendered = dag.render_dag(Path("/repo"), Path("/run"))
    assert rendered.count("JOB SGV") == 4
    assert rendered.count("JOB RECO") == 4
    assert rendered.count("PARENT SGV") == 4
    assert "KINFIT" not in rendered.upper()
    assert "6000" not in rendered and "6500" not in rendered


def test_direct_condor_chain_runs_whole_sgv_then_reco_without_kinfit():
    wrapper = (
        ROOT / "condor/reco_performance/run_whizard_chain.sh"
    ).read_text(encoding="utf-8")
    submit = (
        ROOT / "condor/reco_performance/whizard_direct_chain.sub"
    ).read_text(encoding="utf-8")
    assert wrapper.index("run_whizard_sgv.py") < wrapper.index("run_whizard_marlin.py")
    assert wrapper.count("--event-count 12500") == 2
    assert "--accept-validated-reco-tail-segv" in wrapper
    assert "6000" not in wrapper and "6500" not in wrapper
    assert "kinfit" not in wrapper.lower()
    assert submit.count("I410213_") == 4
    assert "queue index,input from" in submit
    assert "DAG" not in submit


def test_wrappers_refuse_existing_output_before_runtime(tmp_path, monkeypatch):
    input_path = tmp_path / "E550-Test.Ptth.Gwhizard-3_1_5.eL.pR.I410213_0.0.slcio"
    input_path.write_bytes(b"input")
    output = tmp_path / "exists.slcio"
    output.write_bytes(b"existing")
    monkeypatch.setattr(sys, "argv", ["run_whizard_sgv.py", "--input", str(input_path), "--output", str(output), "--run-dir", str(tmp_path / "run"), "--lock-file", str(tmp_path / "lock"), "--event-count", "20", "--prepare-only"])
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        sgv.main()
    authority = ROOT / "reco_performance_study/steering/reference/whizard_complete_reco_20260616.xml"
    monkeypatch.setattr(sys, "argv", ["run_whizard_marlin.py", "reco", "--authority", str(authority), "--input", str(input_path), "--output", str(output), "--run-dir", str(tmp_path / "reco_run"), "--event-count", "20", "--prepare-only"])
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        marlin.main()

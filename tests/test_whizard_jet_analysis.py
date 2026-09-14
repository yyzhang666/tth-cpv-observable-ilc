"""Dependency-free boundary tests for normalized Whizard jet analysis."""

import importlib.util
import json
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "report_whizard_jet_cm",
    ROOT / "scripts/reco_performance/report_whizard_jet_cm.py",
)
CM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CM)
ASSIGNMENT_SPEC = importlib.util.spec_from_file_location(
    "report_whizard_assignment_common",
    ROOT / "scripts/reco_performance/report_whizard_assignment_common.py",
)
ASSIGNMENT = importlib.util.module_from_spec(ASSIGNMENT_SPEC)
ASSIGNMENT_SPEC.loader.exec_module(ASSIGNMENT)


class Relation:
    def __init__(self, size):
        self.size = size

    def getNumberOfElements(self):
        return self.size


class WhizardJetAnalysisTest(unittest.TestCase):
    def test_relation_states(self):
        self.assertEqual(CM.relation_state(None, []), "relation_missing")
        self.assertEqual(CM.relation_state(Relation(0), []), "relation_empty")
        self.assertEqual(
            CM.relation_state(Relation(1), [[0.0] * 6 for _ in range(6)]),
            "relation_no_overlap",
        )
        matrix = [[0.0] * 6 for _ in range(6)]
        matrix[2][4] = 1.0
        self.assertEqual(CM.relation_state(Relation(1), matrix), "relation_eligible")

    def test_positive_dice_assignment_is_atomic(self):
        class Matrix:
            def __init__(self, values):
                self.values = values

            def __getitem__(self, key):
                row, column = key
                return self.values[row][column]

        legacy = types.SimpleNamespace(best_assignment=lambda score: (tuple(range(6)), 5.0))
        positive = Matrix([[1.0 if i == j else 0.0 for j in range(6)] for i in range(6)])
        state, permutation, assigned = CM.positive_dice_assignment({"score": positive}, legacy)
        self.assertEqual(state, "accepted_six_positive")
        self.assertEqual(permutation, tuple(range(6)))
        self.assertEqual(assigned, [1.0] * 6)

        one_zero = Matrix([[1.0 if i == j and i != 4 else 0.0 for j in range(6)] for i in range(6)])
        state, permutation, assigned = CM.positive_dice_assignment({"score": one_zero}, legacy)
        self.assertEqual(state, "relation_nonpositive_assigned_dice")
        self.assertIsNone(permutation)
        self.assertEqual(assigned[4], 0.0)

    def test_authoritative_mode_is_not_offline_reranked(self):
        self.assertEqual(
            ASSIGNMENT.MODES["kinfit + signed flavor"], "authoritative_best_tree"
        )
        self.assertNotIn("kinfit + signed flavor", ASSIGNMENT.OFFLINE_MODES)
        self.assertEqual(
            ASSIGNMENT.MODES["mass-constraint-only"], "price2014_prefit"
        )

    def test_relation_missing_precedes_jet_multiplicity_checks(self):
        legacy = types.SimpleNamespace(get_col=lambda event, name: None)
        state, context = CM.relation_context(object(), "RefinedJets6", legacy)
        self.assertEqual(state, "relation_missing")
        self.assertIsNone(context)

    def test_source_aware_identity(self):
        event = types.SimpleNamespace(getRunNumber=lambda: 7, getEventNumber=lambda: 9)
        self.assertEqual(
            CM.source_event_key("chunk0", 3, event), ("chunk0", 3, 7, 9)
        )
        self.assertNotEqual(
            CM.source_event_key("chunk0", 3, event),
            CM.source_event_key("chunk1", 3, event),
        )
        self.assertNotEqual(
            CM.source_event_key("chunk0", 3, event),
            CM.source_event_key("chunk0", 4, event),
        )

    def test_cm_event_contribution_is_atomic_six_jets(self):
        self.assertEqual(CM.complete_six_jet_entries(list(range(6))), list(range(6)))
        self.assertIsNone(CM.complete_six_jet_entries(list(range(5))))
        self.assertIsNone(CM.complete_six_jet_entries([]))

    def test_top10_alignment_counts_base_combo_ids(self):
        combo_ids = list(range(10))
        rows = [
            {"candidate_rank": rank, "combo_id": combo_id}
            for rank, combo_id in enumerate(combo_ids)
            for _ in range(3)
        ]
        self.assertTrue(ASSIGNMENT.top10_rows_aligned(rows, combo_ids))
        rows[-1]["combo_id"] = 99
        self.assertFalse(ASSIGNMENT.top10_rows_aligned(rows, combo_ids))

    def test_method_denominator_mismatch_is_rejected(self):
        good = {
            method: {("a", 1, 2): object()} for method in ASSIGNMENT.MODES
        }
        sets = ASSIGNMENT.method_key_sets(good)
        self.assertEqual(
            sets["mass-constraint-only"], sets["kinfit + signed flavor"]
        )
        bad = dict(good)
        bad["kinfit + signed flavor"] = {}
        with self.assertRaisesRegex(RuntimeError, "denominator mismatch"):
            ASSIGNMENT.method_key_sets(bad)

    def test_cm_condor_job_is_frozen_to_whole_reco_inputs(self):
        submit = (ROOT / "condor/reco_performance/whizard_jet_cm.sub").read_text()
        wrapper = (ROOT / "condor/reco_performance/run_whizard_jet_cm.sh").read_text()
        self.assertIn("getenv = false", submit)
        self.assertIn("on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)", submit)
        self.assertIn("--expected-events 12500", wrapper)
        self.assertIn("plot_tth_truejet_weaver_cm10.py", wrapper)
        self.assertNotIn("Top180", submit + wrapper)
        self.assertNotIn("kinfit", submit + wrapper.lower())

    def test_smoke_fixture_has_exact_source_local_indices(self):
        indices = json.loads(
            (ROOT / "condor/reco_performance/whizard_jet_smoke_indices.json").read_text()
        )
        expected = json.loads(
            (ROOT / "condor/reco_performance/whizard_jet_smoke_expected_relations.json").read_text()
        )
        fixture_keys = {
            f"{source_id}:{local_index}"
            for source_id, local_indices in indices.items()
            for local_index in local_indices
        }
        self.assertEqual(set(expected), fixture_keys)
        self.assertEqual(len(fixture_keys), 12)


if __name__ == "__main__":
    unittest.main()

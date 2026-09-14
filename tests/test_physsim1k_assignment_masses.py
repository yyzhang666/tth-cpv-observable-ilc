"""Focused dependency-free tests for the historical Physsim-1k diagnostic."""

import importlib.util
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts/reco_performance"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "plot_physsim1k_assignment_masses",
    SCRIPT_DIR / "plot_physsim1k_assignment_masses.py",
)
PLOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLOT)


class Particle:
    def __init__(self, energy, momentum):
        self.energy = energy
        self.momentum = momentum

    def getEnergy(self):
        return self.energy

    def getMomentum(self):
        return self.momentum


def selected_row(event_index, fit_success=1):
    return {
        "event_index": event_index,
        "fit_success": fit_success,
        "mW_had_prefit": 80.0,
        "mt_had_prefit": 170.0,
        "mH_prefit": 125.0,
        "mW_had_postfit": 81.0,
        "mt_had_postfit": 171.0,
        "mH_postfit": 124.0,
    }


class Physsim1kAssignmentMassesTest(unittest.TestCase):
    def test_source_aware_common_intersection_and_duplicates(self):
        truth = {
            0: {"source_file_id": PLOT.SOURCE_ID, "run": 7, "event": 10, "truth": {"W": 80, "top": 172, "H": 125}},
            1: {"source_file_id": PLOT.SOURCE_ID, "run": 7, "event": 11, "truth": {"W": 81, "top": 173, "H": 126}},
        }
        selections = {
            PLOT.PRICE_MODE: [selected_row(0, 0), selected_row(1, 1)],
            PLOT.KINFIT_MODE: [selected_row(0, 1), selected_row(1, 1)],
        }
        indexed, common = PLOT.validate_common_selection(selections, truth, expected_common=2)
        self.assertEqual(common, [0, 1])
        self.assertEqual(len(indexed[PLOT.PRICE_MODE]), 2)
        with self.assertRaisesRegex(RuntimeError, "duplicate selected row"):
            bad = dict(selections)
            bad[PLOT.PRICE_MODE] = selections[PLOT.PRICE_MODE] + [selected_row(0)]
            PLOT.validate_common_selection(bad, truth, expected_common=2)

    def test_presence_map_does_not_filter_or_fabricate_truth_fields(self):
        rows = [
            {"event_index": 0, "combo_id": 10},
            {"event_index": 0, "combo_id": 10},
            {"event_index": 0, "combo_id": 11},
            {"event_index": 1, "combo_id": 20},
        ]
        presence, counters = PLOT.build_presence_only_assignment_map(rows)
        self.assertEqual(counters["presence_map_events"], 2)
        self.assertEqual(counters["presence_map_event_combo_pairs"], 3)
        self.assertTrue(
            all(
                presence[int(row["event_index"])][int(row["combo_id"])]
                == {"assignment_truth_status": "not_evaluated_for_mass_plot"}
                for row in rows
            )
        )
        self.assertFalse(
            any(
                key.startswith("truth_match_")
                for event in presence.values()
                for payload in event.values()
                for key in payload
            )
        )

    def test_truth_parent_four_vector_mass(self):
        self.assertAlmostEqual(PLOT.particle_mass(Particle(5.0, [3.0, 0.0, 0.0])), 4.0)
        self.assertTrue(math.isfinite(PLOT.particle_mass(Particle(5.0, [3.0, 0.0, 0.0]))))

    def test_histogram_closure_counts_underflow_and_overflow(self):
        result = PLOT.histogram_accounting([39, 40, 80, 130, 131], 40, 130, 60, 5)
        self.assertEqual((result["underflow"], result["in_range"], result["overflow"]), (1, 3, 1))
        self.assertEqual(result["closure_count"], 5)
        self.assertEqual(result["closure_fraction"], 1.0)

    def test_existing_output_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "refusing to reuse"):
                PLOT.assert_new_output_dir(Path(directory))


if __name__ == "__main__":
    unittest.main()

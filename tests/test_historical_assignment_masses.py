"""Focused tests for the historical 830-event mass diagnostic."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "plot_historical_assignment_masses",
    ROOT / "scripts/reco_performance/plot_historical_assignment_masses.py",
)
PLOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLOT)


def row(mode, event_index, combo_id):
    payload = {
        "source_mode": PLOT.SOURCE_MODE,
        "rerank_mode": mode,
        "event_index": str(event_index),
        "combo_id": str(combo_id),
    }
    for spec in PLOT.MODE_SPECS.values():
        for column in spec["columns"].values():
            payload[column] = "100.0"
    return payload


class HistoricalAssignmentMassesTest(unittest.TestCase):
    def test_common_rows_are_unique_and_use_exact_intersection(self):
        rows = [
            row(PLOT.PRICE_MODE, 1, 10),
            row(PLOT.PRICE_MODE, 2, 20),
            row(PLOT.KINFIT_MODE, 1, 11),
            row(PLOT.KINFIT_MODE, 2, 20),
        ]
        selected, common, summary = PLOT.validate_common_rows(
            rows, list(rows[0]), expected_common=2
        )
        self.assertEqual(common, [1, 2])
        self.assertEqual(summary["differing_combo_id_events"], 1)
        self.assertEqual(len(selected[PLOT.PRICE_MODE]), 2)
        with self.assertRaisesRegex(RuntimeError, "duplicate row"):
            PLOT.validate_common_rows(rows + [dict(rows[0])], list(rows[0]), expected_common=2)

    def test_histogram_closure_includes_underflow_and_overflow(self):
        result = PLOT.histogram_accounting(
            [39.0, 40.0, 80.0, 130.0, 131.0], 40.0, 130.0, 60, 5
        )
        self.assertEqual(result["underflow"], 1)
        self.assertEqual(result["in_range"], 3)
        self.assertEqual(result["overflow"], 1)
        self.assertEqual(result["closure_count"], 5)
        self.assertAlmostEqual(result["closure_fraction"], 1.0)

    def test_existing_output_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "refusing to reuse"):
                PLOT.assert_new_output_dir(Path(directory))


if __name__ == "__main__":
    unittest.main()

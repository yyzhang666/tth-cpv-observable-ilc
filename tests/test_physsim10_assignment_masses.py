"""Focused tests for the ten-chunk Physsim mass diagnostic."""
import importlib.util, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/"scripts/reco_performance/plot_physsim10_assignment_masses.py"
SPEC=importlib.util.spec_from_file_location("plot_physsim10_assignment_masses",SCRIPT); PLOT=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(PLOT)

class TestPlot(unittest.TestCase):
    def test_display_rename_preserves_internal_mode(self):
        self.assertEqual(PLOT.PRICE_MODE,"price2014_prefit_bcharge1p00"); self.assertEqual(PLOT.DISPLAY[PLOT.PRICE_MODE]["label"],"mass-constraint-only + signed flavor (PREFIT)")
    def test_source_key(self): self.assertEqual(PLOT.source_key({"source_id":"j","run_number":1,"event_number":2,"event_index":3}),("j",1,2,3))
    def test_histogram_closure(self):
        r=PLOT.histogram_accounting([39,40,80,130,131],40,130,60,5); self.assertEqual((r["underflow"],r["in_range"],r["overflow"]),(1,3,1)); self.assertEqual(r["closure_fraction"],1)
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"refusing to reuse"): PLOT.assert_new_output_dir(Path(d))
    def test_frozen_counts(self): self.assertEqual(PLOT.EXPECTED["common_rows"],46414); self.assertEqual(PLOT.EXPECTED_FAILED_BEST,{(8,1,6976,6976)})
    def test_csv_fields_are_union_of_both_modes(self):
        self.assertEqual(PLOT.csv_field_union([{"a":1,"shared":2},{"b":3,"shared":4}]),["a","shared","b"])
    def test_failed_authoritative_row_needs_no_kinfit_diagnostic(self):
        self.assertFalse(PLOT.diagnostic_combo_mismatch({"fit_success":0,"combo_id":1},None))
        self.assertFalse(PLOT.diagnostic_mass_row_mismatch({"fit_success":0},None))
        with self.assertRaisesRegex(RuntimeError,"no diagnostic kinfit winner"):
            PLOT.diagnostic_combo_mismatch({"fit_success":1,"combo_id":1},None)
    def test_mass_row_identity_is_distinct_from_combo_identity(self):
        best={"fit_success":1,"combo_id":4,"mW_had_postfit":80.,"mt_had_postfit":172.,"mH_postfit":125.}
        other={"combo_id":4,"mW_had_postfit":81.,"mt_had_postfit":172.,"mH_postfit":125.}
        self.assertFalse(PLOT.diagnostic_combo_mismatch(best,other)); self.assertTrue(PLOT.diagnostic_mass_row_mismatch(best,other))

if __name__ == "__main__": unittest.main()

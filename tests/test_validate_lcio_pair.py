"""Focused fake-reader tests for the streaming LCIO pair validator."""

import importlib.util
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_lcio_pair",
    ROOT / "scripts/reco_performance/validate_lcio_pair.py",
)
PAIR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAIR)


class FakeEvent:
    def __init__(self, run, event):
        self.run = run
        self.event = event

    def getRunNumber(self):
        return self.run

    def getEventNumber(self):
        return self.event


class FalseNull:
    def __bool__(self):
        return False

    def getRunNumber(self):
        raise AssertionError("EOF proxy must not be dereferenced")


class FakeReader:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = False

    def open(self, path):
        self.path = path

    def readNextEvent(self):
        return next(self.events, None)

    def close(self):
        self.closed = True


def pair_factory(left, right):
    readers = (FakeReader(left), FakeReader(right))
    iterator = iter(readers)
    return (lambda: next(iterator)), readers


class ValidateLcioPairTest(unittest.TestCase):
    def validate(self, left, right, expected):
        factory, readers = pair_factory(left, right)
        result = PAIR.validate_lcio_pair("left", "right", expected, factory)
        self.assertTrue(all(reader.closed for reader in readers))
        return result

    def test_success(self):
        events = [FakeEvent(1, 10), FakeEvent(1, 11)]
        result = self.validate(events, events, 2)
        self.assertEqual(result["events"], 2)
        self.assertTrue(result["simultaneous_eof"])

    def test_early_eof_on_either_side(self):
        event = FakeEvent(1, 10)
        for left, right in (([], [event]), ([event], [])):
            with self.subTest(left_count=len(left)):
                factory, _ = pair_factory(left, right)
                with self.assertRaisesRegex(RuntimeError, "different indices"):
                    PAIR.validate_lcio_pair("left", "right", 1, factory)

    def test_duplicate_on_either_side(self):
        duplicate = [FakeEvent(1, 10), FakeEvent(1, 10)]
        unique = [FakeEvent(1, 10), FakeEvent(1, 11)]
        for left, right, message in (
            (duplicate, unique, "duplicate left"),
            (unique, duplicate, "duplicate right"),
        ):
            with self.subTest(message=message):
                factory, _ = pair_factory(left, right)
                with self.assertRaisesRegex(RuntimeError, message):
                    PAIR.validate_lcio_pair("left", "right", 2, factory)

    def test_reordered_or_mismatched_keys(self):
        left = [FakeEvent(1, 10), FakeEvent(1, 11)]
        right = [FakeEvent(1, 11), FakeEvent(1, 10)]
        factory, _ = pair_factory(left, right)
        with self.assertRaisesRegex(RuntimeError, "ordered event-key mismatch"):
            PAIR.validate_lcio_pair("left", "right", 2, factory)

    def test_reader_exception_propagates(self):
        error = RuntimeError("read failure")
        left = types.SimpleNamespace(
            open=lambda path: None,
            readNextEvent=lambda: (_ for _ in ()).throw(error),
            close=lambda: None,
        )
        right = FakeReader([])
        readers = iter((left, right))
        with self.assertRaisesRegex(RuntimeError, "read failure"):
            PAIR.validate_lcio_pair("left", "right", 1, lambda: next(readers))

    def test_false_null_proxy_is_eof_without_dereference(self):
        factory, readers = pair_factory([FalseNull()], [FalseNull()])
        with self.assertRaisesRegex(RuntimeError, "event count 0 != expected 1"):
            PAIR.validate_lcio_pair("left", "right", 1, factory)
        self.assertTrue(all(reader.closed for reader in readers))

    def test_reco_recovery_submit_is_four_whole_chunks_only(self):
        submit = (
            ROOT / "condor/reco_performance/whizard_reco_recovery.sub"
        ).read_text(encoding="utf-8")
        self.assertIn("$(sgv_root)/sgv/whizard_I410213_$(index)_sgv.slcio", submit)
        self.assertIn("--event-count 12500", submit)
        self.assertIn("+RequestRuntime = 36000", submit)
        self.assertIn("queue index from (\n0\n1\n2\n3\n)", submit)
        self.assertNotIn("--event-count 6000", submit)
        self.assertNotIn("--event-count 6500", submit)
        self.assertNotIn("kinfit", submit.lower())


if __name__ == "__main__":
    unittest.main()

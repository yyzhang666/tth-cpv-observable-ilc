"""Tests of the process-independent provenance utilities."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ilc_miner.provenance import (
    atomic_write_json,
    file_records,
    git_state,
    runtime_state,
    sha256_file,
)


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_sha256_and_atomic_json(self):
        source = self.root / "source.txt"
        source.write_text("observable\n")
        self.assertEqual(
            sha256_file(source),
            "7073c52c8cae9566b9dc5ecd255165f8eda779fa6627248b68a15f20f397e081",
        )
        output = self.root / "nested" / "manifest.json"
        atomic_write_json(output, {"status": "ok"})
        self.assertEqual(output.read_text(), '{\n  "status": "ok"\n}\n')

    def test_hash_covers_bytes_after_sixteen_megabytes(self):
        source = self.root / "large.bin"
        payload = b"a" * (16 * 1024 * 1024) + b"tail"
        source.write_bytes(payload)
        self.assertEqual(sha256_file(source), hashlib.sha256(payload).hexdigest())
        before = sha256_file(source)
        with source.open("r+b") as stream:
            stream.seek(-1, 2)
            stream.write(b"X")
        self.assertNotEqual(sha256_file(source), before)

    def test_file_records_preserve_order_and_full_hashes(self):
        first = self.root / "first.txt"
        second = self.root / "second.txt"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        records = file_records([second, first])
        self.assertEqual([r["path"] for r in records], [str(second.resolve()), str(first.resolve())])
        self.assertEqual([r["size"] for r in records], [6, 5])
        self.assertEqual(records[0]["sha256"], hashlib.sha256(b"second").hexdigest())

    def test_atomic_json_replaces_existing_file(self):
        output = self.root / "manifest.json"
        atomic_write_json(output, {"status": "old"})
        atomic_write_json(output, {"status": "new", "count": 3})
        self.assertEqual(json.loads(output.read_text()), {"status": "new", "count": 3})
        self.assertEqual(list(self.root.glob(".manifest.json.*.tmp")), [])

    def test_failed_json_write_preserves_destination_and_cleans_temporary(self):
        output = self.root / "manifest.json"
        atomic_write_json(output, {"status": "original"})
        original = output.read_bytes()
        with self.assertRaises(TypeError):
            atomic_write_json(output, {"unsupported": object()})
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual(list(self.root.glob(".manifest.json.*.tmp")), [])

    @patch("ilc_miner.provenance.subprocess.run")
    def test_git_state_records_commit_branch_and_changes(self, run):
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=" M file.py\n"),
            subprocess.CompletedProcess([], 0, stdout="abc123\n"),
            subprocess.CompletedProcess([], 0, stdout="ilc-miner\n"),
        ]
        result = git_state(self.root)
        self.assertEqual(result["commit"], "abc123")
        self.assertEqual(result["branch"], "ilc-miner")
        self.assertTrue(result["dirty"])
        self.assertEqual(run.call_count, 3)

    @patch("ilc_miner.provenance.subprocess.run", side_effect=OSError("git unavailable"))
    def test_git_state_reports_unavailable(self, run):
        result = git_state(self.root)
        self.assertFalse(result["available"])
        self.assertIn("git unavailable", result["error"])

    def test_runtime_records_missing_dependency_explicitly(self):
        missing = "ilc-miner-nonexistent-dependency-for-test"
        result = runtime_state([missing])
        self.assertIsNone(result["packages"][missing])
        self.assertTrue(result["python"])
        self.assertTrue(result["executable"])


if __name__ == "__main__":
    unittest.main()

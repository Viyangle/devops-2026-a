import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scan_runtime_logs


class RuntimeLogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def scan(self, *paths):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = scan_runtime_logs.main([str(path) for path in paths])
        return code, output.getvalue(), error.getvalue()

    def test_fake_key_hit_is_redacted_and_cleanup_passes(self):
        value = "sk-" + "a" * 24
        log = self.root / "build.log"
        log.write_text('api_key = "' + value + '"\n')
        code, output, _ = self.scan(log)
        self.assertEqual(code, 1)
        self.assertIn("FOUND", output)
        self.assertNotIn(value, output)
        log.write_text("build completed\n")
        self.assertEqual(self.scan(log)[0], 0)

    def test_legacy_text_is_scanned_with_replacement_decoding(self):
        log = self.root / "legacy.log"
        log.write_bytes(b"\xff\xfe completed\n")
        self.assertEqual(self.scan(log)[0], 0)

    def test_missing_or_empty_input_is_incomplete_even_with_a_clean_log(self):
        log = self.root / "clean.log"
        log.write_text("completed\n")
        empty = self.root / "empty"
        empty.mkdir()
        for incomplete in (self.root / "missing", empty):
            with self.subTest(path=incomplete):
                self.assertEqual(self.scan(log, incomplete)[0], 2)

    def test_traversal_failure_is_incomplete(self):
        log = self.root / "clean.log"
        log.write_text("completed\n")

        def walk(root, onerror):
            yield str(root), [], ["clean.log"]
            onerror(PermissionError(13, "denied", str(root / "blocked")))

        with patch.object(scan_runtime_logs.os, "walk", side_effect=walk):
            code, _, error = self.scan(self.root)
        self.assertEqual(code, 2)
        self.assertIn("PermissionError", error)

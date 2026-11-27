import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "e11e12"))
import pipeline


class FixedReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "repo").mkdir()
        self.report = {
            "schema_version": "e11e12-1", "kind": "fixed-md",
            "status": "SUCCEEDED", "commit": "b" * 40,
            "data": {"commit": "b" * 40, "findings": []},
            "source_report": {"job_id": "job-source", "trace_id": "trace-source",
                              "uri": "artifact://job-source/incremental-check.json", "sha256": "c" * 64},
        }
        self.payload = (json.dumps(self.report) + "\n").encode()
        self.source = self.root / "fixed-md.json"
        self.source.write_bytes(self.payload)
        self.request = {
            "mode": "e11-b", "repo": str(self.root / "repo"),
            "base": "a" * 40, "target": "b" * 40,
            "fixed_report": str(self.source),
            "fixed_report_sha256": hashlib.sha256(self.payload).hexdigest(),
        }

    def execute(self):
        def snapshot(repo, revision, destination, logs, *, subdir):
            destination.mkdir(parents=True)
            return revision

        def resume(out, result, image):
            result["status"] = "SUCCEEDED"

        def build(request, target, out):
            result = {"attempts": [{"image_id": "test-image"}]}
            pipeline.save(out / "draft-build/result.json", result)
            return result

        with patch.object(pipeline, "snapshot", side_effect=snapshot), \
             patch.object(pipeline, "validate_project"), \
             patch.object(pipeline, "draft_for", side_effect=build) as draft, \
             patch.object(pipeline, "run_in_draft", side_effect=resume):
            self.draft = draft
            return pipeline.execute(self.request, self.root / "out")

    def test_original_bytes_and_a_provenance_are_retained(self):
        result = self.execute()
        self.assertEqual(result["status"], "SUCCEEDED")
        copy = self.root / "out/fixed-md-input.json"
        self.assertEqual(copy.read_bytes(), self.payload)
        self.assertEqual(json.loads(copy.read_bytes())["source_report"], self.report["source_report"])

    def test_transfer_change_with_original_hash_fails_before_build(self):
        self.source.write_bytes(self.payload + b"\n")
        result = self.execute()
        self.assertEqual(result["error"]["code"], "ARTIFACT_HASH_MISMATCH")
        self.assertEqual(result["stages"], [])
        self.assertFalse((self.root / "out/fixed-md-input.json").exists())
        self.draft.assert_not_called()

    def test_legacy_request_without_hash_still_accepts_current_report(self):
        del self.request["fixed_report_sha256"]
        self.assertEqual(self.execute()["status"], "SUCCEEDED")

    def test_current_hash_does_not_accept_another_target(self):
        self.report["commit"] = "a" * 40
        self.source.write_text(json.dumps(self.report))
        self.request["fixed_report_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(self.execute()["error"]["code"], "STALE_REPORT")

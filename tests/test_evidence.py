import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sandbox.evidence import evidence_run
from sandbox.keycloak_lifecycle import LabError
from sandbox import verify_auth


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "report.json"
        self.path.write_text('{"status":"passed","run_id":"old"}')

    def test_start_replaces_old_pass_before_work(self):
        report = {}
        with evidence_run(self.path, report):
            started = json.loads(self.path.read_text())
            self.assertEqual(started["status"], "running")
            self.assertNotEqual(started["run_id"], "old")
            report["status"] = "passed"
        self.assertEqual(json.loads(self.path.read_text())["status"], "passed")
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_error_is_recorded_without_sensitive_message(self):
        with self.assertRaises(ValueError):
            with evidence_run(self.path, {}):
                raise ValueError("secret-not-for-report")
        written = self.path.read_text()
        self.assertEqual(json.loads(written)["status"], "failed")
        self.assertNotIn("secret-not-for-report", written)

    def test_unfinished_run_is_not_success(self):
        with evidence_run(self.path, {}):
            pass
        self.assertEqual(json.loads(self.path.read_text())["status"], "incomplete")

    def test_auth_startup_failure_overwrites_stale_success(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(LabError):
            verify_auth.run(self.path)
        self.assertEqual(json.loads(self.path.read_text())["status"], "failed")

    def test_cleanup_failure_does_not_mask_original_error_or_lose_report(self):
        client = MagicMock()
        client.request.return_value = {"access_token": "dummy"}
        client.api.return_value = []
        with patch.dict(os.environ, {"LAB_CLIENT_SECRET": "dummy", "LAB_ADMIN_PASSWORD": "dummy"}):
            with patch.object(verify_auth, "Client", return_value=client):
                with patch.object(verify_auth, "execute"):
                    with patch.object(verify_auth, "user_lookup",
                                      side_effect=[{"id": "u1"}, LabError("cleanup unavailable")]):
                        with patch.object(verify_auth, "Browser", side_effect=ValueError("original")):
                            with self.assertRaisesRegex(ValueError, "original"):
                                verify_auth.run(self.path)
        result = json.loads(self.path.read_text())
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failure_type"], "ValueError")
        self.assertEqual(result["cleanup"], "incomplete")
        self.assertEqual(result["cleanup_failure_type"], "LabError")


if __name__ == "__main__":
    unittest.main()

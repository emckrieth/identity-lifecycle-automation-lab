import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlencode
from sandbox.asset_workflow import Queue
from sandbox.keycloak_lifecycle import LabError
from sandbox.slack_intake import accept


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.queue = Queue(str(Path(self.folder.name) / "queue.db"))
        self.assets = MagicMock()
        self.assets.user.return_value = {"id": 5}
        self.assets.asset.return_value = {"assigned_to": None}
        self.identity = MagicMock()

    def submit(self, action="joiner", ticket="REQ-1"):
        return self.queue.submit(ticket, action, "lab-avery", "LAB-001", "requester")

    def approve(self, ticket="REQ-1"):
        return self.queue.approve(ticket, "reviewer", {"reviewer"})

    def test_duplicate_request_is_one_row_and_conflicting_payload_rejected(self):
        self.submit()
        self.submit()
        with self.queue.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM requests").fetchone()[0], 1)
        with self.assertRaises(LabError):
            self.queue.submit("REQ-1", "leaver", "lab-avery", "LAB-001", "requester")

    def test_no_processing_without_approval(self):
        self.submit()
        with self.assertRaises(LabError):
            self.queue.process("REQ-1", self.assets, self.identity)
        self.identity.assert_not_called()

    def test_unauthorized_and_self_approval_rejected(self):
        self.submit()
        with self.assertRaises(LabError):
            self.queue.approve("REQ-1", "stranger", {"reviewer"})
        with self.assertRaises(LabError):
            self.queue.approve("REQ-1", "requester", {"requester"})

    def test_partial_asset_failure_persists_incomplete_and_retry_finishes(self):
        self.submit()
        self.approve()
        self.assets.assign.side_effect = LabError("asset unavailable")
        with self.assertRaises(LabError):
            self.queue.process("REQ-1", self.assets, self.identity)
        self.assertEqual(self.queue.get("REQ-1")["status"], "incomplete")
        self.assets.assign.side_effect = None
        self.assertEqual(self.queue.process("REQ-1", self.assets, self.identity)["status"], "complete")
        self.queue.process("REQ-1", self.assets, self.identity)
        self.assertEqual(self.assets.assign.call_count, 2)

    def test_leaver_remains_open_until_authorized_physical_receipt(self):
        self.submit("leaver")
        self.approve()
        self.assertEqual(self.queue.process("REQ-1", self.assets, self.identity)["status"], "awaiting_return")
        self.assets.confirm_return.assert_not_called()
        with self.assertRaises(LabError):
            self.queue.receive("REQ-1", "requester", {"reviewer"}, self.assets)
        result = self.queue.receive("REQ-1", "reviewer", {"reviewer"}, self.assets)
        self.assertEqual(result["status"], "complete")

    def signed(self, **overrides):
        values = {"team_id": "T_LAB", "user_id": "U_LAB", "trigger_id": "trigger1",
                  "command": "/lab-onboard", "text": "lab-avery LAB-001"}
        values.update(overrides)
        body = urlencode(values).encode()
        signature = "v0=" + hmac.new(b"fixture-secret", b"v0:1000:" + body, hashlib.sha256).hexdigest()
        return body, {"X-Slack-Request-Timestamp": "1000", "X-Slack-Signature": signature}

    def test_signed_slack_request_deduplicates_and_only_queues(self):
        body, headers = self.signed()
        result = accept(body, headers, "fixture-secret", {"T_LAB"}, self.queue, now=1000)
        self.assertEqual(result, accept(body, headers, "fixture-secret", {"T_LAB"}, self.queue, now=1000))
        self.assertIn("pending_approval", result["text"])
        self.identity.assert_not_called()

    def test_slack_tampering_expiration_and_wrong_team_rejected(self):
        body, headers = self.signed()
        for changed_body, teams, now in [(body + b"x", {"T_LAB"}, 1000),
                                         (body, {"T_LAB"}, 1301), (body, {"OTHER"}, 1000)]:
            with self.assertRaises(LabError):
                accept(changed_body, headers, "fixture-secret", teams, self.queue, now=now)


if __name__ == "__main__":
    unittest.main()

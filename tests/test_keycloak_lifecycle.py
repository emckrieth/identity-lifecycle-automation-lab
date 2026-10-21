import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from sandbox.keycloak_lifecycle import Client, LabError, execute, lifecycle


class FakeKeycloak:
    """Stateful contract double, not an actual Keycloak server."""
    def __init__(self):
        self.user = None
        self.groups = []
        self.sessions = []
        self.creates = 0
        self.fail_logout = False
        self.fail_auth = False
        self.ignore_disable = False
        self.ambiguous = False
        self.group_available = True

    def login(self):
        if self.fail_auth:
            raise LabError("API HTTP 403")

    def api(self, method, path, data=None):
        if method == "GET" and path.startswith("/users?"):
            return [self.user, self.user] if self.ambiguous else ([self.user] if self.user else [])
        if method == "GET" and path.startswith("/groups?"):
            return [{"id": "g1", "path": "/lab-support"}] if self.group_available else []
        if method == "POST" and path == "/users":
            self.creates += 1
            self.user = dict(data, id="u1")
        elif method == "GET" and path == "/users/u1":
            return dict(self.user)
        elif path == "/users/u1/groups/g1" and method == "PUT":
            self.groups = [{"id": "g1"}]
        elif path == "/users/u1/groups/g1" and method == "DELETE":
            self.groups = []
        elif method == "GET" and path.startswith("/users/u1/groups?"):
            return list(self.groups)
        elif path == "/users/u1" and method == "PUT":
            if not self.ignore_disable:
                self.user.update(data)
        elif path == "/users/u1/logout" and method == "POST":
            if self.fail_logout:
                raise LabError("API unavailable")
            self.sessions = []
        elif path == "/users/u1/sessions" and method == "GET":
            return list(self.sessions)
        else:
            raise AssertionError((method, path))


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeKeycloak()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audit = Path(self.tmp.name) / "audit.jsonl"

    def run_flow(self, action="joiner"):
        return execute(self.client, action, "lab-avery", "REQ-101", self.audit)

    def test_duplicate_joiner_and_leaver_are_safe(self):
        self.run_flow()
        self.run_flow()
        self.assertEqual(self.client.creates, 1)
        self.client.sessions = [{"id": "session1"}]
        result = self.run_flow("leaver")
        self.run_flow("leaver")
        self.assertFalse(self.client.user["enabled"])
        self.assertEqual(self.client.groups, [])
        self.assertEqual(result["interactive_access_test"], "not_performed")

    def test_partial_offboarding_is_incomplete_and_retry_finishes(self):
        self.run_flow()
        self.client.sessions = [{"id": "session1"}]
        self.client.fail_logout = True
        with self.assertRaises(LabError):
            self.run_flow("leaver")
        self.assertFalse(self.client.user["enabled"])
        self.assertEqual(self.client.sessions, [{"id": "session1"}])
        events = [json.loads(line) for line in self.audit.read_text().splitlines()]
        self.assertEqual(events[-1]["outcome"], "incomplete")
        self.client.fail_logout = False
        self.run_flow("leaver")
        self.assertEqual(self.client.sessions, [])

    def test_auth_denied_has_no_mutations_and_records_failure(self):
        self.client.fail_auth = True
        with self.assertRaises(LabError):
            self.run_flow()
        self.assertEqual(self.client.creates, 0)
        self.assertEqual(json.loads(self.audit.read_text().splitlines()[-1])["outcome"], "incomplete")

    def test_ambiguous_identity_fails_before_mutation(self):
        self.run_flow()
        self.client.ambiguous = True
        with self.assertRaisesRegex(LabError, "Ambiguous"):
            self.run_flow("leaver")
        self.assertTrue(self.client.user["enabled"])

    def test_missing_group_does_not_create_account(self):
        self.client.group_available = False
        with self.assertRaises(LabError):
            self.run_flow()
        self.assertEqual(self.client.creates, 0)

    def test_read_back_catches_ignored_disable(self):
        self.run_flow()
        self.client.ignore_disable = True
        with self.assertRaisesRegex(LabError, "read-back"):
            self.run_flow("leaver")

    def test_joiner_does_not_reactivate_leaver(self):
        self.run_flow()
        self.run_flow("leaver")
        with self.assertRaisesRegex(LabError, "rehire"):
            self.run_flow()

    def test_unknown_leaver_and_non_lab_user_rejected(self):
        with self.assertRaises(LabError):
            self.run_flow("leaver")
        with self.assertRaises(LabError):
            lifecycle(self.client, "leaver", "real-user", lambda *args: None)


class TransportTests(unittest.TestCase):
    def test_only_loopback_http_base_is_allowed(self):
        for url in ["https://example.com", "http://127.0.0.1@evil.test",
                    "http://127.0.0.1/path", "http://localhost:8080",
                    "http://127.0.0.1?redirect=evil"]:
            with self.subTest(url=url), self.assertRaises(LabError):
                Client(url, "test-secret")

    def test_permission_error_omits_response_body(self):
        client = Client("http://127.0.0.1:8080", "test-secret")
        error = HTTPError(client.base, 403, "secret-body", {}, None)
        with patch.object(client.opener, "open", side_effect=error):
            with self.assertRaisesRegex(LabError, "^API HTTP 403$"):
                client.login()

    def test_unavailable_service_returns_bounded_failure(self):
        client = Client("http://127.0.0.1:8080", "test-secret")
        with patch.object(client.opener, "open", side_effect=URLError("secret-body")):
            with self.assertRaisesRegex(LabError, "^API unavailable"):
                client.login()


if __name__ == "__main__":
    unittest.main()

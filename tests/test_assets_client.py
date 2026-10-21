import io
import json
import unittest
from unittest.mock import patch
from sandbox.assets_api import Assets
from sandbox.keycloak_lifecycle import LabError


class AssetsClientTests(unittest.TestCase):
    def test_http_200_logical_error_is_not_success(self):
        client = Assets("fixture-token")
        response = io.BytesIO(json.dumps({"status": "error", "messages": "fixture"}).encode())
        with patch.object(client.opener, "open", return_value=response):
            with self.assertRaisesRegex(LabError, "rejected"):
                client.api("POST", "/hardware/1/checkout", {})

    def test_other_owner_is_not_silently_reassigned(self):
        client = Assets("fixture-token")
        with patch.object(client, "user", return_value={"id": 1}):
            with patch.object(client, "asset", return_value={"id": 4, "assigned_to": {"type": "user", "id": 2}}):
                with patch.object(client, "api") as request:
                    with self.assertRaisesRegex(LabError, "another owner"):
                        client.assign("LAB-001", "lab-avery", "REQ-1")
                    request.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.request import Request

from sandbox.keycloak_lifecycle import LabError
from sandbox.verify_auth import Browser, Forms, LoopbackCookiePolicy, totp


class AuthHarnessTests(unittest.TestCase):
    def test_totp_known_rfc_vector(self):
        # RFC 6238 SHA-1 test secret at 59 seconds, truncated to six digits.
        with patch("sandbox.verify_auth.time.time", return_value=59):
            self.assertEqual(totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"), "287082")

    def test_visible_seed_is_separate_from_opaque_csrf_field(self):
        parsed = Forms('<a id="mode-manual" href="http://127.0.0.1:8080/manual"></a>'
                       '<span id="kc-totp-secret-key">GEZD GNBV</span>'
                       '<form action="http://127.0.0.1:8080/check?a=1&amp;b=2">'
                       '<input name="totpSecret" value="opaque-test-token"></form>')
        self.assertEqual(parsed.visible_otp, "GEZD GNBV")
        self.assertEqual(parsed.forms[0]["inputs"]["totpSecret"], "opaque-test-token")
        self.assertTrue(parsed.forms[0]["action"].endswith("?a=1&b=2"))

    def test_remote_form_destination_blocked_before_network(self):
        browser = Browser("test-client-secret")
        with patch.object(browser.opener, "open") as request:
            with self.assertRaises(LabError):
                browser.request("https://example.com/collect", {"password": "test"})
            request.assert_not_called()

    def test_secure_cookie_exception_only_for_loopback(self):
        policy = LoopbackCookiePolicy()
        cookie = SimpleNamespace(secure=True)
        self.assertTrue(policy.return_ok_secure(cookie, Request("http://127.0.0.1:8080")))
        self.assertFalse(policy.return_ok_secure(cookie, Request("http://example.com")))
        self.assertFalse(policy.return_ok_secure(cookie, Request("http://127.0.0.1.evil.test")))

    def test_callback_state_mismatch_rejected(self):
        browser = Browser("test-client-secret")
        response = MagicMock()
        response.__enter__.return_value = response
        response.code = 302
        response.read.return_value = b""
        response.headers = {"Location": "http://127.0.0.1:8765/callback?code=test-code&state=wrong"}
        with patch.object(browser.opener, "open", return_value=response):
            with self.assertRaisesRegex(LabError, "state mismatch"):
                browser.request("http://127.0.0.1:8080/test")


if __name__ == "__main__":
    unittest.main()

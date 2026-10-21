"""Opt-in Keycloak login-form, PKCE, TOTP, and offboarding protocol checks.

This is an HTTP protocol harness, not a production OIDC relying party.
Secrets, HTML, authorization codes and tokens stay in memory.
"""
import argparse
import base64
import hashlib
import hmac
import http.cookiejar
import json
import os
import secrets
import struct
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from sandbox.keycloak_lifecycle import Client, LabError, NoRedirect, execute, user_lookup, verify
from sandbox.evidence import evidence_run

BASE = "http://127.0.0.1:8080"
REALM = "portfolio-lab"
CLIENT = "portfolio-demo"
CALLBACK = "http://127.0.0.1:8765/callback"
OIDC = "/realms/" + REALM + "/protocol/openid-connect"


def totp(secret, offset=0):
    normalized = secret.replace(" ", "").upper()
    key = base64.b32decode(normalized + "=" * (-len(normalized) % 8))
    digest = hmac.new(key, struct.pack(">Q", int(time.time()) // 30 + offset), hashlib.sha1).digest()
    index = digest[-1] & 15
    value = struct.unpack(">I", digest[index:index + 4])[0] & 0x7fffffff
    return str(value % 1000000).zfill(6)


class Forms(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.forms = []
        self.current = None
        self.visible_otp = ""
        self.manual_url = None
        self.capture_otp = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("id") == "mode-manual":
            self.manual_url = attrs.get("href")
        if attrs.get("id") == "kc-totp-secret-key":
            self.capture_otp = True
        if tag == "form":
            self.current = {"action": attrs.get("action"), "inputs": {}}
            self.forms.append(self.current)
        if tag == "input" and self.current is not None and attrs.get("name"):
            # Submit only explicit button selections; preserve hidden CSRF fields.
            if attrs.get("type") not in ("submit", "button", "checkbox"):
                self.current["inputs"][attrs["name"]] = attrs.get("value", "")

    def handle_data(self, data):
        if self.capture_otp:
            self.visible_otp += data

    def handle_endtag(self, tag):
        if tag == "span":
            self.capture_otp = False
        if tag == "form":
            self.current = None


class LoopbackCookiePolicy(http.cookiejar.DefaultCookiePolicy):
    """Treat only the fixed local HTTP fixture as a secure cookie destination.

    Keycloak emits Secure cookies even for this loopback development origin.
    The harness is not a general browser; every request is separately restricted
    to BASE. Never use this policy for a remote service or production client.
    """
    def return_ok_secure(self, cookie, request):
        if urlsplit(request.get_full_url()).hostname == "127.0.0.1":
            return True
        return super().return_ok_secure(cookie, request)


class Browser:
    def __init__(self, client_secret):
        self.client_secret = client_secret
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(
            http.cookiejar.CookieJar(policy=LoopbackCookiePolicy())), NoRedirect())
        self.verifier = secrets.token_urlsafe(48)
        self.state = secrets.token_urlsafe(24)
        self.otp_secret = None

    def request(self, url, values=None):
        verify(urlsplit(url).scheme + "://" + urlsplit(url).netloc == BASE,
               "Unexpected form destination")
        data = urlencode(values).encode() if values is not None else None
        req = Request(url, data, method="POST" if data is not None else "GET")
        try:
            response = self.opener.open(req, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.code
            text = response.read().decode("utf-8")
            location = response.headers.get("Location")
        if location and status in (302, 303):
            if location.startswith(CALLBACK + "?"):
                params = parse_qs(urlsplit(location).query)
                verify(params.get("state") == [self.state], "OAuth state mismatch")
                verify("code" in params, "Authorization did not return a code")
                return {"code": params["code"][0]}
            verify(location.startswith(BASE + "/"), "Unexpected authentication redirect")
            return self.request(location)
        verify(status == 200, "Authentication endpoint HTTP " + str(status) + "; cookie_missing=" + str("Cookie not found" in text) + "; invalid_code=" + str("Invalid code" in text) + "; expired=" + str("expired" in text.lower()))
        return {"html": text}

    def submit(self, page, field, values):
        matches = [form for form in Forms(page["html"]).forms if field in form["inputs"]]
        verify(len(matches) == 1, "Expected authentication form: " + field)
        form = matches[0]
        return self.request(form["action"], dict(form["inputs"], **values))

    def start(self):
        challenge = base64.urlsafe_b64encode(hashlib.sha256(
            self.verifier.encode()).digest()).decode().rstrip("=")
        return self.request(BASE + OIDC + "/auth?" + urlencode({
            "client_id": CLIENT, "response_type": "code", "scope": "openid",
            "redirect_uri": CALLBACK, "state": self.state,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "prompt": "login"}))

    def password(self, username, password):
        return self.submit(self.start(), "username", {"username": username, "password": password})

    def enroll(self, page):
        parsed = Forms(page["html"])
        if parsed.manual_url:
            page = self.request(parsed.manual_url)
            parsed = Forms(page["html"])
        forms = parsed.forms
        matches = [form for form in forms if "totpSecret" in form["inputs"]]
        verify(len(matches) == 1, "TOTP enrollment form not found")
        self.otp_secret = parsed.visible_otp.strip()
        verify(bool(self.otp_secret), "Visible enrollment seed missing")
        self.enrollment_counter = int(time.time()) // 30
        return self.submit(page, "totpSecret", {"totp": totp(self.otp_secret),
                                              "userLabel": "Disposable lab test"})

    def exchange(self, page):
        verify("code" in page, "Sign-in did not complete")
        transport = Client(BASE, "unused-for-public-client")
        return transport.request("POST", OIDC + "/token", {
            "grant_type": "authorization_code", "client_id": CLIENT,
            "client_secret": self.client_secret,
            "redirect_uri": CALLBACK, "code": page["code"],
            "code_verifier": self.verifier}, form=True)


def run(report_path):
    checks = []
    report = {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
              "keycloak_image": "quay.io/keycloak/keycloak:26.8.1",
              "checks": checks,
              "limits": ["HTTP form automation; no visual browser walkthrough",
                         "Not a production OIDC application; ID tokens are not consumed",
                         "No offline JWT-validation or downstream application session test",
                         "TOTP seed is held by the harness, not an independently held second factor",
                         "No SAML or SCIM integration", "Owner review pending"]}
    with evidence_run(report_path, report):
        secret = os.environ.get("LAB_CLIENT_SECRET", "")
        admin_password = os.environ.get("LAB_ADMIN_PASSWORD", "")
        verify(bool(admin_password), "Run Start-KeycloakSandbox.ps1 in this terminal first")
        service = Client(BASE, secret)
        service.login()
        username = "lab-auth-" + secrets.token_hex(5)
        password = secrets.token_urlsafe(32)
        demo_secret = secrets.token_urlsafe(32)
        audit = Path("output/keycloak-auth-audit.jsonl")

        def mark(name, **evidence):
            checks.append({"check": name, "result": "passed", **evidence})
            print(name + ": passed", flush=True)

        def introspect(token):
            response = Client(BASE, secret).request("POST", OIDC + "/token/introspect", {
                "client_id": CLIENT, "client_secret": demo_secret, "token": token}, form=True)
            return response.get("active") is True

        try:
            # Bootstrap client configuration only inside the fixed local lab realm.
            fixture = Client(BASE, secret)
            fixture.token = fixture.request("POST", "/realms/master/protocol/openid-connect/token", {
                "grant_type": "password", "client_id": "admin-cli",
                "username": "lab-admin", "password": admin_password}, form=True)["access_token"]
            configuration = {"clientId": CLIENT, "enabled": True, "protocol": "openid-connect",
                             "publicClient": False, "secret": demo_secret, "standardFlowEnabled": True,
                             "directAccessGrantsEnabled": False,
                             "redirectUris": [CALLBACK],
                             "attributes": {"pkce.code.challenge.method": "S256"},
                             "fullScopeAllowed": False,
                             "protocolMappers": [{
                                 "name": "demo-audience", "protocol": "openid-connect",
                                 "protocolMapper": "oidc-audience-mapper",
                                 "config": {"included.client.audience": CLIENT,
                                            "access.token.claim": "true",
                                            "introspection.token.claim": "true",
                                            "id.token.claim": "false"}}]}
            clients = fixture.api("GET", "/clients?" + urlencode({"clientId": CLIENT}))
            if not clients:
                fixture.api("POST", "/clients", configuration)
            else:
                verify(len(clients) == 1, "Ambiguous demo client")
                fixture.api("PUT", "/clients/" + clients[0]["id"], configuration)

            execute(service, "joiner", username, "AUTH-JOIN", audit)
            user = user_lookup(service, username)
            uid = user["id"]
            service.api("PUT", "/users/" + uid, {
                "firstName": "Avery", "lastName": "Lab", "emailVerified": True,
                "requiredActions": ["CONFIGURE_TOTP"]})
            service.api("PUT", "/users/" + uid + "/reset-password",
                        {"type": "password", "value": password, "temporary": False})

            first = Browser(demo_secret)
            challenge = first.password(username, password)
            verify("code" not in challenge, "MFA enrollment was bypassed")
            completed = first.enroll(challenge)
            first_tokens = first.exchange(completed)
            credentials = service.api("GET", "/users/" + uid + "/credentials")
            verify(any(item.get("type") == "otp" for item in credentials),
                   "Enrolled OTP credential missing")
            mark("totp_enrollment_required_and_persisted")

            bad = Browser(demo_secret)
            challenge = bad.password(username, password)
            verify("code" not in challenge, "Password bypassed configured MFA")
            mark("password_alone_not_sufficient")
            rejected_code = "000000"
            while rejected_code in {totp(first.otp_secret, offset) for offset in range(-1, 2)}:
                rejected_code = str((int(rejected_code) + 1) % 1000000).zfill(6)
            rejected = bad.submit(challenge, "otp", {"otp": rejected_code})
            verify("code" not in rejected and any(
                "otp" in form["inputs"] for form in Forms(rejected["html"]).forms),
                "Invalid OTP was not rejected")
            mark("invalid_totp_rejected")

            good = Browser(demo_secret)
            challenge = good.password(username, password)
            # Keycloak rejects OTP reuse; wait for a fresh code after enrollment.
            while int(time.time()) // 30 <= first.enrollment_counter:
                time.sleep(0.25)
            completed = good.submit(challenge, "otp", {"otp": totp(first.otp_secret)})
            tokens = good.exchange(completed)
            bearer = Client(BASE, "unused")
            bearer.token = tokens["access_token"]
            claims = bearer.request("GET", OIDC + "/userinfo")
            verify(claims["sub"] == uid, "UserInfo did not identify the fixture user")
            verify(introspect(tokens["access_token"]), "Access token not active before offboarding")
            sessions = service.api("GET", "/users/" + uid + "/sessions")
            verify(len(sessions) >= 1, "No active session before offboarding")
            mark("pkce_code_flow_and_userinfo", active_sessions_before=len(sessions))
            mark("access_token_active_before_offboarding")

            execute(Client(BASE, secret), "leaver", username, "AUTH-LEAVER", audit)
            verify(service.api("GET", "/users/" + uid + "/sessions") == [],
                   "Active user session survived offboarding")
            mark("active_sessions_removed")

            try:
                Client(BASE, "unused").request("POST", OIDC + "/token", {
                    "grant_type": "refresh_token", "client_id": CLIENT,
                    "client_secret": demo_secret,
                    "refresh_token": tokens["refresh_token"]}, form=True)
            except LabError as exc:
                verify(str(exc) == "API HTTP 400", "Unexpected refresh failure")
            else:
                raise LabError("Refresh token worked after offboarding")
            mark("refresh_token_rejected_after_offboarding")

            verify(not introspect(tokens["access_token"]),
                   "Introspection still reports old token active")
            mark("old_access_token_inactive_at_introspection")
            try:
                bearer.request("GET", OIDC + "/userinfo")
            except LabError as exc:
                verify(str(exc) in ("API HTTP 401", "API HTTP 403"), "Unexpected UserInfo failure")
            else:
                raise LabError("UserInfo accepted old token after offboarding")
            mark("old_access_token_rejected_at_userinfo")

            disabled = Browser(demo_secret).password(username, password)
            verify("code" not in disabled and "input-error" in disabled.get("html", ""),
                   "Disabled account did not produce sign-in rejection")
            mark("fresh_password_signin_denied_after_offboarding")
            report["status"] = "passed"
        except Exception as exc:
            report["status"] = "failed"
            report["failure_type"] = type(exc).__name__
            raise
        finally:
            original_failure = sys.exc_info()[0] is not None
            try:
                if user_lookup(service, username):
                    execute(Client(BASE, secret), "leaver", username, "AUTH-CLEANUP", audit)
                report["cleanup"] = "complete"
            except Exception as cleanup_error:
                report["cleanup"] = "incomplete"
                report["cleanup_failure_type"] = type(cleanup_error).__name__
                if not original_failure:
                    raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true")
    parser.add_argument("--report", default="output/verification/keycloak-auth-results.json")
    args = parser.parse_args()
    if not args.run_live:
        parser.error("--run-live is required")
    run(args.report)


if __name__ == "__main__":
    main()

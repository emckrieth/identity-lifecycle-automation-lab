"""Local Keycloak lifecycle lab. No third-party Python dependencies."""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

REALM = "portfolio-lab"


class LabError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base_url, secret):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or parsed.username or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment):
            raise LabError("Only http://127.0.0.1:<port> is allowed")
        if not secret:
            raise LabError("Set LAB_CLIENT_SECRET locally")
        self.base = base_url.rstrip("/")
        self.secret = secret
        self.token = None
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, data=None, form=False):
        headers = {}
        body = None
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if data is not None:
            body = (urlencode(data) if form else json.dumps(data)).encode()
            headers["Content-Type"] = ("application/x-www-form-urlencoded"
                                       if form else "application/json")
        try:
            req = Request(self.base + path, body, headers, method=method)
            with self.opener.open(req, timeout=10) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            # Never log server bodies: they may contain credentials or user data.
            raise LabError("API HTTP " + str(exc.code)) from None
        except (URLError, TimeoutError, OSError):
            raise LabError("API unavailable; check sandbox service") from None
        except (ValueError, UnicodeError):
            raise LabError("Invalid API response") from None

    def login(self):
        result = self.request("POST", "/realms/" + REALM + "/protocol/openid-connect/token",
                              {"grant_type": "client_credentials",
                               "client_id": "lifecycle-runner",
                               "client_secret": self.secret}, form=True)
        if not isinstance(result, dict) or not result.get("access_token"):
            raise LabError("Missing service access token")
        self.token = result["access_token"]

    def api(self, method, path, data=None):
        return self.request(method, "/admin/realms/" + REALM + path, data)


def user_lookup(client, username):
    users = client.api("GET", "/users?" + urlencode(
        {"username": username, "exact": "true", "max": 2}))
    if not isinstance(users, list) or len(users) > 1:
        raise LabError("Ambiguous identity lookup")
    if users and users[0].get("username") != username:
        raise LabError("Identity lookup mismatch")
    return users[0] if users else None


def verify(condition, message):
    if not condition:
        raise LabError(message)


def lifecycle(client, action, username, record):
    if not re.fullmatch(r"lab-[a-z0-9][a-z0-9-]{0,39}", username):
        raise LabError("Only fictional lab- usernames are allowed")
    user = user_lookup(client, username)
    record("lookup", "complete")
    if action == "joiner":
        # Resolve the group before creating the account.
        groups = client.api("GET", "/groups?" + urlencode(
            {"search": "lab-support", "exact": "true", "max": 2}))
        groups = [g for g in groups if g.get("path") == "/lab-support"]
        verify(len(groups) == 1, "Expected exactly one /lab-support group")
        group = groups[0]
        if user is None:
            client.api("POST", "/users", {"username": username, "enabled": True,
                                         "email": username + "@example.invalid"})
            record("create", "complete")
            user = user_lookup(client, username)
            verify(user is not None, "Created user not found")
        else:
            verify(user.get("enabled") is True,
                   "Existing disabled identity requires a separate rehire review")
            record("create", "already_present")
        uid = quote(user["id"], safe="")
        gid = quote(group["id"], safe="")
        client.api("PUT", "/users/" + uid + "/groups/" + gid)
        record("assign_group", "complete")
        state = client.api("GET", "/users/" + uid)
        memberships = client.api("GET", "/users/" + uid + "/groups?max=1000")
        verify(state.get("enabled") is True and any(
            g["id"] == group["id"] for g in memberships), "Joiner read-back failed")
        record("verify_enabled_and_group", "complete")
    else:
        verify(user is not None, "Unknown identity; offboarding remains incomplete")
        uid = quote(user["id"], safe="")
        client.api("PUT", "/users/" + uid, {"enabled": False})
        record("disable", "complete")
        client.api("POST", "/users/" + uid + "/logout")
        record("end_sessions", "complete")
        groups = client.api("GET", "/users/" + uid + "/groups?max=1000")
        # Do not silently close a ticket if group enumeration may be truncated.
        verify(len(groups) < 1000, "Group enumeration limit reached")
        for group in groups:
            client.api("DELETE", "/users/" + uid + "/groups/" + quote(group["id"], safe=""))
        record("remove_groups", "complete")
        state = client.api("GET", "/users/" + uid)
        memberships = client.api("GET", "/users/" + uid + "/groups?max=1000")
        sessions = client.api("GET", "/users/" + uid + "/sessions")
        verify(state.get("enabled") is False and memberships == [] and sessions == [],
               "Offboarding read-back failed")
        record("verify_disabled_groups_sessions", "complete")
    return {"status": "admin_state_verified",
            "interactive_access_test": "not_performed",
            "downstream_access_revocation": "not_verified"}


def execute(client, action, username, ticket, audit_path):
    if not ticket.strip():
        raise LabError("A ticket reference is required")
    audit_path = Path(audit_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        def record(step, outcome):
            handle.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticket": ticket, "action": action, "username": username,
                "step": step, "outcome": outcome}) + "\n")
            handle.flush()
        record("workflow", "started")
        try:
            client.login()
            record("authenticate", "complete")
            result = lifecycle(client, action, username, record)
            record("workflow", "admin_state_verified")
            return result
        except Exception:
            record("workflow", "incomplete")
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["joiner", "leaver"])
    parser.add_argument("--username", required=True)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--audit", default="output/keycloak-audit.jsonl")
    args = parser.parse_args()
    try:
        client = Client(args.url, os.environ.get("LAB_CLIENT_SECRET", ""))
        print(json.dumps(execute(client, args.action, args.username, args.ticket, args.audit),
                         indent=2))
        return 0
    except LabError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Signed Slack slash-command intake. Queue only: no automatic provisioning."""
import argparse
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from sandbox.asset_workflow import Queue
from sandbox.keycloak_lifecycle import LabError, verify


def accept(body, headers, secret, teams, queue, now=None):
    verify(bool(secret) and bool(teams), "Slack signing secret and team allowlist required")
    lowered = {key.lower(): value for key, value in headers.items()}
    timestamp = lowered.get("x-slack-request-timestamp", "")
    try:
        age = abs((time.time() if now is None else now) - int(timestamp))
    except ValueError:
        raise LabError("Invalid Slack timestamp") from None
    verify(age <= 300, "Expired Slack request")
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    verify(hmac.compare_digest(expected, lowered.get("x-slack-signature", "")),
           "Invalid Slack signature")
    try:
        values = parse_qs(body.decode("utf-8"), strict_parsing=True)
        def one(key):
            verify(len(values.get(key, [])) == 1, "Missing or duplicate Slack field")
            return values[key][0]
        team, actor, trigger = one("team_id"), one("user_id"), one("trigger_id")
        verify(team in teams, "Slack team is not allowed")
        action = {"/lab-onboard": "joiner", "/lab-offboard": "leaver"}.get(one("command"))
        verify(action is not None, "Unsupported Slack command")
        parts = one("text").split()
        verify(len(parts) == 2, "Use: lab-username LAB-ASSET")
        ticket = "SLK-" + hashlib.sha256((team + ":" + actor + ":" + trigger).encode()).hexdigest()[:24]
        result = queue.submit(ticket, action, parts[0], parts[1], team + ":" + actor)
        return {"response_type": "ephemeral", "text": result["id"] + ": " + result["status"]}
    except (ValueError, UnicodeError):
        raise LabError("Malformed Slack command") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8095)
    args = parser.parse_args()
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    teams = set(filter(None, os.environ.get("SLACK_TEAM_IDS", "").split(",")))
    verify(bool(secret) and bool(teams), "Configure local Slack credentials before starting")
    queue = Queue()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != "/slack/commands":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                verify(0 < length <= 8192, "Invalid request size")
                result = accept(self.rfile.read(length), dict(self.headers), secret, teams, queue)
                payload = json.dumps(result).encode()
                self.send_response(200)
            except (LabError, ValueError):
                payload = b'{"error":"request rejected"}'
                self.send_response(403)
            except Exception:
                payload = b'{"error":"queue unavailable; retry later"}'
                self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    print("Slack intake listening on loopback port " + str(args.port), flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

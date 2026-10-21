"""Run opt-in checks against the local Keycloak lab, including a service outage."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sandbox.keycloak_lifecycle import Client, LabError, execute, user_lookup, verify


def run_live(docker, report_path):
    repo = Path(__file__).resolve().parent.parent
    report_path = Path(report_path)
    audit = repo / "output" / "keycloak-live-audit.jsonl"
    username = "lab-live-" + uuid4().hex[:10]
    secret = os.environ.get("LAB_CLIENT_SECRET", "")
    base = "http://127.0.0.1:8080"
    checks = []
    report = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"keycloak_image": "quay.io/keycloak/keycloak:26.8.1",
                        "python": sys.version.split()[0], "realm": "portfolio-lab",
                        "endpoint": base},
        "username": username,
        "checks": checks,
        "limits": [
            "No interactive end-user sign-in or MFA test",
            "No active end-user session was created; zero-session state only",
            "No downstream application, offline-session, or access-token revocation test",
            "No SCIM or SAML integration in this increment",
            "Owner personal review is pending"
        ]
    }
    compose = [docker, "compose", "--project-name", "portfolio-identity-lab",
               "--env-file", str(repo / "sandbox" / ".env"),
               "-f", str(repo / "sandbox" / "compose.yaml")]

    def command(*args):
        result = subprocess.run(compose + list(args), cwd=repo, capture_output=True,
                                text=True, timeout=60)
        verify(result.returncode == 0, "Docker operation failed: " + args[0])

    def client():
        return Client(base, secret)

    def ready():
        deadline = time.monotonic() + 60
        while True:
            try:
                probe = client()
                probe.login()
                return probe
            except LabError:
                if time.monotonic() >= deadline:
                    raise LabError("Service did not become ready within 60 seconds") from None
                time.sleep(1)

    def mark(name, **evidence):
        checks.append({"check": name, "result": "passed", **evidence})
        print(name + ": passed", flush=True)

    def flow(action, ticket):
        return execute(client(), action, username, ticket, audit)

    try:
        probe = ready()
        flow("joiner", "LIVE-JOIN")
        original = user_lookup(probe, username)
        verify(original and original["enabled"] is True, "First joiner state invalid")
        mark("provision", enabled=True)

        flow("joiner", "LIVE-JOIN-RETRY")
        probe = ready()
        repeated = user_lookup(probe, username)
        groups = probe.api("GET", "/users/" + repeated["id"] + "/groups?max=1000")
        verify(original["id"] == repeated["id"] and len(groups) == 1
               and groups[0]["path"] == "/lab-support", "Duplicate joiner changed identity")
        mark("duplicate_joiner", same_identity=True, group_count=len(groups))

        bad = Client(base, "intentionally-invalid-lab-secret")
        try:
            execute(bad, "leaver", username, "LIVE-BAD-CREDENTIAL", audit)
        except LabError as exc:
            verify(str(exc).startswith("API HTTP 40"), "Unexpected credential failure")
        else:
            raise LabError("Invalid credential was accepted")
        verify(user_lookup(probe, username)["enabled"] is True,
               "Denied request changed account")
        mark("invalid_credentials", account_unchanged=True)

        # This affects only the named lab project's Keycloak service.
        try:
            command("stop", "keycloak")
            try:
                flow("leaver", "LIVE-OUTAGE")
            except LabError as exc:
                verify(str(exc).startswith("API unavailable"), "Unexpected outage failure")
            else:
                raise LabError("Stopped service unexpectedly accepted the request")
            last = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
            verify(last["ticket"] == "LIVE-OUTAGE" and last["outcome"] == "incomplete",
                   "Outage was not recorded as incomplete")
            mark("service_outage", outcome="incomplete")
        finally:
            command("start", "keycloak")

        probe = ready()
        result = flow("leaver", "LIVE-OUTAGE")
        state = user_lookup(probe, username)
        memberships = probe.api("GET", "/users/" + state["id"] + "/groups?max=1000")
        sessions = probe.api("GET", "/users/" + state["id"] + "/sessions")
        verify(state["enabled"] is False and memberships == [] and sessions == [],
               "Recovery verification failed")
        mark("restart_and_retry", enabled=False, groups=0, returned_user_sessions=0,
             verification=result["status"])

        flow("leaver", "LIVE-LEAVER-RETRY")
        mark("duplicate_leaver")

        try:
            flow("joiner", "LIVE-REHIRE")
        except LabError as exc:
            verify("rehire" in str(exc), "Unexpected rehire failure")
        else:
            raise LabError("Joiner silently reactivated offboarded identity")
        verify(user_lookup(probe, username)["enabled"] is False, "Rehire changed state")
        mark("implicit_rehire_denied", enabled=False)
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["failure_type"] = type(exc).__name__
        # Keep potentially sensitive exception details out of the public report.
        raise
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true",
                        help="Explicitly allow test identities and lab service stop/start")
    parser.add_argument("--docker", required=True)
    parser.add_argument("--report", default="examples/keycloak-live-results.json")
    args = parser.parse_args()
    if not args.run_live:
        parser.error("--run-live is required; this modifies the local lab")
    run_live(args.docker, args.report)


if __name__ == "__main__":
    main()

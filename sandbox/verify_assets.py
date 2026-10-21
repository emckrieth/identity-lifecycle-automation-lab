"""Opt-in real Keycloak/Snipe-IT workflow verification; Slack ingress uses a signed fixture."""
import argparse
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from urllib.parse import urlencode

from sandbox.asset_workflow import Queue, identity
from sandbox.assets_api import Assets
from sandbox.evidence import evidence_run
from sandbox.keycloak_lifecycle import Client, LabError, user_lookup, verify
from sandbox.slack_intake import accept
import os


def run(report_path):
    report = {"checks": [], "limits": [
        "Slack request is signed locally; no live Slack workspace/app installation",
        "Asset physical receipt is an operator assertion, not proof of shipment",
        "No MDM enrollment, Google Workspace, SCIM or SAML in this increment",
        "Owner walkthrough pending"]}
    with evidence_run(report_path, report):
        assets = Assets()
        suffix = secrets.token_hex(4)
        username, tag = "lab-assets-" + suffix, "LAB-" + suffix.upper()
        queue = Queue("output/asset-demo.sqlite3")
        approvers = {"lab-reviewer"}
        def mark(name, **evidence):
            report["checks"].append({"check": name, "result": "passed", **evidence})
            print(name + ": passed", flush=True)
        def ensure(collection, name, values):
            rows = assets.api("GET", "/" + collection + "?" + urlencode({"search": name, "limit": 100}))["rows"]
            exact = [row for row in rows if row["name"] == name]
            verify(len(exact) <= 1, "Ambiguous asset fixture")
            return exact[0]["id"] if exact else assets.api("POST", "/" + collection,
                                                         dict(values, name=name))["payload"]["id"]
        category = ensure("categories", "Portfolio Lab Devices", {"category_type": "asset"})
        model = ensure("models", "Portfolio Lab Laptop", {"category_id": category})
        status = ensure("statuslabels", "Portfolio Ready", {"type": "deployable"})
        password = secrets.token_urlsafe(32)
        assets.api("POST", "/users", {"first_name": "Avery", "last_name": "Lab",
                   "username": username, "email": username + "@example.invalid",
                   "password": password, "password_confirmation": password, "activated": True})
        assets.api("POST", "/hardware", {"asset_tag": tag, "name": "Fictional lab laptop",
                   "model_id": model, "status_id": status})
        mark("real_snipeit_fixtures_created", username=username, asset_tag=tag)

        body = urlencode({"team_id": "T_FIXTURE", "user_id": "U_REQUESTER",
                          "trigger_id": suffix, "command": "/lab-onboard",
                          "text": username + " " + tag}).encode()
        timestamp = "1000"
        signature = "v0=" + hmac.new(b"local-fixture-secret", b"v0:1000:" + body, hashlib.sha256).hexdigest()
        headers = {"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": signature}
        response = accept(body, headers, "local-fixture-secret", {"T_FIXTURE"}, queue, now=1000)
        ticket = response["text"].split(":")[0]
        accept(body, headers, "local-fixture-secret", {"T_FIXTURE"}, queue, now=1000)
        verify(queue.get(ticket)["status"] == "pending_approval", "Intake unexpectedly provisioned")
        probe = Client("http://127.0.0.1:8080", os.environ.get("LAB_CLIENT_SECRET", ""))
        probe.login()
        verify(user_lookup(probe, username) is None, "Identity created before approval")
        mark("signed_slack_fixture_queues_once_without_provisioning", ticket=ticket)

        try:
            queue.approve(ticket, "not-authorized", approvers)
        except LabError:
            pass
        else:
            raise LabError("Unauthorized approval accepted")
        mark("unauthorized_approval_rejected")
        queue.approve(ticket, "lab-reviewer", approvers)
        result = queue.process(ticket, assets, identity)
        verify(result["status"] == "complete", "Joiner did not complete")
        uid = user_lookup(probe, username)["id"]
        verify(assets.asset(tag)["assigned_to"]["id"] == assets.user(username)["id"],
               "Assignment not reflected in real Snipe-IT")
        mark("approved_joiner_verified_in_both_services")

        # Inject an asset-stage failure after the real identity step.
        retry_ticket = "RETRY-" + suffix
        queue.submit(retry_ticket, "joiner", username, tag, "lab-requester")
        queue.approve(retry_ticket, "lab-reviewer", approvers)
        class FailingAssets:
            user = assets.user
            asset = assets.asset
            def assign(self, *args):
                raise LabError("Injected asset-stage failure")
        try:
            queue.process(retry_ticket, FailingAssets(), identity)
        except LabError:
            pass
        else:
            raise LabError("Failure injection did not fail")
        verify(queue.get(retry_ticket)["status"] == "incomplete", "Partial failure not persisted")
        mark("partial_failure_remains_incomplete", fault="injected at asset stage")
        queue.process(retry_ticket, assets, identity)
        verify(user_lookup(probe, username)["id"] == uid, "Retry duplicated identity")
        mark("retry_reuses_identity_and_existing_assignment")

        leaver = "LEAVER-" + suffix
        queue.submit(leaver, "leaver", username, tag, "lab-requester")
        queue.approve(leaver, "lab-reviewer", approvers)
        result = queue.process(leaver, assets, identity)
        verify(result["status"] == "awaiting_return", "Leaver closed before physical receipt")
        verify(user_lookup(probe, username)["enabled"] is False, "Identity not disabled")
        verify(assets.asset(tag).get("assigned_to") is not None, "Asset silently checked in")
        mark("leaver_disables_access_but_awaits_asset_return")
        result = queue.receive(leaver, "lab-reviewer", approvers, assets)
        verify(result["status"] == "complete" and assets.asset(tag).get("assigned_to") is None,
               "Physical receipt did not verify check-in")
        mark("operator_receipt_verifies_checkin_and_closes_ticket")
        report["status"] = "passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true")
    parser.add_argument("--report", default="output/verification/asset-workflow-results.json")
    args = parser.parse_args()
    if not args.run_live:
        parser.error("--run-live required")
    run(args.report)


if __name__ == "__main__":
    main()

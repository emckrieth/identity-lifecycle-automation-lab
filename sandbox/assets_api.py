"""Snipe-IT client restricted to the loopback portfolio sandbox."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, build_opener

from sandbox.keycloak_lifecycle import LabError, NoRedirect, verify

BASE = "http://127.0.0.1:8090/api/v1"


class Assets:
    def __init__(self, token=None):
        if token is None:
            path = Path(__file__).resolve().parent / "assets/.env"
            values = dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
            token = values.get("SNIPEIT_TOKEN", "")
        verify(bool(token), "Start the Snipe-IT sandbox first")
        self.token = token
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def api(self, method, path, values=None):
        verify(path.startswith("/") and not path.startswith("//"), "Invalid Snipe-IT resource")
        body = json.dumps(values).encode() if values is not None else None
        request = Request(BASE + path, body,
                          {"Authorization": "Bearer " + self.token,
                           "Accept": "application/json", "Content-Type": "application/json"},
                          method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                result = json.load(response)
        except HTTPError as error:
            raise LabError("Snipe-IT HTTP " + str(error.code)) from None
        except (URLError, OSError, ValueError):
            raise LabError("Snipe-IT unavailable or invalid response") from None
        # Snipe-IT can return a logical failure with HTTP 200.
        if result.get("status") == "error":
            raise LabError("Snipe-IT rejected the operation")
        return result

    def user(self, username):
        verify(username.startswith("lab-"), "Only lab identities are permitted")
        result = self.api("GET", "/users?" + urlencode({"search": username, "limit": 100}))
        rows = [row for row in result["rows"] if row["username"] == username]
        verify(len(rows) == 1, "Expected exactly one Snipe-IT lab identity")
        return rows[0]

    def asset(self, tag):
        verify(tag.startswith("LAB-"), "Only LAB- assets are permitted")
        result = self.api("GET", "/hardware?" + urlencode({"search": tag, "limit": 100}))
        rows = [row for row in result["rows"] if row["asset_tag"] == tag]
        verify(len(rows) == 1, "Expected exactly one lab asset")
        return self.api("GET", "/hardware/" + str(rows[0]["id"]))

    def assign(self, tag, username, ticket):
        user = self.user(username)
        asset = self.asset(tag)
        assigned = asset.get("assigned_to")
        if assigned:
            verify(assigned.get("type") == "user" and assigned["id"] == user["id"],
                   "Asset already assigned to another owner; escalate")
        else:
            self.api("POST", "/hardware/" + str(asset["id"]) + "/checkout",
                     {"checkout_to_type": "user", "assigned_user": user["id"],
                      "note": "Portfolio lab ticket " + ticket})
        after = self.asset(tag)
        owner = after.get("assigned_to") or {}
        verify(owner.get("type") == "user" and owner.get("id") == user["id"],
               "Asset assignment verification failed")
        return {"asset_tag": tag, "assigned_to": username, "verified": True}

    def confirm_return(self, tag, username, ticket):
        asset = self.asset(tag)
        user = self.user(username)
        assigned = asset.get("assigned_to")
        if assigned:
            verify(assigned.get("type") == "user" and assigned.get("id") == user["id"],
                   "Returned asset owner mismatch")
            self.api("POST", "/hardware/" + str(asset["id"]) + "/checkin",
                     {"note": "Physical receipt confirmed; lab ticket " + ticket})
        verify(self.asset(tag).get("assigned_to") is None, "Asset check-in verification failed")
        return {"asset_tag": tag, "assigned_to": None, "verified": True}

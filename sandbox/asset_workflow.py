"""Durable lab request queue with explicit approval and physical-return confirmation."""
import argparse
from contextlib import contextmanager
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sandbox.assets_api import Assets
from sandbox.keycloak_lifecycle import Client, LabError, execute, verify

DEFAULT_DB = "output/operations.sqlite3"


class Queue:
    def __init__(self, path=DEFAULT_DB):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests(
                id TEXT PRIMARY KEY, action TEXT, username TEXT, asset_tag TEXT,
                requester TEXT, approver TEXT, status TEXT, error_type TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY, request_id TEXT, timestamp TEXT, event TEXT)""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, ticket):
        with self.connect() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (ticket,)).fetchone()
            verify(row is not None, "Unknown request")
            return dict(row)

    def event(self, db, ticket, value):
        db.execute("INSERT INTO events(request_id,timestamp,event) VALUES(?,?,?)",
                   (ticket, datetime.now(timezone.utc).isoformat(), value))

    def submit(self, ticket, action, username, tag, requester):
        verify(bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", ticket)), "Invalid request ID")
        verify(action in ("joiner", "leaver"), "Invalid workflow")
        verify(bool(re.fullmatch(r"lab-[a-z0-9][a-z0-9-]{0,39}", username)), "Invalid lab identity")
        verify(bool(re.fullmatch(r"LAB-[A-Z0-9-]{1,40}", tag)), "Invalid lab asset tag")
        with self.connect() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (ticket,)).fetchone()
            if row:
                verify((row["action"], row["username"], row["asset_tag"], row["requester"]) ==
                       (action, username, tag, requester), "Request ID reused with different content")
            else:
                db.execute("INSERT INTO requests VALUES(?,?,?,?,?,NULL,'pending_approval',NULL)",
                           (ticket, action, username, tag, requester))
                self.event(db, ticket, "submitted")
        return self.get(ticket)

    def approve(self, ticket, actor, approvers):
        verify(actor in approvers, "Actor is not an authorized approver")
        with self.connect() as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (ticket,)).fetchone()
            verify(row is not None and row["status"] == "pending_approval", "Request is not awaiting approval")
            verify(actor != row["requester"], "Requester cannot approve own request")
            db.execute("UPDATE requests SET status='approved',approver=? WHERE id=?", (actor, ticket))
            self.event(db, ticket, "approved")
        return self.get(ticket)

    def process(self, ticket, assets, identity):
        # Persist a processing claim before network calls. A crashed worker requires
        # explicit operator review; there is no time-based automatic unlock.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM requests WHERE id=?", (ticket,)).fetchone()
            verify(row is not None, "Unknown request")
            if row["status"] in ("complete", "awaiting_return"):
                return dict(row)
            verify(row["status"] in ("approved", "incomplete") and row["approver"],
                   "Request must be approved and not already processing")
            db.execute("UPDATE requests SET status='processing',error_type=NULL WHERE id=?", (ticket,))
            self.event(db, ticket, "processing")
            row = dict(row)
        try:
            # Fail before provisioning if the requested asset or Snipe-IT user is missing.
            if row["action"] == "joiner":
                assets.user(row["username"])
                asset = assets.asset(row["asset_tag"])
                owner = asset.get("assigned_to")
                if owner:
                    verify(owner.get("id") == assets.user(row["username"])["id"],
                           "Asset assigned to another owner")
            identity(row["action"], row["username"], ticket)
            if row["action"] == "joiner":
                assets.assign(row["asset_tag"], row["username"], ticket)
                status = "complete"
            else:
                # Access removal never implies the physical laptop was received.
                status = "awaiting_return"
            with self.connect() as db:
                db.execute("UPDATE requests SET status=? WHERE id=?", (status, ticket))
                self.event(db, ticket, status)
        except Exception as error:
            with self.connect() as db:
                db.execute("UPDATE requests SET status='incomplete',error_type=? WHERE id=?",
                           (type(error).__name__, ticket))
                self.event(db, ticket, "incomplete")
            raise
        return self.get(ticket)

    def receive(self, ticket, actor, approvers, assets):
        verify(actor in approvers, "Actor is not authorized to confirm physical receipt")
        row = self.get(ticket)
        verify(row["action"] == "leaver" and row["status"] == "awaiting_return",
               "Request is not awaiting physical return")
        assets.confirm_return(row["asset_tag"], row["username"], ticket)
        with self.connect() as db:
            db.execute("UPDATE requests SET status='complete' WHERE id=?", (ticket,))
            self.event(db, ticket, "physical_return_confirmed:" + actor)
        return self.get(ticket)


def identity(action, username, ticket):
    client = Client("http://127.0.0.1:8080", os.environ.get("LAB_CLIENT_SECRET", ""))
    return execute(client, action, username, ticket, "output/keycloak-operations-audit.jsonl")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["submit", "approve", "process", "receive", "show"])
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--action", choices=["joiner", "leaver"])
    parser.add_argument("--username")
    parser.add_argument("--asset")
    parser.add_argument("--actor", default="lab-requester")
    args = parser.parse_args()
    queue = Queue()
    approvers = set(filter(None, os.environ.get("LAB_APPROVERS", "").split(",")))
    if args.command == "submit":
        result = queue.submit(args.ticket, args.action, args.username or "", args.asset or "", args.actor)
    elif args.command == "approve":
        result = queue.approve(args.ticket, args.actor, approvers)
    elif args.command == "process":
        result = queue.process(args.ticket, Assets(), identity)
    elif args.command == "receive":
        result = queue.receive(args.ticket, args.actor, approvers, Assets())
    else:
        result = queue.get(args.ticket)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

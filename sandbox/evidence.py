"""Atomic, run-scoped verification evidence; never retain a prior passing status."""
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + report["run_id"] + ".tmp")
    try:
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def evidence_run(path, report):
    report.update(status="running", run_id=uuid4().hex,
                  started_at_utc=datetime.now(timezone.utc).isoformat())
    if os.environ.get("GITHUB_SHA"):
        report["source_commit"] = os.environ["GITHUB_SHA"]
    save_report(path, report)
    try:
        yield report
    except BaseException as error:
        report.update(status="failed", failure_type=type(error).__name__)
        raise
    finally:
        if report["status"] == "running":
            report["status"] = "incomplete"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_report(path, report)

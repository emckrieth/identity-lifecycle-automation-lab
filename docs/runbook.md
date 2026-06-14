# Runbook

## Pre-Checks

1. Confirm the request is approved in the ITSM platform.
2. Confirm the request type: joiner, mover, leaver, or access review.
3. Validate the ticket ID, effective date, department, manager, and role.
4. Confirm that the role exists in `data/role_map.json`.
5. Confirm that the output folder exists.

## Joiner Procedure

```powershell
.\scripts\Invoke-Joiner.ps1 -InputPath .\data\new_hires.csv -TicketId REQ-1001
```

Validation:

- user is created in `data/users.json`
- role-based groups are assigned
- license is assigned
- MFA flag is set
- audit entries are written

## Mover Procedure

```powershell
.\scripts\Invoke-Mover.ps1 -InputPath .\data\movers.csv -TicketId CHG-2001
```

Validation:

- department, title, manager, and role are updated
- old role groups are removed
- new role groups are added
- access conflicts are flagged
- audit entries are written

## Leaver Procedure

```powershell
.\scripts\Invoke-Leaver.ps1 -InputPath .\data\leavers.csv -TicketId REQ-3001
```

Validation:

- account is disabled
- groups are removed
- privileged groups are explicitly recorded
- license is revoked
- mailbox handling note is recorded

## Access Review Procedure

```powershell
.\scripts\Invoke-AccessReview.ps1
```

Validation:

- report is generated at `output/access-review-report.csv`
- stale accounts are flagged
- missing MFA is flagged
- privileged access is flagged
- missing manager records are flagged

## Escalation Criteria

Escalate to Identity, Collaboration, Infrastructure, or Application teams when:

- role mapping is missing or unclear
- access conflicts are detected
- privileged access is requested without approval
- leaver access cannot be fully revoked
- report findings suggest recurring process failure

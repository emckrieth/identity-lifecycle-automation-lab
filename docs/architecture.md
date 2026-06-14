# Architecture Overview

## Purpose

This lab simulates identity lifecycle automation for an enterprise IT operations team. It is intentionally local and safe: CSV and JSON files stand in for HR input, Active Directory, Entra ID, Microsoft 365, Active Roles, and ITSM systems.

## Simulated Systems

| System | Local Simulation | Real-World Equivalent |
| --- | --- | --- |
| HR source | `data/new_hires.csv`, `data/movers.csv`, `data/leavers.csv` | HRIS or ITSM request payload |
| Identity directory | `data/users.json` | Active Directory or Entra ID |
| Role catalog | `data/role_map.json` | Active Roles policy, group catalog, access matrix |
| Audit trail | `output/audit-log.csv` | ITSM work notes, SIEM, audit platform |
| Access review | `output/access-review-report.csv` | Access review campaign, compliance report |

## Workflow Design

Each workflow follows the same operational pattern:

1. Read approved request input.
2. Validate user and role data.
3. Apply simulated identity changes.
4. Check for risk or access conflicts.
5. Write audit records with ticket IDs.
6. Generate output that can be reviewed by support or engineering teams.

## Control Points

- Every action includes a ticket ID.
- Unknown roles fail closed.
- Access conflicts are flagged instead of silently ignored.
- Leaver workflows remove privileged groups explicitly.
- Access review output is generated as a report that can be attached to an ITSM ticket.

## Future Integration Path

In a real environment, the same structure could be extended to call:

- Active Directory PowerShell cmdlets
- Microsoft Graph API
- Active Roles Server workflows
- ITSM platform APIs
- Monitoring or alerting tools
- Secure file transfer or document management provisioning APIs

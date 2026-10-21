# Identity Lifecycle Automation Lab

A PowerShell-based identity operations lab that simulates joiner, mover, and leaver workflows, entitlement changes, audit logging, and access review reporting for enterprise IT operations teams.

This project was designed to show identity and access management as an operational support function: controlled provisioning, exception handling, auditability, access review, and repeatable runbooks.


## Keycloak sandbox extension

A new Python workflow targets a real local Keycloak API for fictional-user provisioning and offboarding. Contract tests cover duplicate requests, partial failure, safe retry, and state verification. Seven live Keycloak checks passed, covering provisioning, duplicate requests, rejected credentials, service outage, and offboarding recovery. Ten additional HTTP protocol checks passed for PKCE sign-in, TOTP enforcement, active-session removal, and token denial at Keycloak. See [authentication verification](docs/keycloak-auth-verification.md). Production app federation and downstream/offline token validation remain separate milestones.

See the [live case study](docs/keycloak-case-study.md), [sanitized results](examples/keycloak-live-results.json), [sandbox setup and evidence](docs/keycloak-sandbox.md) and the [AI assistance and review record](docs/ai-development-review.md). The original PowerShell workflows below remain CSV/JSON simulations.

## Approved identity and asset operations

The lab now connects Keycloak and a local Snipe-IT instance through a durable request queue. Approval gates provisioning, retries preserve incomplete work, and offboarding remains open until an operator confirms physical asset return. Eight checks passed against the real services; Slack intake was tested with locally signed fixtures and is not live-connected.

See the [workflow case study and diagram](docs/approved-asset-workflow.md) and [archived observed results](examples/asset-workflow-results.json). Current verification runs write fresh, run-scoped reports under ignored output/verification; CI never uploads old committed examples as current evidence.
## What It Demonstrates

- PowerShell automation for identity lifecycle workflows
- Joiner, mover, and leaver operational processes
- Role-based group and entitlement assignment
- Microsoft 365-style license simulation
- MFA and privileged access review flags
- Audit logging for compliance and support traceability
- Exception handling for failed or risky provisioning requests
- ITSM-style ticket references in every workflow

## Why This Matters for IT Operations

Enterprise IT operations teams often support identity, SaaS access, email, file access, secure file transfer, two-factor authentication, and service request workflows. This lab mirrors those responsibilities in a safe local simulation.

The original PowerShell scripts do not connect to real Active Directory, Entra ID, Microsoft 365, or Active Roles. Instead, they use CSV and JSON data to demonstrate the logic, controls, and documentation an operations engineer would use before integrating with live systems.

## Quick Start

Run from the repository root in PowerShell:

```powershell
.\scripts\Invoke-Joiner.ps1 -InputPath .\data\new_hires.csv -TicketId INC-1001
.\scripts\Invoke-Mover.ps1 -InputPath .\data\movers.csv -TicketId CHG-2001
.\scripts\Invoke-Leaver.ps1 -InputPath .\data\leavers.csv -TicketId REQ-3001
.\scripts\Invoke-AccessReview.ps1
```

Generated files are written to `output/`.

## Project Structure

```text
identity-lifecycle-automation-lab/
|-- README.md
|-- data/
|   |-- leavers.csv
|   |-- movers.csv
|   |-- new_hires.csv
|   |-- role_map.json
|   `-- users.json
|-- docs/
|   |-- access-review-guide.md
|   |-- architecture.md
|   |-- controls-mapping.md
|   |-- incident-scenarios.md
|   |-- rollback-notes.md
|   `-- runbook.md
|-- examples/
|   `-- sample-results.md
|-- output/
|   |-- .gitkeep
|   |-- access-review-report.csv
|   `-- audit-log.csv
`-- scripts/
    |-- Common.ps1
    |-- Invoke-AccessReview.ps1
    |-- Invoke-Joiner.ps1
    |-- Invoke-Leaver.ps1
    `-- Invoke-Mover.ps1
```

## Workflow Summary

### Joiner

Creates a simulated identity record, assigns role-based groups, assigns a license profile, sets MFA status, and writes audit entries for each action.

### Mover

Updates department and role, removes old role groups, adds new role groups, updates entitlements, and flags access conflicts such as finance and HR access assigned together.

### Leaver

Disables the simulated account, removes privileged and application groups, revokes license assignments, records mailbox handling notes, and writes an auditable closure summary.

### Access Review

Generates a report for stale accounts, privileged group membership, orphaned manager records, missing MFA, disabled users with access, and conflicting entitlements.

## Role Alignment

This lab aligns with IT operations roles that require:

- identity and access management support
- PowerShell automation
- service request and incident handling
- ITSM documentation discipline
- operational runbooks
- monitoring and exception reporting
- compliance-minded access reviews
- cross-functional support between identity, collaboration, infrastructure, and application teams

## Controls and Risk Coverage

The repo includes examples that map to common IAM controls:

- joiner, mover, and leaver workflow traceability
- role-based access assignment
- disabled account review
- privileged group review
- stale access review detection
- missing MFA detection
- conflicting entitlement detection

See `docs/controls-mapping.md` for a support-focused view of these controls.

## Suggested GitHub Pin Description

PowerShell identity lifecycle automation lab for joiner/mover/leaver workflows, audit logging, access review, and enterprise IT operations support.

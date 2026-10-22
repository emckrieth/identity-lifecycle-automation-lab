# Live Slack identity and asset walkthrough

On October 22, 2026, the owner completed a guided walkthrough using a custom Slack app, local Keycloak and local Snipe-IT. The app receives real Slack requests through a temporary HTTPS tunnel; Slack intake only queues work. Approval and processing remain explicit local operator actions.

## Observed outcomes

| Operation | Observed transitions | Meaning |
| --- | --- | --- |
| Slack onboarding | pending_approval -> approved -> complete | Identity step completed and laptop assignment verified |
| Slack offboarding | pending_approval -> approved -> awaiting_return | Access step completed while receipt remained outstanding |
| Simulated receipt | awaiting_return -> complete | Snipe-IT check-in verified after local operator assertion |

[Sanitized evidence](../examples/slack-live-walkthrough.json) contains actual queue event timestamps and final API read-back. Original Slack IDs, ticket IDs, secrets and temporary hostnames are omitted. Intermediate historical API states are supported by the owner's CLI output and workflow execution, not an independent API snapshot at each transition. Final API read-back independently confirmed lab-avery disabled and LAB-DEMO unassigned.

## Setup and troubleshooting findings

- Slack rejected the original manifest because slash commands with bot scopes required a bot_user section. The template now includes it.
- An expired/unresolvable temporary tunnel hostname prevented delivery. Restarting a Quick Tunnel changes its hostname; both slash-command Request URLs must be updated.
- A reachable endpoint returning 403 to an unsigned probe confirms connectivity and rejection only; it does not establish successful Slack authentication.
- Fixed-message intake diagnostics identified Invalid Slack signature on a real request. Re-entering the correct app Signing Secret resolved it. Never substitute an OAuth token or Client Secret.
- A ticket ID assigned without quotation marks was interpreted as a PowerShell command. Ticket strings must be quoted.

## Repeat the walkthrough

Start Keycloak and Snipe-IT using [the setup guide](approved-asset-workflow.md#start-local-services). Keep the intake in one PowerShell window and use a second for operator commands. Before onboarding, create a fictional Snipe-IT user and available LAB- asset matching the command. The automated verifier creates separate fixtures; it does not prepare arbitrary manual names.

Configure the secret privately in the intake window:

```powershell
$privateSecret = Read-Host "Slack Signing Secret" -AsSecureString
$env:SLACK_SIGNING_SECRET = ([System.Net.NetworkCredential]::new("", $privateSecret).Password).Trim()
Remove-Variable privateSecret
$env:SLACK_TEAM_IDS = "YOUR_WORKSPACE_ID"
python -m sandbox.slack_intake
```

Start an installed cloudflared in another terminal:

```powershell
cloudflared tunnel --url http://127.0.0.1:8095 --no-autoupdate
```

Save its HTTPS URL plus /slack/commands as the Request URL for both slash commands. Keep the intake and tunnel running. Send in Slack:

```text
/lab-onboard lab-avery LAB-DEMO
```

Use the returned ticket in the operator window after loading Keycloak configuration with scripts/Start-KeycloakSandbox.ps1:

```powershell
$env:LAB_APPROVERS = "lab-reviewer"
$ticket = "SLK-REPLACE-WITH-ACTUAL-TICKET"
python -m sandbox.asset_workflow show --ticket $ticket
python -m sandbox.asset_workflow approve --ticket $ticket --actor lab-reviewer
python -m sandbox.asset_workflow process --ticket $ticket
```

Confirm complete. Send /lab-offboard lab-avery LAB-DEMO in Slack and repeat show, approve and process with its new ticket ID. Confirm awaiting_return before running:

```powershell
python -m sandbox.asset_workflow receive --ticket $ticket --actor lab-reviewer
python -m sandbox.asset_workflow show --ticket $ticket
```

Confirm complete. Reusing this identity for another onboarding after offboarding is intentionally refused; use fresh fictional fixtures for a new cycle.

## Evidence boundaries and AI assistance

The owner personally executed this guided workflow and resolved configuration errors. Codex implemented the integration, prepared fixtures, supplied commands and independently checked final local API state. This does not claim independent owner implementation or comprehensive code review. The approver is a local CLI role assertion, not a separately authenticated person. Receipt was simulated; no physical logistics occurred. CI still uses locally signed Slack fixtures. There is no production hosting, compliance certification or proof of all downstream SaaS access removal.

Sources: [Slack slash commands](https://docs.slack.dev/interactivity/implementing-slash-commands/), [Slack signature verification](https://docs.slack.dev/authentication/verifying-requests-from-slack/), [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

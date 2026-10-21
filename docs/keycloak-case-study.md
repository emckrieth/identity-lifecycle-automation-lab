# Case study: verifying an AI-assisted identity workflow

## Problem and scope

The original identity lab stores users in CSV/JSON and simulates operational controls. The next increment needed observable behavior against an identity provider: provision a user, retry without duplication, handle failure, and verify offboarding state.

This increment uses Keycloak 26.8.1 on Docker Desktop with a loopback-only endpoint and a dedicated portfolio-lab realm. Python 3.12.14 calls the Admin REST API. It exercises fictional users only.

## Development and review attribution

Codex prepared the API client, contract tests, live verification runner, startup helper, and documentation. The project owner requested the direction and supplied the Docker-enabled environment. Owner code review and a personal demonstration remain pending; the automated results below do not establish independent hands-on proficiency or production experience.

## Decisions and evidence

| Decision | Why | Evidence |
| --- | --- | --- |
| Keep the original simulation | Retain a simple way to study workflow logic | Existing PowerShell commands remain available |
| Use a local dedicated realm | Make integration repeatable without a paid SaaS tenant | Compose configuration and realm import |
| Reuse exact identity matches | Avoid duplicate users on retry | Repeated joiner retained the same identity and one group |
| Read state back | API acceptance alone is insufficient completion evidence | Account, membership, and session GET checks |
| Keep failure visible | Offboarding cannot be closed during an outage | Audit recorded incomplete; retry used the same ticket |
| Refuse implicit rehire | A repeated joiner must not restore disabled access | Rehire attempt failed and account remained disabled |
| Wait for readiness | Container started does not mean identity API ready | Initial CLI call failed during startup; helper now waits for realm discovery |

## Live results

Executed on October 21, 2026. See the [machine-readable evidence](../examples/keycloak-live-results.json) and [reproducible runner](../sandbox/verify_live.py).

| Scenario | Observed result |
| --- | --- |
| First joiner | Enabled account created with the lab group |
| Repeated joiner | Same identity; exactly one lab-support membership |
| Invalid service credential | Request rejected; account unchanged |
| Stopped Keycloak service | Workflow failed; audit ended as incomplete |
| Restart and retry | Same offboarding ticket succeeded; disabled account, zero groups, zero returned user sessions |
| Repeated leaver | Verified disabled state again |
| Joiner after offboarding | Rejected pending rehire review; account stayed disabled |

Seven live checks passed. Eleven separate contract tests cover additional failure paths, including a failure after disablement and failed state verification. The live outage occurred before mutation; the mid-workflow failure remains contract-tested rather than live-tested.

## Demo narrative

```mermaid
sequenceDiagram
    participant R as Lifecycle runner
    participant K as Local Keycloak
    participant A as Ticket audit
    R->>K: Provision fictional user and group
    R->>K: Repeat request
    K-->>R: Same identity
    Note over K: Lab service deliberately stopped
    R->>K: Attempt offboarding
    R->>A: Record incomplete
    Note over K: Lab service restarted
    R->>K: Retry same ticket; disable and remove groups
    R->>K: Read account, memberships, sessions
    K-->>R: Disabled; no groups; zero sessions returned
    R->>A: Record verified admin state
```

Run the setup helper and live verifier using the instructions in [the sandbox guide](keycloak-sandbox.md). The runner prints each check and writes a sanitized report. It briefly stops and restarts only the named lab service and leaves its fictional user disabled.

## Authentication extension

A subsequent run added ten real protocol checks for required TOTP enrollment, invalid-code rejection, authorization-code login with PKCE, active-session removal, refresh-token denial, introspection, UserInfo rejection, and fresh sign-in denial after offboarding. The combined contract suite now has sixteen passing tests.

See [authentication verification and review findings](keycloak-auth-verification.md) and the [newer report](../examples/keycloak-auth-results.json). The original seven-check snapshot above is retained as historical evidence.

## Boundaries of the original seven-check run

The original lifecycle run did not establish an active end-user session. The authentication extension subsequently added that evidence, PKCE login and TOTP enforcement. A visual walkthrough, SCIM, SAML, offline sessions, and downstream application/offline JWT validation remain outside the current milestone.

## Owner walkthrough prompts

Before presenting this as personal technical ownership, review the code and explain:

1. Which failure conditions leave a ticket incomplete?
2. How does a repeated request reuse the existing identity?
3. Why does offboarding not roll back to enabled?
4. Why might an existing access token still work?
5. What would change when integrating a remote production identity provider?

Record actual findings and improvements after that review.

# Sign-in, MFA and offboarding protocol verification

This extends the lifecycle evidence with real Keycloak authorization-code requests, PKCE, login forms, authenticator enrollment, and token endpoints. It is a protocol harness, not a production OIDC relying party or an independently performed user walkthrough.

## Run

From the repository root, in one PowerShell terminal:

```powershell
.\scripts\Start-KeycloakSandbox.ps1
python -m sandbox.verify_auth --run-live
```

The runner creates or updates the fixed `portfolio-demo` client in the local `portfolio-lab` realm using the local bootstrap admin. It generates a new disposable fictional user, password, client secret, and TOTP seed. The harness does not write passwords, seeds, tokens or login HTML to reports; Keycloak retains its own credential records in the private local volume; the test user is offboarded at the end. The client secret is randomized on each run, so this demo client must not be shared with another application.

The bootstrap password is used only to configure this local test client. Lifecycle operations still use the dedicated lifecycle-runner service account.

## Observed results

Ten checks passed on October 21, 2026. See [the sanitized report](../examples/keycloak-auth-results.json).

| Check | Result |
| --- | --- |
| Required TOTP enrollment | OTP credential persisted |
| Password without OTP | Did not complete sign-in |
| Invalid OTP | Rejected; OTP challenge remained |
| Authorization code with PKCE and valid OTP | Tokens issued; UserInfo matched the fixture identity |
| Token before offboarding | Introspection reported active |
| Active sessions after offboarding | None returned |
| Refresh token after offboarding | Rejected |
| Existing access token at introspection | Inactive |
| Existing access token at UserInfo | Rejected |
| Fresh sign-in after offboarding | Rejected |

## Findings and corrections

### Readiness is separate from container startup

The first lifecycle request arrived before the realm was ready. The startup helper now waits for realm discovery rather than treating a running container as a ready identity provider.

### An opaque form value is not the authenticator seed

Keycloak's hidden enrollment token is preserved unchanged. The harness follows the manual-enrollment link and reads the displayed seed separately. A failed early implementation attempted to decode the opaque field. The parser now has a regression test that keeps those values distinct.

### TOTP anti-replay matters

The harness waits for a new time step after enrollment before a second successful sign-in. Reusing a previously accepted code can be rejected.

### Token audience is part of validation

UserInfo succeeded while introspection initially returned inactive. The demo client now has an explicit audience mapper so the introspecting client is a token recipient. The test did not disable Keycloak's audience checks.

### HTTP test clients and browsers differ

The local development server emits Secure cookies. Python's default cookie policy withheld them over HTTP, producing missing-cookie errors. The harness permits those cookies only for the fixed 127.0.0.1 fixture; every request and redirect is restricted to the fixed local origin, except that the callback redirect is intercepted rather than fetched. This special policy belongs only in the test harness. Remote systems require HTTPS and normal cookie enforcement.

## Interpretation limits

- This runs the real login-form and token protocol, without a visual browser or owner walkthrough.
- The same automated process holds the password and TOTP seed. It tests server enforcement, not possession of independent physical factors.
- ID tokens are not consumed or validated by a relying-party application in this increment.
- Introspection and UserInfo consult Keycloak. These results do not prove an unrelated API that validates JWTs offline immediately rejects an already issued token.
- Offline sessions, downstream application cookies, SCIM and SAML remain outside this increment.
- The seven-check lifecycle snapshot predates this extension and accurately states that it did not establish an active session. This newer report adds that separate evidence.

## Reproducibility and CI

The contract tests cover workflow failure behavior plus TOTP correctness, callback state validation, credential destination restriction, and the loopback cookie exception. The GitHub Actions workflow defines separate contract and real-container jobs. Local execution passed. GitHub-hosted contract and real-container jobs also passed for implementation commit d7bf576: [verified Actions run](https://github.com/emckrieth/identity-lifecycle-automation-lab/actions/runs/39647478562).

Sources: [Keycloak OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers), [server administration](https://www.keycloak.org/docs/latest/server_admin/index.html).


Runtime reports now use output/verification/keycloak-auth-results.json with a fresh run ID. Startup and cleanup failures are recorded atomically; committed example reports are never used as current CI artifacts. See docs/approved-asset-workflow.md for the reporting fix and expanded workflow.

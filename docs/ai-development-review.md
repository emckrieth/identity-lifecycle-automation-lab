# AI assistance and review record

## Scope and attribution

This sandbox increment was prepared with Codex assistance. Existing commit history is retained. This document distinguishes assistant-generated implementation and automated checks from the project owner's personal review.

No personal design, review, hands-on verification, or production outcome is claimed on the owner's behalf.

## Decisions embodied in this increment

| Decision | Reason | Owner review |
| --- | --- | --- |
| Keep the PowerShell simulation | Preserve the original learning workflow | Pending |
| Use a local Keycloak realm | Allow a real identity API without paid SaaS access | Pending |
| Restrict URL and username | Reduce accidental use against non-lab identities | Pending |
| Read state back after writes | An accepted API request is not completion evidence | Pending |
| Preserve partial failure | An incomplete leaver must remain visible and safely retryable | Pending |
| Refuse implicit rehire | A repeated joiner must not restore offboarded access | Pending |
| Separate state from access verification | Session/token behavior needs independent testing | Pending |

## Review findings

Assistant review identified that counting a successful disable API call as complete offboarding would be misleading. The implementation reads back disabled state, membership, and user sessions, but explicitly reports interactive and downstream access tests as unverified.

A fake API contract can test retry behavior; it cannot prove compatibility with a real Keycloak release. Seven real Keycloak checks passed on October 21, 2026; see the case study for results and boundaries. Owner review remains pending.

## Owner walkthrough checklist

- Explain the difference between OAuth client credentials and end-user SSO.
- Trace one joiner request through API calls and the audit.
- Explain what happens if logout fails after disablement.
- Explain why retry does not create another user or reactivate a leaver.
- Explain why existing access tokens may still work.
- Record a genuine finding and the change it motivated.

## Next milestones

1. Owner review of the recorded live results and workflow (container run completed).
2. Add an OIDC application and before/after access verification.
3. Add MFA enrollment and policy tests.
4. Add SCIM provisioning as a distinct protocol integration.
5. Connect asset assignment and ticket intake after identity verification is demonstrated.

# Controls Mapping

This lab is a simulation, but it reflects controls that matter in real IAM operations.

## Joiner Controls

| Control | Where it appears | Why it matters |
| --- | --- | --- |
| Ticket reference required | Joiner input and audit log | Keeps provisioning tied to an approved request |
| Role-based groups | `data/role_map.json` | Reduces manual entitlement decisions |
| MFA status tracked | `data/users.json` and reports | Flags incomplete identity readiness |
| License profile assigned | Joiner workflow | Simulates M365-style access provisioning |

## Mover Controls

| Control | Where it appears | Why it matters |
| --- | --- | --- |
| Old groups removed | Mover workflow | Reduces privilege accumulation |
| New groups added by role | Mover workflow | Keeps access aligned to job function |
| Conflicting access flagged | Access review output | Supports separation of duties review |

## Leaver Controls

| Control | Where it appears | Why it matters |
| --- | --- | --- |
| Account disabled | Leaver workflow | Stops interactive access |
| Groups removed | Leaver workflow | Reduces residual access |
| License revoked | Leaver workflow | Controls SaaS access and cost |
| Mailbox handling noted | Leaver workflow | Supports operational continuity |

## Access Review Controls

The access review report identifies:

- stale accounts
- privileged users
- missing MFA
- disabled users with remaining access
- orphaned manager records
- conflicting entitlements

These findings are written as operational evidence an IAM or support engineer could use in a ticket, review meeting, or escalation.

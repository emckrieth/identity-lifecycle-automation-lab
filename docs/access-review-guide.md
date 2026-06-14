# Access Review Guide

## Purpose

The access review identifies identity records that need support, compliance, or manager follow-up.

## Findings

| Finding | Meaning | Recommended Action |
| --- | --- | --- |
| MFA missing for enabled account | User can sign in but MFA is not enabled | Enforce MFA or verify exception approval |
| Missing manager | User has no manager listed | Confirm HR or directory data quality |
| Privileged access requires review | User belongs to admin or privileged groups | Confirm approval and business need |
| Disabled account still has groups | Deprovisioning is incomplete | Remove access and review leaver process |
| Stale account | User has not logged in within threshold | Confirm employment status and disable if needed |
| Access conflict | User has conflicting role entitlements | Escalate for segregation-of-duties review |

## Review Cadence

Suggested cadence:

- privileged access: monthly
- standard application access: quarterly
- stale accounts: weekly monitoring
- leaver validation: same day as termination

## Evidence to Attach to ITSM Ticket

- access review report
- user principal name
- finding type
- group list
- remediation action
- approval or exception note

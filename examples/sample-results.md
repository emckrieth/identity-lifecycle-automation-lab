# Sample Results

## Joiner

Input:

```text
jordan.lee@example.com, FinanceAnalyst
```

Expected outcome:

- account created
- Finance groups assigned
- M365 E3 license assigned
- MFA enabled
- audit entries written with ticket ID

## Mover

Input:

```text
alex.morgan@example.com -> ComplianceAnalyst
```

Expected outcome:

- old Finance groups removed
- Compliance groups assigned
- title and manager updated
- access conflicts checked

## Leaver

Input:

```text
sam.taylor@example.com
```

Expected outcome:

- account disabled
- privileged groups removed
- license revoked
- mailbox handling note recorded

## Access Review

Sample findings:

```text
Privileged access requires review
MFA missing for enabled account
Missing manager
Stale account
```

These findings can be used as evidence in an ITSM ticket or recurring access review process.

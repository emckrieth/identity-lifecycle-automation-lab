# Rollback Notes

## Purpose

Identity changes can affect user productivity and security. This document describes how rollback would be handled in this simulated lab and how the same idea maps to production.

## Joiner Rollback

If a joiner request was processed in error:

1. Disable the newly created account.
2. Remove assigned groups.
3. Revoke license assignment.
4. Add a note to the ticket explaining why provisioning was reversed.

## Mover Rollback

If a mover request assigned the wrong role:

1. Restore previous department, title, manager, and role.
2. Remove newly added groups.
3. Restore previously removed groups if still approved.
4. Run access review to confirm no conflicting access remains.

## Leaver Rollback

If a leaver request was submitted in error:

1. Confirm HR and manager approval before re-enabling the account.
2. Restore only approved role-based groups.
3. Reassign license if needed.
4. Require MFA validation before restoring access.

## Production Considerations

In a real environment, rollback should be documented in the ITSM ticket and should follow change management or emergency access procedures when privileged access is involved.

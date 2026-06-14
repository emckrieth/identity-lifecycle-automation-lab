# Incident Scenarios

## Scenario 1: New Hire Missing Required Access

**Symptom:** User reports they cannot access a required SaaS application.

**Investigation:**

- confirm ticket ID and requested role
- review joiner audit entries
- compare assigned groups against `data/role_map.json`
- check for failed group assignment entries

**Likely Cause:** Role map missing required application group or request submitted with wrong role.

**Corrective Action:** Update role map after approval and rerun the joiner workflow for the affected user.

## Scenario 2: Mover Retains Old Department Access

**Symptom:** Access review shows a user has both old and new department groups.

**Investigation:**

- review mover audit entries
- compare old groups removed and new groups added
- check for access conflict warnings

**Likely Cause:** Manual group assignment outside standard workflow or incomplete mover processing.

**Corrective Action:** Remove old department groups and document the remediation in the ITSM ticket.

## Scenario 3: Leaver Still Has Privileged Access

**Symptom:** Access review flags disabled user with privileged group membership.

**Investigation:**

- confirm leaver request completed
- inspect group removal audit entries
- identify privileged groups still attached

**Likely Cause:** Privileged access managed outside the standard identity workflow.

**Corrective Action:** Escalate to Identity or Infrastructure owner and remove access immediately.

## Scenario 4: Missing MFA for Enabled Account

**Symptom:** Access review report flags `MFA missing for enabled account`.

**Investigation:**

- confirm whether the user is active
- confirm role requires MFA
- review recent joiner or mover changes

**Likely Cause:** MFA enrollment failed or the user was created outside the standard process.

**Corrective Action:** Enforce MFA, document user impact, and review onboarding controls.

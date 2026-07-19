# Cross-Tenant Access Runbook

Use this runbook for a suspected or confirmed cross-workspace read, write,
retrieval hit, object access, session misuse, or authorization bypass.

## Detection

- Treat cross-tenant access attempts, tenant-scope denials, unexpected object
  access, and inconsistent workspace correlation as high-priority signals.

## Initial Triage

- Determine the actor/session, source and target workspace, resource class,
  action outcome, RLS context, and whether the access was attempted or confirmed.

## Containment

- Revoke affected sessions, suspend the narrowest unsafe endpoint/capability,
  and prevent writes while preserving tenant-scoped investigation access.

## Kill Switches

- Use `disable_all_agent_writes` or `disable_memory_writes` when the path can
  mutate state; use `disable_external_egress` or `disable_external_mcp` only if
  they are part of the suspected cross-tenant route.

## Evidence Preservation

- Preserve actor/session digests, redacted audit and security-event IDs, RLS
  policy/configuration version, resource class, and audit-chain verification.

## Credential Rotation

- Revoke the affected session and rotate implicated signing, service, object,
  or provider credentials when compromise or over-broad scope is plausible.

## Affected-Data Analysis

- Establish source/target tenants, confirmed records or objects, data classes,
  time window, and access outcome without moving customer content into the case.

## Eradication

- Correct the missing tenant predicate, RLS context, authorization check,
  object-key scope, cache key, or identity mapping that enabled the route.

## Recovery

- Validate with direct wrong-tenant tests and Postgres RLS coverage before
  restoring capability; monitor denials and affected tenants after release.

## User/Customer Notification Considerations

- Engage legal/privacy and account teams immediately for confirmed access or
  material credible suspicion. Notify according to contract and legal duty.

## Postmortem

- Document tenant impact, access certainty, control layer failure, session/
  credential actions, remediation, and owner for residual-risk follow-up.

## Regression-Test Addition

- Add a direct cross-workspace read/write/retrieval/object test proving a
  non-enumerating denial and verifying no target resource value is audited.

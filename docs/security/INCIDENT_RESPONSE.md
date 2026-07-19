# Incident Response

This runbook is the command process for every security incident. The incident
commander owns decisions and timeline; responders use the scenario-specific
runbook for containment details. Do not place prompts, source bodies, secrets,
or customer data in tickets, chat, or the incident timeline.

## Detection

- Treat high/critical security alerts, tenant-scope denials, provider DLP
  failures, quarantine events, and credible customer reports as incidents.
- Capture the security-event, alert, audit, project, workflow, and trace IDs.
  Use the Security Overview and the redacted project security endpoints; do not
  export raw event content for routine triage.

## Initial Triage

- Assign an incident commander, scribe, and technical owner; classify severity,
  affected workspaces/projects, active attack surface, and suspected data class.
- Start a time-stamped incident record with only correlation IDs, decisions,
  and approved evidence locations.

## Containment

- Stop the smallest risky capability first, then widen only when evidence
  requires it. Preserve read-only access needed for investigation.
- Confirm the control took effect by recording the resulting audited denial or
  security event.

## Kill Switches

- Workspace owners change durable controls through `PATCH /api/security/kill-switches`.
  Security administrators can review effective state through `GET /api/security/kill-switches`.
- Available controls are `disable_all_agent_writes`, `disable_external_mcp`,
  `disable_external_egress`, `disable_model_provider`, `disable_memory_writes`,
  and `disable_source_fetching`. Environment controls override workspace state.

## Evidence Preservation

- Preserve the incident timeline, redacted audit-chain verification output,
  relevant normalized security events/alerts, configuration version, and
  immutable object identifiers in access-controlled evidence storage.
- Run `python scripts/verify_audit_chain.py` with an authorized migration-role
  database URL. Record the command result and checksum; never alter audit rows.

## Credential Rotation

- Rotate only credentials plausibly exposed or used by the affected boundary:
  OIDC signing keys, service/API keys, provider keys, object-store credentials,
  MCP OAuth tokens, or MCP client credentials.
- Revoke affected sessions and record the rotation owner, scope, completion
  time, and verification without storing credential values.

## Affected-Data Analysis

- Use workspace/project correlation IDs, source classifications, provider
  routing records, retention metadata, and object identifiers to establish the
  affected-data set. State uncertainty explicitly.
- Separate confirmed access from attempted access, and preserve tenant boundaries
  throughout analysis.

## Eradication

- Remove the triggering configuration, endpoint, source, credential, policy,
  or dependency only after evidence is preserved and a rollback plan exists.
- Quarantine unsafe sources and revoke retrieval eligibility before remediation.

## Recovery

- Validate the fixed control in a non-production environment, then restore the
  minimum necessary capability. Keep heightened alert review during recovery.
- Re-enable kill switches only with incident-commander approval and an audited
  state change.

## User/Customer Notification Considerations

- Engage legal, privacy, and customer-success owners when confirmed or
  reasonably suspected access involves customer data, regulated data, or a
  cross-tenant boundary. Follow contractual and jurisdictional timelines.
- Notifications must distinguish attempted access, confirmed access, and data
  classes affected; do not speculate beyond the evidence.

## Postmortem

- Publish a blameless record covering timeline, detection, decisions, impact,
  control gaps, residual risk, owners, and dated follow-up actions.
- Link only approved evidence locations and correlation IDs, not raw sensitive
  payloads.

## Regression-Test Addition

- Add a deterministic test at the boundary that failed, including the intended
  denial or containment behavior. Link the test path and command in the
  postmortem before closing the incident.

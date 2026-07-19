# Compromised MCP Runbook

Use this runbook for an untrusted, changed, compromised, or over-scoped remote
MCP server, OAuth authorization, tool schema, credential, or invocation.

## Detection

- Investigate MCP fingerprint/schema changes, failed review, unexpected
  high-risk tool requests, OAuth anomalies, and remote invocation denials.

## Initial Triage

- Identify the server registration, version/fingerprint, tools, workspace,
  credential type, active sessions, and any completed external side effects.

## Containment

- Disable remote MCP access and prevent new invocations before revisiting server
  review or re-authorizing a credential.

## Kill Switches

- Enable `disable_external_mcp`; use `disable_all_agent_writes` when an MCP
  server could initiate durable mutations and `disable_external_egress` for a
  broader network containment boundary.

## Evidence Preservation

- Preserve server registration ID, approved fingerprint/version, reviewed tool
  schema snapshot, audit/event/alert IDs, and redacted invocation outcomes.

## Credential Rotation

- Revoke MCP OAuth grants and rotate server/client credentials or tokens that
  could have been exposed to the affected server.

## Affected-Data Analysis

- Analyze requested/approved tool scope, completed invocations, tenant/project
  correlation, and destination metadata without retaining tool payload secrets.

## Eradication

- Disable or remove the compromised registration, reject the fingerprint/schema
  change, and require a new review before any re-enable.

## Recovery

- Re-register only a verified server version with reviewed schemas, narrowed
  scope, fresh credentials, and a successful controlled invocation.

## User/Customer Notification Considerations

- Obtain notification review if the server received or acted on customer data
  outside approved scope or if an external side effect was completed.

## Postmortem

- Record server identity, trust break, authorization path, credential scope,
  completed effects, and review/process improvements.

## Regression-Test Addition

- Add a test that rejects the observed fingerprint/schema/authorization change
  before any remote call and verifies the kill switch prevents persistence.

# Data Exfiltration Runbook

Use this runbook for suspected disclosure through a provider, tool, MCP server,
download, signed URL, trace, log, or external fetch path.

## Detection

- Treat DLP, provider-policy, unusual retrieval, mass-export, signed-URL, and
  anomalous tool events as potential exfiltration signals.

## Initial Triage

- Identify the destination, time window, workspace/project, data class,
  credential path, and whether transfer was attempted or confirmed.

## Containment

- Stop the destination path first; revoke active grants and prevent new
  transfers while retaining read-only investigation access.

## Kill Switches

- Use `disable_external_egress` for network destinations, `disable_model_provider`
  for provider transfer, `disable_external_mcp` for remote MCP paths, and
  `disable_source_fetching` when fetched content is implicated.

## Evidence Preservation

- Preserve correlation IDs, redacted provider-routing records, object IDs,
  audit-chain verification output, and alert disposition history.

## Credential Rotation

- Rotate the credential authorized for the destination or object access; revoke
  signed URLs and affected sessions where supported.

## Affected-Data Analysis

- Enumerate only authorized metadata: classification, tenant scope, object IDs,
  provider route, and transfer outcome. Do not reconstruct payloads unnecessarily.

## Eradication

- Remove the destination allowlist entry, policy exception, route, tool grant,
  or leaked credential that enabled the transfer.

## Recovery

- Restore only reviewed destinations and validate classification, tenant scope,
  and egress controls before issuing new access grants.

## User/Customer Notification Considerations

- Obtain legal/privacy review for confirmed or reasonably suspected customer
  data disclosure; communicate scope, classification, destination, and remedy.

## Postmortem

- Document confirmation level, data analysis method, containment duration,
  credential actions, and residual destination risk.

## Regression-Test Addition

- Add a deterministic test proving the implicated transfer is denied before
  egress or signed-URL creation and that no sensitive payload is logged.

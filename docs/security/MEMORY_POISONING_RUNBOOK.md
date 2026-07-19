# Memory Poisoning Runbook

Use this runbook for unsafe, untrusted, contradictory, unsupported, or
unexpectedly activated durable project memory.

## Detection

- Investigate untrusted-memory, quarantine, contradiction, rejected-proposal,
  provenance, and unexpected memory-write alerts or audit events.

## Initial Triage

- Identify the memory record/version, project, source provenance/trust,
  proposal/approval state, affected downstream workflows, and active recalls.

## Containment

- Block new memory writes and revoke the affected record from recall before
  editing or deleting supporting evidence.

## Kill Switches

- Enable `disable_memory_writes`; use `disable_all_agent_writes` if the same
  workflow could mutate other state, and `disable_source_fetching` for a hostile
  external-source origin.

## Evidence Preservation

- Preserve memory/version/source IDs, provenance/trust status, approval IDs,
  audit-chain result, and redacted security events without copying memory text.

## Credential Rotation

- Rotate credentials only when a compromised source, MCP server, provider, or
  user identity plausibly authored or approved the poisoned record.

## Affected-Data Analysis

- Trace approved and proposed versions, source links, recall history, related
  artifacts, downstream decisions, and tenants/projects affected.

## Eradication

- Quarantine/supersede unsafe records, invalidate derived state, repair source
  trust/provenance, and require fresh verification before reactivation.

## Recovery

- Validate the corrected proposal and approval path, then restore memory writes
  gradually while reviewing contradictory or untrusted-memory signals.

## User/Customer Notification Considerations

- Engage notification review when poisoned memory caused material customer
  guidance, unauthorized action, or exposure of customer data.

## Postmortem

- Record origin, approval path, containment timing, recalled outputs, source
  remediation, and open provenance/verification gaps.

## Regression-Test Addition

- Add a test proving untrusted or conflicting evidence becomes a proposal or
  quarantine record and cannot enter active recall without approval.

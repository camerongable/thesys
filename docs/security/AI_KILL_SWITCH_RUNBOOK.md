# AI Kill Switch Runbook

Use this runbook for unsafe model behavior, runaway agent execution, provider
anomalies, or any incident needing an immediate AI capability reduction.

## Detection

- Investigate high/critical model, workflow-budget, guardrail, tool, or
  provider-error security events and their associated alerts.

## Initial Triage

- Identify the affected workspace, project, workflow, provider route, and
  whether the unsafe behavior needs model, egress, write, or MCP containment.

## Containment

- Disable the narrowest applicable capability before retrying or inspecting a
  workflow. Cancel active work through the approved workflow operation.

## Kill Switches

- Use `disable_model_provider` for all model calls, `disable_external_egress`
  for provider/network egress, `disable_all_agent_writes` for agent mutations,
  `disable_memory_writes` for memory changes, and `disable_external_mcp` for
  remote tool access. Use the audited security endpoint, not a database edit.

## Evidence Preservation

- Preserve security-event, alert, audit, AI-run, workflow, request, and
  redacted trace identifiers. Verify the audit chain before recovery.

## Credential Rotation

- Rotate the affected provider, Temporal, or MCP credential if compromise,
  unauthorized routing, or credential exposure is plausible.

## Affected-Data Analysis

- Determine which classifications reached the provider and which tool or
  memory writes were attempted, denied, proposed, or completed.

## Eradication

- Correct the provider route, guardrail, policy, budget, prompt boundary, or
  tool configuration that allowed the unsafe path.

## Recovery

- Prove the fixed path with a scoped non-production test, restore capabilities
  incrementally, and watch normalized events and alerts for recurrence.

## User/Customer Notification Considerations

- Escalate for notification review when the event may have exposed customer
  data to an unapproved provider or caused an unauthorized durable mutation.

## Postmortem

- Record the selected switch, activation time, denied workload IDs, recovery
  criteria, and any unsafe behavior that escaped the initial control.

## Regression-Test Addition

- Add coverage for the exact denied boundary, including the switch state and
  proof that no provider call, tool effect, or durable write occurred.

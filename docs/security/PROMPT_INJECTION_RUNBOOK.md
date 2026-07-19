# Prompt Injection Runbook

Use this runbook for direct or indirect instruction attacks, jailbreaks,
system-prompt extraction attempts, or instruction-bearing retrieved content.

## Detection

- Investigate prompt-injection, jailbreak, guardrail-block, tool-denial, and
  source-trust quarantine events together with the resulting alert.

## Initial Triage

- Determine whether the attack was direct input or a fetched/retrieved source,
  which project/workflow handled it, and whether any tool or memory action ran.

## Containment

- Quarantine the source, stop the affected workflow, and block future unsafe
  tool or memory actions before collecting additional evidence.

## Kill Switches

- Use `disable_source_fetching` for hostile external content,
  `disable_all_agent_writes` or `disable_memory_writes` for durable mutations,
  and `disable_external_egress` if further retrieval could widen exposure.

## Evidence Preservation

- Preserve source IDs, trust/quarantine decision, event and alert IDs, audit
  chain result, workflow/run IDs, and redacted detector metadata only.

## Credential Rotation

- Rotate credentials only if the incident shows attempted or confirmed use of a
  credential, external tool, or provider beyond its approved policy.

## Affected-Data Analysis

- Determine whether the source entered parsing, embedding, retrieval, prompt
  assembly, tool invocation, memory proposal, or durable state.

## Eradication

- Remove/quarantine the malicious source, strengthen the matching detector or
  trust rule, and revoke any unsafe derived retrieval eligibility.

## Recovery

- Re-run a sanitized fixture through the fixed boundary and restore retrieval
  only after source trust and policy checks pass.

## User/Customer Notification Considerations

- Escalate notification review only for confirmed unauthorized data exposure or
  durable cross-tenant/customer impact, not for blocked attempts alone.

## Postmortem

- Record attack vector, containment latency, control decision, attempted side
  effects, source disposition, and remaining detector gaps.

## Regression-Test Addition

- Add an adversarial fixture that proves the source is quarantined and any
  high-risk tool attempt is denied before external effect or durable mutation.

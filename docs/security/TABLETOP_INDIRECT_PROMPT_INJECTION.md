# Tabletop: Indirect Prompt Injection

**Date:** 2026-07-18

**Participants:** Incident commander, application security, platform
engineering, and product operations roles.

**Scope:** Simulated tenant-scoped incident using synthetic content only. No
production prompts, sources, credentials, or customer data were used.

## Scenario

A malicious external webpage is submitted as research evidence. Its visible
content looks relevant, but hidden/embedded instructions try to make the agent
ignore policy and invoke a high-risk tool. The target workflow must not execute
the tool or make a durable memory write.

## Exercise Timeline

1. The source-trust/guardrail path identifies instruction-heavy content and
   records a redacted prompt-injection/security event. The source is quarantined
   before vector creation and retrieval.
2. A simulated agent attempts the high-risk tool action. The governed tool
   boundary evaluates identity, scope, policy, approval, and budget controls and
   denies the action before an external effect.
3. The normalized high-severity event opens a security alert. The incident
   commander correlates alert, audit, source, project, workflow, and trace IDs
   in the Security Overview without viewing raw prompt content.
4. The operator enables `disable_external_egress` through the audited workspace
   kill-switch endpoint. New external fetch/provider paths are denied while
   investigation continues.
5. The malicious source remains quarantined and unavailable to retrieval. The
   team preserves redacted event/alert records and verifies the audit chain.
6. The incident is converted into deterministic regression coverage for source
   quarantine, high-risk tool denial, alert escalation, and kill-switch behavior.

## Results

- **Detection:** The exercise relies on normalized prompt-injection and
  quarantine telemetry, not raw-content logging.
- **Containment:** Quarantine, governed tool denial, and the external-egress
  switch stop the modeled progression without deleting evidence.
- **Evidence:** The agreed investigation set is correlation IDs, immutable audit
  records, normalized security events/alerts, source trust status, and verified
  audit-chain output.
- **Recovery:** Re-enablement requires a reviewed source disposition and a
  controlled non-production regression pass.

## Lessons Learned

1. The incident commander needs a short reference from the alert queue to the
   applicable runbook; the common and prompt-injection runbooks now provide it.
2. Correlation IDs are sufficient for initial triage and avoid spreading attack
   payloads through operational channels.
3. Kill-switch selection should be explicit: quarantine stops one source,
   `disable_all_agent_writes` stops mutations, and `disable_external_egress`
   narrows further external exposure.
4. Regression tests must prove absence of external effects and durable writes,
   not only that an attack is detected.

## Regression Evidence

- `apps/api/app/tests/security/test_source_trust.py` covers quarantine before
  vector persistence and retrieval.
- `apps/api/app/tests/test_tool_boundary.py` covers denial of unsafe/disabled
  tool actions before invocation persistence or external effect.
- `apps/api/app/tests/security/test_security_events.py` covers high-severity
  event-to-alert escalation.
- `apps/api/app/tests/test_security_governance.py` and
  `apps/api/app/tests/test_kill_switches.py` cover audited egress and workspace
  kill-switch enforcement.

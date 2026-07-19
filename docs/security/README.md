# Security Documentation Guide

This directory documents the security model for Thesys. It is organized by the
question an owner, reviewer, or incident responder needs to answer. The
documents describe source-controlled controls and their test evidence; hosted
configuration and repository administration remain separate prerequisites.

## Start With The Right Document

| Question | Read | What it provides |
|---|---|---|
| What is the overall security design? | [Security Architecture](SECURITY_ARCHITECTURE.md) | Trust boundaries, control ownership, failure behavior, tenant model, and provider policy. |
| What can attack the system and what remains risky? | [Threat Model](THREAT_MODEL.md) | Actors, assets, scenarios, assumptions, and review triggers. |
| Which controls exist, where are they tested, and what is residual? | [Control Matrix](CONTROL_MATRIX.md) | Code/test ownership, status, residual risk, and framework mappings. |
| What attacks are deliberately tested? | [Abuse Cases](ABUSE_CASES.md) | Adversarial scenarios and expected containment. |
| How is data classified, retained, and removed? | [Data Classification](DATA_CLASSIFICATION.md), [Data Retention](DATA_RETENTION.md) | Data classes, allowed handling, retention, deletion, and review rules. |
| How should an incident be run? | [Incident Response](INCIDENT_RESPONSE.md) | Triage, containment, evidence, recovery, and follow-up. |
| How should a specific high-risk event be contained? | [Prompt Injection](PROMPT_INJECTION_RUNBOOK.md), [Memory Poisoning](MEMORY_POISONING_RUNBOOK.md), [Data Exfiltration](DATA_EXFILTRATION_RUNBOOK.md), [Cross-Tenant Access](CROSS_TENANT_ACCESS_RUNBOOK.md), or [Compromised MCP](COMPROMISED_MCP_RUNBOOK.md) | Scenario-specific containment steps. |
| How do we stop AI capabilities in an incident? | [AI Kill Switch Runbook](AI_KILL_SWITCH_RUNBOOK.md) | Kill-switch scope, verification, and recovery. |
| How was indirect prompt injection rehearsed? | [Tabletop Exercise](TABLETOP_INDIRECT_PROMPT_INJECTION.md) | A repeatable tabletop scenario and expected evidence. |

For a short introduction, start with the repository-level [Security Overview](../security.md).
For local, CI, release, and hosted requirements, read [Deployment And Security](../DEPLOYMENT_SECURITY.md).

## Security Principles

1. **Models propose; deterministic services decide and execute.** A model is
   never an identity, authorization, policy, approval, or tool-execution
   authority.
2. **Every consequential action has a trusted owner.** Authentication, tenant
   scope, data classification, provider selection, tool policy, state changes,
   budgets, memory writes, and audit records are deterministic code paths.
3. **Untrusted content is data, not instruction.** User input, files, fetched
   content, retrieved chunks, model output, and MCP output cross explicit trust
   boundaries and are classified, isolated, or validated before use.
4. **Privileged uncertainty fails closed.** Missing identity, tenant scope,
   provider policy, tool policy, approval, or required output validation blocks
   the action rather than granting a best-effort result.
5. **Defense in depth matters.** Application authorization, database RLS,
   provider egress rules, schemas, approvals, budgets, redaction, auditing, and
   CI checks overlap because no individual control is sufficient.
6. **Evidence is redacted and attributable.** Security events keep bounded
   metadata, correlation, and outcomes without retaining bearer tokens, raw
   secrets, or unnecessary sensitive payloads.
7. **Claims carry an evidence level.** `Enforced` means implementation plus a
   regression test; source code does not prove hosted-cloud configuration or
   organizational response readiness.

## Control Families And Code Entry Points

| Family | Primary implementation | Primary evidence |
|---|---|---|
| Identity and tenant isolation | [auth](../../apps/api/app/core/auth.py), [tenant binding](../../apps/api/app/db/tenant.py) | Auth, tenant-context, and PostgreSQL RLS tests. |
| Guardrails and prompt boundaries | [guardrail gateway](../../apps/api/app/security/guardrails/gateway.py) | Guardrail, prompt-injection, and adversarial tests. |
| Ingestion and source trust | [evidence service](../../apps/api/app/services/evidence_service.py) | Upload, URL, parser, and source-trust tests. |
| Retrieval and citations | [retrieval service](../../apps/api/app/services/retrieval_service.py) | Retrieval security and citation-verification tests. |
| Memory and approval | [memory service](../../apps/api/app/services/memory_service.py) | Memory security, provenance, and approval tests. |
| Tool and MCP policy | [tool service](../../apps/api/app/services/tool_service.py), [MCP adapter](../../apps/api/app/mcp/adapter.py) | Tool/MCP policy, approval, and red-team tests. |
| Resource abuse controls | [workflow budgets](../../apps/api/app/services/workflow_budget_service.py), [security policy](../../apps/api/app/services/security_policy_service.py) | Rate-limit, budget, loop, and anomaly tests. |
| Audit and incident evidence | [security events](../../apps/api/app/services/security_event_service.py), [audit chain](../../apps/api/app/services/audit_chain_service.py) | Security-event and audit-chain tests. |
| Supply chain and release evidence | [Security workflow](../../.github/workflows/security.yml), [Release Security](../../.github/workflows/release-security.yml) | CI artifacts, SBOMs, image scans, and signed-release evidence when configured. |

## Assurance Boundaries

| Evidence source | Proves | Does not prove |
|---|---|---|
| Local test or static check | The repository control behaves as its contract expects in that environment. | Production credentials, cloud IAM, network policy, and external-provider behavior. |
| Pull-request CI | The configured workflow ran its selected checks on the submitted revision. | Branch-protection enforcement or nightly/release jobs unless those jobs ran. |
| Scheduled/release CI | Broader adversarial, dependency, image, and artifact evidence for that run. | A permanently secure runtime after the run completes. |
| Hosted verification | The deployed configuration and integration worked for the recorded environment. | Future configuration drift without continued monitoring and review. |

## Maintenance Rules

When a change adds a trust boundary, data class, auth mode, provider, tool,
memory path, workflow, or external side effect, update the threat model and
control matrix in the same change. When it changes a response procedure, update
the relevant runbook. When it changes test coverage or CI behavior, update
[Evals And Observability](../EVALS_AND_OBSERVABILITY.md) and the corresponding
evidence link. Run `python3 scripts/check_documentation_links.py` before merge.


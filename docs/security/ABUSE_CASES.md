# Security Abuse Cases

These cases turn the threat model into adversarial behaviors that security
tests and later sprint controls must address. Each case has a deterministic
security outcome; model refusal alone is never the control.

## AC-01: Cross-tenant project enumeration

- Actor: authenticated malicious user.
- Path: alter project, source, artifact, workflow, memory, or vector identifiers.
- Impact: disclosure or mutation of another workspace's strategy.
- Required outcome: return not found/forbidden without confirming object
  existence; log repeated denials without sensitive identifiers.
- Controls: workspace-scoped queries now; JWT tenant claims and Postgres RLS in
  Sprint 62.
- Verification: tenant-path invariant plus cross-workspace API/retrieval tests.

## AC-02: Development-header production bypass

- Actor: anonymous or authenticated external user.
- Path: send `X-Dev-User-*` headers to a hosted environment.
- Impact: impersonation and role escalation.
- Required outcome: production configuration cannot start with dev auth, and
  dev headers are rejected outside local mode.
- Controls: header rejection exists; startup/config enforcement belongs to
  Sprint 62.
- Verification: `test_production_auth_cannot_run_in_dev_header_mode` remains an
  expected gap until the configuration validator lands.

## AC-03: Prompt-injected webpage requests a tool call

- Actor: malicious external webpage.
- Path: source text says to ignore policy, reveal context, or invoke a tool.
- Impact: data exfiltration, unauthorized action, poisoned conclusions.
- Required outcome: content remains untrusted evidence, cannot alter system
  instructions, and cannot independently authorize a tool.
- Controls: provenance markers and untrusted prompt boundaries now; centralized
  guardrail gateway in Sprint 64 and trust filtering in Sprint 65.

## AC-04: Jailbreak asks the model to reveal secrets or system prompts

- Actor: authenticated malicious user.
- Path: conversational prompt requests hidden instructions, credentials, or raw
  provider context.
- Impact: policy disclosure and credential compromise.
- Required outcome: input is classified; output DLP blocks secrets; only safe,
  project-scoped content is returned.
- Controls: redaction now; input/output gateway and canary-secret tests in
  Sprints 64/68.

## AC-05: Poisoned evidence becomes durable memory

- Actor: malicious member, document, or agent.
- Path: add plausible false evidence, obtain a high retrieval rank, then propose
  it as validated memory.
- Impact: future recommendations and decisions are systematically corrupted.
- Required outcome: source provenance/trust follows the claim; unsafe memory is
  quarantined; conflict and approval checks run before activation.
- Controls: proposals, provenance, approvals, and conflict detection now;
  poisoning scores, TTL, and quarantine in Sprint 65.

## AC-06: Citation points to unrelated or manipulated text

- Actor: model or poisoned source.
- Path: attach a real source ID to an unsupported factual claim.
- Impact: misinformation appears grounded.
- Required outcome: quote/chunk support is verified; unsupported claims remain
  assumptions and cannot be stored as supported findings.
- Controls: citation verifier now; adversarial citation-confusion suite in
  Sprint 68.

## AC-07: MCP client invokes a high-risk tool without approval

- Actor: compromised MCP client/server or over-permissioned agent.
- Path: call a write/proposal tool directly or replay a previous approval.
- Impact: unauthorized state mutation or external side effect.
- Required outcome: MCP and HTTP share identity, role, tenant, policy, approval,
  idempotency, and audit enforcement.
- Controls: shared registry and parity path now; scoped MCP identity,
  policy-as-code, sandboxing, and approval binding in Sprint 66.

## AC-08: Restricted interview notes are sent to an unapproved provider

- Actor: buggy workflow or compromised account.
- Path: include names/emails in a model, embedding, search, or trace payload.
- Impact: privacy breach and provider-policy violation.
- Required outcome: classification propagates, provider policy denies egress,
  and audit metadata contains no raw restricted values.
- Controls: classification contract and host allowlists now; PII-aware ingestion
  and payload policy in Sprints 62-64.

## AC-09: URL fetch targets internal infrastructure

- Actor: malicious user or webpage.
- Path: loopback/private IP, redirect, DNS rebinding, unsafe port, or embedded
  credentials.
- Impact: metadata theft or internal service access.
- Required outcome: validate every hop and resolved address, cap response size,
  fail the source, and emit a redacted denial event.
- Controls: URL validation now; quarantine and egress proxy/sandbox hardening in
  Sprint 63.

## AC-10: Uploaded file exploits parser or hides malicious instructions

- Actor: malicious uploaded document.
- Path: type confusion, malformed PDF/image, oversized content, malware, or
  hidden prompt injection.
- Impact: code execution, resource exhaustion, or RAG poisoning.
- Required outcome: quarantine first, validate type/size/hash, scan, parse in an
  isolated boundary, classify, and only then promote sanitized text.
- Controls: type/size/magic checks now; quarantine, malware scanning, parser
  isolation, and promotion state in Sprint 63.

## AC-11: Agent loops until budget exhaustion

- Actor: buggy agent or abusive user.
- Path: repeated retrieval/tool/model calls, workflow retries, or concurrent runs.
- Impact: availability loss and provider spend.
- Required outcome: enforce token, cost, duration, retrieval, tool-call,
  concurrency, and retry budgets; cancel and alert on violation.
- Controls: rate/concurrency/preflight controls now; durable budgets, anomaly
  alerts, and kill switches in Sprint 67.

## AC-12: Secret leaks through error, trace, audit, or cache

- Actor: bug, provider, dependency, or curious operator.
- Path: raw exception/provider payload is persisted or exported.
- Impact: credential or PII disclosure.
- Required outcome: central output security scans every persistence/export path;
  canary secrets never appear in logs, traces, memory, or user output.
- Controls: shared redaction now; gateway coverage and adversarial canaries in
  Sprints 64/68.

## AC-13: Dependency or image is compromised

- Actor: supply-chain attacker.
- Path: malicious package, vulnerable transitive dependency, mutable image, or
  tampered build output.
- Impact: runtime code execution and credential/data theft.
- Required outcome: pinned dependencies, strict scans, SBOM, signed artifacts,
  minimal images, and blocked release on critical findings.
- Controls: lockfiles and audit scripts now; release gates in Sprint 68.

## AC-14: Curious operator reads plaintext stores or backups

- Actor: infrastructure operator or compromised cloud account.
- Path: direct database, object-store, trace, Temporal, or backup access.
- Impact: broad confidential/restricted data disclosure.
- Required outcome: managed encryption, scoped break-glass access, audit,
  retention, deletion, and restore tests.
- Controls: application scoping/redaction now; encryption and incident controls
  in Sprints 62/67.

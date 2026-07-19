# Ask Thesys Streaming

Ask Thesys is a bounded project guide. It can retrieve project evidence,
stream answer progress, surface citations, and create approval-gated proposals,
but it does not directly mutate memory, validation plans, or decisions from a
chat message.

## Source-Linked Flow

```text
GuidePanel form submit
-> apps/web/src/lib/api.ts streamProjectGuide
-> POST /api/projects/{project_id}/guide/chat/stream
-> app.routers.projects.stream_project_guide_chat
-> security_policy_service.guarded_workflow
-> app.services.guide_service.stream_chat_events
-> app.features.guide.events
-> final GuideChatResponseRead payload
```

Primary owners:

| Concern | Source |
|---|---|
| Stream endpoint and SSE framing | `apps/api/app/routers/projects.py` |
| Stream orchestration, timeout, cancellation, provider fallback | `apps/api/app/services/guide_service.py` |
| Event serialization | `apps/api/app/features/guide/events.py` |
| Prompt/context projection | `apps/api/app/features/guide/prompting.py`, `apps/api/app/features/guide/context_projection.py` |
| Grounded response shaping | `apps/api/app/features/guide/grounding.py` |
| Citation metadata shaping | `apps/api/app/features/guide/citations.py` |
| Frontend stream parser | `apps/web/src/lib/api.ts` |
| Frontend guide panel and hidden diagnostics | `apps/web/src/features/projects/guide-panel.tsx` |

## Event Contract

The server emits named SSE frames with JSON payloads:

| Event | Purpose |
|---|---|
| `message_started` | Opens the run and returns the `ai_run_id`, provider mode, model, and prompt version. |
| `retrieval_started` | Announces the hybrid evidence search query, mode, and top-k budget. |
| `tool_call_started` | Shows the governed `search_project_evidence` read tool call. |
| `tool_call_completed` | Reports read-tool completion, result count, and cited evidence IDs. |
| `retrieval_result` | Returns retrieval diagnostics, cited source IDs, and citation drilldown details. |
| `context_compiled` | Returns context-pack ID, workflow type, selected item count, dropped count, available citations, and selected memory IDs. |
| `answer_delta` | Streams answer text. Provider deltas use `source=provider`; deterministic/final parity deltas omit the source or use `source=validated_final`. |
| `proposal_created` | Returns proposal tool name, invocation ID, approval request ID, risk, and action-card linkage when the user asks for a state-changing action. |
| `metadata` | Returns final run metadata, citation count, proposal IDs, and context-pack ID before the final payload. |
| `timeout` | Emits a safe timeout disposition before the final fallback payload. |
| `error` | Emits a recoverable stream error payload. |
| `final` | Returns the complete `GuideChatResponseRead` shape used by the non-streaming guide contract. |

The frontend treats `final` as authoritative. Deltas are only progressive UI
state; action cards, citations, related entities, confidence, proposal IDs, and
run IDs come from the final payload.

## Ordering And Parity

Expected evidence-backed ordering is:

```text
message_started
-> retrieval_started
-> tool_call_started
-> tool_call_completed
-> retrieval_result
-> context_compiled
-> answer_delta...
-> metadata
-> final
```

Proposal requests skip direct mutation and include `proposal_created` before
`metadata` and `final`. Timeout responses emit `timeout`, stream a safe fallback
answer, and still end with `final`. Client cancellation closes the generator and
marks the AI run cancelled.

The non-streaming and streaming guide paths share `GuideChatResponseRead`.
Streaming can expose provider deltas, but the backend validates the completed
model output before final metadata is trusted.

## Governance Boundaries

- `guarded_workflow` applies rate, concurrency, budget, auth, and provider
  egress checks before events are emitted.
- State-changing intents are routed through proposal tools and approval
  requests.
- Retrieved content remains untrusted evidence and citations are filtered to
  retrieved source IDs.
- The frontend keeps stream events behind a collapsed diagnostics control so
  the main workflow stays focused on the answer and next action.

## Verification

Backend guide stream tests:

```bash
cd apps/api && .venv/bin/pytest app/tests/test_guide.py app/tests/test_context_compiler.py app/tests/test_feature_package_boundaries.py -q
```

Frontend checks when npm registry access is available:

```bash
pnpm --filter thesys-web typecheck
pnpm --filter thesys-web test
```

Browser QA for Sprint 60 should cover deterministic deltas, provider deltas,
retrieval/tool/proposal events, cancellation, timeout fallback, final metadata
parity, action cards, collapsed citation drilldowns, and no clutter in the main
project workflow.

## Current Limits

- Provider streaming depends on the configured LiteLLM provider supporting
  streamed chat completion deltas.
- Web typecheck, tests, and browser QA remain environment-dependent when npm
  registry access is unstable.
- The UI stores recent guide turns client-side for the current session; long
  term conversational memory is represented as governed project memory, not raw
  chat transcript persistence.

"use client";

import {
  ArrowRight,
  Bell,
  Compass,
  HelpCircle,
  MessageSquare,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  dismissProjectNudge,
  executeGuideAction,
  getGuideRecommendation,
  getProjectNudges,
  GuideAction,
  GuideCitationDetail,
  GuideChatResponse,
  GuideChatTurn,
  GuideStreamEventName,
  ProjectNudge,
  streamProjectGuide,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function GuidePanel({
  className,
  onAction,
  projectId,
}: {
  className?: string;
  onAction: (action: GuideAction) => void;
  projectId: string;
}) {
  const [message, setMessage] = useState("");
  const [chatResponse, setChatResponse] = useState<GuideChatResponse | null>(null);
  const [recentTurns, setRecentTurns] = useState<GuideChatTurn[]>([]);
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [streamEvents, setStreamEvents] = useState<
    { event: GuideStreamEventName; payload: Record<string, unknown> }[]
  >([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const queryClient = useQueryClient();
  const guideQuery = useQuery({
    queryKey: ["projects", projectId, "guide", "recommendation"],
    queryFn: () => getGuideRecommendation(projectId),
  });
  const nudgesQuery = useQuery({
    queryKey: ["projects", projectId, "nudges"],
    queryFn: () => getProjectNudges(projectId),
  });
  const actionMutation = useMutation({
    mutationFn: (action: GuideAction) => executeGuideAction(projectId, action.id),
    onSuccess: (action) => onAction(action),
  });
  const dismissNudgeMutation = useMutation({
    mutationFn: (nudgeId: string) => dismissProjectNudge(projectId, nudgeId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "nudges"] });
    },
  });
  async function askGuide(question: string) {
    const controller = new AbortController();
    setActiveController(controller);
    setChatResponse(null);
    setStreamedAnswer("");
    setStreamEvents([]);
    setStreamError(null);
    setIsStreaming(true);
    try {
      const response = await streamProjectGuide(
        projectId,
        question,
        recentTurns,
        {
          onEvent: (event, payload) => {
            setStreamEvents((events) => [...events, { event, payload }].slice(-16));
          },
          onDelta: (text) => setStreamedAnswer((answer) => `${answer}${text}`),
          onFinal: (response) => setChatResponse(response),
          onError: (payload) => {
            const detail =
              typeof payload.message === "string"
                ? payload.message
                : "Ask Thesys could not finish the streamed answer.";
            setStreamError(detail);
          },
        },
        controller.signal,
      );
      setChatResponse(response);
      const newTurns: GuideChatTurn[] = [
        { role: "user", content: question },
        { role: "assistant", content: response.answer },
      ];
      setRecentTurns((turns) => [...turns, ...newTurns].slice(-6));
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setStreamError("Guide request cancelled.");
      } else {
        setStreamError(error instanceof Error ? error.message : "Guide request failed.");
      }
    } finally {
      setIsStreaming(false);
      setActiveController(null);
    }
  }

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = message.trim();
    if (!question) {
      return;
    }
    void askGuide(question);
    setMessage("");
  }

  function askSuggestedQuestion(question: string) {
    setMessage("");
    void askGuide(question);
  }

  function cancelGuideStream() {
    setStreamEvents((events) => [
      ...events,
      { event: "cancelled", payload: { reason: "client_cancelled" } },
    ]);
    activeController?.abort();
  }

  return (
    <aside
      aria-label="Thesys Guide"
      className={cn(
        "min-w-0 rounded-lg border border-border bg-card p-4 lg:sticky lg:top-5 lg:self-start",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-primary/10 p-2 text-primary">
          <Compass className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">Guide</p>
          <h2 className="text-base font-semibold">Action router</h2>
        </div>
      </div>

      {guideQuery.isLoading ? (
        <GuidePanelSkeleton />
      ) : guideQuery.isError ? (
        <div className="mt-4 rounded-md border border-danger-border bg-danger-muted p-3">
          <p className="text-sm font-medium text-danger-foreground">Guide unavailable</p>
          <p className="mt-1 text-xs leading-5 text-danger-foreground">
            {(guideQuery.error as Error).message}
          </p>
          <Button
            className="mt-3 w-full border-danger-border text-danger-foreground hover:bg-danger-muted"
            onClick={() => void guideQuery.refetch()}
            size="sm"
            type="button"
            variant="secondary"
          >
            Retry guide
          </Button>
        </div>
      ) : guideQuery.data ? (
        <div className="mt-4 space-y-4">
          <section>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              What matters now
            </p>
            <p className="mt-1 text-sm font-medium leading-6">{guideQuery.data.current_focus}</p>
          </section>

          <section>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Why
            </p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {guideQuery.data.why_this_matters}
            </p>
          </section>

          {nudgesQuery.data && nudgesQuery.data.length > 0 ? (
            <section>
              <div className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Nudges</h3>
              </div>
              <div className="mt-2 grid gap-2">
                {nudgesQuery.data.slice(0, 2).map((nudge) => (
                  <GuideNudgeCard
                    disabled={dismissNudgeMutation.isPending}
                    key={nudge.id}
                    nudge={nudge}
                    onAction={() => onAction(nudge.action)}
                    onDismiss={() => dismissNudgeMutation.mutate(nudge.id)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <section className="rounded-md border border-border bg-background p-3">
            <p className="text-xs font-medium text-muted-foreground">Do this next</p>
            <button
              className="mt-2 flex w-full cursor-pointer items-start justify-between gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              disabled={actionMutation.isPending}
              onClick={() => actionMutation.mutate(guideQuery.data.recommended_action)}
              type="button"
            >
              <span className="min-w-0">
                <span className="block text-sm font-semibold">
                  {guideQuery.data.recommended_action.label}
                </span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  {guideQuery.data.recommended_action.description}
                </span>
                <span className="mt-2 block text-xs leading-5 text-muted-foreground">
                  {guideQuery.data.recommended_action.why_it_matters}
                </span>
              </span>
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            </button>
          </section>

          <section>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              After that
            </p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              {guideQuery.data.after_that}
            </p>
          </section>

          {guideQuery.data.secondary_actions.length > 0 ? (
            <section>
              <p className="text-xs font-medium text-muted-foreground">Actions</p>
              <div className="mt-2 grid gap-2">
                {guideQuery.data.secondary_actions.map((action) => (
                  <GuideActionButton
                    action={action}
                    disabled={actionMutation.isPending}
                    key={action.id}
                    onClick={() => actionMutation.mutate(action)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <section>
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Ask Thesys</h3>
            </div>
            <form className="mt-2 flex gap-2" onSubmit={submitMessage}>
              <input
                className="min-h-11 min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-focus"
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Ask what to do next..."
                value={message}
              />
              <Button
                aria-label="Ask guide"
                disabled={isStreaming || !message.trim()}
                size="icon"
                type="submit"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
              </Button>
            </form>

            <div className="mt-2 flex flex-wrap gap-2">
              {guideQuery.data.suggested_questions.slice(0, 6).map((question) => (
                <button
                  className="rounded-md border border-border px-2 py-1 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  disabled={isStreaming}
                  key={question}
                  onClick={() => askSuggestedQuestion(question)}
                  type="button"
                >
                  {question}
                </button>
              ))}
            </div>
          </section>

          {isStreaming || streamedAnswer || chatResponse || streamError ? (
            <section className="rounded-md border border-border bg-background p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
                  <p className="text-xs font-medium text-muted-foreground">Guide answer</p>
                </div>
                {isStreaming ? (
                  <button
                    aria-label="Cancel guide response"
                    className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                    onClick={cancelGuideStream}
                    type="button"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                ) : null}
              </div>
              {streamError ? (
                <p className="mt-2 text-xs leading-5 text-danger-foreground">{streamError}</p>
              ) : null}
              <p className="mt-2 min-h-6 text-sm leading-6">
                {streamedAnswer || chatResponse?.answer || "Thinking through this project..."}
              </p>
              {streamEvents.length > 0 ? <GuideStreamEvents events={streamEvents} /> : null}
              {chatResponse ? <GuideAnswerMetadata response={chatResponse} /> : null}
              {chatResponse?.recommended_action ? (
                <div className="mt-3 rounded-md border border-primary/30 bg-primary/10 p-3">
                  <p className="text-xs font-medium text-primary">Recommended action</p>
                  <GuideActionButton
                    action={chatResponse.recommended_action}
                    disabled={actionMutation.isPending}
                    onClick={() => actionMutation.mutate(chatResponse.recommended_action!)}
                  />
                </div>
              ) : null}
              {chatResponse && chatResponse.action_cards.length > 0 ? (
                <div className="mt-3 grid gap-2">
                  {chatResponse.action_cards
                    .filter((action) => action.id !== chatResponse.recommended_action?.id)
                    .slice(0, 3)
                    .map((action) => (
                      <GuideActionButton
                        action={action}
                        disabled={actionMutation.isPending}
                        key={action.id}
                        onClick={() => actionMutation.mutate(action)}
                      />
                    ))}
                </div>
              ) : null}
              {chatResponse && chatResponse.related_entities.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {chatResponse.related_entities.map((entity) => (
                    <span
                      className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                      key={`${entity.type}:${entity.id}`}
                    >
                      {entity.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}

function GuideStreamEvents({
  events,
}: {
  events: { event: GuideStreamEventName; payload: Record<string, unknown> }[];
}) {
  const latest = events[events.length - 1];
  return (
    <details className="mt-2 rounded-md border border-border bg-muted/30 p-2 text-xs text-muted-foreground">
      <summary className="cursor-pointer select-none">
        {latest ? formatGuideLabel(latest.event) : "Progress"}
      </summary>
      <ol className="mt-2 space-y-1">
        {events.slice(-8).map((item, index) => (
          <li className="flex items-center justify-between gap-3" key={`${item.event}:${index}`}>
            <span>{formatGuideLabel(item.event)}</span>
            <span className="truncate text-right text-foreground">{eventPayloadSummary(item)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

// The guide keeps the default surface short, but this metadata block exposes
// grounding, approvals, and context-pack budgeting when an interviewer or
// developer wants to inspect how an answer was formed.
function GuideAnswerMetadata({ response }: { response: GuideChatResponse }) {
  const contextSummary = contextPackSummary(response.context_pack);
  const hasGrounding =
    response.used_llm ||
    response.cited_evidence_ids.length > 0 ||
    response.citation_details.length > 0 ||
    response.unsupported_or_missing_evidence.length > 0 ||
    contextSummary !== null ||
    response.approval_request_id !== null ||
    response.ai_run_id;
  if (!hasGrounding) {
    return null;
  }

  return (
    <div className="mt-3 rounded-md border border-border bg-muted/40 p-2">
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span>{response.used_llm ? "Grounded LLM" : "Deterministic guide"}</span>
        <span>Confidence: {formatGuideLabel(response.confidence_level)}</span>
        <span>{response.cited_evidence_ids.length} cited source(s)</span>
        {response.ai_run_id ? <span>Trace: {response.ai_run_id.slice(0, 8)}</span> : null}
        {response.approval_request_id ? (
          <span>Approval: {response.approval_request_id.slice(0, 8)}</span>
        ) : null}
      </div>
      {response.unsupported_or_missing_evidence.length > 0 ? (
        <ul className="mt-2 space-y-1 text-xs leading-5 text-muted-foreground">
          {response.unsupported_or_missing_evidence.slice(0, 2).map((item) => (
            <li key={item}>Missing: {item}</li>
          ))}
        </ul>
      ) : null}
      {response.citation_details.length > 0 ? (
        <details className="mt-2 text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">Citations</summary>
          <div className="mt-2 space-y-2">
            {response.citation_details.slice(0, 4).map((citation) => (
              <div className="rounded-md border border-border bg-background p-2" key={citation.source_id}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">
                      {citation.title || "Retrieved evidence"}
                    </p>
                    <p className="mt-0.5 text-muted-foreground">
                      {formatGuideLabel(citation.source_type || "source")} /{" "}
                      {formatGuideLabel(citation.verifier_status)}
                    </p>
                  </div>
                  <span className="shrink-0 text-muted-foreground">
                    {shortId(citation.source_id)}
                  </span>
                </div>
                {citation.url ? (
                  <a
                    className="mt-1 block truncate text-primary hover:underline"
                    href={citation.url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {citation.url}
                  </a>
                ) : null}
                {citation.excerpt ? (
                  <p className="mt-2 line-clamp-3 leading-5 text-muted-foreground">
                    {citation.excerpt}
                  </p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2 text-muted-foreground">
                  {citation.chunk_id ? <span>Chunk {shortId(citation.chunk_id)}</span> : null}
                  <span>{citation.context_item_ids.length} context item(s)</span>
                  <span>{citation.memory_ids.length} memory item(s)</span>
                </div>
                <GuideCitationProvenance citation={citation} />
              </div>
            ))}
          </div>
        </details>
      ) : null}
      {contextSummary ? (
        <details className="mt-2 text-xs text-muted-foreground">
          <summary className="cursor-pointer select-none">Context pack</summary>
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
            <dt>Items</dt>
            <dd className="text-right text-foreground">{contextSummary.itemCount}</dd>
            <dt>Dropped</dt>
            <dd className="text-right text-foreground">{contextSummary.droppedCount}</dd>
            <dt>Tokens</dt>
            <dd className="text-right text-foreground">
              {contextSummary.tokenCount}/{contextSummary.tokenBudget}
            </dd>
          </dl>
        </details>
      ) : null}
    </div>
  );
}

function GuideCitationProvenance({ citation }: { citation: GuideCitationDetail }) {
  const entries = guideCitationMetadataEntries(citation);
  if (entries.length === 0) {
    return null;
  }
  return (
    <details className="mt-2 border-t border-border pt-2">
      <summary className="cursor-pointer select-none">Provenance</summary>
      <dl className="mt-2 grid gap-1">
        {entries.map(([label, value]) => (
          <div key={label} className="grid gap-1 sm:grid-cols-[120px_minmax(0,1fr)]">
            <dt className="font-medium text-foreground">{label}</dt>
            <dd className="min-w-0 break-words">{value}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

// Context packs are returned as generic JSON so the UI can remain decoupled
// from backend context-engineering internals while still showing budget health.
function contextPackSummary(contextPack: Record<string, unknown> | null) {
  if (!contextPack) {
    return null;
  }
  const items = Array.isArray(contextPack.items) ? contextPack.items.length : 0;
  const dropped = Array.isArray(contextPack.dropped_items)
    ? contextPack.dropped_items.length
    : 0;
  const policy =
    contextPack.policy && typeof contextPack.policy === "object"
      ? (contextPack.policy as Record<string, unknown>)
      : {};
  return {
    itemCount: items,
    droppedCount: dropped,
    tokenCount: Number(contextPack.token_count ?? 0),
    tokenBudget: Number(policy.token_budget ?? 0),
  };
}

function eventPayloadSummary({
  event,
  payload,
}: {
  event: GuideStreamEventName;
  payload: Record<string, unknown>;
}) {
  if (event === "answer_delta" && typeof payload.text === "string") {
    return payload.text.slice(0, 32);
  }
  if (typeof payload.tool_name === "string") {
    return payload.tool_name;
  }
  if (typeof payload.phase === "string") {
    return payload.phase;
  }
  if (typeof payload.result_count === "number") {
    return `${payload.result_count} result(s)`;
  }
  if (typeof payload.context_pack_id === "string") {
    return shortId(payload.context_pack_id);
  }
  if (typeof payload.ai_run_id === "string") {
    return shortId(payload.ai_run_id);
  }
  return "";
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function guideCitationMetadataEntries(citation: GuideCitationDetail) {
  const entries: Array<readonly [string, string]> = [];
  addGuideMetadataEntry(entries, "Extraction", citation.extraction.extraction_method);
  addGuideMetadataEntry(entries, "Confidence", citation.extraction.extraction_confidence);
  addGuideMetadataEntry(entries, "Source quality", citation.source_quality.explanation);
  addGuideMetadataEntry(entries, "Quality risk", citation.source_quality.risk_level);
  addGuideMetadataEntry(entries, "Snapshot", citation.provenance.source_snapshot_id);
  addGuideMetadataEntry(entries, "Page", citation.page_number);
  addGuideMetadataEntry(entries, "Section", citation.section_heading);
  addGuideMetadataEntry(entries, "Table", citation.table_id);
  addGuideMetadataEntry(entries, "Region", citation.region);
  addGuideMetadataEntry(entries, "Quote offsets", citation.quote_offsets);
  addGuideMetadataEntry(entries, "Warnings", citation.warnings);
  return entries;
}

function addGuideMetadataEntry(
  entries: Array<readonly [string, string]>,
  label: string,
  value: unknown,
) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  entries.push([label, formatGuideMetadataValue(value)] as const);
}

function formatGuideMetadataValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(", ") : "None";
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}

function GuideNudgeCard({
  disabled,
  nudge,
  onAction,
  onDismiss,
}: {
  disabled: boolean;
  nudge: ProjectNudge;
  onAction: () => void;
  onDismiss: () => void;
}) {
  return (
    <section className={cn("rounded-md border p-3", nudgeToneClass(nudge.severity))}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{nudge.title}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{nudge.message}</p>
        </div>
        <button
          aria-label={`Dismiss ${nudge.title}`}
          className="rounded-md p-1 text-muted-foreground hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          disabled={disabled}
          onClick={onDismiss}
          type="button"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
        {nudge.why_it_matters}
      </p>
      <Button
        className="mt-3 min-h-10 w-full"
        onClick={onAction}
        size="sm"
        type="button"
        variant={nudge.severity === "action_required" ? "default" : "secondary"}
      >
        {nudge.action.label}
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Button>
    </section>
  );
}

function GuideActionButton({
  action,
  disabled,
  onClick,
}: {
  action: GuideAction;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="flex min-h-11 w-full cursor-pointer items-start justify-between gap-3 rounded-md border border-border px-3 py-2 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-60"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">{action.label}</span>
        <span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-muted-foreground">
          {action.why_it_matters}
        </span>
      </span>
      {action.type === "explain" ? (
        <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      ) : (
        <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
      )}
    </button>
  );
}

function nudgeToneClass(severity: ProjectNudge["severity"]) {
  if (severity === "action_required") {
    return "border-warning-border bg-warning-muted";
  }
  if (severity === "warning") {
    return "border-warning-border bg-background";
  }
  return "border-border bg-background";
}

function formatGuideLabel(value: string) {
  return value.replaceAll("_", " ");
}

function GuidePanelSkeleton() {
  return (
    <div className="mt-4 animate-pulse space-y-4 motion-reduce:animate-none">
      <div>
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="mt-2 h-5 w-full rounded bg-muted" />
        <div className="mt-2 h-4 w-5/6 rounded bg-muted" />
      </div>
      <div className="h-24 rounded-md bg-muted" />
      <div className="space-y-2">
        <div className="h-11 rounded-md bg-muted" />
        <div className="h-11 rounded-md bg-muted" />
      </div>
    </div>
  );
}

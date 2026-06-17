"use client";

import { Check, Compass, Edit3, GitBranch, Lightbulb, Save, Search, Target, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  getThesisCanvas,
  generateWedgeOptions,
  listWedgeOptions,
  rejectWedgeOption,
  researchWedgeOptionLater,
  selectWedgeOption,
  ThesisCanvas,
  ThesisEvolutionEvent,
  testWedgeOption,
  updateThesisCanvas,
  UpdateThesisCanvasInput,
  WedgeOption,
} from "@/lib/api";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import { MarkdownContent } from "@/features/projects/markdown-content";

type ThesisTabProps = {
  activeAnchor?: string | null;
  projectId: string;
};

type ThesisDraft = Pick<
  ThesisCanvas,
  | "current_thesis"
  | "target_user"
  | "problem"
  | "current_workaround"
  | "proposed_solution"
  | "wedge"
  | "biggest_unknown"
  | "proof_needed"
  | "rejected_directions"
  | "open_questions"
> & {
  change_reason: string;
};

export function ThesisTab({ activeAnchor, projectId }: ThesisTabProps) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ThesisDraft | null>(null);
  const query = useQuery({
    queryKey: ["projects", projectId, "thesis-canvas"],
    queryFn: () => getThesisCanvas(projectId),
  });
  const mutation = useMutation({
    mutationFn: (input: UpdateThesisCanvasInput) => updateThesisCanvas(projectId, input),
    onSuccess: async (data) => {
      setDraft(draftFromCanvas(data.canvas));
      setEditing(false);
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "guide"],
        refetchType: "active",
      });
    },
  });

  useEffect(() => {
    if (query.data?.canvas && !editing) {
      setDraft(draftFromCanvas(query.data.canvas));
    }
  }, [editing, query.data?.canvas]);

  useEffect(() => {
    if (!activeAnchor) {
      return;
    }
    window.setTimeout(() => {
      document.getElementById(activeAnchor)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 50);
  }, [activeAnchor]);

  if (query.isLoading) {
    return <ThesisSkeleton />;
  }

  if (query.isError) {
    return (
      <DomainError
        action={
          <Button onClick={() => void query.refetch()} size="sm" type="button" variant="secondary">
            Retry thesis
          </Button>
        }
        message={(query.error as Error).message}
      />
    );
  }

  const detail = query.data;
  if (!detail || !draft) {
    return null;
  }
  const canvas = detail.canvas;

  function saveCanvas() {
    if (!draft) {
      return;
    }
    mutation.mutate({
      ...draft,
      rejected_directions: cleanList(draft.rejected_directions),
      open_questions: cleanList(draft.open_questions),
      change_reason: draft.change_reason.trim() || undefined,
    });
  }

  return (
    <section className="space-y-6">
      <DomainHeader
        action={
          editing ? (
            <div className="flex gap-2">
              <Button
                disabled={mutation.isPending}
                onClick={saveCanvas}
                size="sm"
                type="button"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
                {mutation.isPending ? "Saving..." : "Save thesis"}
              </Button>
              <Button
                disabled={mutation.isPending}
                onClick={() => {
                  setDraft(draftFromCanvas(canvas));
                  setEditing(false);
                }}
                size="sm"
                type="button"
                variant="secondary"
              >
                <X className="h-4 w-4" aria-hidden="true" />
                Cancel
              </Button>
            </div>
          ) : (
            <Button onClick={() => setEditing(true)} size="sm" type="button">
              <Edit3 className="h-4 w-4" aria-hidden="true" />
              Edit thesis
            </Button>
          )
        }
        description="Keep the current thesis, wedge, biggest unknown, proof needed, rejected directions, and open questions in one place."
        icon={<Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="How has this idea grown?"
        signals={[
          { label: "Rejected directions", value: canvas.rejected_directions.length },
          { label: "Open questions", value: canvas.open_questions.length },
          { label: "Timeline events", value: detail.evolution.length },
        ]}
        title="Thesis"
      />

      <DomainPanel id="thesis-canvas">
        <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Thesis Canvas</h2>
            </div>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Use this as the short version of what the idea is becoming.
            </p>
          </div>
          {editing ? (
            <span className="w-fit rounded-md bg-warning-muted px-2 py-1 text-xs font-medium text-warning-foreground">
              Editing
            </span>
          ) : (
            <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground">
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
              Saved
            </span>
          )}
        </div>

        <div className="mt-5 grid gap-5">
          <CanvasReadOnlyBlock label="Original idea" value={canvas.original_idea} />

          {editing ? (
            <>
              <CanvasTextarea
                label="Current thesis"
                onChange={(value) => setDraft({ ...draft, current_thesis: value })}
                value={draft.current_thesis}
              />
              <div className="grid gap-4 md:grid-cols-2">
                <CanvasTextarea
                  label="Who is it for?"
                  onChange={(value) => setDraft({ ...draft, target_user: value })}
                  value={draft.target_user}
                />
                <CanvasTextarea
                  label="What problem hurts?"
                  onChange={(value) => setDraft({ ...draft, problem: value })}
                  value={draft.problem}
                />
                <CanvasTextarea
                  label="What do they do today?"
                  onChange={(value) => setDraft({ ...draft, current_workaround: value })}
                  value={draft.current_workaround}
                />
                <CanvasTextarea
                  label="Proposed solution"
                  onChange={(value) => setDraft({ ...draft, proposed_solution: value })}
                  value={draft.proposed_solution}
                />
                <CanvasTextarea
                  label="What is the wedge?"
                  onChange={(value) => setDraft({ ...draft, wedge: value })}
                  value={draft.wedge}
                />
                <CanvasTextarea
                  label="What is the biggest unknown?"
                  onChange={(value) => setDraft({ ...draft, biggest_unknown: value })}
                  value={draft.biggest_unknown}
                />
              </div>
              <CanvasTextarea
                label="What proof would change our mind?"
                onChange={(value) => setDraft({ ...draft, proof_needed: value })}
                value={draft.proof_needed}
              />
              <CanvasListEditor
                label="Rejected directions"
                onChange={(values) => setDraft({ ...draft, rejected_directions: values })}
                values={draft.rejected_directions}
              />
              <CanvasListEditor
                label="Open questions"
                onChange={(values) => setDraft({ ...draft, open_questions: values })}
                values={draft.open_questions}
              />
              <CanvasTextarea
                label="Why did this change?"
                onChange={(value) => setDraft({ ...draft, change_reason: value })}
                value={draft.change_reason}
              />
              {mutation.error ? (
                <DomainError message={(mutation.error as Error).message} />
              ) : null}
              <div className="flex flex-wrap gap-3">
                <Button disabled={mutation.isPending} onClick={saveCanvas} type="button">
                  <Save className="h-4 w-4" aria-hidden="true" />
                  {mutation.isPending ? "Saving thesis..." : "Save thesis"}
                </Button>
                <Button
                  disabled={mutation.isPending}
                  onClick={() => {
                    setDraft(draftFromCanvas(canvas));
                    setEditing(false);
                  }}
                  type="button"
                  variant="secondary"
                >
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <>
              <CanvasReadOnlyBlock label="Current thesis" value={canvas.current_thesis} large />
              <div className="grid gap-4 md:grid-cols-2">
                <CanvasReadOnlyBlock label="Who is it for?" value={canvas.target_user} />
                <CanvasReadOnlyBlock label="What problem hurts?" value={canvas.problem} />
                <CanvasReadOnlyBlock label="What do they do today?" value={canvas.current_workaround} />
                <CanvasReadOnlyBlock label="Proposed solution" value={canvas.proposed_solution} />
                <CanvasReadOnlyBlock label="What is the wedge?" value={canvas.wedge} />
                <CanvasReadOnlyBlock label="What is the biggest unknown?" value={canvas.biggest_unknown} />
              </div>
              <CanvasReadOnlyBlock label="What proof would change our mind?" value={canvas.proof_needed} />
              <CanvasListBlock label="Rejected directions" values={canvas.rejected_directions} />
              <CanvasListBlock label="Open questions" values={canvas.open_questions} />
            </>
          )}
        </div>
      </DomainPanel>

      <WedgeExplorer projectId={projectId} />

      <DomainPanel id="thesis-evolution">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 className="text-base font-semibold">Thesis Evolution</h2>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          The decision trail for how the idea moved from rough thought to current thesis.
        </p>
        <div className="mt-5">
          <ThesisTimeline events={detail.evolution} />
        </div>
      </DomainPanel>
    </section>
  );
}

function WedgeExplorer({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["projects", projectId, "wedges"],
    queryFn: () => listWedgeOptions(projectId),
  });
  const generateMutation = useMutation({
    mutationFn: () => generateWedgeOptions(projectId),
    onSuccess: async () => {
      setNotice("Wedge options refreshed from the current thesis, research, and validation context.");
      await invalidateWedgeState(queryClient, projectId);
    },
  });
  const actionMutation = useMutation({
    mutationFn: ({ action, wedgeId }: { action: WedgeActionKind; wedgeId: string }) => {
      if (action === "select") {
        return selectWedgeOption(projectId, wedgeId);
      }
      if (action === "test") {
        return testWedgeOption(projectId, wedgeId);
      }
      if (action === "research") {
        return researchWedgeOptionLater(projectId, wedgeId);
      }
      return rejectWedgeOption(projectId, wedgeId);
    },
    onSuccess: async (result) => {
      setNotice(result.message);
      await invalidateWedgeState(queryClient, projectId);
    },
  });

  const wedges = query.data?.wedges ?? [];
  const recommended = wedges.find((wedge) => wedge.id === query.data?.recommended_wedge_id);
  const defaultWedges = defaultWedgeOptions(wedges, query.data?.recommended_wedge_id ?? null);

  return (
    <DomainPanel id="wedge-explorer">
      <div className="flex flex-col gap-3 border-b border-border pb-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Wedge Explorer</h2>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Compare possible directions before committing the thesis to a validation path.
          </p>
        </div>
        <Button
          disabled={generateMutation.isPending || actionMutation.isPending}
          onClick={() => generateMutation.mutate()}
          size="sm"
          type="button"
        >
          <Compass className="h-4 w-4" aria-hidden="true" />
          {wedges.length > 0 ? "Refresh wedges" : "Generate wedges"}
        </Button>
      </div>

      {query.isLoading ? (
        <div className="mt-5 grid gap-3">
          <div className="h-20 animate-pulse rounded-md bg-muted motion-reduce:animate-none" />
          <div className="h-20 animate-pulse rounded-md bg-muted motion-reduce:animate-none" />
        </div>
      ) : query.isError ? (
        <div className="mt-5">
          <DomainError
            action={
              <Button onClick={() => void query.refetch()} size="sm" type="button" variant="secondary">
                Retry wedges
              </Button>
            }
            message={(query.error as Error).message}
          />
        </div>
      ) : wedges.length === 0 ? (
        <div className="mt-5 rounded-md bg-surface px-3 py-3">
          <p className="text-sm font-medium">No wedge options yet.</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Generate options to compare the current thesis against narrower, easier-to-test directions.
          </p>
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          {recommended ? (
            <div className="rounded-md border border-success-border bg-success-muted px-3 py-3">
              <p className="text-xs font-medium uppercase tracking-normal text-success-foreground">
                Recommended wedge
              </p>
              <h3 className="mt-2 text-base font-semibold text-foreground">{recommended.name}</h3>
              <p className="mt-2 text-sm leading-6 text-success-foreground">
                {recommended.why_it_might_work}
              </p>
            </div>
          ) : null}

          <div className="grid gap-3">
            {defaultWedges.map((wedge) => (
              <WedgeFocusCard
                disabled={actionMutation.isPending || generateMutation.isPending}
                key={wedge.id}
                onAction={(action) => actionMutation.mutate({ action, wedgeId: wedge.id })}
                wedge={wedge}
              />
            ))}
          </div>

          {wedges.length > defaultWedges.length ? (
            <details className="rounded-md border border-border bg-background p-3">
              <summary className="cursor-pointer list-none rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold">Compare all wedges</p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      Inspect every generated direction, including pressure and evidence details.
                    </p>
                  </div>
                  <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                    {wedges.length} options
                  </span>
                </div>
              </summary>
              <div className="mt-4 divide-y divide-border rounded-md border border-border">
                {wedges.map((wedge) => (
                  <WedgeRow
                    disabled={actionMutation.isPending || generateMutation.isPending}
                    key={wedge.id}
                    onAction={(action) => actionMutation.mutate({ action, wedgeId: wedge.id })}
                    wedge={wedge}
                  />
                ))}
              </div>
            </details>
          ) : null}
        </div>
      )}

      {notice ? (
        <p className="mt-4 rounded-md bg-primary/10 px-3 py-2 text-sm leading-6 text-foreground">
          {notice}
        </p>
      ) : null}
      {generateMutation.error || actionMutation.error ? (
        <div className="mt-4">
          <DomainError
            message={((generateMutation.error || actionMutation.error) as Error).message}
          />
        </div>
      ) : null}
    </DomainPanel>
  );
}

type WedgeActionKind = "select" | "test" | "research" | "reject";

function WedgeFocusCard({
  disabled,
  onAction,
  wedge,
}: {
  disabled: boolean;
  onAction: (action: WedgeActionKind) => void;
  wedge: WedgeOption;
}) {
  const isRecommended = wedge.recommendation === "recommended";
  const isAvoided = wedge.recommendation === "avoid_for_now" || wedge.recommendation === "rejected";
  const primaryAction: WedgeActionKind = isAvoided
    ? "reject"
    : wedge.recommendation === "research_later"
      ? "research"
      : isRecommended
        ? "test"
        : "select";
  return (
    <article
      className={[
        "grid gap-4 rounded-md border px-3 py-4 lg:grid-cols-[minmax(0,1fr)_180px]",
        isRecommended ? "border-success-border bg-success-muted" : "border-border bg-background",
      ].join(" ")}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{wedge.name}</h3>
          <span className={recommendationPillClass(wedge.recommendation)}>
            {formatRecommendation(wedge.recommendation)}
          </span>
        </div>
        <dl className="mt-3 grid gap-3 text-sm">
          <WedgeFact label="Why it might work" value={wedge.why_it_might_work} />
          <WedgeFact label="Main risk" value={wedge.main_risk} />
          <WedgeFact label="First proof" value={wedge.validation_test} />
        </dl>
      </div>
      <div className="grid content-start gap-2">
        <Button
          disabled={disabled || wedge.recommendation === "rejected"}
          onClick={() => onAction(primaryAction)}
          size="sm"
          type="button"
          variant={isRecommended ? "default" : "secondary"}
        >
          {primaryAction === "test" ? (
            <Target className="h-4 w-4" aria-hidden="true" />
          ) : primaryAction === "research" ? (
            <Search className="h-4 w-4" aria-hidden="true" />
          ) : primaryAction === "reject" ? (
            <X className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Check className="h-4 w-4" aria-hidden="true" />
          )}
          {primaryAction === "test"
            ? "Test this wedge"
            : primaryAction === "research"
              ? "Research later"
              : primaryAction === "reject"
                ? "Avoid for now"
                : "Select wedge"}
        </Button>
        {!isRecommended && wedge.recommendation !== "rejected" ? (
          <Button
            disabled={disabled}
            onClick={() => onAction("select")}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            Select instead
          </Button>
        ) : null}
      </div>
    </article>
  );
}

function WedgeRow({
  disabled,
  onAction,
  wedge,
}: {
  disabled: boolean;
  onAction: (action: WedgeActionKind) => void;
  wedge: WedgeOption;
}) {
  return (
    <article className="grid gap-4 px-3 py-4 lg:grid-cols-[minmax(0,1fr)_220px]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">{wedge.name}</h3>
          <span className={recommendationPillClass(wedge.recommendation)}>
            {formatRecommendation(wedge.recommendation)}
          </span>
        </div>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{wedge.description}</p>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <WedgeFact label="Why it might work" value={wedge.why_it_might_work} />
          <WedgeFact label="Main risk" value={wedge.main_risk} />
          <WedgeFact label="First proof" value={wedge.validation_test} />
          <WedgeFact
            label="Pressure / evidence"
            value={`${formatLabel(wedge.competitor_pressure)} pressure · ${formatLabel(
              wedge.evidence_strength,
            )} evidence`}
          />
        </dl>
      </div>
      <div className="grid content-start gap-2 sm:grid-cols-2 lg:grid-cols-1">
        <Button
          disabled={disabled || wedge.recommendation === "rejected"}
          onClick={() => onAction("select")}
          size="sm"
          type="button"
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          Select wedge
        </Button>
        <Button
          disabled={disabled || wedge.recommendation === "rejected"}
          onClick={() => onAction("test")}
          size="sm"
          type="button"
          variant="secondary"
        >
          <Target className="h-4 w-4" aria-hidden="true" />
          Test this
        </Button>
        <Button
          disabled={disabled || wedge.recommendation === "rejected"}
          onClick={() => onAction("research")}
          size="sm"
          type="button"
          variant="secondary"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          Research more
        </Button>
        <Button
          disabled={disabled || wedge.recommendation === "rejected"}
          onClick={() => onAction("reject")}
          size="sm"
          type="button"
          variant="secondary"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          Reject
        </Button>
      </div>
    </article>
  );
}

export function defaultWedgeOptions(
  wedges: WedgeOption[],
  recommendedWedgeId: string | null,
) {
  const selected: WedgeOption[] = [];
  const pushUnique = (wedge: WedgeOption | undefined) => {
    if (!wedge || selected.some((item) => item.id === wedge.id)) {
      return;
    }
    selected.push(wedge);
  };

  pushUnique(wedges.find((wedge) => wedge.id === recommendedWedgeId));
  pushUnique(wedges.find((wedge) => wedge.recommendation === "recommended"));
  pushUnique(
    wedges.find((wedge) =>
      wedge.recommendation === "avoid_for_now" || wedge.recommendation === "rejected",
    ),
  );
  pushUnique(wedges.find((wedge) => wedge.recommendation === "research_later"));
  pushUnique(wedges.find((wedge) => wedge.recommendation === "promising"));

  for (const wedge of wedges) {
    if (selected.length >= 3) {
      break;
    }
    pushUnique(wedge);
  }
  return selected.slice(0, 3);
}

function WedgeFact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 leading-6 text-foreground">{value}</dd>
    </div>
  );
}

function CanvasReadOnlyBlock({
  label,
  large = false,
  value,
}: {
  label: string;
  large?: boolean;
  value: string;
}) {
  return (
    <div className="rounded-md bg-surface px-3 py-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <MarkdownContent
        className={[
          "mt-2 space-y-2 leading-6 text-foreground",
          large ? "text-base font-semibold" : "text-sm",
        ].join(" ")}
        markdown={value || "Not captured yet."}
      />
    </div>
  );
}

function CanvasTextarea({
  label,
  onChange,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <textarea
        className="mt-2 min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-focus"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function CanvasListEditor({
  label,
  onChange,
  values,
}: {
  label: string;
  onChange: (values: string[]) => void;
  values: string[];
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <textarea
        className="mt-2 min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-focus"
        onChange={(event) => onChange(splitLines(event.target.value))}
        placeholder="One item per line"
        value={values.join("\n")}
      />
      <span className="mt-1 block text-xs text-muted-foreground">One item per line.</span>
    </label>
  );
}

function CanvasListBlock({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-md bg-surface px-3 py-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      {values.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-foreground">
          {values.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm leading-6 text-muted-foreground">None recorded yet.</p>
      )}
    </div>
  );
}

function ThesisTimeline({ events }: { events: ThesisEvolutionEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="rounded-md bg-surface px-3 py-3 text-sm leading-6 text-muted-foreground">
        No thesis evolution events yet. Save a thesis change to start the trail.
      </p>
    );
  }

  return (
    <ol className="space-y-4">
      {events.map((event) => (
        <li className="grid gap-3 border-l border-border pl-4" key={event.id}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
              {formatEventType(event.event_type)}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {formatDateTime(event.created_at)}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {formatLabel(event.origin)}
            </span>
          </div>
          <div>
            <h3 className="text-sm font-semibold">{event.title}</h3>
            <MarkdownContent
              className="mt-2 space-y-2 text-sm leading-6 text-foreground"
              markdown={event.change_summary}
            />
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{event.reason}</p>
            {event.source_entity_type ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Source: {formatLabel(event.source_entity_type)}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function ThesisSkeleton() {
  return (
    <div className="animate-pulse space-y-6 motion-reduce:animate-none">
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="h-4 w-28 rounded bg-muted" />
        <div className="mt-3 h-7 w-full max-w-xl rounded bg-muted" />
        <div className="mt-3 h-4 w-full max-w-3xl rounded bg-muted" />
      </div>
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="h-4 w-32 rounded bg-muted" />
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="h-24 rounded-md bg-muted" />
          <div className="h-24 rounded-md bg-muted" />
          <div className="h-24 rounded-md bg-muted" />
          <div className="h-24 rounded-md bg-muted" />
        </div>
      </div>
    </div>
  );
}

function draftFromCanvas(canvas: ThesisCanvas): ThesisDraft {
  return {
    current_thesis: canvas.current_thesis,
    target_user: canvas.target_user,
    problem: canvas.problem,
    current_workaround: canvas.current_workaround,
    proposed_solution: canvas.proposed_solution,
    wedge: canvas.wedge,
    biggest_unknown: canvas.biggest_unknown,
    proof_needed: canvas.proof_needed,
    rejected_directions: canvas.rejected_directions,
    open_questions: canvas.open_questions,
    change_reason: "",
  };
}

function splitLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function cleanList(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function formatEventType(value: string) {
  return formatLabel(value).replace("Thesis", "thesis");
}

function formatLabel(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRecommendation(value: string) {
  return formatLabel(value).replace("For Now", "for now");
}

function recommendationPillClass(value: string) {
  const base = "rounded-md px-2 py-1 text-xs font-medium";
  if (value === "recommended") {
    return `${base} bg-success-muted text-success-foreground`;
  }
  if (value === "avoid_for_now" || value === "rejected") {
    return `${base} bg-danger-muted text-danger-foreground`;
  }
  if (value === "research_later") {
    return `${base} bg-warning-muted text-warning-foreground`;
  }
  return `${base} bg-muted text-muted-foreground`;
}

async function invalidateWedgeState(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
) {
  await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "wedges"] });
  await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "thesis-canvas"] });
  await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
  await queryClient.invalidateQueries({
    queryKey: ["projects", projectId, "guide"],
    refetchType: "active",
  });
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

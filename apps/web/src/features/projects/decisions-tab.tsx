"use client";

import { AlertTriangle, Link2, Plus, ScrollText } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Assumption,
  createDecision,
  DecisionType,
  Experiment,
  getProjectOverview,
  listArtifacts,
  listAssumptions,
  listDecisions,
  listEvidenceSources,
  listExperiments,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";

type DecisionsTabProps = {
  projectId: string;
};

const decisionTypes: DecisionType[] = [
  "build",
  "pivot",
  "pause",
  "kill",
  "change_icp",
  "change_positioning",
  "run_experiment",
  "other",
];

export function DecisionsTab({ projectId }: DecisionsTabProps) {
  const queryClient = useQueryClient();
  const [decisionType, setDecisionType] = useState<DecisionType>("run_experiment");
  const [title, setTitle] = useState("");
  const [rationale, setRationale] = useState("");
  const [expectedOutcome, setExpectedOutcome] = useState("");
  const [reviewDate, setReviewDate] = useState("");
  const [linkedAssumptions, setLinkedAssumptions] = useState<string[]>([]);
  const [linkedEvidence, setLinkedEvidence] = useState<string[]>([]);
  const [linkedArtifacts, setLinkedArtifacts] = useState<string[]>([]);
  const [linkedExperiments, setLinkedExperiments] = useState<string[]>([]);

  const decisionsQuery = useQuery({
    queryKey: ["projects", projectId, "decisions"],
    queryFn: () => listDecisions(projectId),
  });
  const assumptionsQuery = useQuery({
    queryKey: ["projects", projectId, "assumptions"],
    queryFn: () => listAssumptions(projectId),
  });
  const evidenceQuery = useQuery({
    queryKey: ["projects", projectId, "evidence"],
    queryFn: () => listEvidenceSources(projectId),
  });
  const artifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts"],
    queryFn: () => listArtifacts(projectId),
  });
  const experimentsQuery = useQuery({
    queryKey: ["projects", projectId, "experiments"],
    queryFn: () => listExperiments(projectId),
  });
  const overviewQuery = useQuery({
    queryKey: ["projects", projectId, "overview", "decision-recommendation"],
    queryFn: () => getProjectOverview(projectId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createDecision(projectId, {
        decision_type: decisionType,
        title,
        rationale: emptyToUndefined(rationale),
        expected_outcome: emptyToUndefined(expectedOutcome),
        review_date: emptyToUndefined(reviewDate),
        linked_assumption_ids: linkedAssumptions,
        linked_evidence_source_ids: linkedEvidence,
        linked_artifact_ids: linkedArtifacts,
        linked_experiment_ids: linkedExperiments,
      }),
    onSuccess: async () => {
      setTitle("");
      setRationale("");
      setExpectedOutcome("");
      setReviewDate("");
      setLinkedAssumptions([]);
      setLinkedEvidence([]);
      setLinkedArtifacts([]);
      setLinkedExperiments([]);
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "decisions"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
    },
  });

  const decisions = decisionsQuery.data ?? [];
  const assumptions = assumptionsQuery.data ?? [];
  const evidence = evidenceQuery.data ?? [];
  const artifacts = artifactsQuery.data ?? [];
  const experiments = experimentsQuery.data ?? [];
  const hasLoggedResults = experiments.some((experiment) => experiment.results.length > 0);
  const suggestedDecision = buildDecisionSuggestion({
    assumptions,
    evidenceCount: evidence.length,
    experiments,
    overview: overviewQuery.data,
  });
  const error =
    decisionsQuery.error ??
    assumptionsQuery.error ??
    evidenceQuery.error ??
    artifactsQuery.error ??
    experimentsQuery.error ??
    overviewQuery.error ??
    createMutation.error ??
    null;

  function openDecisionForm() {
    const panel = document.getElementById("record-decision-panel") as HTMLDetailsElement | null;
    if (panel) {
      panel.open = true;
    }
    window.setTimeout(() => document.getElementById("decision-title")?.focus(), 0);
  }

  function applyDecisionSuggestion(type: DecisionType, label: string) {
    const suggestion = buildDecisionSuggestion({
      assumptions,
      decisionType: type,
      evidenceCount: evidence.length,
      experiments,
      label,
      overview: overviewQuery.data,
    });
    setDecisionType(type);
    setTitle(suggestion.title);
    setRationale(suggestion.rationale);
    setExpectedOutcome(suggestion.expectedOutcome);
    if (suggestion.linkedAssumptionId) {
      setLinkedAssumptions([suggestion.linkedAssumptionId]);
    }
    if (suggestion.linkedExperimentIds.length > 0) {
      setLinkedExperiments(suggestion.linkedExperimentIds);
    }
    openDecisionForm();
  }

  return (
    <section className="mt-6 space-y-6">
      <div className="rounded-lg border border-border bg-white p-5">
        <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
          Decisions
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-normal">
          What did we decide, and why?
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          Record build, pivot, pause, kill, or continue-research decisions with rationale,
          supporting evidence, and a revisit trigger.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex items-center gap-2">
          <ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />
          <h3 className="text-base font-semibold">Recommended Decision</h3>
        </div>
        <p className="mt-3 text-lg font-semibold leading-7 text-foreground">
          {suggestedDecision.title}
        </p>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
          {suggestedDecision.rationale}
        </p>
        {overviewQuery.data?.current_recommendation.recommendation ? (
          <p className="mt-3 border-l-2 border-primary/50 pl-3 text-sm leading-6 text-muted-foreground">
            Strategic verdict: {overviewQuery.data.current_recommendation.recommendation}
          </p>
        ) : null}
        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="rounded-md border border-border bg-muted/40 p-4">
            <h4 className="text-sm font-semibold">Suggested Decision</h4>
            <p className="mt-2 text-sm font-medium text-foreground">
              {suggestedDecision.title}
            </p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {suggestedDecision.rationale}
            </p>
            {suggestedDecision.missingEvidence.length > 0 ? (
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Do not proceed until: {suggestedDecision.missingEvidence[0]}
              </p>
            ) : null}
            <Button
              className="mt-3"
              onClick={() =>
                applyDecisionSuggestion(suggestedDecision.type, suggestedDecision.actionLabel)
              }
              size="sm"
              type="button"
            >
              Use Suggested Decision
            </Button>
          </div>
          <div className="rounded-md border border-border bg-white p-4">
            <h4 className="text-sm font-semibold">Evidence Required Before Proceeding</h4>
            <div className="mt-3 space-y-2">
              {suggestedDecision.missingEvidence.length === 0 ? (
                <p className="text-sm leading-6 text-muted-foreground">
                  No major missing evidence is flagged, but review the rationale before
                  proceeding.
                </p>
              ) : (
                suggestedDecision.missingEvidence.map((item) => (
                  <p className="text-sm leading-6 text-muted-foreground" key={item}>
                    {item}
                  </p>
                ))
              )}
            </div>
          </div>
        </div>
        {!hasLoggedResults ? (
          <div className="mt-4 flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <p>
              Proceed is premature until at least one validation result is logged. You can
              still record it, but the evidence trail will show the warning.
            </p>
          </div>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {[
            ["build", "Proceed"],
            ["pivot", "Pivot"],
            ["pause", "Pause"],
            ["kill", "Kill"],
            ["run_experiment", "Continue Research"],
          ].map(([type, label]) => (
            <Button
              key={type}
              onClick={() => applyDecisionSuggestion(type as DecisionType, label)}
              size="sm"
              type="button"
              variant="secondary"
            >
              {label}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <details
          className="self-start rounded-lg border border-border bg-white p-5"
          id="record-decision-panel"
        >
          <summary className="cursor-pointer list-none">
            <div className="flex items-center gap-2">
              <Plus className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Record Decision</h2>
            </div>
          </summary>

          <form
            className="mt-5 border-t border-border pt-5"
            onSubmit={(event) => {
              event.preventDefault();
              createMutation.mutate();
            }}
          >

          <label className="mt-4 block">
            <span className="text-sm font-medium">Type</span>
            <select
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setDecisionType(event.target.value as DecisionType)}
              value={decisionType}
            >
              {decisionTypes.map((item) => (
                <option key={item} value={item}>
                  {decisionLabel(item)}
                </option>
              ))}
            </select>
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Title</span>
            <input
              id="decision-title"
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setTitle(event.target.value)}
              value={title}
            />
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Rationale</span>
            <textarea
              className="mt-2 min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setRationale(event.target.value)}
              value={rationale}
            />
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Expected Outcome</span>
            <textarea
              className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setExpectedOutcome(event.target.value)}
              value={expectedOutcome}
            />
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Review Date</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setReviewDate(event.target.value)}
              type="date"
              value={reviewDate}
            />
          </label>

          <div className="mt-5 space-y-4">
            <LinkPicker
              items={assumptions}
              label="Link assumptions"
              onChange={setLinkedAssumptions}
              selected={linkedAssumptions}
              titleFor={(item) => item.text}
            />
            <LinkPicker
              items={evidence}
              label="Link evidence"
              onChange={setLinkedEvidence}
              selected={linkedEvidence}
              titleFor={(item) => item.title ?? item.url ?? item.id}
            />
            <LinkPicker
              items={artifacts}
              label="Link briefs, memos, or plans"
              onChange={setLinkedArtifacts}
              selected={linkedArtifacts}
              titleFor={(item) => item.title}
            />
            <LinkPicker
              items={experiments}
              label="Link experiments"
              onChange={setLinkedExperiments}
              selected={linkedExperiments}
              titleFor={(item) => item.name}
            />
          </div>

          <Button
            className="mt-5"
            disabled={createMutation.isPending || title.trim().length === 0}
            type="submit"
          >
            <ScrollText className="h-4 w-4" aria-hidden="true" />
            {createMutation.isPending ? "Recording..." : "Record Decision"}
          </Button>
          </form>
        </details>

        <div className="self-start rounded-lg border border-border bg-white p-5">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Decision Ledger</h2>
            </div>
            <span className="text-sm text-muted-foreground">{decisions.length} total</span>
          </div>

          {error ? (
            <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {(error as Error).message}
            </div>
          ) : null}

          {decisionsQuery.isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading decisions...</p>
          ) : decisions.length === 0 ? (
            <div className="mt-4 rounded-md border border-dashed border-border p-4">
              <h3 className="text-sm font-semibold">No decisions recorded yet.</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Decisions capture what you chose, why you chose it, what evidence supported
                it, and when to revisit it.
              </p>
              <Button
                className="mt-3"
                onClick={openDecisionForm}
                size="sm"
                type="button"
                variant="secondary"
              >
                <ScrollText className="h-4 w-4" aria-hidden="true" />
                Record Decision
              </Button>
            </div>
          ) : (
            <div className="mt-4 space-y-4">
              {decisions.map((decision) => (
                <details key={decision.id} className="rounded-md border border-border p-4">
                  <summary className="cursor-pointer list-none">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold">{decision.title}</h3>
                          <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                            {decisionLabel(decision.decision_type)}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-muted-foreground">
                          {new Date(decision.created_at).toLocaleDateString()}
                          {decision.review_date ? ` · review ${decision.review_date}` : ""}
                        </p>
                      </div>
                      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
                        {decision.links.length}
                      </span>
                    </div>
                  </summary>
                  {decision.rationale ? (
                    <MarkdownContent
                      className="mt-3 border-t border-border pt-3 text-sm leading-6 text-muted-foreground"
                      markdown={decision.rationale}
                    />
                  ) : null}
                  {decision.expected_outcome ? (
                    <div className="mt-3 border-t border-border pt-3">
                      <MarkdownContent
                        className="space-y-2 text-sm leading-6 text-muted-foreground"
                        markdown={decision.expected_outcome}
                      />
                    </div>
                  ) : null}
                  {decision.links.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {decision.links.map((link) => (
                        <span
                          className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                          key={link.id}
                        >
                          {link.linked_type}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </details>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function LinkPicker<T extends { id: string }>({
  items,
  label,
  onChange,
  selected,
  titleFor,
}: {
  items: T[];
  label: string;
  onChange: (value: string[]) => void;
  selected: string[];
  titleFor: (item: T) => string;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <fieldset>
      <legend className="text-sm font-medium">{label}</legend>
      <div className="mt-2 max-h-32 space-y-2 overflow-auto rounded-md border border-border p-2">
        {items.map((item) => (
          <label className="flex items-start gap-2 text-sm text-muted-foreground" key={item.id}>
            <input
              checked={selected.includes(item.id)}
              className="mt-1"
              onChange={() => onChange(toggle(selected, item.id))}
              type="checkbox"
            />
            <span className="line-clamp-2">{titleFor(item)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

type DecisionSuggestion = {
  actionLabel: string;
  expectedOutcome: string;
  linkedAssumptionId: string | null;
  linkedExperimentIds: string[];
  missingEvidence: string[];
  rationale: string;
  title: string;
  type: DecisionType;
};

function buildDecisionSuggestion({
  assumptions,
  decisionType,
  evidenceCount,
  experiments,
  label,
  overview,
}: {
  assumptions: Assumption[];
  decisionType?: DecisionType;
  evidenceCount: number;
  experiments: Experiment[];
  label?: string;
  overview: Awaited<ReturnType<typeof getProjectOverview>> | undefined;
}): DecisionSuggestion {
  const hasExperiments = experiments.length > 0;
  const hasLoggedResults = experiments.some((experiment) => experiment.results.length > 0);
  const riskiestAssumption = [...assumptions].sort(compareDecisionAssumptions)[0] ?? null;
  const unresolvedHighRisk = riskiestAssumption
    ? riskiestAssumption.status !== "validated"
    : false;
  const type = decisionType ?? "run_experiment";
  const actionLabel = label ?? decisionLabel(type);
  const currentRecommendation =
    overview?.current_recommendation.recommendation ?? "Continue research. Do not build yet.";
  const currentRationale =
    overview?.current_recommendation.rationale ??
    "The project needs decision-grade evidence before a build decision is justified.";
  const explicitRecommendedDecision =
    currentRecommendation.match(/^Recommended decision:\s*(.+)$/i)?.[1] ?? null;
  const missingEvidence = [
    evidenceCount === 0 ? "Add or gather source-backed evidence for the core claim." : null,
    assumptions.length === 0 ? "Identify and rank the riskiest assumptions." : null,
    !hasExperiments ? "Create a validation plan for the riskiest assumption." : null,
    !hasLoggedResults ? "Log at least one real validation result." : null,
    unresolvedHighRisk && riskiestAssumption
      ? `Resolve the riskiest assumption: ${riskiestAssumption.text}`
      : null,
  ].filter((item): item is string => Boolean(item));

  if (type === "build") {
    return {
      actionLabel,
      expectedOutcome: hasLoggedResults
        ? "Move into a narrow build pass only if the logged validation result supports the riskiest assumption."
        : "This should trigger a review after validation results are logged, because proceed evidence is currently missing.",
      linkedAssumptionId: riskiestAssumption?.id ?? null,
      linkedExperimentIds: experiments.slice(0, 1).map((experiment) => experiment.id),
      missingEvidence,
      rationale: hasLoggedResults
        ? `Proceed only with a narrow scope. Current recommendation: ${currentRecommendation}`
        : `Proceed is premature. ${currentRationale} Log validation evidence before committing build effort.`,
      title: hasLoggedResults ? "Proceed with narrow scope" : "Proceed with validation warning",
      type,
    };
  }

  if (type === "pivot") {
    return {
      actionLabel,
      expectedOutcome:
        "Use the evidence trail to narrow the wedge, change the target customer, or reposition the idea before more build work.",
      linkedAssumptionId: riskiestAssumption?.id ?? null,
      linkedExperimentIds: experiments.slice(0, 1).map((experiment) => experiment.id),
      missingEvidence,
      rationale: `A pivot is justified only if the current riskiest assumption is weak or invalidated. Current recommendation: ${currentRecommendation}`,
      title: "Pivot based on validation signal",
      type,
    };
  }

  if (type === "pause" || type === "kill") {
    return {
      actionLabel,
      expectedOutcome:
        type === "kill"
          ? "Stop active work and preserve the evidence trail for future reference."
          : "Pause build work until a stronger validation signal is available.",
      linkedAssumptionId: riskiestAssumption?.id ?? null,
      linkedExperimentIds: experiments.slice(0, 1).map((experiment) => experiment.id),
      missingEvidence,
      rationale: `Use this only when the missing evidence is material enough to stop momentum. Current recommendation: ${currentRecommendation}`,
      title: type === "kill" ? "Kill the idea" : "Pause until evidence improves",
      type,
    };
  }

  return {
    actionLabel: label ?? "Continue Research",
    expectedOutcome:
      "Run or complete the next validation test, update confidence in the riskiest assumption, and revisit the decision after results are logged.",
    linkedAssumptionId: riskiestAssumption?.id ?? null,
    linkedExperimentIds: experiments
      .filter((experiment) => experiment.results.length === 0)
      .slice(0, 1)
      .map((experiment) => experiment.id),
    missingEvidence,
    rationale: `${currentRationale} The next decision should wait until the validation loop has real evidence.`,
    title: explicitRecommendedDecision
      ? sentenceCase(explicitRecommendedDecision)
      : hasLoggedResults
        ? "Continue research unless the result supports a narrow proceed decision"
        : "Continue research. Do not proceed yet",
    type: "run_experiment",
  };
}

function sentenceCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function compareDecisionAssumptions(a: Assumption, b: Assumption) {
  const score = (assumption: Assumption) =>
    (assumption.kill_risk ? 100 : 0) +
    importanceScore(assumption.importance) +
    uncertaintyScore(assumption.uncertainty);
  return score(b) - score(a);
}

function importanceScore(value: Assumption["importance"]) {
  return { critical: 40, high: 30, medium: 15, low: 5 }[value];
}

function uncertaintyScore(value: Assumption["uncertainty"]) {
  return { high: 25, medium: 12, low: 3 }[value];
}

function toggle(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function emptyToUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function decisionLabel(value: DecisionType) {
  const labels: Record<DecisionType, string> = {
    build: "Proceed",
    pivot: "Pivot",
    pause: "Pause",
    kill: "Kill",
    change_icp: "Change ICP",
    change_positioning: "Change Positioning",
    run_experiment: "Continue Research",
    other: "Other",
  };
  return labels[value] ?? formatLabel(value);
}

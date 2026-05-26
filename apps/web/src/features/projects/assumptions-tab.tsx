"use client";

import {
  AlertTriangle,
  ArrowRight,
  Beaker,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { ReactNode, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Assumption,
  Experiment,
  extractAssumptions,
  generateValidationPlan,
  listExperiments,
  listAssumptions,
  listRisks,
  updateAssumption,
  ValidationPlanGenerateResult,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

type AssumptionsTabProps = {
  projectId: string;
  onOpenExperiments?: () => void;
};

type GeneratedValidationPlan = {
  assumptionId: string;
  result: ValidationPlanGenerateResult;
};

export function AssumptionsTab({ projectId, onOpenExperiments }: AssumptionsTabProps) {
  const queryClient = useQueryClient();
  const [lastWorkflowRunId, setLastWorkflowRunId] = useState<string | null>(null);
  const [pendingPlanAssumptionId, setPendingPlanAssumptionId] = useState<string | null>(null);
  const [generatedPlan, setGeneratedPlan] = useState<GeneratedValidationPlan | null>(null);
  const [filter, setFilter] = useState<
    "all" | "high_risk" | "low_confidence" | "needs_validation" | "validated" | "invalidated"
  >("all");
  const [showAllAssumptions, setShowAllAssumptions] = useState(false);
  const assumptionsQuery = useQuery({
    queryKey: ["projects", projectId, "assumptions"],
    queryFn: () => listAssumptions(projectId),
  });
  const experimentsQuery = useQuery({
    queryKey: ["projects", projectId, "experiments"],
    queryFn: () => listExperiments(projectId),
  });
  const risksQuery = useQuery({
    queryKey: ["projects", projectId, "risks"],
    queryFn: () => listRisks(projectId),
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assumptions"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "risks"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "experiments"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "workflows"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
  };

  const extractMutation = useMutation({
    mutationFn: () => extractAssumptions(projectId),
    onMutate: () => {
      setLastWorkflowRunId(null);
    },
    onSuccess: async (result) => {
      setLastWorkflowRunId(result.ai_run_id);
      await invalidate();
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ assumption, status }: { assumption: Assumption; status: Assumption["status"] }) =>
      updateAssumption(projectId, assumption.id, { status }),
    onSuccess: invalidate,
  });

  const planMutation = useMutation({
    mutationFn: (assumptionId: string) =>
      generateValidationPlan(projectId, { assumption_ids: [assumptionId], max_plans: 1 }),
    onMutate: (assumptionId) => {
      setLastWorkflowRunId(null);
      setPendingPlanAssumptionId(assumptionId);
      setGeneratedPlan(null);
    },
    onSuccess: async (result, assumptionId) => {
      setLastWorkflowRunId(result.ai_run_id);
      setGeneratedPlan({ assumptionId, result });
      await invalidate();
    },
    onSettled: () => {
      setPendingPlanAssumptionId(null);
    },
  });

  const assumptions = assumptionsQuery.data ?? [];
  const experiments = experimentsQuery.data ?? [];
  const risks = risksQuery.data ?? [];
  const experimentsByAssumption = new Map<string, Experiment[]>();
  for (const experiment of experiments) {
    if (!experiment.assumption_id) {
      continue;
    }
    const existing = experimentsByAssumption.get(experiment.assumption_id) ?? [];
    experimentsByAssumption.set(experiment.assumption_id, [...existing, experiment]);
  }
  const error =
    assumptionsQuery.error ??
    experimentsQuery.error ??
    risksQuery.error ??
    extractMutation.error ??
    statusMutation.error ??
    planMutation.error ??
    null;
  const rankedAssumptions = [...assumptions].sort(compareAssumptions);
  const riskiestAssumption = rankedAssumptions[0] ?? null;
  const visibleAssumptions = rankedAssumptions.filter((assumption) => {
    if (filter === "high_risk") {
      return assumption.kill_risk || assumption.importance === "critical" || assumption.importance === "high";
    }
    if (filter === "low_confidence") {
      return confidenceValue(assumption.confidence_score) < 0.4;
    }
    if (filter === "needs_validation") {
      return assumption.status === "untested" || assumption.status === "testing";
    }
    if (filter === "validated") {
      return assumption.status === "validated";
    }
    if (filter === "invalidated") {
      return assumption.status === "invalidated";
    }
    return true;
  });
  const displayedAssumptions = showAllAssumptions
    ? visibleAssumptions
    : visibleAssumptions.slice(0, 5);
  const hiddenAssumptionCount = visibleAssumptions.length - displayedAssumptions.length;

  return (
    <section className="mt-6 space-y-6">
      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Assumptions
            </p>
          <h2 className="mt-2 text-xl font-semibold tracking-normal">What must be true?</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Turn strategic uncertainty into operational validation priorities. Start with
            the riskiest assumption, then work down the ranked list.
          </p>
        </div>
        <Button
          disabled={extractMutation.isPending}
          onClick={() => extractMutation.mutate()}
          type="button"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {extractMutation.isPending ? "Extracting..." : "Extract Assumptions"}
        </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {(error as Error).message}
        </div>
      ) : null}

      <WorkflowTrace
        pending={extractMutation.isPending || planMutation.isPending}
        pendingSteps={
          extractMutation.isPending
            ? ["extract_assumptions_risks"]
            : ["generate_validation_plan", "write_artifact_version", "write_experiments"]
        }
        runId={lastWorkflowRunId}
      />

      {riskiestAssumption ? (
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-base font-semibold">Riskiest Assumption</h3>
              </div>
              <MarkdownContent
                className="mt-3 max-w-3xl space-y-2 text-sm leading-6 text-foreground"
                markdown={riskiestAssumption.text}
              />
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <Badge>{riskLabel(riskiestAssumption)}</Badge>
                <Badge>{formatConfidence(riskiestAssumption.confidence_score)}</Badge>
                <Badge>{evidenceStrength(riskiestAssumption.evidence_links.length)}</Badge>
                <Badge>{formatLabel(riskiestAssumption.status)}</Badge>
              </div>
              {riskiestAssumption.recommended_test ? (
                <MarkdownContent
                  className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground"
                  markdown={riskiestAssumption.recommended_test}
                />
              ) : null}
            </div>
            <Button
              disabled={planMutation.isPending}
              onClick={() => planMutation.mutate(riskiestAssumption.id)}
              type="button"
            >
              <Beaker className="h-4 w-4" aria-hidden="true" />
              Create Validation Plan
            </Button>
          </div>
        </div>
      ) : null}

      <div className="grid gap-5">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Ranked Assumptions</h3>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                onChange={(event) => setFilter(event.target.value as typeof filter)}
                value={filter}
              >
                <option value="all">All</option>
                <option value="high_risk">High risk</option>
                <option value="low_confidence">Low confidence</option>
                <option value="needs_validation">Needs validation</option>
                <option value="validated">Validated</option>
                <option value="invalidated">Invalidated</option>
              </select>
              <span className="text-sm text-muted-foreground">{visibleAssumptions.length} shown</span>
            </div>
          </div>

          {assumptionsQuery.isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading assumptions...</p>
          ) : assumptions.length === 0 ? (
            <div className="mt-4 rounded-md border border-dashed border-border p-4">
              <h4 className="text-sm font-semibold">No assumptions identified yet.</h4>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Assumptions are the beliefs that must be true for this idea to work. The
                system will help rank them by risk and turn them into validation
                experiments.
              </p>
              <Button
                className="mt-3"
                disabled={extractMutation.isPending}
                onClick={() => extractMutation.mutate()}
                size="sm"
                type="button"
                variant="secondary"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {extractMutation.isPending ? "Extracting..." : "Extract Assumptions"}
              </Button>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {visibleAssumptions.length === 0 ? (
                <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
                  No assumptions match this filter.
                </div>
              ) : null}

              {displayedAssumptions.map((assumption, index) => {
                const isGeneratingPlan =
                  planMutation.isPending && pendingPlanAssumptionId === assumption.id;
                const generatedPlanForAssumption =
                  generatedPlan?.assumptionId === assumption.id ? generatedPlan.result : null;
                const generatedExperiments =
                  generatedPlanForAssumption?.experiments.filter(
                    (experiment) => experiment.assumption_id === assumption.id,
                  ) ?? [];
                const planExperiments = generatedPlanForAssumption
                  ? generatedExperiments.length > 0
                    ? generatedExperiments
                    : generatedPlanForAssumption.experiments
                  : experimentsByAssumption.get(assumption.id) ?? [];

                return (
                  <article
                    className="rounded-md border border-border p-4"
                    key={assumption.id}
                  >
                    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
                      <div className="min-w-0">
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                            {index + 1}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                              Assumption
                            </p>
                            <MarkdownContent
                              className="mt-2 max-w-3xl space-y-2 text-sm leading-6 text-foreground"
                              markdown={assumption.text}
                            />
                            <div className="mt-3 flex flex-wrap gap-2 text-xs">
                              <Badge>{riskLabel(assumption)}</Badge>
                              <Badge>{formatConfidence(assumption.confidence_score)}</Badge>
                              <Badge>{evidenceStrength(assumption.evidence_links.length)}</Badge>
                            </div>
                            {assumption.recommended_test ? (
                              <details className="mt-3">
                                <summary className="cursor-pointer text-xs font-medium text-primary">
                                  Show validation method
                                </summary>
                                <MarkdownContent
                                  className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground"
                                  markdown={assumption.recommended_test}
                                />
                              </details>
                            ) : null}
                          </div>
                        </div>
                        <ValidationPlanSummary
                          isFresh={Boolean(generatedPlanForAssumption)}
                          onOpenExperiments={onOpenExperiments}
                          experiments={planExperiments}
                        />
                      </div>

                      <div className="rounded-md bg-muted/50 p-3">
                        <label
                          className="text-xs font-medium uppercase tracking-normal text-muted-foreground"
                          htmlFor={`assumption-status-${assumption.id}`}
                        >
                          Status
                        </label>
                        <select
                          className="mt-2 w-full rounded-md border border-border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                          disabled={statusMutation.isPending}
                          id={`assumption-status-${assumption.id}`}
                          onChange={(event) =>
                            statusMutation.mutate({
                              assumption,
                              status: event.target.value as Assumption["status"],
                            })
                          }
                          value={assumption.status}
                        >
                          {["untested", "testing", "validated", "invalidated", "inconclusive"].map(
                            (status) => (
                              <option key={status} value={status}>
                                {formatLabel(status)}
                              </option>
                            ),
                          )}
                        </select>
                        <Button
                          aria-busy={isGeneratingPlan}
                          className="mt-3 w-full whitespace-nowrap"
                          disabled={planMutation.isPending}
                          onClick={() => planMutation.mutate(assumption.id)}
                          type="button"
                        >
                          <Beaker className="h-4 w-4" aria-hidden="true" />
                          {isGeneratingPlan ? "Generating..." : "Create Validation Plan"}
                        </Button>
                      </div>
                    </div>
                  </article>
                );
              })}
              {hiddenAssumptionCount > 0 ? (
                <Button
                  onClick={() => setShowAllAssumptions(true)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  Show {hiddenAssumptionCount} more assumptions
                </Button>
              ) : showAllAssumptions && visibleAssumptions.length > 5 ? (
                <Button
                  onClick={() => setShowAllAssumptions(false)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  Show fewer assumptions
                </Button>
              ) : null}
            </div>
          )}
        </div>

        <details className="rounded-lg border border-border bg-white p-5">
          <summary className="cursor-pointer list-none">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Risks</h3>
              </div>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {risks.length}
              </span>
            </div>
          </summary>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {risksQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading risks...</p>
            ) : risks.length === 0 ? (
              <p className="text-sm leading-6 text-muted-foreground">
                No risks recorded yet. Extract assumptions to surface likely failure modes and
                mitigation paths.
              </p>
            ) : (
              risks.map((risk) => (
                <div key={risk.id} className="rounded-md border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                      {risk.severity}
                    </span>
                    <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                      likelihood {risk.likelihood}
                    </span>
                  </div>
                  <MarkdownContent
                    className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground"
                    markdown={risk.text}
                  />
                  {risk.mitigation ? (
                    <div className="mt-2 border-t border-border pt-2">
                      <MarkdownContent
                        className="space-y-2 text-xs leading-5 text-muted-foreground"
                        markdown={risk.mitigation}
                      />
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </details>
      </div>
    </section>
  );
}

function ValidationPlanSummary({
  experiments,
  isFresh,
  onOpenExperiments,
}: {
  experiments: Experiment[];
  isFresh: boolean;
  onOpenExperiments?: () => void;
}) {
  if (experiments.length === 0) {
    return null;
  }

  const shownExperiments = experiments.slice(0, 2);
  const hiddenCount = experiments.length - shownExperiments.length;

  return (
    <div className="mt-4 border-l-2 border-emerald-600 bg-emerald-50 px-4 py-3">
      <details>
        <summary className="cursor-pointer list-none">
          <div className="flex items-center gap-2 text-sm font-medium text-emerald-900">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            {isFresh ? "Validation plan created" : "Validation plan available"}
          </div>
          <p className="mt-1 text-sm leading-6 text-emerald-900/80">
            {experiments.length} experiment{experiments.length === 1 ? "" : "s"}{" "}
            {isFresh ? "written" : "linked"} for this assumption.
          </p>
        </summary>
        {onOpenExperiments ? (
          <Button className="mt-3" onClick={onOpenExperiments} size="sm" type="button" variant="secondary">
            View in Validation
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : null}

        <div className="mt-3 space-y-3">
          {shownExperiments.map((experiment) => (
            <GeneratedExperimentSummary experiment={experiment} key={experiment.id} />
          ))}
          {hiddenCount > 0 ? (
            <p className="border-t border-emerald-200 pt-3 text-sm text-emerald-950/80">
              {hiddenCount} more experiment{hiddenCount === 1 ? "" : "s"} available in Validation.
            </p>
          ) : null}
        </div>
      </details>
    </div>
  );
}

function GeneratedExperimentSummary({ experiment }: { experiment: Experiment }) {
  return (
    <div className="border-t border-emerald-200 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-medium text-emerald-950">{experiment.name}</h4>
        {experiment.method ? (
          <span className="rounded-md bg-white/70 px-2 py-1 text-xs text-emerald-900">
            {formatLabel(experiment.method)}
          </span>
        ) : null}
      </div>
      {experiment.plan ? (
        <MarkdownContent
          className="mt-2 space-y-2 text-sm leading-6 text-emerald-950/80"
          markdown={experiment.plan}
        />
      ) : null}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <GeneratedExperimentBlock title="Success Criteria" value={experiment.success_criteria} />
        <GeneratedExperimentBlock title="Failure Threshold" value={experiment.failure_threshold} />
      </div>
    </div>
  );
}

function GeneratedExperimentBlock({ title, value }: { title: string; value: string | null }) {
  if (!value) {
    return null;
  }
  return (
    <div>
      <h5 className="text-xs font-medium uppercase tracking-normal text-emerald-900/70">
        {title}
      </h5>
      <MarkdownContent className="mt-1 text-sm leading-6 text-emerald-950/80" markdown={value} />
    </div>
  );
}

function formatConfidence(value: string | null) {
  if (value === null) {
    return "Confidence unknown";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return `${Math.round(parsed * 100)}% confidence`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
      {children}
    </span>
  );
}

function compareAssumptions(a: Assumption, b: Assumption) {
  const score = (assumption: Assumption) =>
    (assumption.kill_risk ? 100 : 0) +
    importanceScore(assumption.importance) +
    uncertaintyScore(assumption.uncertainty) -
    confidenceValue(assumption.confidence_score) * 10;
  return score(b) - score(a);
}

function importanceScore(value: Assumption["importance"]) {
  return { critical: 40, high: 30, medium: 15, low: 5 }[value];
}

function uncertaintyScore(value: Assumption["uncertainty"]) {
  return { high: 25, medium: 12, low: 3 }[value];
}

function confidenceValue(value: string | null) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function riskLabel(assumption: Assumption) {
  if (assumption.kill_risk || assumption.importance === "critical") {
    return "High risk";
  }
  if (assumption.importance === "high" || assumption.uncertainty === "high") {
    return "Medium risk";
  }
  return "Lower risk";
}

function evidenceStrength(linkCount: number) {
  if (linkCount >= 3) {
    return "Evidence strong";
  }
  if (linkCount >= 1) {
    return "Evidence partial";
  }
  return "Evidence weak";
}

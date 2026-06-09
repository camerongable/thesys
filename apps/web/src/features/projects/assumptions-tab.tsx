"use client";

import {
  AlertTriangle,
  ArrowRight,
  Beaker,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { Fragment, ReactNode, useState } from "react";
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

const assumptionFilters = [
  "all",
  "high_risk",
  "low_confidence",
  "needs_validation",
  "validated",
  "invalidated",
] as const;

type AssumptionFilter = (typeof assumptionFilters)[number];

export function AssumptionsTab({ projectId, onOpenExperiments }: AssumptionsTabProps) {
  const queryClient = useQueryClient();
  const [lastWorkflowRunId, setLastWorkflowRunId] = useState<string | null>(null);
  const [pendingPlanAssumptionId, setPendingPlanAssumptionId] = useState<string | null>(null);
  const [generatedPlan, setGeneratedPlan] = useState<GeneratedValidationPlan | null>(null);
  const [filter, setFilter] = useState<AssumptionFilter>("all");
  const [showAllAssumptions, setShowAllAssumptions] = useState(false);
  const [selectedAssumptionId, setSelectedAssumptionId] = useState<string | null>(null);
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
  const topValidationPriorities = rankedAssumptions
    .filter((assumption) => assumption.status !== "validated")
    .slice(0, 3);
  const visibleAssumptions = rankedAssumptions.filter((assumption) =>
    matchesAssumptionFilter(assumption, filter),
  );
  const filterCounts = assumptionFilters.reduce(
    (counts, option) => ({
      ...counts,
      [option]: rankedAssumptions.filter((assumption) =>
        matchesAssumptionFilter(assumption, option),
      ).length,
    }),
    {} as Record<AssumptionFilter, number>,
  );
  const activeFilterDescription = filterDescription(filter);
  const displayedAssumptions = showAllAssumptions
    ? visibleAssumptions
    : visibleAssumptions.slice(0, 5);
  const hiddenAssumptionCount = visibleAssumptions.length - displayedAssumptions.length;
  const selectedAssumption =
    visibleAssumptions.find((assumption) => assumption.id === selectedAssumptionId) ??
    visibleAssumptions[0] ??
    null;
  const selectedGeneratedPlan =
    selectedAssumption && generatedPlan?.assumptionId === selectedAssumption.id
      ? generatedPlan.result
      : null;
  const selectedGeneratedExperiments =
    selectedGeneratedPlan?.experiments.filter(
      (experiment) => experiment.assumption_id === selectedAssumption?.id,
    ) ?? [];
  const selectedPlanExperiments = selectedAssumption
    ? selectedGeneratedPlan
      ? selectedGeneratedExperiments.length > 0
        ? selectedGeneratedExperiments
        : selectedGeneratedPlan.experiments
      : experimentsByAssumption.get(selectedAssumption.id) ?? []
    : [];
  const selectedIsGeneratingPlan =
    selectedAssumption !== null &&
    planMutation.isPending &&
    pendingPlanAssumptionId === selectedAssumption.id;
  const tracePending = extractMutation.isPending || planMutation.isPending;
  const selectFilter = (nextFilter: AssumptionFilter) => {
    setFilter(nextFilter);
    setShowAllAssumptions(false);
    setSelectedAssumptionId(null);
  };
  const runAssumptionAction = (assumption: Assumption, planExperiments: Experiment[]) => {
    if (planExperiments.length > 0 && onOpenExperiments) {
      onOpenExperiments();
      return;
    }
    planMutation.mutate(assumption.id);
  };

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
            className="w-full justify-center whitespace-nowrap sm:w-60"
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

      {tracePending || lastWorkflowRunId ? (
        <details className="rounded-lg border border-border bg-white p-5" open={tracePending}>
          <summary className="cursor-pointer text-sm font-semibold">View activity trace</summary>
          <div className="mt-4 border-t border-border pt-4">
            <WorkflowTrace
              pending={tracePending}
              pendingSteps={
                extractMutation.isPending
                  ? ["extract_assumptions_risks"]
                  : ["generate_validation_plan", "write_artifact_version", "write_experiments"]
              }
              runId={lastWorkflowRunId}
            />
          </div>
        </details>
      ) : null}

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
              className="w-full justify-center whitespace-nowrap sm:w-60"
              disabled={planMutation.isPending}
              onClick={() =>
                runAssumptionAction(
                  riskiestAssumption,
                  experimentsByAssumption.get(riskiestAssumption.id) ?? [],
                )
              }
              type="button"
            >
              <Beaker className="h-4 w-4" aria-hidden="true" />
              {assumptionCtaLabel(
                experimentsByAssumption.get(riskiestAssumption.id) ?? [],
                false,
              )}
            </Button>
          </div>
        </div>
      ) : null}

      {topValidationPriorities.length > 0 ? (
        <TopValidationPriorities
          assumptions={topValidationPriorities}
          experimentsByAssumption={experimentsByAssumption}
          onAction={runAssumptionAction}
          pendingAssumptionId={pendingPlanAssumptionId}
          pending={planMutation.isPending}
        />
      ) : null}

      {rankedAssumptions.length > 0 ? (
        <AssumptionPriorityMatrix
          assumptions={rankedAssumptions}
          onSelect={(assumption) => {
            setFilter("all");
            setSelectedAssumptionId(assumption.id);
          }}
          selectedAssumptionId={selectedAssumption?.id ?? null}
        />
      ) : null}

      <div className="grid gap-5">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Ranked Assumptions</h3>
            </div>
            <div className="flex flex-col gap-2 sm:items-end">
              <div className="flex flex-wrap gap-2 sm:justify-end">
                {assumptionFilters.map((option) => {
                  const isSelected = filter === option;
                  return (
                    <button
                      aria-pressed={isSelected}
                      className={[
                        "inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs font-medium transition",
                        isSelected
                          ? "border-action bg-action text-action-foreground"
                          : "border-border bg-white text-muted-foreground hover:border-primary/60 hover:text-foreground",
                      ].join(" ")}
                      key={option}
                      onClick={() => selectFilter(option)}
                      type="button"
                    >
                      <span>{filterLabel(option)}</span>
                      <span
                        className={[
                          "rounded px-1.5 py-0.5 text-[11px]",
                          isSelected
                            ? "bg-black/10 text-action-foreground"
                            : "bg-muted text-muted-foreground",
                        ].join(" ")}
                      >
                        {filterCounts[option]}
                      </span>
                    </button>
                  );
                })}
              </div>
              <span className="text-xs leading-5 text-muted-foreground">
                Showing {visibleAssumptions.length} of {rankedAssumptions.length}
                {filter !== "all" ? ` - ${activeFilterDescription}` : ""}
              </span>
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
                <div className="rounded-md border border-dashed border-border p-4">
                  <h4 className="text-sm font-semibold">
                    No {filterLabel(filter).toLowerCase()} assumptions found.
                  </h4>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {activeFilterDescription}. Try a broader filter to review the full ranked
                    list.
                  </p>
                  <Button
                    className="mt-3"
                    onClick={() => selectFilter("all")}
                    size="sm"
                    type="button"
                    variant="secondary"
                  >
                    Show All
                  </Button>
                </div>
              ) : null}

              {visibleAssumptions.length > 0 ? (
                <div className="space-y-3">
                  <div className="min-w-0 space-y-3">
                    <div className="hidden overflow-hidden rounded-md border border-border lg:block">
                      <table className="w-full table-fixed border-collapse text-left text-sm">
                        <thead>
                          <tr className="border-b border-border text-xs uppercase tracking-normal text-muted-foreground">
                            <th className="w-[42%] px-3 py-3 font-medium">Assumption</th>
                            <th className="w-[8%] px-3 py-3 font-medium">Risk</th>
                            <th className="w-[12%] px-3 py-3 font-medium">Confidence</th>
                            <th className="w-[9%] px-3 py-3 font-medium">Evidence</th>
                            <th className="w-[15%] px-3 py-3 font-medium">Status</th>
                            <th className="w-[14%] px-3 py-3 font-medium">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {displayedAssumptions.map((assumption) => {
                            const isGeneratingPlan =
                              planMutation.isPending && pendingPlanAssumptionId === assumption.id;
                            const isSelected = selectedAssumption?.id === assumption.id;
                            const planExperiments = experimentsByAssumption.get(assumption.id) ?? [];
                            return (
                              <Fragment key={assumption.id}>
                                <tr
                                  className={[
                                    "cursor-pointer align-top transition",
                                    isSelected
                                      ? "bg-muted/70"
                                      : "hover:bg-muted/40",
                                  ].join(" ")}
                                  onClick={() => setSelectedAssumptionId(assumption.id)}
                                >
                                  <td className="px-3 py-4">
                                    <div className="line-clamp-3 text-foreground">{assumption.text}</div>
                                    {assumption.recommended_test ? (
                                      <div className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                                        {assumption.recommended_test}
                                      </div>
                                    ) : null}
                                  </td>
                                  <td className="px-3 py-4">
                                    <Badge>{compactRiskLabel(assumption)}</Badge>
                                  </td>
                                  <td className="px-3 py-4">
                                    <Badge>{compactConfidenceLabel(assumption.confidence_score)}</Badge>
                                  </td>
                                  <td className="px-3 py-4">
                                    <Badge>{compactEvidenceLabel(assumption.evidence_links.length)}</Badge>
                                  </td>
                                  <td className="px-3 py-4">
                                    <select
                                      className="w-full rounded-md border border-border bg-white px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary"
                                      disabled={statusMutation.isPending}
                                      onClick={(event) => event.stopPropagation()}
                                      onChange={(event) =>
                                        statusMutation.mutate({
                                          assumption,
                                          status: event.target.value as Assumption["status"],
                                        })
                                      }
                                      value={assumption.status}
                                    >
                                      {[
                                        "untested",
                                        "testing",
                                        "validated",
                                        "invalidated",
                                        "inconclusive",
                                      ].map((status) => (
                                        <option key={status} value={status}>
                                          {formatLabel(status)}
                                        </option>
                                      ))}
                                    </select>
                                  </td>
                                  <td className="px-3 py-4">
                                    <Button
                                      aria-busy={isGeneratingPlan}
                                      className="w-full justify-center whitespace-nowrap px-2"
                                      disabled={planMutation.isPending}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        runAssumptionAction(assumption, planExperiments);
                                      }}
                                      size="sm"
                                      type="button"
                                      variant="secondary"
                                    >
                                      {assumptionCtaLabel(planExperiments, isGeneratingPlan)}
                                    </Button>
                                  </td>
                                </tr>
                                {isSelected ? (
                                  <tr className="bg-muted/40">
                                    <td className="px-3 py-3" colSpan={6}>
                                      <AssumptionDetailPanel
                                        assumption={assumption}
                                        experiments={selectedPlanExperiments}
                                        isFreshPlan={Boolean(selectedGeneratedPlan)}
                                        isGeneratingPlan={selectedIsGeneratingPlan}
                                        onCreatePlan={(assumptionId) => planMutation.mutate(assumptionId)}
                                        onOpenExperiments={onOpenExperiments}
                                      />
                                    </td>
                                  </tr>
                                ) : null}
                              </Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    <div className="space-y-3 lg:hidden">
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
                                  onClick={() => runAssumptionAction(assumption, planExperiments)}
                                  type="button"
                                  variant="secondary"
                                >
                                  <Beaker className="h-4 w-4" aria-hidden="true" />
                                  {assumptionCtaLabel(planExperiments, isGeneratingPlan)}
                                </Button>
                              </div>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  </div>

                </div>
              ) : null}
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

function AssumptionPriorityMatrix({
  assumptions,
  onSelect,
  selectedAssumptionId,
}: {
  assumptions: Assumption[];
  onSelect: (assumption: Assumption) => void;
  selectedAssumptionId: string | null;
}) {
  const validateFirstIds = new Set(
    assumptions
      .filter(
        (assumption) =>
          isDecisionCritical(assumption) &&
          isHighRisk(assumption) &&
          isLowConfidence(assumption),
      )
      .slice(0, 3)
      .map((assumption) => assumption.id),
  );
  const quadrants = [
    {
      key: "validate-first",
      title: "Validate first",
      subtitle: "Top decision-critical items",
      items: assumptions.filter((assumption) => validateFirstIds.has(assumption.id)),
    },
    {
      key: "monitor",
      title: "Monitor",
      subtitle: "High risk - watch closely",
      items: assumptions.filter(
        (assumption) =>
          isHighRisk(assumption) &&
          !validateFirstIds.has(assumption.id),
      ),
    },
    {
      key: "research-later",
      title: "Research later",
      subtitle: "Lower risk - Low confidence",
      items: assumptions.filter((assumption) => !isHighRisk(assumption) && isLowConfidence(assumption)),
    },
    {
      key: "safe",
      title: "Safer assumptions",
      subtitle: "Lower risk - Higher confidence",
      items: assumptions.filter((assumption) => !isHighRisk(assumption) && !isLowConfidence(assumption)),
    },
  ];

  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-2 border-b border-border pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Risk / Confidence Matrix</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Use this view to spot the assumptions that deserve validation before more build work.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {assumptions.length} ranked
        </span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-4">
        {quadrants.map((quadrant) => (
          <div
            className={
              quadrant.key === "validate-first"
                ? "rounded-md border border-action/50 bg-action/10 p-3"
                : "rounded-md border border-border bg-muted/30 p-3"
            }
            key={quadrant.key}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold">{quadrant.title}</h4>
                <p className="mt-1 text-xs text-muted-foreground">{quadrant.subtitle}</p>
              </div>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {quadrant.items.length}
              </span>
            </div>
            <div className="mt-3 space-y-2">
              {quadrant.items.slice(0, 2).map((assumption) => {
                const selected = selectedAssumptionId === assumption.id;
                return (
                  <button
                    className={[
                      "w-full rounded-md border px-2 py-2 text-left text-xs leading-5 transition",
                      selected
                        ? "border-action bg-action/15 text-foreground"
                        : "border-border bg-muted/40 text-muted-foreground hover:border-primary/60 hover:text-foreground",
                    ].join(" ")}
                    key={assumption.id}
                    onClick={() => onSelect(assumption)}
                    type="button"
                  >
                    <span className="line-clamp-2">{assumption.text}</span>
                  </button>
                );
              })}
              {quadrant.items.length === 0 ? (
                <p className="rounded-md border border-dashed border-border px-2 py-2 text-xs text-muted-foreground">
                  No assumptions here.
                </p>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopValidationPriorities({
  assumptions,
  experimentsByAssumption,
  onAction,
  pending,
  pendingAssumptionId,
}: {
  assumptions: Assumption[];
  experimentsByAssumption: Map<string, Experiment[]>;
  onAction: (assumption: Assumption, planExperiments: Experiment[]) => void;
  pending: boolean;
  pendingAssumptionId: string | null;
}) {
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-2 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Top Validation Priorities</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Start here. The full matrix remains available below, but these are the assumptions
            most likely to change the decision.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          top {assumptions.length}
        </span>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        {assumptions.map((assumption, index) => {
          const planExperiments = experimentsByAssumption.get(assumption.id) ?? [];
          const isPending = pending && pendingAssumptionId === assumption.id;
          return (
            <article className="rounded-md border border-border p-4" key={assumption.id}>
              <div className="flex items-start gap-3">
                <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <MarkdownContent
                    className="line-clamp-4 space-y-2 text-sm font-semibold leading-6 text-foreground"
                    markdown={assumption.text}
                  />
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <Badge>{compactRiskLabel(assumption)}</Badge>
                    <Badge>{compactConfidenceLabel(assumption.confidence_score)}</Badge>
                    <Badge>{compactEvidenceLabel(assumption.evidence_links.length)}</Badge>
                  </div>
                </div>
              </div>
              {assumption.recommended_test ? (
                <MarkdownContent
                  className="mt-3 line-clamp-3 space-y-2 text-sm leading-6 text-muted-foreground"
                  markdown={assumption.recommended_test}
                />
              ) : null}
              <Button
                aria-busy={isPending}
                className="mt-4 w-full"
                disabled={pending}
                onClick={() => onAction(assumption, planExperiments)}
                size="sm"
                type="button"
                variant="secondary"
              >
                <Beaker className="h-4 w-4" aria-hidden="true" />
                {assumptionCtaLabel(planExperiments, isPending)}
              </Button>
            </article>
          );
        })}
      </div>
    </div>
  );
}

function AssumptionDetailPanel({
  assumption,
  experiments,
  isFreshPlan,
  isGeneratingPlan,
  onCreatePlan,
  onOpenExperiments,
}: {
  assumption: Assumption;
  experiments: Experiment[];
  isFreshPlan: boolean;
  isGeneratingPlan: boolean;
  onCreatePlan: (assumptionId: string) => void;
  onOpenExperiments?: () => void;
}) {
  return (
    <div className="rounded-md border border-border bg-background/60 p-4">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Assumption detail
            </p>
            <Badge>{formatLabel(assumption.status)}</Badge>
          </div>
          <h4 className="mt-2 max-w-4xl text-sm font-semibold leading-6">{assumption.text}</h4>

          {assumption.recommended_test ? (
            <div className="mt-4 border-t border-border pt-4">
              <h5 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                Recommended validation
              </h5>
              <MarkdownContent
                className="mt-2 max-w-4xl space-y-2 text-sm leading-6 text-muted-foreground"
                markdown={assumption.recommended_test}
              />
            </div>
          ) : null}
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <DetailMetric label="Risk" value={compactRiskLabel(assumption)} />
            <DetailMetric label="Confidence" value={compactConfidenceLabel(assumption.confidence_score)} />
            <DetailMetric label="Evidence" value={compactEvidenceLabel(assumption.evidence_links.length)} />
            <DetailMetric label="Citations" value={String(assumption.evidence_links.length)} />
          </div>
          <Button
            aria-busy={isGeneratingPlan}
            className="w-full justify-center whitespace-nowrap"
            disabled={isGeneratingPlan}
            onClick={() => {
              if (experiments.length > 0 && onOpenExperiments) {
                onOpenExperiments();
                return;
              }
              onCreatePlan(assumption.id);
            }}
            type="button"
          >
            <Beaker className="h-4 w-4" aria-hidden="true" />
            {assumptionCtaLabel(experiments, isGeneratingPlan)}
          </Button>
        </div>
      </div>

      <ValidationPlanSummary
        experiments={experiments}
        isFresh={isFreshPlan}
        onOpenExperiments={onOpenExperiments}
      />
    </div>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-background/70 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
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
    return "Unknown confidence";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  const percentage = `${Math.round(parsed * 100)}%`;
  if (parsed >= 0.7) {
    return `High confidence (${percentage})`;
  }
  if (parsed >= 0.4) {
    return `Medium confidence (${percentage})`;
  }
  return `Low confidence (${percentage})`;
}

function compactConfidenceLabel(value: string | null) {
  if (value === null) {
    return "Unknown";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  const percentage = `${Math.round(parsed * 100)}%`;
  if (parsed >= 0.7) {
    return `High (${percentage})`;
  }
  if (parsed >= 0.4) {
    return `Medium (${percentage})`;
  }
  return `Low (${percentage})`;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex w-fit whitespace-nowrap rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
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

function matchesAssumptionFilter(assumption: Assumption, filter: AssumptionFilter) {
  if (filter === "high_risk") {
    return assumption.kill_risk || assumption.importance === "critical" || assumption.importance === "high";
  }
  if (filter === "low_confidence") {
    return confidenceValue(assumption.confidence_score) < 0.4;
  }
  if (filter === "needs_validation") {
    return (
      assumption.status === "untested" ||
      assumption.status === "testing" ||
      assumption.status === "inconclusive"
    );
  }
  if (filter === "validated") {
    return assumption.status === "validated";
  }
  if (filter === "invalidated") {
    return assumption.status === "invalidated";
  }
  return true;
}

function filterLabel(filter: AssumptionFilter) {
  if (filter === "high_risk") {
    return "High risk";
  }
  if (filter === "low_confidence") {
    return "Low confidence";
  }
  if (filter === "needs_validation") {
    return "Needs validation";
  }
  if (filter === "validated") {
    return "Validated";
  }
  if (filter === "invalidated") {
    return "Invalidated";
  }
  return "All";
}

function filterDescription(filter: AssumptionFilter) {
  if (filter === "high_risk") {
    return "Risk is high or critical";
  }
  if (filter === "low_confidence") {
    return "Confidence is below 40%";
  }
  if (filter === "needs_validation") {
    return "Status is untested, testing, or inconclusive";
  }
  if (filter === "validated") {
    return "Status is validated";
  }
  if (filter === "invalidated") {
    return "Status is invalidated";
  }
  return "All ranked assumptions";
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

function compactRiskLabel(assumption: Assumption) {
  if (assumption.kill_risk || assumption.importance === "critical") {
    return "High";
  }
  if (assumption.importance === "high" || assumption.uncertainty === "high") {
    return "Medium";
  }
  return "Low";
}

function isHighRisk(assumption: Assumption) {
  return assumption.kill_risk || assumption.importance === "critical" || assumption.importance === "high";
}

function isDecisionCritical(assumption: Assumption) {
  return assumption.kill_risk || assumption.importance === "critical";
}

function isLowConfidence(assumption: Assumption) {
  return confidenceValue(assumption.confidence_score) < 0.4;
}

function assumptionCtaLabel(experiments: Experiment[], pending: boolean) {
  if (pending) {
    return "Creating...";
  }
  if (experiments.length === 0) {
    return "Create Plan";
  }
  if (experiments.some((experiment) => experiment.results.length > 0)) {
    return "Review Evidence";
  }
  if (experiments.some((experiment) => experiment.status === "running")) {
    return "Log Results";
  }
  return "Open Plan";
}

function evidenceStrength(linkCount: number) {
  if (linkCount >= 3) {
    return "Strong evidence";
  }
  if (linkCount >= 1) {
    return "Partial evidence";
  }
  return "Needs evidence";
}

function compactEvidenceLabel(linkCount: number) {
  if (linkCount >= 3) {
    return "Strong";
  }
  if (linkCount >= 1) {
    return "Partial";
  }
  return "None";
}

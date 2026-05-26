"use client";

import {
  AlertTriangle,
  ArrowRight,
  Beaker,
  CheckCircle2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { useState } from "react";
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

  return (
    <section className="mt-6 space-y-6">
      <div className="flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Assumptions and Risks</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Ranked by kill risk, importance, and uncertainty.
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

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Ranked Assumptions</h3>
            </div>
            <span className="text-sm text-muted-foreground">{assumptions.length} total</span>
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
            <div className="mt-4 space-y-4">
              {assumptions.map((assumption) => {
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
                  <div key={assumption.id} className="rounded-md border border-border p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                            {assumption.importance}
                          </span>
                          <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                            uncertainty {assumption.uncertainty}
                          </span>
                          {assumption.kill_risk ? (
                            <span className="rounded-md bg-red-50 px-2 py-1 text-red-700">
                              kill risk
                            </span>
                          ) : null}
                          {assumption.evidence_links.length > 0 ? (
                            <span className="rounded-md bg-emerald-50 px-2 py-1 text-emerald-700">
                              {assumption.evidence_links.length} evidence link
                              {assumption.evidence_links.length === 1 ? "" : "s"}
                            </span>
                          ) : null}
                        </div>
                        <MarkdownContent
                          className="mt-3 space-y-2 text-sm leading-6 text-foreground"
                          markdown={assumption.text}
                        />
                      </div>
                      <div className="shrink-0 text-sm text-muted-foreground">
                        {formatConfidence(assumption.confidence_score)}
                      </div>
                    </div>

                    {assumption.recommended_test ? (
                      <MarkdownContent
                        className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground"
                        markdown={assumption.recommended_test}
                      />
                    ) : null}

                    <ValidationPlanSummary
                      isFresh={Boolean(generatedPlanForAssumption)}
                      onOpenExperiments={onOpenExperiments}
                      experiments={planExperiments}
                    />

                    <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <select
                        className="w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary sm:w-56"
                        disabled={statusMutation.isPending}
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
                        disabled={planMutation.isPending}
                        onClick={() => planMutation.mutate(assumption.id)}
                        type="button"
                      >
                        <Beaker className="h-4 w-4" aria-hidden="true" />
                        {isGeneratingPlan ? "Generating..." : "Create Validation Plan"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <aside className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Risks</h3>
          </div>
          <div className="mt-4 space-y-3">
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
        </aside>
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-emerald-900">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            {isFresh ? "Validation plan created" : "Validation plan available"}
          </div>
          <p className="mt-1 text-sm leading-6 text-emerald-900/80">
            {experiments.length} experiment{experiments.length === 1 ? "" : "s"}{" "}
            {isFresh ? "written" : "linked"} for this assumption.
          </p>
        </div>
        {onOpenExperiments ? (
          <Button onClick={onOpenExperiments} size="sm" type="button" variant="secondary">
            View in Experiments
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      <div className="mt-3 space-y-3">
        {shownExperiments.map((experiment) => (
          <GeneratedExperimentSummary experiment={experiment} key={experiment.id} />
        ))}
        {hiddenCount > 0 ? (
          <p className="border-t border-emerald-200 pt-3 text-sm text-emerald-950/80">
            {hiddenCount} more experiment{hiddenCount === 1 ? "" : "s"} available in Experiments.
          </p>
        ) : null}
      </div>
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
    return "No confidence";
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

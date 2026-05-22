"use client";

import { AlertTriangle, Beaker, RefreshCw, ShieldAlert } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Assumption,
  extractAssumptions,
  generateValidationPlan,
  listAssumptions,
  listRisks,
  updateAssumption,
} from "@/lib/api";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

type AssumptionsTabProps = {
  projectId: string;
};

export function AssumptionsTab({ projectId }: AssumptionsTabProps) {
  const queryClient = useQueryClient();
  const assumptionsQuery = useQuery({
    queryKey: ["projects", projectId, "assumptions"],
    queryFn: () => listAssumptions(projectId),
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
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "workflows"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
  };

  const extractMutation = useMutation({
    mutationFn: () => extractAssumptions(projectId),
    onSuccess: invalidate,
  });

  const statusMutation = useMutation({
    mutationFn: ({ assumption, status }: { assumption: Assumption; status: Assumption["status"] }) =>
      updateAssumption(projectId, assumption.id, { status }),
    onSuccess: invalidate,
  });

  const planMutation = useMutation({
    mutationFn: (assumptionId: string) =>
      generateValidationPlan(projectId, { assumption_ids: [assumptionId], max_plans: 1 }),
    onSuccess: invalidate,
  });

  const assumptions = assumptionsQuery.data ?? [];
  const risks = risksQuery.data ?? [];
  const error =
    assumptionsQuery.error ??
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
          {extractMutation.isPending ? "Extracting..." : "Extract"}
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
        runId={
          extractMutation.data?.ai_run_id ?? planMutation.data?.ai_run_id ?? null
        }
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
            <p className="mt-4 text-sm text-muted-foreground">
              No assumptions yet. Generate a brief or extract assumptions directly.
            </p>
          ) : (
            <div className="mt-4 space-y-4">
              {assumptions.map((assumption) => (
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
                      </div>
                      <p className="mt-3 text-sm leading-6 text-foreground">{assumption.text}</p>
                    </div>
                    <div className="shrink-0 text-sm text-muted-foreground">
                      {formatConfidence(assumption.confidence_score)}
                    </div>
                  </div>

                  {assumption.recommended_test ? (
                    <p className="mt-3 text-sm leading-6 text-muted-foreground">
                      {assumption.recommended_test}
                    </p>
                  ) : null}

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
                      disabled={planMutation.isPending}
                      onClick={() => planMutation.mutate(assumption.id)}
                      type="button"
                    >
                      <Beaker className="h-4 w-4" aria-hidden="true" />
                      {planMutation.isPending ? "Generating..." : "Validation Plan"}
                    </Button>
                  </div>
                </div>
              ))}
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
              <p className="text-sm text-muted-foreground">No risks recorded.</p>
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
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{risk.text}</p>
                  {risk.mitigation ? (
                    <p className="mt-2 border-t border-border pt-2 text-xs leading-5 text-muted-foreground">
                      {risk.mitigation}
                    </p>
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

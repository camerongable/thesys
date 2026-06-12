"use client";

import { CheckCircle2, Circle, ExternalLink, Loader2, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getWorkflowEventsUrl, WorkflowRun, WorkflowStep } from "@/lib/api";

type WorkflowTraceProps = {
  runId?: string | null;
  pending?: boolean;
  pendingSteps?: string[];
};

type TraceStep = Pick<
  WorkflowStep,
  "step_name" | "status" | "latency_ms" | "tokens" | "cost" | "error"
>;
const terminalStatuses = new Set(["succeeded", "failed", "cancelled", "waiting_for_human"]);

export function WorkflowTrace({ runId, pending = false, pendingSteps = [] }: WorkflowTraceProps) {
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const latestStatusRef = useRef<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      setStreamError(null);
      latestStatusRef.current = null;
      return;
    }

    latestStatusRef.current = null;
    let closedCleanly = false;
    const source = new EventSource(getWorkflowEventsUrl(runId));
    source.onmessage = (event) => {
      const nextRun = JSON.parse(event.data) as WorkflowRun;
      latestStatusRef.current = nextRun.status;
      setRun(nextRun);
      setStreamError(null);
      if (terminalStatuses.has(nextRun.status)) {
        closedCleanly = true;
        source.close();
      }
    };
    source.onerror = () => {
      if (closedCleanly || !terminalStatuses.has(latestStatusRef.current ?? "")) {
        return;
      }
      if (!closedCleanly) {
        setStreamError("Workflow event stream disconnected.");
      }
      source.close();
    };

    return () => {
      closedCleanly = true;
      source.close();
    };
  }, [runId]);

  if (!pending && !runId && !run) {
    return null;
  }

  const status = run?.status ?? (pending ? "running" : null);
  const steps: TraceStep[] =
    run?.steps ??
    pendingSteps.map((step_name) => ({
      step_name,
      status: "queued",
      latency_ms: null,
      tokens: null,
      cost: null,
      error: null,
    }));

  return (
    <details className="rounded-lg border border-border bg-card p-4">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Process details</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {run?.workflow_type ? friendlyWorkflowLabel(run.workflow_type) : "Evidence review is starting"}
            </p>
          </div>
          {status ? (
            <span className={statusClass(status)}>{formatLabel(status)}</span>
          ) : null}
        </div>
      </summary>

      <div className="mt-4 border-t border-border pt-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Debug details</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              {run?.workflow_type ? friendlyWorkflowLabel(run.workflow_type) : "Pending process"}
            </p>
            {run ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {run.model_provider ?? "unknown provider"} · {run.model_name ?? "unknown model"}
              </p>
            ) : null}
          </div>
          {status ? (
            <span className={statusClass(status)}>{formatLabel(status)}</span>
          ) : null}
        </div>

      {run ? (
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span className="rounded-md bg-muted px-2 py-1">
            Tokens: {run.total_tokens ?? "unavailable"}
          </span>
          <span className="rounded-md bg-muted px-2 py-1">
            Cost: {formatCost(run.total_cost)}
          </span>
          {run.langsmith_trace_url ? (
            <a
              className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-primary hover:underline"
              href={run.langsmith_trace_url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
              View trace
            </a>
          ) : null}
        </div>
      ) : null}

      {streamError ? (
        <div
          className="mt-3 break-words rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-xs text-danger-foreground"
          role="alert"
        >
          {streamError}
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        {steps.length === 0 ? (
          <div className="text-sm text-muted-foreground">Waiting for the first step...</div>
        ) : (
          steps.map((step, index) => (
            <div className="flex items-start gap-2 text-sm" key={`${step.step_name}-${index}`}>
              <StepIcon status={pending && !run ? pendingStepStatus(index) : step.status} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{friendlyStepLabel(step.step_name)}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatLabel(pending && !run ? pendingStepStatus(index) : step.status)}
                  </span>
                </div>
                {step.latency_ms !== null ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {[
                      `${step.latency_ms} ms`,
                      step.tokens !== null ? `${step.tokens} tokens` : null,
                      step.cost !== null ? formatCost(step.cost) : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                ) : null}
                {step.error ? (
                  <p className="mt-1 text-xs text-danger-foreground">{step.error}</p>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      {run?.output_summary ? (
        <p className="mt-4 border-t border-border pt-3 text-xs leading-5 text-muted-foreground">
          {run.output_summary}
        </p>
      ) : null}

      {run?.error ? (
        <p className="mt-4 border-t border-border pt-3 text-xs leading-5 text-danger-foreground">
          {run.error}
        </p>
      ) : null}
      </div>
    </details>
  );
}

function StepIcon({ status }: { status: string }) {
  if (status === "succeeded") {
    return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success-foreground" aria-hidden="true" />;
  }
  if (status === "failed") {
    return <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger-foreground" aria-hidden="true" />;
  }
  if (status === "running") {
    return <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />;
  }
  return <Circle className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />;
}

function pendingStepStatus(index: number) {
  return index === 0 ? "running" : "queued";
}

function statusClass(status: string) {
  if (status === "succeeded") {
    return "w-fit rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground";
  }
  if (status === "failed" || status === "cancelled") {
    return "w-fit rounded-md bg-danger-muted px-2 py-1 text-xs font-medium text-danger-foreground";
  }
  return "w-fit rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground";
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function friendlyWorkflowLabel(value: string) {
  const labels: Record<string, string> = {
    agentic_research: "Evidence memo generation",
    competitor_analysis: "Competitor analysis",
    evidence_retrieval: "Evidence search",
    evidence_ingestion: "Evidence added",
    opportunity_brief: "Brief generation",
    research_sprint_planning: "Evidence review planning",
    structured_intake: "Idea structuring",
    validation_plan: "Validation plan",
    assumption_extraction: "Assumption review",
  };
  return labels[value] ?? formatLabel(value);
}

function friendlyStepLabel(value: string) {
  const labels: Record<string, string> = {
    generate_research_plan: "Generate evidence plan",
    research_sprint_planning: "Evidence review planning",
  };
  return labels[value] ?? formatLabel(value);
}

function formatCost(value: string | null) {
  if (value === null) {
    return "unavailable";
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return value;
  }
  if (numeric === 0) {
    return "$0";
  }
  if (numeric < 0.01) {
    return `$${numeric.toFixed(6)}`;
  }
  return `$${numeric.toFixed(2)}`;
}

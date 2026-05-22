"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { getWorkflowEventsUrl, WorkflowRun, WorkflowStep } from "@/lib/api";

type WorkflowTraceProps = {
  runId?: string | null;
  pending?: boolean;
  pendingSteps?: string[];
};

type TraceStep = Pick<WorkflowStep, "step_name" | "status" | "latency_ms" | "error">;
const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);

export function WorkflowTrace({ runId, pending = false, pendingSteps = [] }: WorkflowTraceProps) {
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      setStreamError(null);
      return;
    }

    let closedCleanly = false;
    const source = new EventSource(getWorkflowEventsUrl(runId));
    source.onmessage = (event) => {
      const nextRun = JSON.parse(event.data) as WorkflowRun;
      setRun(nextRun);
      setStreamError(null);
      if (terminalStatuses.has(nextRun.status)) {
        closedCleanly = true;
        source.close();
      }
    };
    source.onerror = () => {
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
      error: null,
    }));

  return (
    <aside className="rounded-lg border border-border bg-white p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold">Workflow Trace</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {run?.workflow_type ? formatLabel(run.workflow_type) : "Pending workflow"}
          </p>
        </div>
        {status ? (
          <span className={statusClass(status)}>{formatLabel(status)}</span>
        ) : null}
      </div>

      {streamError ? (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
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
                  <span className="font-medium">{formatLabel(step.step_name)}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatLabel(pending && !run ? pendingStepStatus(index) : step.status)}
                  </span>
                </div>
                {step.latency_ms !== null ? (
                  <p className="mt-1 text-xs text-muted-foreground">{step.latency_ms} ms</p>
                ) : null}
                {step.error ? (
                  <p className="mt-1 text-xs text-red-700">{step.error}</p>
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
    </aside>
  );
}

function StepIcon({ status }: { status: string }) {
  if (status === "succeeded") {
    return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" aria-hidden="true" />;
  }
  if (status === "failed") {
    return <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-700" aria-hidden="true" />;
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
    return "w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700";
  }
  if (status === "failed" || status === "cancelled") {
    return "w-fit rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700";
  }
  return "w-fit rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground";
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

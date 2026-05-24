"use client";

import { AlertTriangle, BrainCircuit, CheckCircle2, ServerOff } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getAIStatus } from "@/lib/api";

export function AiModeIndicator() {
  const statusQuery = useQuery({
    queryKey: ["ai-status"],
    queryFn: getAIStatus,
    refetchInterval: 30000,
  });
  const status = statusQuery.data;

  if (statusQuery.isLoading) {
    return (
      <div className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 py-2 text-xs text-muted-foreground">
        <BrainCircuit className="h-4 w-4" aria-hidden="true" />
        Checking AI mode
      </div>
    );
  }

  if (statusQuery.isError || !status) {
    return (
      <div className="inline-flex min-h-10 items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
        <ServerOff className="h-4 w-4" aria-hidden="true" />
        AI status unavailable
      </div>
    );
  }

  const liveMode = status.resolved_mode === "live";
  const litellmReachable = status.litellm_reachability.reachable;
  const Icon = liveMode ? (litellmReachable ? CheckCircle2 : AlertTriangle) : BrainCircuit;
  const statusText = liveMode
    ? litellmReachable
      ? "LiteLLM reachable"
      : "LiteLLM unreachable"
    : "Deterministic responses";

  return (
    <div
      className={
        liveMode
          ? litellmReachable
            ? "inline-flex min-h-10 items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800"
            : "inline-flex min-h-10 items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
          : "inline-flex min-h-10 items-center gap-2 rounded-md border border-border bg-white px-3 py-2 text-xs text-muted-foreground"
      }
      title={`${status.litellm_base_url} · ${statusText}`}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="min-w-0">
        <span className="block font-medium text-foreground">
          {liveMode ? "Live LLM" : "Stub mode"}
        </span>
        <span className="block truncate">
          {status.litellm_model} · {statusText}
        </span>
      </span>
    </div>
  );
}

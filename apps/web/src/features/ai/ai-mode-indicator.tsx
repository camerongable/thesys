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
      <div className="inline-flex h-10 max-w-full min-w-0 items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
        <BrainCircuit className="h-4 w-4" aria-hidden="true" />
        <span className="truncate">Checking evidence engine</span>
      </div>
    );
  }

  if (statusQuery.isError || !status) {
    return (
      <div className="inline-flex h-10 max-w-full min-w-0 items-center gap-2 rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-xs text-danger-foreground">
        <ServerOff className="h-4 w-4" aria-hidden="true" />
        <span className="truncate">Evidence engine unavailable</span>
      </div>
    );
  }

  const liveMode = status.resolved_mode === "live";
  const litellmReachable = status.litellm_reachability.reachable;
  const Icon = liveMode ? (litellmReachable ? CheckCircle2 : AlertTriangle) : BrainCircuit;
  const operationalText = liveMode
    ? litellmReachable
      ? "LiteLLM reachable"
      : "LiteLLM unreachable"
    : "Deterministic responses";
  const productStatus = liveMode
    ? litellmReachable
      ? "Evidence engine live"
      : "Evidence engine limited"
    : "Local evidence mode";
  const productDetail = liveMode
    ? litellmReachable
      ? "Ready"
      : "Needs connection"
    : "Deterministic";
  const statusClassName = liveMode
    ? litellmReachable
      ? "inline-flex h-10 max-w-full min-w-0 items-center gap-2 rounded-md border border-success-border bg-success-muted px-3 py-2 text-xs text-success-foreground"
      : "inline-flex h-10 max-w-full min-w-0 items-center gap-2 rounded-md border border-warning-border bg-warning-muted px-3 py-2 text-xs text-warning-foreground"
    : "inline-flex h-10 max-w-full min-w-0 items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-xs text-muted-foreground";

  return (
    <div
      className={statusClassName}
      title={`${status.resolved_mode} · ${status.litellm_model} · ${status.litellm_base_url} · ${operationalText}`}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="min-w-0 truncate font-medium">
        {productStatus}
      </span>
      <span className="hidden shrink-0 opacity-80 md:inline">
        {productDetail}
      </span>
    </div>
  );
}

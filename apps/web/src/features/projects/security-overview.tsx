"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  CircleAlert,
  Database,
  FileWarning,
  Gauge,
  Network,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { DomainError } from "@/features/projects/decision-room";
import { getProjectSecurityOverview, type SecurityOverview } from "@/lib/api";

type MetricTone = "danger" | "neutral" | "warning";

type SecurityMetric = {
  icon: LucideIcon;
  label: string;
  tone: MetricTone;
  value: number;
};

export function SecurityOverview() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const overviewQuery = useQuery({
    queryKey: ["projects", projectId, "security-overview"],
    queryFn: () => getProjectSecurityOverview(projectId),
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1280px]">
        <div className="flex items-center justify-between gap-3">
          <Link
            className="-ml-2 inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            href={`/projects/${projectId}`}
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Project
          </Link>
          <div className="flex items-center gap-2">
            <button
              aria-label="Refresh security overview"
              className="inline-flex h-11 min-h-11 w-11 cursor-pointer items-center justify-center rounded-md border border-border bg-card text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-50 sm:h-10 sm:min-h-10 sm:w-10"
              disabled={overviewQuery.isFetching}
              onClick={() => void overviewQuery.refetch()}
              title="Refresh security overview"
              type="button"
            >
              <RefreshCw
                className={overviewQuery.isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"}
                aria-hidden="true"
              />
            </button>
            <ThemeToggle />
          </div>
        </div>

        {overviewQuery.isLoading ? (
          <SecurityOverviewSkeleton />
        ) : overviewQuery.isError ? (
          <div className="mt-8">
            <DomainError
              action={
                <Button
                  className="w-fit border-danger-border text-danger-foreground hover:bg-danger-muted"
                  onClick={() => void overviewQuery.refetch()}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  Retry
                </Button>
              }
              message={(overviewQuery.error as Error).message}
            />
          </div>
        ) : overviewQuery.data ? (
          <SecurityOverviewContent overview={overviewQuery.data} />
        ) : null}
      </div>
    </main>
  );
}

function SecurityOverviewContent({ overview }: { overview: SecurityOverview }) {
  const detectionMetrics: SecurityMetric[] = [
    {
      icon: ShieldAlert,
      label: "High-priority events",
      tone: overview.high_or_critical_event_count > 0 ? "danger" : "neutral",
      value: overview.high_or_critical_event_count,
    },
    {
      icon: AlertTriangle,
      label: "Blocked prompt attacks",
      tone: overview.blocked_prompt_attack_count > 0 ? "warning" : "neutral",
      value: overview.blocked_prompt_attack_count,
    },
    {
      icon: Wrench,
      label: "Denied tools",
      tone: overview.denied_tool_count > 0 ? "warning" : "neutral",
      value: overview.denied_tool_count,
    },
    {
      icon: FileWarning,
      label: "PII redactions",
      tone: overview.pii_redaction_count > 0 ? "warning" : "neutral",
      value: overview.pii_redaction_count,
    },
    {
      icon: Database,
      label: "Memory quarantines",
      tone: overview.memory_quarantine_count > 0 ? "warning" : "neutral",
      value: overview.memory_quarantine_count,
    },
    {
      icon: Network,
      label: "Anomalous retrieval",
      tone: overview.anomalous_retrieval_count > 0 ? "warning" : "neutral",
      value: overview.anomalous_retrieval_count,
    },
  ];
  const operationalMetrics: SecurityMetric[] = [
    {
      icon: CircleAlert,
      label: "Pending high-risk approvals",
      tone: overview.pending_high_risk_approval_count > 0 ? "warning" : "neutral",
      value: overview.pending_high_risk_approval_count,
    },
    {
      icon: Gauge,
      label: "Open budget alerts",
      tone: overview.budget_alert_count > 0 ? "warning" : "neutral",
      value: overview.budget_alert_count,
    },
    {
      icon: Network,
      label: "Active workflows",
      tone: "neutral",
      value: overview.active_workflow_count,
    },
    {
      icon: Ban,
      label: "Active kill switches",
      tone: overview.active_kill_switches.length > 0 ? "danger" : "neutral",
      value: overview.active_kill_switches.length,
    },
  ];

  return (
    <>
      <header className="mt-6 border-b border-border pb-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <span>Security Overview</span>
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal sm:text-3xl">
              Project security posture
            </h1>
          </div>
          <p className="shrink-0 text-xs text-muted-foreground">
            Updated {formatDateTime(overview.generated_at)}
          </p>
        </div>
      </header>

      <section aria-labelledby="security-detection-heading" className="mt-6">
        <SectionHeading id="security-detection-heading" title="Detection" />
        <dl className="mt-3 grid border-y border-border sm:grid-cols-2 xl:grid-cols-3">
          {detectionMetrics.map((metric) => (
            <MetricRow key={metric.label} metric={metric} />
          ))}
        </dl>
      </section>

      <section aria-labelledby="security-operations-heading" className="mt-7">
        <SectionHeading id="security-operations-heading" title="Operations" />
        <dl className="mt-3 grid border-y border-border sm:grid-cols-2 xl:grid-cols-4">
          {operationalMetrics.map((metric) => (
            <MetricRow key={metric.label} metric={metric} />
          ))}
        </dl>
      </section>

      <div className="mt-7 grid gap-7 lg:grid-cols-2">
        <section aria-labelledby="security-containment-heading" className="border-t border-border pt-4">
          <SectionHeading id="security-containment-heading" title="Containment" />
          {overview.active_kill_switches.length === 0 ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
              <span>No kill switches are active.</span>
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-border border-y border-border">
              {overview.active_kill_switches.map((switchState) => (
                <li className="flex items-center justify-between gap-4 py-3 text-sm" key={switchState.name}>
                  <span className="font-medium text-foreground">{formatSwitchName(switchState.name)}</span>
                  <span className="text-xs font-medium text-danger-foreground">Active</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="security-mcp-heading" className="border-t border-border pt-4">
          <SectionHeading id="security-mcp-heading" title="MCP servers" />
          {overview.mcp_servers.length === 0 ? (
            <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
              <span>No reviewed MCP servers are registered.</span>
            </div>
          ) : (
            <ul className="mt-4 divide-y divide-border border-y border-border">
              {overview.mcp_servers.map((server) => (
                <li className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4" key={server.name}>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{server.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Version {server.approved_version} · Reviewed {formatDateTime(server.reviewed_at)}
                    </p>
                  </div>
                  <span className={server.enabled ? "text-xs font-medium text-success-foreground" : "text-xs font-medium text-muted-foreground"}>
                    {server.enabled ? "Enabled" : "Disabled"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}

function MetricRow({ metric }: { metric: SecurityMetric }) {
  const Icon = metric.icon;
  return (
    <div className="flex min-h-24 items-center gap-3 border-b border-border px-1 py-4 sm:px-4 sm:[&:nth-last-child(-n+2)]:border-b-0 xl:[&:nth-last-child(-n+3)]:border-b-0">
      <Icon className={metricIconClass(metric.tone)} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <dt className="text-xs leading-5 text-muted-foreground">{metric.label}</dt>
        <dd className="mt-1 text-2xl font-semibold tracking-normal text-foreground">{metric.value}</dd>
      </div>
    </div>
  );
}

function SecurityOverviewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading security overview" className="mt-6 animate-pulse motion-reduce:animate-none">
      <div className="border-b border-border pb-5">
        <div className="h-4 w-36 rounded bg-muted" />
        <div className="mt-3 h-8 w-full max-w-md rounded bg-muted" />
      </div>
      <div className="mt-6 grid border-y border-border sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <div className="h-24 border-b border-border sm:px-4 xl:[&:nth-last-child(-n+3)]:border-b-0" key={index} />
        ))}
      </div>
    </div>
  );
}

function SectionHeading({ id, title }: { id: string; title: string }) {
  return (
    <h2 className="text-sm font-semibold text-foreground" id={id}>
      {title}
    </h2>
  );
}

function metricIconClass(tone: MetricTone) {
  if (tone === "danger") {
    return "h-4 w-4 shrink-0 text-danger";
  }
  if (tone === "warning") {
    return "h-4 w-4 shrink-0 text-warning";
  }
  return "h-4 w-4 shrink-0 text-muted-foreground";
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "unavailable";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function formatSwitchName(name: string) {
  return name.replace(/^disable_/, "Disable ").replaceAll("_", " ");
}

"use client";

import {
  Activity,
  ArrowLeft,
  Beaker,
  ClipboardCheck,
  FileText,
  ScrollText,
  ShieldAlert,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  getMvpEval,
  getProject,
  listArtifacts,
  listAssumptions,
  listCompetitors,
  listDecisions,
  listExperiments,
  listProjectWorkflows,
} from "@/lib/api";
import { AiModeIndicator } from "@/features/ai/ai-mode-indicator";
import { AssumptionsTab } from "@/features/projects/assumptions-tab";
import { BriefTab } from "@/features/projects/brief-tab";
import { CompetitorsTab } from "@/features/projects/competitors-tab";
import { DecisionsTab } from "@/features/projects/decisions-tab";
import { EvidenceTab } from "@/features/projects/evidence-tab";
import { ExperimentsTab } from "@/features/projects/experiments-tab";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { StructuredIntakeWizard } from "@/features/projects/structured-intake-wizard";

const emptyStates = [
  { label: "Opportunity Brief", detail: "No brief generated yet.", icon: FileText },
  { label: "Competitors", detail: "No competitors analyzed yet.", icon: Users },
  { label: "Assumptions", detail: "No assumptions extracted yet.", icon: ShieldAlert },
  { label: "Experiments", detail: "No validation plans generated yet.", icon: Beaker },
  { label: "Decisions", detail: "No decisions recorded yet.", icon: ScrollText },
];

const tabs = [
  "Overview",
  "Brief",
  "Evidence",
  "Competitors",
  "Assumptions",
  "Experiments",
  "Decisions",
] as const;
type ProjectTab = (typeof tabs)[number];

export function ProjectOverview() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [activeTab, setActiveTab] = useState<ProjectTab>("Overview");
  const projectQuery = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => getProject(projectId),
  });
  const briefArtifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts", "opportunity_brief"],
    queryFn: () => listArtifacts(projectId, "opportunity_brief"),
  });
  const competitorsQuery = useQuery({
    queryKey: ["projects", projectId, "competitors"],
    queryFn: () => listCompetitors(projectId),
  });
  const assumptionsQuery = useQuery({
    queryKey: ["projects", projectId, "assumptions"],
    queryFn: () => listAssumptions(projectId),
  });
  const experimentsQuery = useQuery({
    queryKey: ["projects", projectId, "experiments"],
    queryFn: () => listExperiments(projectId),
  });
  const decisionsQuery = useQuery({
    queryKey: ["projects", projectId, "decisions"],
    queryFn: () => listDecisions(projectId),
  });
  const evalQuery = useQuery({
    queryKey: ["projects", projectId, "evals", "mvp"],
    queryFn: () => getMvpEval(projectId),
  });
  const workflowsQuery = useQuery({
    queryKey: ["projects", projectId, "workflows"],
    queryFn: () => listProjectWorkflows(projectId, 5),
  });

  const project = projectQuery.data;
  const opportunityBriefCount = briefArtifactsQuery.data?.length ?? 0;
  const competitors = competitorsQuery.data ?? [];
  const assumptions = assumptionsQuery.data ?? [];
  const experiments = experimentsQuery.data ?? [];
  const decisions = decisionsQuery.data ?? [];
  const analyzedCompetitorCount = competitors.filter(
    (competitor) => competitor.last_analyzed_at !== null,
  ).length;
  const overviewCards = emptyStates.map((item) =>
    item.label === "Opportunity Brief"
      ? briefOverviewCard(item, briefArtifactsQuery.isLoading, opportunityBriefCount)
      : item.label === "Competitors"
        ? competitorOverviewCard(
            item,
            competitorsQuery.isLoading,
            competitors.length,
            analyzedCompetitorCount,
          )
        : item.label === "Assumptions"
          ? countOverviewCard(item, assumptionsQuery.isLoading, assumptions.length, "assumption")
          : item.label === "Experiments"
            ? countOverviewCard(item, experimentsQuery.isLoading, experiments.length, "experiment")
            : item.label === "Decisions"
              ? countOverviewCard(item, decisionsQuery.isLoading, decisions.length, "decision")
              : item,
  );

  return (
    <main className="min-h-screen px-5 py-6 md:px-8">
      <div className="mx-auto max-w-6xl">
        <Link
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          href="/projects"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Projects
        </Link>

        {projectQuery.isLoading ? (
          <div className="mt-8 text-sm text-muted-foreground">Loading project...</div>
        ) : projectQuery.isError ? (
          <div className="mt-8 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {(projectQuery.error as Error).message}
          </div>
        ) : project ? (
          <>
            <header className="mt-6 border-b border-border pb-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Project Overview</p>
                  <h1 className="mt-1 text-2xl font-semibold tracking-normal">{project.name}</h1>
                  <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                    {project.short_description ?? "No description"}
                  </p>
                </div>
                <div className="flex flex-col gap-2 sm:items-end">
                  <AiModeIndicator />
                  <span className="w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                    {project.status}
                  </span>
                </div>
              </div>
            </header>

            <nav
              className="mt-5 flex gap-2 overflow-x-auto border-b border-border"
              aria-label="Project sections"
            >
              {tabs.map((tab) => (
                <button
                  className={
                    activeTab === tab
                      ? "cursor-pointer border-b-2 border-primary px-3 py-2 text-sm font-medium text-foreground"
                      : "cursor-pointer px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
                  }
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  type="button"
                >
                  {tab}
                </button>
              ))}
            </nav>

            {activeTab === "Overview" ? (
              <>
                <section className="mt-6 rounded-lg border border-border bg-white p-5">
                  <h2 className="text-base font-semibold">Current Thesis</h2>
                  <MarkdownContent
                    className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground"
                    markdown={project.current_thesis?.thesis_text ?? "No thesis recorded yet."}
                  />
                </section>

                {project.customer_segments.length > 0 || project.problems.length > 0 ? (
                  <section className="mt-6 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-lg border border-border bg-white p-5">
                      <h2 className="text-base font-semibold">Customer Segments</h2>
                      <div className="mt-3 space-y-3">
                        {project.customer_segments.map((segment) => (
                          <div key={segment.id}>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium">{segment.name}</span>
                              {segment.priority ? (
                                <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                                  {segment.priority}
                                </span>
                              ) : null}
                            </div>
                            <MarkdownContent
                              className="mt-1 space-y-2 text-sm leading-6 text-muted-foreground"
                              markdown={segment.description ?? "No segment notes yet."}
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-border bg-white p-5">
                      <h2 className="text-base font-semibold">Problem Hypotheses</h2>
                      <div className="mt-3 space-y-3">
                        {project.problems.map((problem) => (
                          <div key={problem.id}>
                            <MarkdownContent
                              className="space-y-2 text-sm font-medium leading-6 text-foreground"
                              markdown={problem.description}
                            />
                            <p className="mt-1 text-sm text-muted-foreground">
                              Severity: {problem.severity ?? "unknown"}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </section>
                ) : null}

                <StructuredIntakeWizard project={project} />

                <section className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                  <div className="rounded-lg border border-border bg-white p-5">
                    <div className="flex items-center gap-2">
                      <ClipboardCheck className="h-4 w-4 text-primary" aria-hidden="true" />
                      <h2 className="text-base font-semibold">MVP Readiness</h2>
                    </div>
                    {evalQuery.isLoading ? (
                      <p className="mt-4 text-sm text-muted-foreground">Checking demo flow...</p>
                    ) : evalQuery.isError ? (
                      <p className="mt-4 text-sm text-red-700">
                        {(evalQuery.error as Error).message}
                      </p>
                    ) : evalQuery.data ? (
                      <>
                        <div className="mt-4 flex items-end gap-2">
                          <span className="text-3xl font-semibold">
                            {evalQuery.data.score}/{evalQuery.data.total}
                          </span>
                          <span className="pb-1 text-sm text-muted-foreground">
                            checks passed
                          </span>
                        </div>
                        <div className="mt-4 space-y-2">
                          {evalQuery.data.checks.slice(0, 6).map((check) => (
                            <div
                              className="flex items-start justify-between gap-3 text-sm"
                              key={check.key}
                            >
                              <span className="text-muted-foreground">{check.label}</span>
                              <span
                                className={
                                  check.passed
                                    ? "text-xs font-medium text-emerald-700"
                                    : "text-xs font-medium text-red-700"
                                }
                              >
                                {check.passed ? "pass" : "open"}
                              </span>
                            </div>
                          ))}
                        </div>
                      </>
                    ) : null}
                  </div>

                  <div className="rounded-lg border border-border bg-white p-5">
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-primary" aria-hidden="true" />
                      <h2 className="text-base font-semibold">Recent Workflows</h2>
                    </div>
                    {workflowsQuery.isLoading ? (
                      <p className="mt-4 text-sm text-muted-foreground">Loading workflow runs...</p>
                    ) : workflowsQuery.isError ? (
                      <p className="mt-4 text-sm text-red-700">
                        {(workflowsQuery.error as Error).message}
                      </p>
                    ) : workflowsQuery.data && workflowsQuery.data.length > 0 ? (
                      <div className="mt-4 divide-y divide-border">
                        {workflowsQuery.data.map((run) => (
                          <div className="py-3" key={run.id}>
                            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                              <span className="text-sm font-medium">
                                {formatLabel(run.workflow_type)}
                              </span>
                              <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                                {formatLabel(run.status)}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {run.steps.length} step{run.steps.length === 1 ? "" : "s"}
                              {run.completed_at
                                ? ` · ${new Date(run.completed_at).toLocaleString()}`
                                : ""}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-4 text-sm text-muted-foreground">
                        No workflow runs recorded yet.
                      </p>
                    )}
                  </div>
                </section>

                <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {overviewCards.map((item) => {
                    const Icon = item.icon;
                    return (
                      <div key={item.label} className="rounded-lg border border-border bg-white p-5">
                        <div className="flex items-center justify-between">
                          <h2 className="text-base font-semibold">{item.label}</h2>
                          <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                        </div>
                        <p className="mt-3 text-sm text-muted-foreground">{item.detail}</p>
                      </div>
                    );
                  })}
                </section>
              </>
            ) : activeTab === "Brief" ? (
              <BriefTab projectId={project.id} />
            ) : activeTab === "Evidence" ? (
              <EvidenceTab projectId={project.id} />
            ) : activeTab === "Competitors" ? (
              <CompetitorsTab projectId={project.id} />
            ) : activeTab === "Assumptions" ? (
              <AssumptionsTab projectId={project.id} />
            ) : activeTab === "Experiments" ? (
              <ExperimentsTab projectId={project.id} />
            ) : (
              <DecisionsTab projectId={project.id} />
            )}
          </>
        ) : null}
      </div>
    </main>
  );
}

function briefOverviewCard(
  item: (typeof emptyStates)[number],
  isLoading: boolean,
  opportunityBriefCount: number,
) {
  if (isLoading) {
    return { ...item, detail: "Checking generated briefs..." };
  }
  if (opportunityBriefCount > 0) {
    return {
      ...item,
      detail: `${opportunityBriefCount} generated brief${
        opportunityBriefCount === 1 ? "" : "s"
      }`,
    };
  }
  return item;
}

function competitorOverviewCard(
  item: (typeof emptyStates)[number],
  isLoading: boolean,
  competitorCount: number,
  analyzedCompetitorCount: number,
) {
  if (isLoading) {
    return { ...item, detail: "Checking competitors..." };
  }
  if (analyzedCompetitorCount > 0) {
    return {
      ...item,
      detail: `${analyzedCompetitorCount} analyzed competitor${
        analyzedCompetitorCount === 1 ? "" : "s"
      }`,
    };
  }
  if (competitorCount > 0) {
    return {
      ...item,
      detail: `${competitorCount} saved competitor${competitorCount === 1 ? "" : "s"}`,
    };
  }
  return { ...item, detail: "No competitors added yet." };
}

function countOverviewCard(
  item: (typeof emptyStates)[number],
  isLoading: boolean,
  count: number,
  noun: string,
) {
  if (isLoading) {
    return { ...item, detail: `Checking ${noun}s...` };
  }
  if (count > 0) {
    return { ...item, detail: `${count} ${noun}${count === 1 ? "" : "s"}` };
  }
  return item;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

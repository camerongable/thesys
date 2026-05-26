"use client";

import {
  ArrowLeft,
  AlertTriangle,
  Beaker,
  Building2,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Database,
  ExternalLink,
  FileSearch,
  FileText,
  Globe2,
  Lightbulb,
  ListChecks,
  Route,
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  approveAgenticResearchMemo,
  approveCompetitorCandidate,
  approveDiscoveredSource,
  approveResearchSprint,
  Artifact,
  ArtifactVersion,
  Citation,
  CompetitorCandidate,
  CompetitorCandidateUpdateInput,
  discoverCompetitorCandidates,
  discoverSources,
  DiscoveredSource,
  executeNextAction,
  getProjectResearchHistory,
  getProjectOverview,
  getV1ResearchEval,
  IdeaReadiness,
  listArtifacts,
  listCompetitorCandidates,
  listDiscoveredSources,
  listResearchSprints,
  NextBestAction,
  ProjectStage,
  rejectCompetitorCandidate,
  rejectDiscoveredSource,
  rejectAgenticResearchMemo,
  rejectResearchSprint,
  ResearchPlan,
  ResearchPlanUpdateInput,
  ResearchSprint,
  runAgenticResearch,
  StrategicSnapshot,
  StrategicRecommendation,
  startResearchSprintPlan,
  updateCompetitorCandidate,
  updateResearchPlan,
} from "@/lib/api";
import { AssumptionsTab } from "@/features/projects/assumptions-tab";
import { BriefTab } from "@/features/projects/brief-tab";
import { CompetitorsTab } from "@/features/projects/competitors-tab";
import { DecisionsTab } from "@/features/projects/decisions-tab";
import { EvidenceTab } from "@/features/projects/evidence-tab";
import { ExperimentsTab } from "@/features/projects/experiments-tab";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { StructuredIntakeWizard } from "@/features/projects/structured-intake-wizard";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

const tabs = [
  "Overview",
  "Research",
  "Evidence",
  "Competitors",
  "Assumptions",
  "Validation",
  "Decisions",
] as const;
type ProjectTab = (typeof tabs)[number];

export function ProjectOverview() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [activeTab, setActiveTab] = useState<ProjectTab>("Overview");
  const overviewQuery = useQuery({
    queryKey: ["projects", projectId, "overview"],
    queryFn: () => getProjectOverview(projectId),
  });
  const nextActionMutation = useMutation({
    mutationFn: () => executeNextAction(projectId),
    onSuccess: activateAction,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const tab = tabFromHash(window.location.hash);
    if (tab) {
      setActiveTab(tab);
    }
  }, []);

  const overview = overviewQuery.data;
  const project = overview?.project;

  function selectTab(tab: ProjectTab) {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${tab.toLowerCase()}`);
    }
  }

  function runAction(action: NextBestAction) {
    activateAction(action);
    if (action.primary) {
      nextActionMutation.mutate();
    }
  }

  function activateAction(action: NextBestAction) {
    const tab = tabForAction(action);
    const anchor = anchorForAction(action);
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${anchor ?? tab.toLowerCase()}`);
    }
    if (anchor) {
      window.setTimeout(() => {
        const target = document.getElementById(anchor);
        if (target) {
          window.scrollTo({
            top: target.getBoundingClientRect().top + window.scrollY - 16,
            behavior: "auto",
          });
        }
        document.getElementById("structured-intake-raw-idea")?.focus({ preventScroll: true });
      }, 50);
    }
  }

  async function refreshOverviewAfterIntake() {
    const result = await overviewQuery.refetch();
    return result.data?.next_best_action.label ?? null;
  }

  return (
    <main className="min-h-screen px-5 py-6 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-center justify-between gap-3">
          <Link
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            href="/projects"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Projects
          </Link>
          <ThemeToggle />
        </div>

        {overviewQuery.isLoading ? (
          <div className="mt-8 text-sm text-muted-foreground">Loading project...</div>
        ) : overviewQuery.isError ? (
          <div className="mt-8 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {(overviewQuery.error as Error).message}
          </div>
        ) : overview && project ? (
          <>
            <header className="mt-6 border-b border-border pb-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                      {formatStage(overview.strategic_snapshot.current_stage)}
                    </span>
                    <span className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                      {formatLabel(project.status)}
                    </span>
                  </div>
                  <h1 className="mt-3 text-2xl font-semibold tracking-normal">{project.name}</h1>
                  <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                    {project.short_description ?? "No description recorded yet."}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Last updated {formatDateTime(project.updated_at)}
                  </p>
                  <div className="mt-4 max-w-3xl">
                    <LifecycleMiniRail currentStage={overview.strategic_snapshot.current_stage} />
                  </div>
                </div>
                <ProjectHeaderStatus overview={overview} />
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
                  onClick={() => selectTab(tab)}
                  type="button"
                >
                  {tab}
                </button>
              ))}
            </nav>

            {activeTab === "Overview" ? (
              <GuidedOverview
                actionPending={nextActionMutation.isPending}
                onAction={runAction}
                onIntakeFinalized={refreshOverviewAfterIntake}
                overview={overview}
              />
            ) : activeTab === "Research" ? (
              <ResearchTab overview={overview} />
            ) : activeTab === "Evidence" ? (
              <EvidenceTab projectId={project.id} />
            ) : activeTab === "Competitors" ? (
              <CompetitorsTab projectId={project.id} />
            ) : activeTab === "Assumptions" ? (
              <AssumptionsTab
                onOpenExperiments={() => selectTab("Validation")}
                projectId={project.id}
              />
            ) : activeTab === "Validation" ? (
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

function GuidedOverview({
  actionPending,
  onAction,
  onIntakeFinalized,
  overview,
}: {
  actionPending: boolean;
  onAction: (action: NextBestAction) => void;
  onIntakeFinalized: () => Promise<string | null>;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const { current_recommendation, next_best_action } = overview;
  const snapshot = overview.strategic_snapshot;
  const showIntake =
    snapshot.current_stage === "draft_idea" ||
    snapshot.current_stage === "structured_intake" ||
    !snapshot.current_thesis ||
    !snapshot.target_user ||
    !snapshot.primary_problem;

  return (
    <section className="mt-6 space-y-6">
      <OverviewStatusPanel
        actionPending={actionPending}
        currentRecommendation={current_recommendation}
        nextBestAction={next_best_action}
        onAction={onAction}
        overview={overview}
      />

      {showIntake ? (
        <StructuredIntakeWizard
          onFinalized={onIntakeFinalized}
          project={overview.project}
        />
      ) : null}

      <LifecycleProgressCard overview={overview} />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <StrategicSnapshotCard snapshot={overview.strategic_snapshot} />
        <EvidenceHealthCard health={overview.evidence_health} />
      </div>

      <TopRisksCard risks={overview.key_risks} />

      <RecentUpdatesCard updates={overview.recent_strategic_updates} />
    </section>
  );
}

function ProjectHeaderStatus({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const health = projectHealth(overview);
  return (
    <div className="rounded-lg border border-border bg-white p-3 sm:w-80">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
          Project health
        </span>
        <HealthBadge health={health} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
        <HeaderStatusMetric label="Stage" value={formatStage(overview.strategic_snapshot.current_stage)} />
        <HeaderStatusMetric label="Readiness" value={`${overview.idea_readiness.score}%`} />
        <HeaderStatusMetric label="Evidence" value={`${overview.evidence_health.source_count} sources`} />
        <HeaderStatusMetric label="Focus" value={overview.next_best_action.label} />
      </div>
    </div>
  );
}

function HeaderStatusMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[0.68rem] uppercase tracking-normal text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 truncate text-xs font-medium text-foreground" title={value}>
        {value}
      </div>
    </div>
  );
}

function OverviewStatusPanel({
  actionPending,
  currentRecommendation,
  nextBestAction,
  onAction,
  overview,
}: {
  actionPending: boolean;
  currentRecommendation: StrategicRecommendation;
  nextBestAction: NextBestAction;
  onAction: (action: NextBestAction) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const health = projectHealth(overview);
  const metrics = [
    ["Stage", formatStage(overview.strategic_snapshot.current_stage)],
    ["Confidence", formatLabel(currentRecommendation.confidence)],
    ["Evidence", `${overview.evidence_health.source_count} sources`],
    ["Readiness", `${overview.idea_readiness.score}%`],
  ] as const;

  return (
    <div className="rounded-lg border border-border bg-white">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Current State</h2>
            </div>
            <HealthBadge health={health} />
          </div>
          <h3 className="mt-4 text-xl font-semibold tracking-normal">
            {currentRecommendation.recommendation}
          </h3>
          <MarkdownContent
            className="mt-3 max-w-3xl space-y-2 text-sm leading-6 text-muted-foreground"
            markdown={currentRecommendation.rationale}
          />
          <div className="mt-5 overflow-hidden rounded-md border border-border">
            <div className="grid divide-y divide-border text-sm sm:grid-cols-4 sm:divide-x sm:divide-y-0">
              {metrics.map(([label, value]) => (
                <div className="px-3 py-2" key={label}>
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className="mt-1 break-words font-medium leading-5 text-foreground">
                    {value}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            {health.detail}
          </p>
        </div>

        <aside
          className="border-t border-border p-5 lg:border-l lg:border-t-0"
          id="next-best-action"
        >
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-sm font-semibold">Next Best Action</h2>
          </div>
          <h3 className="mt-4 text-lg font-semibold tracking-normal">
            {nextBestAction.label}
          </h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {nextBestAction.description}
          </p>
          <p className="mt-3 border-l-2 border-primary/50 pl-3 text-sm leading-6 text-muted-foreground">
            {nextBestAction.why_it_matters}
          </p>
          <Button
            className="mt-4 w-full"
            disabled={actionPending}
            onClick={() => onAction(nextBestAction)}
            type="button"
          >
            <Target className="h-4 w-4" aria-hidden="true" />
            {actionPending ? "Opening..." : nextBestAction.label}
          </Button>
          {overview.secondary_actions.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {overview.secondary_actions.map((action) => (
                <Button
                  key={action.action_type}
                  onClick={() => onAction(action)}
                  size="sm"
                  type="button"
                  variant="secondary"
                >
                  {action.label}
                </Button>
              ))}
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function ResearchTab({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  return (
    <section className="mt-6 space-y-6">
      <PageIntro
        actionLabel="Run Research Sprint"
        description="Use the research agent to plan the investigation, discover sources and competitors, synthesize a cited memo, and decide what to validate next."
        eyebrow="Research"
        title="What did the system investigate, and what did it conclude?"
      />

      <ResearchSprintSummary projectId={overview.project.id} />
      <ResearchSprintCard projectId={overview.project.id} />

      <details className="rounded-lg border border-border bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold">Show opportunity brief</summary>
        <div className="mt-5 border-t border-border pt-5">
          <BriefTab projectId={overview.project.id} />
        </div>
      </details>
    </section>
  );
}

function PageIntro({
  actionLabel,
  description,
  eyebrow,
  title,
}: {
  actionLabel: string;
  description: string;
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
            {eyebrow}
          </p>
          <h2 className="mt-2 text-xl font-semibold tracking-normal">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-3 py-2 text-xs font-medium text-muted-foreground">
          Primary action: {actionLabel}
        </span>
      </div>
    </div>
  );
}

function LifecycleMiniRail({ currentStage }: { currentStage: ProjectStage }) {
  const currentIndex = lifecycleStepIndex(currentStage);
  const steps = ["Idea", "Research", "Evidence", "Assumptions", "Validation", "Decision"];

  return (
    <div className="grid grid-cols-6 gap-1" aria-label="Idea validation lifecycle">
      {steps.map((step, index) => {
        const done = index < currentIndex;
        const current = index === currentIndex;
        return (
          <div key={step}>
            <div
              className={
                done
                  ? "h-1.5 rounded-full bg-emerald-600"
                  : current
                    ? "h-1.5 rounded-full bg-amber-500"
                    : "h-1.5 rounded-full bg-muted"
              }
            />
            <div
              className={
                current
                  ? "mt-1 truncate text-[0.68rem] font-medium text-foreground"
                  : "mt-1 truncate text-[0.68rem] text-muted-foreground"
              }
            >
              {step}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ResearchWorkflowTimeline({
  history,
  sprint,
}: {
  history: NonNullable<Awaited<ReturnType<typeof getProjectResearchHistory>>>["sprints"][number] | null;
  sprint: ResearchSprint;
}) {
  const steps = [
    {
      label: "Planned research",
      complete: true,
      detail: `${sprint.plan.research_questions.length} research question${
        sprint.plan.research_questions.length === 1 ? "" : "s"
      }`,
    },
    {
      label: "Discovered sources",
      complete: (history?.source_candidate_count ?? 0) > 0,
      detail: `${history?.source_candidate_count ?? 0} candidate${
        (history?.source_candidate_count ?? 0) === 1 ? "" : "s"
      }`,
    },
    {
      label: "Found competitors",
      complete: (history?.competitor_candidate_count ?? 0) > 0,
      detail: `${history?.competitor_candidate_count ?? 0} candidate${
        (history?.competitor_candidate_count ?? 0) === 1 ? "" : "s"
      }`,
    },
    {
      label: "Added evidence",
      complete: (history?.ingested_source_count ?? 0) > 0,
      detail: `${history?.ingested_source_count ?? 0} source${
        (history?.ingested_source_count ?? 0) === 1 ? "" : "s"
      } added`,
    },
    {
      label: "Generated memo",
      complete: Boolean(history?.memo_artifact_id),
      detail: history?.memo_artifact_id ? "Memo ready" : "Not generated",
    },
    {
      label: "Updated strategy",
      complete: history?.memory_update_status === "approved",
      detail: history?.memory_update_status
        ? formatLabel(history.memory_update_status)
        : "Awaiting approval",
    },
  ];
  return (
    <div className="mt-5 rounded-md border border-border p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold">Research workflow</h4>
          <p className="mt-1 text-xs text-muted-foreground">
            Inspect the run as plain-language steps before accepting strategy updates.
          </p>
        </div>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          Clay-style execution view
        </span>
      </div>
      <div className="mt-4 overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[680px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-normal text-muted-foreground">
              <th className="px-3 py-2 font-medium">Step</th>
              <th className="px-3 py-2 font-medium">Health</th>
              <th className="px-3 py-2 font-medium">Output</th>
              <th className="px-3 py-2 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {steps.map((step, index) => (
              <tr key={step.label}>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                      {index + 1}
                    </span>
                    <span className="font-medium">{step.label}</span>
                  </div>
                </td>
                <td className="px-3 py-3">
                  <span
                    className={
                      step.complete
                        ? "inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-700"
                        : "inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                    }
                  >
                    {step.complete ? (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {step.complete ? "Complete" : "Needs work"}
                  </span>
                </td>
                <td className="px-3 py-3 text-muted-foreground">{step.detail}</td>
                <td className="px-3 py-3 text-muted-foreground">
                  {step.complete ? "Review" : "Run sprint"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResearchSprintSummary({ projectId }: { projectId: string }) {
  const sprintsQuery = useQuery({
    queryKey: ["projects", projectId, "research-sprints", "summary"],
    queryFn: () => listResearchSprints(projectId),
  });
  const historyQuery = useQuery({
    queryKey: ["projects", projectId, "research-history", "summary"],
    queryFn: () => getProjectResearchHistory(projectId),
  });
  const latestSprint = sprintsQuery.data?.[0] ?? null;
  const latestHistory = historyQuery.data?.sprints[0] ?? null;

  if (sprintsQuery.isLoading || historyQuery.isLoading) {
    return <div className="rounded-lg border border-border bg-white p-5 text-sm text-muted-foreground">Loading latest research...</div>;
  }

  if (!latestSprint) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-white p-5">
        <h3 className="text-sm font-semibold">No research sprint yet.</h3>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Run a research sprint to discover sources, identify competitors, gather evidence,
          and generate a cited strategic memo.
        </p>
      </div>
    );
  }

  const metrics = [
    ["Status", formatLabel(latestSprint.status)],
    ["Sources discovered", latestHistory?.source_candidate_count ?? 0],
    ["Sources added", latestHistory?.ingested_source_count ?? 0],
    ["Competitors found", latestHistory?.competitor_candidate_count ?? 0],
    ["Competitors saved", latestHistory?.merged_competitor_count ?? 0],
    ["Strategy update", latestHistory?.memory_update_status ? formatLabel(latestHistory.memory_update_status) : "pending"],
  ] as const;

  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold">Latest Research Sprint</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {latestSprint.plan.objective}
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {formatDateTime(latestSprint.updated_at)}
        </span>
      </div>
      <div className="mt-4 overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[620px] border-collapse text-left text-sm">
          <tbody className="divide-y divide-border">
            {metrics.map(([label, value]) => (
              <tr key={label}>
                <th className="w-48 px-3 py-2 text-xs font-medium uppercase tracking-normal text-muted-foreground">
                  {label}
                </th>
                <td className="px-3 py-2 font-semibold">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {latestHistory?.recommendation_change ? (
        <div className="mt-4 rounded-md border border-border p-3">
          <h4 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
            Recommendation change
          </h4>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {truncate(latestHistory.recommendation_change, 260)}
          </p>
        </div>
      ) : null}
      <ResearchWorkflowTimeline sprint={latestSprint} history={latestHistory} />
    </div>
  );
}

type ResearchPlanDraftState = {
  objective: string;
  target_customer_hypotheses: string;
  research_questions: string;
  competitor_queries: string;
  market_queries: string;
  substitute_queries: string;
  source_types: string;
  assumptions_to_test: string;
  expected_outputs: string;
};

type MemoryUpdateSummary = {
  assumption_ids: string[];
  risk_ids: string[];
  recommended_validation_actions: string[];
};

function ResearchSprintCard({ projectId }: { projectId: string }) {
  const [objective, setObjective] = useState("");
  const [draft, setDraft] = useState<ResearchPlanDraftState | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const sprintsQuery = useQuery({
    queryKey: ["projects", projectId, "research-sprints"],
    queryFn: () => listResearchSprints(projectId),
  });
  const latestSprint = sprintsQuery.data?.[0] ?? null;

  useEffect(() => {
    if (!latestSprint || latestSprint.status !== "planned") {
      return;
    }
    setDraft(planToDraftState(latestSprint.plan));
    setLastRunId(latestSprint.ai_run_id);
  }, [latestSprint?.id, latestSprint?.status]);

  const startMutation = useMutation({
    mutationFn: () =>
      startResearchSprintPlan(projectId, {
        objective: objective.trim() || undefined,
      }),
    onSuccess: async (result) => {
      setObjective("");
      setDraft(planToDraftState(result.sprint.plan));
      setLastRunId(result.ai_run_id);
      await sprintsQuery.refetch();
    },
  });
  const saveMutation = useMutation({
    mutationFn: () => {
      if (!latestSprint || !draft) {
        throw new Error("No draft research plan to save.");
      }
      return updateResearchPlan(projectId, latestSprint.plan.id, draftToUpdate(draft));
    },
    onSuccess: async (plan) => {
      setDraft(planToDraftState(plan));
      await sprintsQuery.refetch();
    },
  });
  const approveMutation = useMutation({
    mutationFn: () => {
      if (!latestSprint) {
        throw new Error("No research sprint to approve.");
      }
      return approveResearchSprint(
        projectId,
        latestSprint.id,
        draft ? draftToUpdate(draft) : {},
      );
    },
    onSuccess: async (result) => {
      setDraft(planToDraftState(result.sprint.plan));
      setLastRunId(result.ai_run_id);
      await sprintsQuery.refetch();
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => {
      if (!latestSprint) {
        throw new Error("No research sprint to reject.");
      }
      return rejectResearchSprint(projectId, latestSprint.id);
    },
    onSuccess: async (result) => {
      setLastRunId(result.ai_run_id);
      await sprintsQuery.refetch();
    },
  });

  const busy =
    startMutation.isPending ||
    saveMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending;
  const error =
    startMutation.error ??
    saveMutation.error ??
    approveMutation.error ??
    rejectMutation.error ??
    (sprintsQuery.error as Error | null);
  const activePlan = latestSprint?.status === "planned" && draft ? draft : null;
  const traceRunId = lastRunId ?? latestSprint?.ai_run_id ?? null;
  const traceKey = [
    traceRunId,
    latestSprint?.status,
    latestSprint?.updated_at,
    approveMutation.submittedAt,
    rejectMutation.submittedAt,
  ].join(":");
  const canReviewDiscovery =
    latestSprint !== null &&
    ["approved", "running", "needs_review", "completed"].includes(latestSprint.status);

  return (
    <div id="research-sprint" className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Run Research Sprint</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Ask the system to plan the investigation before it discovers sources or
            competitors. No research starts until you approve the plan.
          </p>
        </div>
        {latestSprint ? (
          <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
            Latest: {formatLabel(latestSprint.status)}
          </span>
        ) : null}
      </div>

      {!activePlan ? (
        <div className="mt-5 space-y-3">
          <label className="block">
            <span className="text-sm font-medium">Research objective</span>
            <textarea
              className="mt-2 min-h-20 w-full resize-y rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Investigate whether this idea has a strong wedge, which competitors matter, and what to validate next."
              value={objective}
            />
          </label>
          <div className="flex flex-col gap-3">
            {latestSprint?.status === "approved" ? (
              <p className="text-xs leading-5 text-muted-foreground">
                The latest plan is approved. Discover sources and competitors before generating
                the research memo.
              </p>
            ) : latestSprint?.status === "rejected" ? (
              <p className="text-xs leading-5 text-muted-foreground">
                The latest plan was rejected. Generate a new plan when the objective changes.
              </p>
            ) : null}
            <Button
              className="w-full whitespace-nowrap"
              disabled={busy}
              onClick={() => startMutation.mutate()}
              type="button"
            >
              <FileSearch className="h-4 w-4" aria-hidden="true" />
              {startMutation.isPending ? "Planning..." : "Run Research Sprint"}
            </Button>
          </div>
        </div>
      ) : (
        <ResearchPlanEditor
          busy={busy}
          draft={activePlan}
          onApprove={() => approveMutation.mutate()}
          onChange={setDraft}
          onReject={() => rejectMutation.mutate()}
          onSave={() => saveMutation.mutate()}
        />
      )}

      {canReviewDiscovery && latestSprint ? (
        <ResearchDiscoveryPanel
          onRunTrace={setLastRunId}
          onSprintUpdated={() => sprintsQuery.refetch()}
          projectId={projectId}
          sprint={latestSprint}
        />
      ) : null}

      <ResearchHistoryPanel projectId={projectId} />
      <ResearchQualityPanel projectId={projectId} />

      {error ? (
        <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error.message}
        </div>
      ) : null}

      <div className="mt-5">
        <WorkflowTrace
          key={traceKey}
          pending={startMutation.isPending}
          pendingSteps={["load_project_context", "generate_research_plan", "persist_research_plan"]}
          runId={traceRunId}
        />
      </div>

      {sprintsQuery.data && sprintsQuery.data.length > 1 ? (
        <div className="mt-5 border-t border-border pt-4">
          <h3 className="text-sm font-semibold">Recent Research Plans</h3>
          <div className="mt-3 space-y-2">
            {sprintsQuery.data.slice(1, 4).map((sprint) => (
              <div
                className="flex flex-col gap-1 rounded-md bg-muted px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between"
                key={sprint.id}
              >
                <span className="line-clamp-1">{sprint.plan.objective}</span>
                <span className="text-xs text-muted-foreground">{formatLabel(sprint.status)}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ResearchHistoryPanel({ projectId }: { projectId: string }) {
  const historyQuery = useQuery({
    queryKey: ["projects", projectId, "research-history"],
    queryFn: () => getProjectResearchHistory(projectId),
  });
  const history = historyQuery.data;

  return (
    <details className="mt-6 border-t border-border pt-5">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Research History</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Review what changed across previous sprints.
            </p>
          </div>
          {history ? (
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-md bg-muted px-2 py-1">
                {history.sprint_count} sprint{history.sprint_count === 1 ? "" : "s"}
              </span>
              <span className="rounded-md bg-muted px-2 py-1">
                {history.completed_sprint_count} completed
              </span>
            </div>
          ) : null}
        </div>
      </summary>

      {historyQuery.isLoading ? (
        <p className="mt-3 text-sm text-muted-foreground">Loading research history...</p>
      ) : historyQuery.isError ? (
        <p className="mt-3 text-sm text-red-700">{(historyQuery.error as Error).message}</p>
      ) : !history || history.sprints.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No research sprints yet. Run a research sprint to create a history trail.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          {history.sprints.slice(0, 3).map((sprintHistory) => (
            <div className="rounded-md bg-muted p-4" key={sprintHistory.sprint.id}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h4 className="text-sm font-semibold">
                    {truncate(sprintHistory.sprint.plan.objective, 120)}
                  </h4>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {formatLabel(sprintHistory.sprint.status)} ·{" "}
                    {formatDateTime(sprintHistory.sprint.created_at)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span className="rounded-md bg-white px-2 py-1">
                    {sprintHistory.ingested_source_count}/{sprintHistory.source_candidate_count} sources
                  </span>
                  <span className="rounded-md bg-white px-2 py-1">
                    {sprintHistory.merged_competitor_count}/
                    {sprintHistory.competitor_candidate_count} competitors
                  </span>
                  {sprintHistory.memory_update_status ? (
                    <span className="rounded-md bg-white px-2 py-1">
                      {formatLabel(sprintHistory.memory_update_status)}
                    </span>
                  ) : null}
                </div>
              </div>
              {sprintHistory.recommendation_change ? (
                <p className="mt-3 text-sm leading-6 text-muted-foreground">
                  Recommendation: {truncate(sprintHistory.recommendation_change, 220)}
                </p>
              ) : null}
              <div className="mt-4 space-y-2">
                {sprintHistory.events.slice(-5).map((event) => (
                  <div className="border-l-2 border-border pl-3" key={event.id}>
                    <p className="text-sm font-medium">{event.title}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {event.summary}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      Why it matters: {event.why_it_matters}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </details>
  );
}

function ResearchQualityPanel({ projectId }: { projectId: string }) {
  const evalQuery = useQuery({
    queryKey: ["projects", projectId, "evals", "v1-research"],
    queryFn: () => getV1ResearchEval(projectId),
  });
  const evaluation = evalQuery.data;

  return (
    <details className="mt-6 border-t border-border pt-5">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Research Quality</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              View source, citation, traceability, cost, and latency checks.
            </p>
          </div>
          {evaluation ? (
            <span
              className={
                evaluation.passed
                  ? "w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
                  : "w-fit rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700"
              }
            >
              {evaluation.score}/{evaluation.total} checks
            </span>
          ) : null}
        </div>
      </summary>

      {evalQuery.isLoading ? (
        <p className="mt-3 text-sm text-muted-foreground">Loading research eval...</p>
      ) : evalQuery.isError ? (
        <p className="mt-3 text-sm text-red-700">{(evalQuery.error as Error).message}</p>
      ) : evaluation ? (
        <>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {evaluation.metrics.map((metric) => (
              <div className="rounded-md bg-muted px-3 py-2" key={metric.key}>
                <div className="flex items-center gap-2">
                  {metric.passed ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <CircleAlert className="h-4 w-4 shrink-0 text-amber-600" />
                  )}
                  <span className="text-sm font-medium">{metric.label}</span>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Observed: {String(metric.observed ?? "none")}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs leading-5 text-muted-foreground">
            Eval dataset: {evaluation.dataset_case_count} idea categories,{" "}
            {evaluation.demo_ready_case_count} demo-ready cases.
          </p>
        </>
      ) : null}
    </details>
  );
}

function ResearchPlanEditor({
  busy,
  draft,
  onApprove,
  onChange,
  onReject,
  onSave,
}: {
  busy: boolean;
  draft: ResearchPlanDraftState;
  onApprove: () => void;
  onChange: (draft: ResearchPlanDraftState) => void;
  onReject: () => void;
  onSave: () => void;
}) {
  function updateField(field: keyof ResearchPlanDraftState, value: string) {
    onChange({ ...draft, [field]: value });
  }

  return (
    <div className="mt-5 space-y-4">
      <PlanTextArea
        label="Objective"
        onChange={(value) => updateField("objective", value)}
        value={draft.objective}
      />
      <div className="grid gap-4 md:grid-cols-2">
        <PlanTextArea
          label="Target customer hypotheses"
          onChange={(value) => updateField("target_customer_hypotheses", value)}
          value={draft.target_customer_hypotheses}
        />
        <PlanTextArea
          label="Research questions"
          onChange={(value) => updateField("research_questions", value)}
          value={draft.research_questions}
        />
        <PlanTextArea
          label="Competitor discovery queries"
          onChange={(value) => updateField("competitor_queries", value)}
          value={draft.competitor_queries}
        />
        <PlanTextArea
          label="Market research queries"
          onChange={(value) => updateField("market_queries", value)}
          value={draft.market_queries}
        />
        <PlanTextArea
          label="Substitute behavior queries"
          onChange={(value) => updateField("substitute_queries", value)}
          value={draft.substitute_queries}
        />
        <PlanTextArea
          label="Source types to inspect"
          onChange={(value) => updateField("source_types", value)}
          value={draft.source_types}
        />
        <PlanTextArea
          label="Assumptions likely to be tested"
          onChange={(value) => updateField("assumptions_to_test", value)}
          value={draft.assumptions_to_test}
        />
        <PlanTextArea
          label="Expected output artifacts"
          onChange={(value) => updateField("expected_outputs", value)}
          value={draft.expected_outputs}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={onApprove} type="button">
          Approve Plan
        </Button>
        <Button disabled={busy} onClick={onSave} type="button" variant="secondary">
          Save Draft
        </Button>
        <Button disabled={busy} onClick={onReject} type="button" variant="secondary">
          Reject
        </Button>
      </div>
    </div>
  );
}

function PlanTextArea({
  label,
  onChange,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <textarea
        className="mt-2 min-h-24 w-full resize-y rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-primary"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function ResearchDiscoveryPanel({
  onRunTrace,
  onSprintUpdated,
  projectId,
  sprint,
}: {
  onRunTrace: (runId: string) => void;
  onSprintUpdated: () => Promise<unknown>;
  projectId: string;
  sprint: ResearchSprint;
}) {
  const queryClient = useQueryClient();
  const sourcesQuery = useQuery({
    queryKey: ["projects", projectId, "research-sprints", sprint.id, "sources"],
    queryFn: () => listDiscoveredSources(projectId, sprint.id),
  });
  const candidatesQuery = useQuery({
    queryKey: ["projects", projectId, "research-sprints", sprint.id, "competitor-candidates"],
    queryFn: () => listCompetitorCandidates(projectId, sprint.id),
  });
  const researchMemosQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts", "research_memo"],
    queryFn: () => listArtifacts(projectId, "research_memo"),
  });

  const discoverSourcesMutation = useMutation({
    mutationFn: () => discoverSources(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await sourcesQuery.refetch();
    },
  });
  const discoverCompetitorsMutation = useMutation({
    mutationFn: () => discoverCompetitorCandidates(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await candidatesQuery.refetch();
    },
  });
  const agenticResearchMutation = useMutation({
    mutationFn: () => runAgenticResearch(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await researchMemosQuery.refetch();
      await onSprintUpdated();
    },
  });
  const approveMemoMutation = useMutation({
    mutationFn: () => approveAgenticResearchMemo(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await researchMemosQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assumptions"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "risks"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "experiments"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-history"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "v1-research"] });
      await onSprintUpdated();
    },
  });
  const rejectMemoMutation = useMutation({
    mutationFn: () => rejectAgenticResearchMemo(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await researchMemosQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-history"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "v1-research"] });
      await onSprintUpdated();
    },
  });
  const approveSourceMutation = useMutation({
    mutationFn: (sourceId: string) => approveDiscoveredSource(projectId, sprint.id, sourceId),
    onSuccess: async () => {
      await sourcesQuery.refetch();
    },
  });
  const rejectSourceMutation = useMutation({
    mutationFn: (sourceId: string) => rejectDiscoveredSource(projectId, sprint.id, sourceId),
    onSuccess: async () => {
      await sourcesQuery.refetch();
    },
  });
  const updateCandidateMutation = useMutation({
    mutationFn: ({
      candidateId,
      input,
    }: {
      candidateId: string;
      input: CompetitorCandidateUpdateInput;
    }) => updateCompetitorCandidate(projectId, sprint.id, candidateId, input),
    onSuccess: async () => {
      await candidatesQuery.refetch();
    },
  });
  const approveCandidateMutation = useMutation({
    mutationFn: (candidateId: string) => approveCompetitorCandidate(projectId, sprint.id, candidateId),
    onSuccess: async () => {
      await candidatesQuery.refetch();
    },
  });
  const rejectCandidateMutation = useMutation({
    mutationFn: (candidateId: string) => rejectCompetitorCandidate(projectId, sprint.id, candidateId),
    onSuccess: async () => {
      await candidatesQuery.refetch();
    },
  });

  const sources = sourcesQuery.data ?? [];
  const candidates = candidatesQuery.data ?? [];
  const memoArtifact =
    approveMemoMutation.data?.artifact ??
    agenticResearchMutation.data?.artifact ??
    researchMemoForSprint(researchMemosQuery.data ?? [], sprint.id);
  const memoVersion =
    approveMemoMutation.data?.version ??
    agenticResearchMutation.data?.version ??
    memoArtifact?.current_version ??
    null;
  const unsupportedClaims =
    agenticResearchMutation.data?.unsupported_claims ?? unsupportedClaimsFromArtifact(memoArtifact);
  const citations = agenticResearchMutation.data?.citations ?? citationsFromArtifact(memoArtifact);
  const retrievalToolCallCount =
    agenticResearchMutation.data?.retrieval_tool_call_count ??
    retrievalToolCallCountFromArtifact(memoArtifact);
  const evidenceGapCount =
    agenticResearchMutation.data?.evidence_gap_count ?? evidenceGapsFromArtifact(memoArtifact).length;
  const memoryUpdateStatus = memoryUpdateStatusFromArtifact(memoArtifact);
  const memoryUpdateSummary = memoryUpdateSummaryFromArtifact(memoArtifact);
  const error =
    discoverSourcesMutation.error ??
    discoverCompetitorsMutation.error ??
    agenticResearchMutation.error ??
    approveMemoMutation.error ??
    rejectMemoMutation.error ??
    approveSourceMutation.error ??
    rejectSourceMutation.error ??
    updateCandidateMutation.error ??
    approveCandidateMutation.error ??
    rejectCandidateMutation.error ??
    (researchMemosQuery.error as Error | null) ??
    (sourcesQuery.error as Error | null) ??
    (candidatesQuery.error as Error | null);
  const busy =
    discoverSourcesMutation.isPending ||
    discoverCompetitorsMutation.isPending ||
    agenticResearchMutation.isPending ||
    approveMemoMutation.isPending ||
    rejectMemoMutation.isPending ||
    approveSourceMutation.isPending ||
    rejectSourceMutation.isPending ||
    updateCandidateMutation.isPending ||
    approveCandidateMutation.isPending ||
    rejectCandidateMutation.isPending;

  return (
    <div className="mt-6 border-t border-border pt-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-sm font-semibold">Review Findings</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Generate candidate sources and competitors from the approved plan. Review items before
            they are ingested as evidence or merged into the project competitor set, then synthesize
            a cited research memo from the project evidence graph.
          </p>
        </div>
        <div className="grid w-full grid-cols-[repeat(auto-fit,minmax(12rem,1fr))] gap-2 lg:w-[28rem] xl:w-[40rem]">
          <Button
            className="w-full whitespace-nowrap"
            disabled={busy}
            onClick={() => discoverSourcesMutation.mutate()}
            type="button"
            variant="secondary"
          >
            <Globe2 className="h-4 w-4" aria-hidden="true" />
            {discoverSourcesMutation.isPending ? "Discovering..." : "Discover Sources"}
          </Button>
          <Button
            className="w-full whitespace-nowrap"
            disabled={busy}
            onClick={() => discoverCompetitorsMutation.mutate()}
            type="button"
            variant="secondary"
          >
            <Building2 className="h-4 w-4" aria-hidden="true" />
            {discoverCompetitorsMutation.isPending
              ? "Discovering..."
              : "Discover Competitors"}
          </Button>
          <Button
            className="w-full whitespace-nowrap"
            disabled={busy || sprint.status === "completed"}
            onClick={() => agenticResearchMutation.mutate()}
            type="button"
          >
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            {agenticResearchMutation.isPending ? "Synthesizing..." : "Generate Research Memo"}
          </Button>
        </div>
      </div>

      {error ? (
        <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error.message}
        </div>
      ) : null}

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <SourceCandidateList
          busy={busy}
          onApprove={(sourceId) => approveSourceMutation.mutate(sourceId)}
          onReject={(sourceId) => rejectSourceMutation.mutate(sourceId)}
          sources={sources}
        />
        <CompetitorCandidateList
          busy={busy}
          candidates={candidates}
          onApprove={(candidateId) => approveCandidateMutation.mutate(candidateId)}
          onReject={(candidateId) => rejectCandidateMutation.mutate(candidateId)}
          onSave={(candidateId, input) =>
            updateCandidateMutation.mutate({ candidateId, input })
          }
        />
      </div>

      {memoArtifact && memoVersion ? (
        <div className="mt-5 rounded-md border border-border bg-muted p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h4 className="text-sm font-semibold">Research memo ready for review</h4>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                The research agent used {retrievalToolCallCount} retrieval passes, found{" "}
                {evidenceGapCount} evidence gaps, and paused before updating project strategy.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-fit rounded-md bg-white px-2 py-1 text-xs text-muted-foreground">
                {formatLabel(memoArtifact.artifact_type)}
              </span>
            </div>
          </div>
          {memoryUpdateStatus ? (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Project strategy update: {formatLabel(memoryUpdateStatus)}.
            </p>
          ) : null}
          {unsupportedClaims.length > 0 ? (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Open questions: {unsupportedClaims.slice(0, 2).join("; ")}
            </p>
          ) : null}
          <ResearchMemoReview
            artifact={memoArtifact}
            approvalPending={approveMemoMutation.isPending}
            citations={citations}
            memoryUpdateStatus={memoryUpdateStatus}
            memoryUpdateSummary={memoryUpdateSummary}
            onApprove={() => approveMemoMutation.mutate()}
            onReject={() => rejectMemoMutation.mutate()}
            rejectionPending={rejectMemoMutation.isPending}
            unsupportedClaims={unsupportedClaims}
            version={memoVersion}
          />
        </div>
      ) : null}
    </div>
  );
}

function ResearchMemoReview({
  artifact,
  approvalPending,
  citations,
  memoryUpdateStatus,
  memoryUpdateSummary,
  onApprove,
  onReject,
  rejectionPending,
  unsupportedClaims,
  version,
}: {
  artifact: Artifact;
  approvalPending: boolean;
  citations: Citation[];
  memoryUpdateStatus: string | null;
  memoryUpdateSummary: MemoryUpdateSummary | null;
  onApprove: () => void;
  onReject: () => void;
  rejectionPending: boolean;
  unsupportedClaims: string[];
  version: ArtifactVersion;
}) {
  const supportedClaims = version.claims.filter((claim) => claim.support_level !== "unsupported");
  const unsupportedClaimRecords = version.claims.filter(
    (claim) => claim.support_level === "unsupported",
  );
  const displayUnsupported = unsupportedClaims.length > 0
    ? unsupportedClaims
    : unsupportedClaimRecords.map((claim) => claim.text);
  const approved = memoryUpdateStatus === "approved";
  const rejected = memoryUpdateStatus === "rejected";
  const reviewed = approved || rejected;

  return (
    <div id="research-memo-review" className="mt-4 border-t border-border pt-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Review memo and strategy updates</h3>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-md bg-white px-2 py-1">{artifact.title}</span>
            <span className="rounded-md bg-muted px-2 py-1">Version {version.version}</span>
            <span className="rounded-md bg-muted px-2 py-1">
              {formatDateTime(version.created_at)}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={
              approved
                ? "w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700"
                : rejected
                  ? "w-fit rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700"
                : "w-fit rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700"
            }
          >
          {approved ? "Approved" : rejected ? "Rejected" : "Review pending"}
          </span>
          <Button
            disabled={reviewed || approvalPending || rejectionPending}
            onClick={onApprove}
            size="sm"
            type="button"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            {approved ? "Approved" : approvalPending ? "Approving..." : "Approve Updates"}
          </Button>
          <Button
            disabled={reviewed || approvalPending || rejectionPending}
            onClick={onReject}
            size="sm"
            type="button"
            variant="secondary"
          >
            {rejected ? "Rejected" : rejectionPending ? "Rejecting..." : "Reject Updates"}
          </Button>
        </div>
      </div>

      {memoryUpdateSummary ? (
        <div className="mt-4 rounded-md bg-white px-4 py-3 text-sm leading-6 text-muted-foreground">
          <span className="font-medium text-foreground">Project strategy updates:</span>{" "}
          {memoryUpdateSummary.assumption_ids.length} assumption
          {memoryUpdateSummary.assumption_ids.length === 1 ? "" : "s"},{" "}
          {memoryUpdateSummary.risk_ids.length} risk
          {memoryUpdateSummary.risk_ids.length === 1 ? "" : "s"} written after approval.
          {memoryUpdateSummary.recommended_validation_actions.length > 0 ? (
            <span>
              {" "}
              First validation action:{" "}
              {truncate(memoryUpdateSummary.recommended_validation_actions[0], 160)}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="rounded-md bg-white px-3 py-2">
          <div className="text-xs text-muted-foreground">Cited claims</div>
          <div className="mt-1 text-sm font-semibold">{supportedClaims.length}</div>
        </div>
        <div className="rounded-md bg-white px-3 py-2">
          <div className="text-xs text-muted-foreground">Sources</div>
          <div className="mt-1 text-sm font-semibold">{citations.length}</div>
        </div>
        <div className="rounded-md bg-white px-3 py-2">
          <div className="text-xs text-muted-foreground">Open questions</div>
          <div className="mt-1 text-sm font-semibold">{displayUnsupported.length}</div>
        </div>
      </div>

      <SourceGroundedMemo
        citations={citations}
        markdown={version.markdown_content}
        unsupportedClaims={displayUnsupported}
      />

      <details className="mt-3 rounded-md bg-white p-3">
        <summary className="cursor-pointer text-sm font-medium">
          Show evidence and open questions
        </summary>
        <div className="mt-3 grid gap-5 border-t border-border pt-3 lg:grid-cols-3">
          <section>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h4 className="text-sm font-semibold">Cited Claims</h4>
            </div>
            <div className="mt-4 space-y-3">
              {supportedClaims.length === 0 ? (
                <p className="text-sm text-muted-foreground">No cited claims recorded.</p>
              ) : (
                supportedClaims.map((claim) => (
                  <div key={claim.id} className="border-b border-border pb-3 last:border-b-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        {formatLabel(claim.support_level)}
                      </span>
                      <span className="text-muted-foreground">
                        {claim.evidence_links.length} citation
                        {claim.evidence_links.length === 1 ? "" : "s"}
                      </span>
                    </div>
                    <MarkdownContent
                      className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground"
                      markdown={claim.text}
                    />
                    {claim.evidence_links.length > 0 ? (
                      <div className="mt-2 space-y-1">
                        {claim.evidence_links.slice(0, 2).map((link) => (
                          <p className="text-xs leading-5 text-muted-foreground" key={link.id}>
                            {link.quote
                              ? truncate(link.quote, 180)
                              : `Source ${link.evidence_source_id}`}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </section>

          <section>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-primary" aria-hidden="true" />
              <h4 className="text-sm font-semibold">Unsupported Claims</h4>
            </div>
            <div className="mt-4 space-y-2">
              {displayUnsupported.length === 0 ? (
                <p className="text-sm text-muted-foreground">None recorded.</p>
              ) : (
                displayUnsupported.map((claim) => (
                  <MarkdownContent
                    className="space-y-2 text-sm leading-6 text-muted-foreground"
                    key={claim}
                    markdown={claim}
                  />
                ))
              )}
            </div>
          </section>

          <section>
            <div className="flex items-center gap-2">
              <Globe2 className="h-4 w-4 text-primary" aria-hidden="true" />
              <h4 className="text-sm font-semibold">Evidence Sources</h4>
            </div>
            <div className="mt-4 space-y-3">
              {citations.length === 0 ? (
                <p className="text-sm text-muted-foreground">No citations recorded.</p>
              ) : (
                citations.map((citation) => (
                  <div key={`${citation.source_id}-${citation.chunk_id ?? "source"}`}>
                    {citation.url ? (
                      <a
                        className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                        href={citation.url}
                        rel="noreferrer"
                        target="_blank"
                      >
                        {citation.title ?? citation.url}
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </a>
                    ) : (
                      <p className="text-sm font-medium">{citation.title ?? citation.source_id}</p>
                    )}
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {citation.quote
                        ? truncate(citation.quote, 180)
                        : `Source ${citation.source_id}`}
                    </p>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </details>
    </div>
  );
}

function SourceGroundedMemo({
  citations,
  markdown,
  unsupportedClaims,
}: {
  citations: Citation[];
  markdown: string;
  unsupportedClaims: string[];
}) {
  const sections = extractMemoSections(markdown);
  const primarySections = preferredMemoSections(sections).slice(0, 4);

  return (
    <div className="mt-4 rounded-md bg-white p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold">Source-grounded memo</h4>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Summary first. Sources, open questions, and full details stay close by.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span className="rounded-md bg-muted px-2 py-1">{citations.length} sources used</span>
          <span className="rounded-md bg-muted px-2 py-1">
            {unsupportedClaims.length} open question{unsupportedClaims.length === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {primarySections.length > 0 ? (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {primarySections.map((section) => (
            <section className="rounded-md border border-border p-3" key={section.title}>
              <h5 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                {section.title}
              </h5>
              <MarkdownContent
                className="mt-2 line-clamp-6 space-y-2 text-sm leading-6 text-foreground"
                markdown={section.body}
              />
            </section>
          ))}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium">Sources Used</summary>
          <div className="mt-3 max-h-72 space-y-3 overflow-auto border-t border-border pt-3">
            {citations.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sources recorded.</p>
            ) : (
              citations.map((citation) => (
                <div key={`${citation.source_id}-${citation.chunk_id ?? "source"}`}>
                  {citation.url ? (
                    <a
                      className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                      href={citation.url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {citation.title ?? citation.url}
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                  ) : (
                    <p className="text-sm font-medium">{citation.title ?? citation.source_id}</p>
                  )}
                  {citation.quote ? (
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {truncate(citation.quote, 180)}
                    </p>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </details>

        <details className="rounded-md border border-border p-3">
          <summary className="cursor-pointer text-sm font-medium">
            What We Still Do Not Know
          </summary>
          <div className="mt-3 max-h-72 space-y-2 overflow-auto border-t border-border pt-3">
            {unsupportedClaims.length === 0 ? (
              <p className="text-sm text-muted-foreground">No unsupported claims recorded.</p>
            ) : (
              unsupportedClaims.map((claim) => (
                <MarkdownContent
                  className="space-y-2 text-sm leading-6 text-muted-foreground"
                  key={claim}
                  markdown={claim}
                />
              ))
            )}
          </div>
        </details>
      </div>

      <details className="mt-3 rounded-md border border-border p-3">
        <summary className="cursor-pointer text-sm font-medium">Full Details</summary>
        <article className="mt-3 max-h-[28rem] min-w-0 overflow-auto border-t border-border pt-3">
          <MarkdownContent markdown={markdown} />
        </article>
      </details>
    </div>
  );
}

function SourceCandidateList({
  busy,
  onApprove,
  onReject,
  sources,
}: {
  busy: boolean;
  onApprove: (sourceId: string) => void;
  onReject: (sourceId: string) => void;
  sources: DiscoveredSource[];
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold">Source Candidates</h4>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {sources.length}
        </span>
      </div>
      {sources.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No candidate sources yet. Run source discovery after approving the research plan.
        </p>
      ) : (
        <div className="mt-3 space-y-3">
          {sources.map((source) => (
            <details className="rounded-md border border-border p-3" key={source.id}>
              <summary className="cursor-pointer list-none">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        {formatLabel(source.source_type)}
                      </span>
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        {formatLabel(source.status)}
                      </span>
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        score {formatScore(source.relevance_score)}
                      </span>
                    </div>
                    <h5 className="mt-2 line-clamp-2 text-sm font-semibold">
                      {source.title ?? "Untitled source"}
                    </h5>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                  {source.status === "candidate" || source.status === "failed" ? (
                    <>
                      <Button
                        disabled={busy}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          onApprove(source.id);
                        }}
                        size="sm"
                        type="button"
                      >
                        Approve
                      </Button>
                      <Button
                        disabled={busy}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          onReject(source.id);
                        }}
                        size="sm"
                        type="button"
                        variant="secondary"
                      >
                        Reject
                      </Button>
                    </>
                  ) : null}
                    <span className="text-xs font-medium text-primary">Show details</span>
                  </div>
                </div>
              </summary>
              <div className="mt-3 border-t border-border pt-3">
                <a
                  className="block break-all text-xs text-primary hover:underline"
                  href={source.url}
                  rel="noreferrer"
                  target="_blank"
                >
                  {source.url}
                </a>
                {source.snippet ? (
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {source.snippet}
                  </p>
                ) : null}
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Why: {source.reason_selected}
                </p>
                {source.ingestion_error ? (
                  <p className="mt-2 text-xs text-red-700">{source.ingestion_error}</p>
                ) : null}
                {source.ingested_at ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Evidence added {formatDateTime(source.ingested_at)}
                  </p>
                ) : null}
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

function CompetitorCandidateList({
  busy,
  candidates,
  onApprove,
  onReject,
  onSave,
}: {
  busy: boolean;
  candidates: CompetitorCandidate[];
  onApprove: (candidateId: string) => void;
  onReject: (candidateId: string) => void;
  onSave: (candidateId: string, input: CompetitorCandidateUpdateInput) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold">Competitor Candidates</h4>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {candidates.length}
        </span>
      </div>
      {candidates.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No competitor candidates yet. Run competitor discovery to review direct competitors,
          substitutes, and incumbents.
        </p>
      ) : (
        <div className="mt-3 space-y-3">
          {candidates.map((candidate) => (
            <CompetitorCandidateItem
              busy={busy}
              candidate={candidate}
              key={candidate.id}
              onApprove={onApprove}
              onReject={onReject}
              onSave={onSave}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CompetitorCandidateItem({
  busy,
  candidate,
  onApprove,
  onReject,
  onSave,
}: {
  busy: boolean;
  candidate: CompetitorCandidate;
  onApprove: (candidateId: string) => void;
  onReject: (candidateId: string) => void;
  onSave: (candidateId: string, input: CompetitorCandidateUpdateInput) => void;
}) {
  const [name, setName] = useState(candidate.name);
  const [url, setUrl] = useState(candidate.url ?? "");
  const [category, setCategory] = useState(candidate.category);
  const [threatLevel, setThreatLevel] = useState(candidate.threat_level);
  const [whyItMatters, setWhyItMatters] = useState(candidate.why_it_matters);

  useEffect(() => {
    setName(candidate.name);
    setUrl(candidate.url ?? "");
    setCategory(candidate.category);
    setThreatLevel(candidate.threat_level);
    setWhyItMatters(candidate.why_it_matters);
  }, [candidate.id, candidate.updated_at]);

  const canEdit = candidate.status === "candidate";
  return (
    <details className="rounded-md border border-border p-3">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                {formatLabel(candidate.category)}
              </span>
              <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                {formatLabel(candidate.status)}
              </span>
              <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                threat {candidate.threat_level}
              </span>
              <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                score {formatScore(candidate.relevance_score)}
              </span>
            </div>
            <h5 className="mt-2 line-clamp-2 text-sm font-semibold">{candidate.name}</h5>
          </div>
          <div className="flex shrink-0 items-center gap-2">
          {candidate.status === "candidate" ? (
            <>
              <Button
                disabled={busy}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onApprove(candidate.id);
                }}
                size="sm"
                type="button"
              >
                Approve
              </Button>
              <Button
                disabled={busy}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onReject(candidate.id);
                }}
                size="sm"
                type="button"
                variant="secondary"
              >
                Reject
              </Button>
            </>
          ) : null}
            <span className="text-xs font-medium text-primary">Show details</span>
          </div>
        </div>
      </summary>

      <div className="mt-3 border-t border-border pt-3">
        {candidate.url ? (
          <a
            className="block break-all text-xs text-primary hover:underline"
            href={candidate.url}
            rel="noreferrer"
            target="_blank"
          >
            {candidate.url}
          </a>
        ) : null}
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {candidate.positioning ?? "No positioning note yet."}
        </p>
        <p className="mt-2 text-xs leading-5 text-muted-foreground">
          Why: {candidate.why_it_matters}
        </p>
        {candidate.core_features.length > 0 ? (
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Features: {candidate.core_features.join(", ")}
          </p>
        ) : null}
        {candidate.evidence_source_id ? (
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Evidence added{candidate.ingested_at ? ` ${formatDateTime(candidate.ingested_at)}` : ""}.
          </p>
        ) : null}
        {candidate.ingestion_error ? (
          <p className="mt-2 text-xs text-red-700">{candidate.ingestion_error}</p>
        ) : null}

      {canEdit ? (
        <details className="mt-3 rounded-md bg-muted p-3">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            Edit candidate
          </summary>
          <div className="mt-3 grid gap-3">
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">Name</span>
              <input
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
                onChange={(event) => setName(event.target.value)}
                value={name}
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">URL</span>
              <input
                className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
                onChange={(event) => setUrl(event.target.value)}
                value={url}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="text-xs font-medium text-muted-foreground">Category</span>
                <select
                  className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
                  onChange={(event) =>
                    setCategory(event.target.value as CompetitorCandidate["category"])
                  }
                  value={category}
                >
                  {[
                    "direct_competitor",
                    "indirect_competitor",
                    "substitute_behavior",
                    "incumbent_platform",
                    "adjacent_solution",
                    "irrelevant",
                  ].map((value) => (
                    <option key={value} value={value}>
                      {formatLabel(value)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs font-medium text-muted-foreground">Threat</span>
                <select
                  className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
                  onChange={(event) =>
                    setThreatLevel(event.target.value as CompetitorCandidate["threat_level"])
                  }
                  value={threatLevel}
                >
                  {["low", "medium", "high"].map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">Why it matters</span>
              <textarea
                className="mt-1 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm"
                onChange={(event) => setWhyItMatters(event.target.value)}
                value={whyItMatters}
              />
            </label>
            <Button
              disabled={busy}
              onClick={() =>
                onSave(candidate.id, {
                  category,
                  name,
                  threat_level: threatLevel,
                  url,
                  why_it_matters: whyItMatters,
                })
              }
              size="sm"
              type="button"
            >
              Save Candidate
            </Button>
          </div>
        </details>
      ) : null}
      </div>
    </details>
  );
}

function LifecycleProgressCard({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const rows = lifecycleRows(overview);

  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Lifecycle Status</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Compact view of what is complete, what is active, and where the next
            decision pressure sits.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {formatStage(overview.strategic_snapshot.current_stage)}
        </span>
      </div>
      <div className="mt-5 overflow-x-auto rounded-md border border-border">
        <table className="min-w-[720px] w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-normal text-muted-foreground">
              <th className="px-3 py-2 font-medium">Stage</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Signal</th>
              <th className="px-3 py-2 font-medium">Next</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr key={row.key}>
                <td className="px-3 py-3 font-medium text-foreground">{row.label}</td>
                <td className="px-3 py-3">
                  <LifecycleStatusBadge status={row.status} />
                </td>
                <td className="px-3 py-3 text-muted-foreground">{row.signal}</td>
                <td className="px-3 py-3 text-muted-foreground">{row.next}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function IdeaReadinessCard({ readiness }: { readiness: IdeaReadiness }) {
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex items-center gap-2">
        <ClipboardCheck className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold">Idea Readiness</h2>
      </div>
      <div className="mt-4 flex items-end gap-2">
        <span className="text-3xl font-semibold">{readiness.score}%</span>
        <span className="pb-1 text-sm text-muted-foreground">
          {formatLabel(readiness.status)}
        </span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary" style={{ width: `${readiness.score}%` }} />
      </div>
      <p className="mt-4 text-sm leading-6 text-muted-foreground">
        Weakest area: {readiness.weakest_area}
      </p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">
        Recommended next action: {readiness.recommended_next_action}
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
        <ReadinessList
          emptyLabel="No completed items yet."
          items={readiness.completed_items.slice(0, 6)}
          title="Ready"
        />
        <ReadinessList
          emptyLabel="Nothing missing."
          items={readiness.missing_items.slice(0, 6)}
          title="Missing or Needs Work"
        />
      </div>
    </div>
  );
}

function ReadinessList({
  emptyLabel,
  items,
  title,
}: {
  emptyLabel: string;
  items: IdeaReadiness["completed_items"];
  title: string;
}) {
  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item) => (
            <div className="flex items-start gap-2 text-sm" key={item.key}>
              {item.status === "complete" ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              ) : (
                <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              )}
              <span className="text-muted-foreground">{item.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TopRisksCard({
  risks,
}: {
  risks: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["key_risks"];
}) {
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex items-center gap-2">
        <Beaker className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold">Key Risks</h2>
      </div>
      {risks.length === 0 ? (
        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          No risks recorded yet. Run research or extract assumptions to surface likely failure
          modes and what to test next.
        </p>
      ) : (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {risks.slice(0, 3).map((risk) => (
            <div key={risk.id} className="rounded-md border border-border p-4">
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                  {risk.severity} risk
                </span>
                <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                  {risk.likelihood} likelihood
                </span>
              </div>
              <MarkdownContent
                className="mt-3 line-clamp-4 space-y-2 text-sm leading-6 text-foreground"
                markdown={risk.text}
              />
              <p className="mt-3 text-xs font-medium uppercase tracking-normal text-muted-foreground">
                Recommended action
              </p>
              <MarkdownContent
                className="mt-1 line-clamp-3 space-y-2 text-sm leading-6 text-muted-foreground"
                markdown={risk.mitigation ?? "Turn this risk into a validation test."}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StrategicSnapshotCard({ snapshot }: { snapshot: StrategicSnapshot }) {
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex items-center gap-2">
        <ListChecks className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold">Strategic Snapshot</h2>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <SnapshotField label="Current Thesis" value={snapshot.current_thesis} />
        <SnapshotField label="Target User" value={snapshot.target_user} />
        <SnapshotField label="Primary Problem" value={snapshot.primary_problem} />
        <SnapshotField label="Proposed Wedge" value={snapshot.proposed_wedge} />
        <SnapshotField label="Main Risk" value={snapshot.main_risk} />
        <SnapshotField label="Current Confidence" value={formatLabel(snapshot.current_confidence)} />
      </div>
    </div>
  );
}

function SnapshotField({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
        {label}
      </h3>
      {value ? (
        <MarkdownContent
          className="mt-1 line-clamp-4 space-y-2 text-sm leading-6 text-foreground"
          markdown={value}
        />
      ) : (
        <a className="mt-1 block text-sm text-amber-700 hover:underline" href="#structured-intake">
          Missing - structure idea
        </a>
      )}
    </div>
  );
}

function EvidenceHealthCard({
  health,
}: {
  health: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["evidence_health"];
}) {
  const metrics = [
    ["Sources", health.source_count],
    ["Competitors", health.competitor_count],
    ["Cited claims", health.cited_claim_count],
    ["Unsupported claims", health.unsupported_claim_count],
    ["Validated assumptions", health.validated_assumption_count],
  ] as const;
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold">Evidence Health</h2>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        {metrics.map(([label, value]) => (
          <div className="rounded-md bg-muted px-3 py-2" key={label}>
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="mt-1 text-lg font-semibold">{value}</div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-sm leading-6 text-muted-foreground">
        Weakest area: {health.weakest_evidence_area}
      </p>
      {health.last_evidence_update ? (
        <p className="mt-1 text-xs text-muted-foreground">
          Last evidence update: {new Date(health.last_evidence_update).toLocaleString()}
        </p>
      ) : null}
    </div>
  );
}

function RecentUpdatesCard({
  updates,
}: {
  updates: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["recent_strategic_updates"];
}) {
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex items-center gap-2">
        <ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold">Recent Strategic Updates</h2>
      </div>
      {updates.length === 0 ? (
        <p className="mt-4 text-sm leading-6 text-muted-foreground">
          No strategic updates yet. Structure the idea, add evidence, or generate the first
          brief to start building the evidence trail.
        </p>
      ) : (
        <div className="mt-4 divide-y divide-border">
          {updates.slice(0, 6).map((update) => (
            <div className="py-3" key={update.id}>
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <h3 className="text-sm font-semibold">{update.title}</h3>
                <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                  {formatLabel(update.related_entity_type)}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {truncate(update.summary, 220)}
              </p>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Why it matters: {truncate(update.why_it_matters, 180)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function KeyAssumptionsAndRisks({
  assumptions,
  risks,
}: {
  assumptions: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["key_assumptions"];
  risks: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["key_risks"];
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 className="text-base font-semibold">Key Assumptions</h2>
        </div>
        {assumptions.length === 0 ? (
          <p className="mt-4 text-sm leading-6 text-muted-foreground">
            No assumptions identified yet. Assumptions are the beliefs that must be true for
            this idea to work.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {assumptions.slice(0, 4).map((assumption) => (
              <div key={assumption.id} className="rounded-md border border-border p-3">
                <div className="flex flex-wrap gap-2 text-xs">
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
                <MarkdownContent
                  className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground"
                  markdown={assumption.text}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex items-center gap-2">
          <Beaker className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 className="text-base font-semibold">Key Risks</h2>
        </div>
        {risks.length === 0 ? (
          <p className="mt-4 text-sm leading-6 text-muted-foreground">
            No risks recorded yet. Risks show why the idea might fail and what should be
            tested or mitigated.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {risks.slice(0, 4).map((risk) => (
              <div key={risk.id} className="rounded-md border border-border p-3">
                <div className="flex flex-wrap gap-2 text-xs">
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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function tabForAction(action: NextBestAction): ProjectTab {
  const hash = action.target_route?.split("#")[1];
  return tabFromHash(hash ? `#${hash}` : "") ?? tabForActionType(action.action_type);
}

function anchorForAction(action: NextBestAction): string | null {
  const hash = action.target_route?.split("#")[1];
  if (hash && !tabFromHash(`#${hash}`)) {
    return hash;
  }
  if (action.action_type === "structure_idea") {
    return "structured-intake";
  }
  return null;
}

function tabForActionType(actionType: string): ProjectTab {
  if (actionType.includes("brief") || actionType.includes("research")) {
    return "Research";
  }
  if (actionType.includes("competitor")) {
    return "Competitors";
  }
  if (actionType.includes("assumption")) {
    return "Assumptions";
  }
  if (
    actionType.includes("experiment") ||
    actionType.includes("validation") ||
    actionType.includes("result")
  ) {
    return "Validation";
  }
  if (actionType.includes("decision")) {
    return "Decisions";
  }
  if (actionType.includes("evidence")) {
    return "Evidence";
  }
  return "Overview";
}

function tabFromHash(hash: string): ProjectTab | null {
  const normalized = hash.replace("#", "").toLowerCase();
  if (normalized === "brief") {
    return "Research";
  }
  if (normalized === "experiments") {
    return "Validation";
  }
  const match = tabs.find((tab) => tab.toLowerCase() === normalized);
  return match ?? null;
}

function formatStage(stage: ProjectStage) {
  return formatLabel(stage);
}

function lifecycleStepIndex(stage: ProjectStage) {
  if (stage === "draft_idea" || stage === "structured_intake") {
    return 0;
  }
  if (stage === "brief_generated" || stage === "competitors_analyzed") {
    return 1;
  }
  if (stage === "assumptions_identified") {
    return 3;
  }
  if (stage === "validation_plan_created" || stage === "experiment_running") {
    return 4;
  }
  if (
    stage === "decision_ready" ||
    stage === "paused" ||
    stage === "killed" ||
    stage === "proceeding"
  ) {
    return 5;
  }
  return 2;
}

type HealthTone = "good" | "warning" | "danger" | "neutral";

type ProjectHealth = {
  label: string;
  tone: HealthTone;
  detail: string;
};

type LifecycleStatus = "complete" | "current" | "needs_work" | "blocked";

type LifecycleRow = {
  key: string;
  label: string;
  status: LifecycleStatus;
  signal: string;
  next: string;
};

function projectHealth(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
): ProjectHealth {
  const stage = overview.strategic_snapshot.current_stage;
  const highRiskCount = overview.key_risks.filter(
    (risk) => risk.severity === "critical" || risk.severity === "high",
  ).length;

  if (stage === "killed" || overview.project.status === "killed") {
    return {
      label: "Off track",
      tone: "danger",
      detail: "The project is marked as killed. Preserve the evidence trail for future review.",
    };
  }

  if (stage === "paused" || overview.project.status === "paused") {
    return {
      label: "Paused",
      tone: "neutral",
      detail: "The project is paused. Resume with the current next best action when ready.",
    };
  }

  if (overview.evidence_health.source_count === 0) {
    return {
      label: "Needs evidence",
      tone: "warning",
      detail: "The idea needs source-backed evidence before the recommendation can be trusted.",
    };
  }

  if (
    overview.current_recommendation.confidence === "low" ||
    highRiskCount > 0 ||
    overview.evidence_health.unsupported_claim_count > overview.evidence_health.cited_claim_count
  ) {
    return {
      label: "At risk",
      tone: "warning",
      detail: "There are material risks or weak evidence areas that should be validated next.",
    };
  }

  return {
    label: "On track",
    tone: "good",
    detail: "The project has a clear current state, supporting evidence, and a defined next action.",
  };
}

function HealthBadge({ health }: { health: ProjectHealth }) {
  return (
    <span className={healthBadgeClass(health.tone)}>
      <span className={healthDotClass(health.tone)} aria-hidden="true" />
      {health.label}
    </span>
  );
}

function healthBadgeClass(tone: HealthTone) {
  if (tone === "good") {
    return "inline-flex w-fit items-center gap-1.5 rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700";
  }
  if (tone === "warning") {
    return "inline-flex w-fit items-center gap-1.5 rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700";
  }
  if (tone === "danger") {
    return "inline-flex w-fit items-center gap-1.5 rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700";
  }
  return "inline-flex w-fit items-center gap-1.5 rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground";
}

function healthDotClass(tone: HealthTone) {
  if (tone === "good") {
    return "h-2 w-2 rounded-full bg-emerald-600";
  }
  if (tone === "warning") {
    return "h-2 w-2 rounded-full bg-amber-500";
  }
  if (tone === "danger") {
    return "h-2 w-2 rounded-full bg-red-600";
  }
  return "h-2 w-2 rounded-full bg-muted-foreground";
}

function lifecycleRows(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
): LifecycleRow[] {
  const currentStepIndex = lifecycleStepIndex(overview.strategic_snapshot.current_stage);
  const readinessKeys = new Set(overview.idea_readiness.completed_items.map((item) => item.key));
  const ideaComplete =
    readinessKeys.has("rough_idea") || Boolean(overview.strategic_snapshot.current_thesis);
  const researchComplete =
    overview.evidence_health.source_count > 0 ||
    overview.strategic_snapshot.current_stage !== "draft_idea";
  const validationComplete =
    overview.strategic_snapshot.current_stage === "validation_plan_created" ||
    overview.strategic_snapshot.current_stage === "experiment_running" ||
    overview.strategic_snapshot.current_stage === "decision_ready" ||
    overview.strategic_snapshot.current_stage === "proceeding";
  const decisionComplete =
    overview.strategic_snapshot.current_stage === "decision_ready" ||
    overview.strategic_snapshot.current_stage === "proceeding" ||
    overview.strategic_snapshot.current_stage === "paused" ||
    overview.strategic_snapshot.current_stage === "killed";

  const baseRows = [
    {
      key: "idea",
      label: "Idea",
      complete: ideaComplete,
      signal: overview.strategic_snapshot.current_thesis ? "Thesis captured" : "Thesis missing",
      next: ideaComplete ? "Pressure-test with research" : "Structure the rough idea",
    },
    {
      key: "research",
      label: "Research",
      complete: researchComplete,
      signal: `${overview.evidence_health.source_count} sources found`,
      next: researchComplete ? "Review findings" : "Run a research sprint",
    },
    {
      key: "evidence",
      label: "Evidence",
      complete: overview.evidence_health.source_count > 0,
      signal: `${overview.evidence_health.cited_claim_count} cited claims`,
      next:
        overview.evidence_health.unsupported_claim_count > 0
          ? "Resolve unsupported claims"
          : "Keep evidence current",
    },
    {
      key: "assumptions",
      label: "Assumptions",
      complete: overview.key_assumptions.length > 0,
      signal: `${overview.key_assumptions.length} ranked`,
      next: overview.key_assumptions.length > 0 ? "Validate riskiest item" : "Extract assumptions",
    },
    {
      key: "validation",
      label: "Validation",
      complete: validationComplete,
      signal: validationComplete ? "Plan active" : "Plan needed",
      next: validationComplete ? "Log results" : "Create validation plan",
    },
    {
      key: "decision",
      label: "Decision",
      complete: decisionComplete,
      signal: decisionComplete ? "Decision ready" : "Not ready",
      next: decisionComplete ? "Record rationale" : "Wait for validation signal",
    },
  ] as const;

  return baseRows.map((row, index) => ({
    key: row.key,
    label: row.label,
    status: row.complete ? "complete" : index === currentStepIndex ? "current" : "needs_work",
    signal: row.signal,
    next: row.next,
  }));
}

function LifecycleStatusBadge({ status }: { status: LifecycleStatus }) {
  if (status === "complete") {
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
        Complete
      </span>
    );
  }
  if (status === "current") {
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
        <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
        Current
      </span>
    );
  }
  if (status === "blocked") {
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
        <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
        Blocked
      </span>
    );
  }
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
      <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
      Needs work
    </span>
  );
}

function extractMemoSections(markdown: string) {
  const lines = markdown.split(/\r?\n/);
  const sections: Array<{ title: string; body: string }> = [];
  let currentTitle = "Executive Verdict";
  let currentBody: string[] = [];

  for (const line of lines) {
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      if (currentBody.join("\n").trim().length > 0) {
        sections.push({ title: currentTitle, body: currentBody.join("\n").trim() });
      }
      currentTitle = heading[1].trim();
      currentBody = [];
    } else {
      currentBody.push(line);
    }
  }

  if (currentBody.join("\n").trim().length > 0) {
    sections.push({ title: currentTitle, body: currentBody.join("\n").trim() });
  }

  return sections.filter((section) => section.body.trim().length > 0);
}

function preferredMemoSections(sections: Array<{ title: string; body: string }>) {
  const preferred = [
    "executive verdict",
    "best wedge",
    "key findings",
    "evidence summary",
    "risks",
    "assumptions",
    "what we still do not know",
    "recommended validation actions",
  ];
  const byTitle = new Map(sections.map((section) => [section.title.toLowerCase(), section]));
  const ordered = preferred
    .map((title) => {
      const exact = byTitle.get(title);
      if (exact) {
        return exact;
      }
      return sections.find((section) => section.title.toLowerCase().includes(title));
    })
    .filter((section): section is { title: string; body: string } => Boolean(section));
  const seen = new Set<string>();
  return [...ordered, ...sections].filter((section) => {
    const key = section.title.toLowerCase();
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function planToDraftState(plan: ResearchPlan): ResearchPlanDraftState {
  return {
    objective: plan.objective,
    target_customer_hypotheses: linesFromList(plan.target_customer_hypotheses),
    research_questions: linesFromList(plan.research_questions),
    competitor_queries: linesFromList(plan.competitor_queries),
    market_queries: linesFromList(plan.market_queries),
    substitute_queries: linesFromList(plan.substitute_queries),
    source_types: linesFromList(plan.source_types),
    assumptions_to_test: linesFromList(plan.assumptions_to_test),
    expected_outputs: linesFromList(plan.expected_outputs),
  };
}

function draftToUpdate(draft: ResearchPlanDraftState): ResearchPlanUpdateInput {
  return {
    objective: draft.objective,
    target_customer_hypotheses: listFromLines(draft.target_customer_hypotheses),
    research_questions: listFromLines(draft.research_questions),
    competitor_queries: listFromLines(draft.competitor_queries),
    market_queries: listFromLines(draft.market_queries),
    substitute_queries: listFromLines(draft.substitute_queries),
    source_types: listFromLines(draft.source_types),
    assumptions_to_test: listFromLines(draft.assumptions_to_test),
    expected_outputs: listFromLines(draft.expected_outputs),
  };
}

function researchMemoForSprint(artifacts: Artifact[], sprintId: string) {
  return (
    artifacts.find((artifact) => {
      const content = artifact.current_version?.structured_content;
      return content?.research_sprint_id === sprintId;
    }) ??
    artifacts[0] ??
    null
  );
}

function unsupportedClaimsFromArtifact(artifact: Artifact | null) {
  const content = artifact?.current_version?.structured_content;
  const memo = asRecord(content?.memo);
  return stringsFromUnknown(content?.unsupported_claims ?? memo?.unsupported_claims);
}

function citationsFromArtifact(artifact: Artifact | null): Citation[] {
  const content = artifact?.current_version?.structured_content;
  const memo = asRecord(content?.memo);
  return valuesFromUnknown(content?.citations ?? memo?.citations)
    .map(normalizeCitation)
    .filter((citation): citation is Citation => citation !== null);
}

function evidenceGapsFromArtifact(artifact: Artifact | null) {
  const content = artifact?.current_version?.structured_content;
  const memo = asRecord(content?.memo);
  return stringsFromUnknown(content?.evidence_gaps ?? memo?.evidence_gaps);
}

function retrievalToolCallCountFromArtifact(artifact: Artifact | null) {
  const content = artifact?.current_version?.structured_content;
  return valuesFromUnknown(content?.tool_calls).filter((value) => {
    const toolCall = asRecord(value);
    const tool = toolCall?.tool;
    return tool === "semantic_search" || tool === "keyword_search" || tool === "source_reader";
  }).length;
}

function memoryUpdateStatusFromArtifact(artifact: Artifact | null) {
  const status = artifact?.current_version?.structured_content.memory_update_status;
  return typeof status === "string" ? status : null;
}

function memoryUpdateSummaryFromArtifact(artifact: Artifact | null): MemoryUpdateSummary | null {
  const summary = asRecord(artifact?.current_version?.structured_content.memory_update_summary);
  if (!summary) {
    return null;
  }
  return {
    assumption_ids: stringsFromUnknown(summary.assumption_ids),
    risk_ids: stringsFromUnknown(summary.risk_ids),
    recommended_validation_actions: stringsFromUnknown(summary.recommended_validation_actions),
  };
}

function stringsFromUnknown(value: unknown) {
  return valuesFromUnknown(value).filter((item): item is string => typeof item === "string");
}

function valuesFromUnknown(value: unknown) {
  return Array.isArray(value) ? value : [];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeCitation(value: unknown): Citation | null {
  const citation = asRecord(value);
  if (!citation || typeof citation.source_id !== "string") {
    return null;
  }
  return {
    source_id: citation.source_id,
    chunk_id: nullableString(citation.chunk_id),
    title: nullableString(citation.title),
    url: nullableString(citation.url),
    quote: nullableString(citation.quote),
    retrieved_at: nullableString(citation.retrieved_at),
    relevance_score:
      typeof citation.relevance_score === "number" ? citation.relevance_score : null,
  };
}

function nullableString(value: unknown) {
  return typeof value === "string" ? value : null;
}

function linesFromList(values: string[]) {
  return values.join("\n");
}

function listFromLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatScore(value: string) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return parsed.toFixed(2);
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function truncate(value: string, maxLength: number) {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

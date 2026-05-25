"use client";

import {
  ArrowLeft,
  Beaker,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Database,
  FileSearch,
  Lightbulb,
  ListChecks,
  Route,
  ScrollText,
  ShieldAlert,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  approveResearchSprint,
  executeNextAction,
  getProjectOverview,
  IdeaReadiness,
  listResearchSprints,
  NextBestAction,
  ProjectStage,
  rejectResearchSprint,
  ResearchPlan,
  ResearchPlanUpdateInput,
  StrategicSnapshot,
  startResearchSprintPlan,
  updateResearchPlan,
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
import { WorkflowTrace } from "@/features/projects/workflow-trace";

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
        <Link
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          href="/projects"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Projects
        </Link>

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
                    <span className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                      {formatStage(overview.strategic_snapshot.current_stage)}
                    </span>
                    <span className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                      {formatLabel(project.status)}
                    </span>
                  </div>
                  <h1 className="mt-3 text-2xl font-semibold tracking-normal">{project.name}</h1>
                  <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                    {project.short_description ?? "No description recorded yet."}
                  </p>
                </div>
                <div className="sm:min-w-56">
                  <AiModeIndicator />
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
  const { current_recommendation, idea_readiness, next_best_action } = overview;
  const snapshot = overview.strategic_snapshot;
  const showIntake =
    snapshot.current_stage === "draft_idea" ||
    snapshot.current_stage === "structured_intake" ||
    !snapshot.current_thesis ||
    !snapshot.target_user ||
    !snapshot.primary_problem;

  return (
    <section className="mt-6 space-y-6">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Current Recommendation</h2>
          </div>
          <h3 className="mt-4 text-xl font-semibold tracking-normal">
            {current_recommendation.recommendation}
          </h3>
          <MarkdownContent
            className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground"
            markdown={current_recommendation.rationale}
          />
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
              Confidence: {formatLabel(current_recommendation.confidence)}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
              Next: {current_recommendation.next_action_label}
            </span>
          </div>
        </div>

        <div id="next-best-action" className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Next Best Action</h2>
          </div>
          <h3 className="mt-4 text-lg font-semibold tracking-normal">
            {next_best_action.label}
          </h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {next_best_action.description}
          </p>
          <div className="mt-4 rounded-md bg-muted p-3">
            <h4 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Why it matters
            </h4>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {next_best_action.why_it_matters}
            </p>
          </div>
          <Button
            className="mt-4 w-full"
            disabled={actionPending}
            onClick={() => onAction(next_best_action)}
            type="button"
          >
            <Target className="h-4 w-4" aria-hidden="true" />
            {actionPending ? "Opening..." : next_best_action.label}
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
        </div>
      </div>

      {showIntake ? (
        <StructuredIntakeWizard
          onFinalized={onIntakeFinalized}
          project={overview.project}
        />
      ) : null}

      <ResearchSprintCard projectId={overview.project.id} />

      <div className="grid gap-5 lg:grid-cols-[380px_minmax(0,1fr)]">
        <IdeaReadinessCard readiness={idea_readiness} />
        <StrategicSnapshotCard snapshot={overview.strategic_snapshot} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[380px_minmax(0,1fr)]">
        <EvidenceHealthCard health={overview.evidence_health} />
        <RecentUpdatesCard updates={overview.recent_strategic_updates} />
      </div>

      <KeyAssumptionsAndRisks
        assumptions={overview.key_assumptions}
        risks={overview.key_risks}
      />
    </section>
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

  return (
    <div id="research-sprint" className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Research Sprint</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Ask the system to plan an autonomous investigation before it discovers sources or
            competitors. No browsing or ingestion starts until you approve the plan.
          </p>
        </div>
        {latestSprint ? (
          <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
            Latest: {formatLabel(latestSprint.status)}
          </span>
        ) : null}
      </div>

      {!activePlan ? (
        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <label className="block">
            <span className="text-sm font-medium">Research objective</span>
            <textarea
              className="mt-2 min-h-24 w-full resize-y rounded-md border border-border px-3 py-2 text-sm outline-none focus:border-primary"
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Investigate whether this idea has a strong wedge, which competitors matter, and what to validate next."
              value={objective}
            />
          </label>
          <div className="flex flex-col justify-end gap-3">
            <Button
              disabled={busy}
              onClick={() => startMutation.mutate()}
              type="button"
            >
              <FileSearch className="h-4 w-4" aria-hidden="true" />
              {startMutation.isPending ? "Planning..." : "Run Research Sprint"}
            </Button>
            {latestSprint?.status === "approved" ? (
              <p className="text-xs leading-5 text-muted-foreground">
                The latest plan is approved. Source discovery and execution begin in V1 Sprint 2.
              </p>
            ) : latestSprint?.status === "rejected" ? (
              <p className="text-xs leading-5 text-muted-foreground">
                The latest plan was rejected. Generate a new plan when the objective changes.
              </p>
            ) : null}
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
  if (actionType.includes("brief")) {
    return "Brief";
  }
  if (actionType.includes("competitor")) {
    return "Competitors";
  }
  if (actionType.includes("assumption")) {
    return "Assumptions";
  }
  if (actionType.includes("experiment") || actionType.includes("result")) {
    return "Experiments";
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
  const match = tabs.find((tab) => tab.toLowerCase() === normalized);
  return match ?? null;
}

function formatStage(stage: ProjectStage) {
  return formatLabel(stage);
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

function truncate(value: string, maxLength: number) {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

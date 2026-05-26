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
  getProjectOverview,
  IdeaReadiness,
  listArtifacts,
  listCompetitorCandidates,
  listDiscoveredSources,
  listResearchSprints,
  NextBestAction,
  ProjectStage,
  rejectCompetitorCandidate,
  rejectDiscoveredSource,
  rejectResearchSprint,
  ResearchPlan,
  ResearchPlanUpdateInput,
  ResearchSprint,
  runAgenticResearch,
  StrategicSnapshot,
  startResearchSprintPlan,
  updateCompetitorCandidate,
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
              <AssumptionsTab
                onOpenExperiments={() => selectTab("Experiments")}
                projectId={project.id}
              />
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
                The latest plan is approved. Discover sources and competitors before generating
                the research memo.
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

      {canReviewDiscovery && latestSprint ? (
        <ResearchDiscoveryPanel
          onRunTrace={setLastRunId}
          onSprintUpdated={() => sprintsQuery.refetch()}
          projectId={projectId}
          sprint={latestSprint}
        />
      ) : null}

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
  const [memoReviewOpen, setMemoReviewOpen] = useState(false);
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
      setMemoReviewOpen(true);
      await researchMemosQuery.refetch();
      await onSprintUpdated();
    },
  });
  const approveMemoMutation = useMutation({
    mutationFn: () => approveAgenticResearchMemo(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      setMemoReviewOpen(true);
      await researchMemosQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assumptions"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "risks"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "experiments"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
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
    approveSourceMutation.isPending ||
    rejectSourceMutation.isPending ||
    updateCandidateMutation.isPending ||
    approveCandidateMutation.isPending ||
    rejectCandidateMutation.isPending;

  return (
    <div className="mt-6 border-t border-border pt-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 className="text-sm font-semibold">Discovery Review</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Generate candidate sources and competitors from the approved plan. Review items before
            they are ingested as evidence or merged into the project competitor set, then synthesize
            a cited research memo from the project evidence graph.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={busy}
            onClick={() => discoverSourcesMutation.mutate()}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Globe2 className="h-4 w-4" aria-hidden="true" />
            {discoverSourcesMutation.isPending ? "Discovering..." : "Discover Sources"}
          </Button>
          <Button
            disabled={busy}
            onClick={() => discoverCompetitorsMutation.mutate()}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Building2 className="h-4 w-4" aria-hidden="true" />
            {discoverCompetitorsMutation.isPending
              ? "Discovering..."
              : "Discover Competitors"}
          </Button>
          <Button
            disabled={busy || sprint.status === "completed"}
            onClick={() => agenticResearchMutation.mutate()}
            size="sm"
            type="button"
          >
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            {agenticResearchMutation.isPending ? "Synthesizing..." : "Run Agentic RAG"}
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
                The workflow used {retrievalToolCallCount} retrieval calls, found{" "}
                {evidenceGapCount} evidence gaps, and paused before major memory updates.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-fit rounded-md bg-white px-2 py-1 text-xs text-muted-foreground">
                {formatLabel(memoArtifact.artifact_type)}
              </span>
              <Button
                onClick={() => setMemoReviewOpen((open) => !open)}
                size="sm"
                type="button"
                variant="secondary"
              >
                <ScrollText className="h-4 w-4" aria-hidden="true" />
                {memoReviewOpen ? "Hide Memo" : "Review Memo"}
              </Button>
            </div>
          </div>
          {memoryUpdateStatus ? (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Memory update status: {formatLabel(memoryUpdateStatus)}.
            </p>
          ) : null}
          {unsupportedClaims.length > 0 ? (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Open questions: {unsupportedClaims.slice(0, 2).join("; ")}
            </p>
          ) : null}
        </div>
      ) : null}

      {memoReviewOpen && memoArtifact && memoVersion ? (
        <ResearchMemoReview
          artifact={memoArtifact}
          approvalPending={approveMemoMutation.isPending}
          citations={citations}
          memoryUpdateStatus={memoryUpdateStatus}
          memoryUpdateSummary={memoryUpdateSummary}
          onApprove={() => approveMemoMutation.mutate()}
          unsupportedClaims={unsupportedClaims}
          version={memoVersion}
        />
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
  unsupportedClaims,
  version,
}: {
  artifact: Artifact;
  approvalPending: boolean;
  citations: Citation[];
  memoryUpdateStatus: string | null;
  memoryUpdateSummary: MemoryUpdateSummary | null;
  onApprove: () => void;
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

  return (
    <div id="research-memo-review" className="mt-5 border-t border-border pt-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-base font-semibold">{artifact.title}</h3>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
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
                : "w-fit rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700"
            }
          >
          {approved ? "Approved" : "Human review pending"}
          </span>
          <Button
            disabled={approved || approvalPending}
            onClick={onApprove}
            size="sm"
            type="button"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            {approved ? "Approved" : approvalPending ? "Approving..." : "Approve Memo"}
          </Button>
        </div>
      </div>

      {memoryUpdateSummary ? (
        <div className="mt-4 rounded-md bg-muted px-4 py-3 text-sm leading-6 text-muted-foreground">
          <span className="font-medium text-foreground">Memory updates:</span>{" "}
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

      <div className="mt-5 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <article className="min-w-0">
          <MarkdownContent markdown={version.markdown_content} />
        </article>

        <aside className="space-y-5">
          <section className="border-b border-border pb-5">
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

          <section className="border-b border-border pb-5">
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
        </aside>
      </div>
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
            <div className="rounded-md border border-border p-3" key={source.id}>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
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
                  <h5 className="mt-2 text-sm font-semibold">
                    {source.title ?? "Untitled source"}
                  </h5>
                </div>
                {source.status === "candidate" || source.status === "failed" ? (
                  <div className="flex gap-2">
                    <Button
                      disabled={busy}
                      onClick={() => onApprove(source.id)}
                      size="sm"
                      type="button"
                    >
                      Approve
                    </Button>
                    <Button
                      disabled={busy}
                      onClick={() => onReject(source.id)}
                      size="sm"
                      type="button"
                      variant="secondary"
                    >
                      Reject
                    </Button>
                  </div>
                ) : null}
              </div>
              <a
                className="mt-2 block break-all text-xs text-primary hover:underline"
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
                  Ingested {formatDateTime(source.ingested_at)}
                </p>
              ) : null}
            </div>
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
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
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
          <h5 className="mt-2 text-sm font-semibold">{candidate.name}</h5>
        </div>
        {candidate.status === "candidate" ? (
          <div className="flex gap-2">
            <Button
              disabled={busy}
              onClick={() => onApprove(candidate.id)}
              size="sm"
              type="button"
            >
              Approve
            </Button>
            <Button
              disabled={busy}
              onClick={() => onReject(candidate.id)}
              size="sm"
              type="button"
              variant="secondary"
            >
              Reject
            </Button>
          </div>
        ) : null}
      </div>
      {candidate.url ? (
        <a
          className="mt-2 block break-all text-xs text-primary hover:underline"
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
          Evidence ingested{candidate.ingested_at ? ` ${formatDateTime(candidate.ingested_at)}` : ""}.
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

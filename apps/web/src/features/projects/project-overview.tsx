"use client";

import {
  ArrowLeft,
  AlertTriangle,
  Beaker,
  Building2,
  ChevronDown,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  Compass,
  Database,
  ExternalLink,
  FileSearch,
  FileText,
  GitBranch,
  Globe2,
  Lightbulb,
  ListChecks,
  Menu,
  Route,
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  Target,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  approveAgenticResearchMemo,
  approveApprovalRequest,
  approveCompetitorCandidate,
  approveDiscoveredSource,
  approveResearchSprint,
  ApprovalRequest,
  Artifact,
  ArtifactVersion,
  cancelDurableResearchWorkflow,
  Citation,
  CompetitorCandidate,
  CompetitorCandidateUpdateInput,
  discoverCompetitorCandidates,
  discoverSources,
  DiscoveredSource,
  dismissProjectNudge,
  executeNextAction,
  GuideAction,
  getIdeaStory,
  getDurableResearchStatus,
  getProjectResearchHistory,
  getProjectOverview,
  getProjectNudges,
  getV1ResearchEval,
  listApprovalRequests,
  listArtifacts,
  listAuditEvents,
  listCompetitorCandidates,
  listDiscoveredSources,
  listResearchSprints,
  listToolInvocations,
  NextBestAction,
  ProjectStage,
  ProjectNudge,
  rejectApprovalRequest,
  rejectCompetitorCandidate,
  rejectDiscoveredSource,
  rejectAgenticResearchMemo,
  rejectResearchSprint,
  RecommendationConfidence,
  retryDurableResearchWorkflow,
  ResearchPlan,
  ResearchPlanUpdateInput,
  ResearchSprint,
  runAgenticResearch,
  StrategicRecommendation,
  startDurableResearchWorkflow,
  startResearchSprintPlan,
  ToolInvocation,
  updateCompetitorCandidate,
  updateResearchPlan,
} from "@/lib/api";
import { AssumptionsTab } from "@/features/projects/assumptions-tab";
import {
  assumptionBeliefText,
  clarifyDecisionNarrative,
  decisionBlockerText,
  evidenceReadinessText,
  nextProofText,
} from "@/features/projects/assumption-copy";
import { BriefTab } from "@/features/projects/brief-tab";
import { CompetitorsTab } from "@/features/projects/competitors-tab";
import { DecisionsTab } from "@/features/projects/decisions-tab";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import { EvidenceTab } from "@/features/projects/evidence-tab";
import { ExperimentsTab } from "@/features/projects/experiments-tab";
import { GuidePanel } from "@/features/projects/guide-panel";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { StructuredIntakeWizard } from "@/features/projects/structured-intake-wizard";
import { ThesisTab } from "@/features/projects/thesis-tab";
import { WorkflowTrace } from "@/features/projects/workflow-trace";
import { cn } from "@/lib/utils";
import {
  hashShouldRemainAnchor,
  projectNavigationItems,
  recordSurfaceForTab,
  type ProjectNavigationItem,
  type ProjectTab,
  tabForActionType as routeTabForActionType,
  tabForGuideAction as routeTabForGuideAction,
  tabFromAnchor,
  tabFromHash,
  tabHash,
} from "@/features/projects/project-overview-routing";

type IntelligenceDetailMode = "evidence" | "competitors" | "review" | "brief";
type ValidationDetailMode = "tests" | "blockers";
type RecordDetailMode = "brief";

type EvidenceReviewQueueItem =
  | { id: string; kind: "source"; source: DiscoveredSource }
  | { id: string; kind: "competitor"; candidate: CompetitorCandidate }
  | { artifact: Artifact; id: string; kind: "memo"; version: ArtifactVersion };

const playbookIcons: Record<string, LucideIcon> = {
  "current-step": Target,
  decide: ClipboardCheck,
  decision: ClipboardCheck,
  guide: Lightbulb,
  history: ScrollText,
  research: FileSearch,
  shape: GitBranch,
  test: Beaker,
  thesis: GitBranch,
};

export function ProjectOverview() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [activeTab, setActiveTab] = useState<ProjectTab>("Current Step");
  const [activeAnchor, setActiveAnchor] = useState<string | null>(null);
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
    const syncTabFromHash = () => {
      const hash = window.location.hash;
      const rawAnchor = hash.replace("#", "") || null;
      const tabFromAlias = tabFromHash(hash);
      const tab = tabFromAlias ?? tabFromAnchor(rawAnchor);
      if (tab) {
        setActiveTab(tab);
      }
      setActiveAnchor(tabFromAlias && hashShouldRemainAnchor(rawAnchor) ? rawAnchor : tabFromAlias ? null : rawAnchor);
    };
    syncTabFromHash();
    window.addEventListener("hashchange", syncTabFromHash);
    return () => window.removeEventListener("hashchange", syncTabFromHash);
  }, []);

  const overview = overviewQuery.data;
  const project = overview?.project;
  const recordSurface = recordSurfaceForTab(activeTab);

  function openNavigationItem(item: ProjectNavigationItem) {
    openWorkspace(item.label, item.anchor);
  }

  function runAction(action: NextBestAction) {
    activateAction(action);
    if (action.primary) {
      nextActionMutation.mutate();
    }
  }

  function runGuideAction(action: GuideAction) {
    const hash = action.target_route?.split("#")[1] ?? null;
    const tab = tabFromHash(hash ? `#${hash}` : "") ?? tabFromAnchor(hash) ?? routeTabForGuideAction(action);
    const anchor = hash && !tabFromHash(`#${hash}`) ? hash : action.target_modal;
    openWorkspace(tab, anchor ?? null);
  }

  function activateAction(action: NextBestAction) {
    const tab = tabForAction(action);
    const anchor = anchorForAction(action);
    openWorkspace(tab, anchor);
  }

  function openWorkspace(tab: ProjectTab, anchor: string | null = null) {
    setActiveTab(tab);
    setActiveAnchor(anchor);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${anchor ?? tabHash(tab)}`);
    }
    if (anchor) {
      window.setTimeout(() => {
        if (anchor === "structured-intake") {
          const drawer = document.getElementById(anchor) as HTMLDetailsElement | null;
          if (drawer?.tagName === "DETAILS") {
            drawer.open = true;
            drawer.dispatchEvent(new Event("toggle"));
          }
        }
        const target = document.getElementById(anchor);
        if (target?.tagName === "DETAILS") {
          const drawer = target as HTMLDetailsElement;
          drawer.open = true;
          drawer.dispatchEvent(new Event("toggle"));
        }
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
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1280px]">
        <div className="flex items-center justify-between gap-3">
          <Link
            className="-ml-2 inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            href="/projects"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Projects
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <MobileProjectMenu activeTab={activeTab} onOpen={openNavigationItem} />
          </div>
        </div>

        {overviewQuery.isLoading ? (
          <ProjectOverviewSkeleton />
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
                  Retry project
                </Button>
              }
              message={(overviewQuery.error as Error).message}
            />
          </div>
        ) : overview && project ? (
          <>
            <header className="mt-6 border-b border-border pb-5">
              <div className="min-w-0">
                <div className="hidden flex-wrap items-center gap-2 sm:flex">
                  <span className={stageBadgeClass(overview.strategic_snapshot.current_stage)}>
                    {formatStage(overview.strategic_snapshot.current_stage)}
                  </span>
                  <span className="rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                    {formatLabel(project.status)}
                  </span>
                </div>
                <h1 className="mt-3 text-2xl font-semibold tracking-normal sm:text-3xl">
                  {project.name}
                </h1>
                <p className="mt-2 hidden max-w-[68ch] text-sm leading-6 text-muted-foreground sm:block">
                  {project.short_description ?? "No description recorded yet."}
                </p>
                <p className="mt-2 hidden text-xs text-muted-foreground sm:block">
                  Last updated {formatDateTime(project.updated_at)}
                </p>
              </div>
            </header>

            <ProjectStatusBar overview={overview} />

            <MobileWorkspaceAction
              activeTab={activeTab}
              actionPending={nextActionMutation.isPending}
              onAction={runAction}
              onOpenWorkspace={openWorkspace}
              overview={overview}
            />

            <div className="mt-5 grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[250px_minmax(0,1fr)]">
              <ProjectMap
                activeAnchor={activeAnchor}
                activeTab={activeTab}
                onOpen={openNavigationItem}
                overview={overview}
              />

              <div className="min-w-0">
                {activeTab === "Current Step" ? (
                  <GuidedOverview
                    actionPending={nextActionMutation.isPending}
                    onAction={runAction}
                    onGuideAction={runGuideAction}
                    onIntakeFinalized={refreshOverviewAfterIntake}
                    onOpenWorkspace={openWorkspace}
                    overview={overview}
                  />
                ) : activeTab === "Shape" ? (
                  <ThesisTab activeAnchor={activeAnchor} projectId={project.id} />
                ) : activeTab === "Research" ? (
                  <IntelligenceWorkspace
                    activeAnchor={activeAnchor}
                    overview={overview}
                    projectId={project.id}
                  />
                ) : activeTab === "Test" ? (
                  <ValidationWorkspace
                    activeAnchor={activeAnchor}
                    onAction={runAction}
                    overview={overview}
                    projectId={project.id}
                  />
                ) : recordSurface === "decision" ? (
                  <RecordWorkspace
                    activeAnchor={activeAnchor}
                    onOpenValidation={() => openWorkspace("Test", "validation-mission")}
                    projectId={project.id}
                  />
                ) : recordSurface === "history" ? (
                  <HistoryWorkspace overview={overview} />
                ) : null}
                <GuideActionDrawer
                  onAction={runGuideAction}
                  projectId={project.id}
                />
              </div>
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}

function ProjectOverviewSkeleton() {
  return (
    <div
      aria-label="Loading project"
      aria-busy="true"
      className="mt-6 animate-pulse motion-reduce:animate-none"
    >
      <div className="border-b border-border pb-5">
        <div className="h-5 w-44 rounded bg-muted" />
        <div className="mt-4 h-8 w-full max-w-xl rounded bg-muted" />
        <div className="mt-3 h-4 w-full max-w-2xl rounded bg-muted" />
        <div className="mt-2 h-4 w-72 rounded bg-muted" />
      </div>
      <div className="mt-5 rounded-lg border border-border bg-card p-4">
        <div className="h-4 w-36 rounded bg-muted" />
        <div className="mt-3 h-5 w-full max-w-3xl rounded bg-muted" />
        <div className="mt-2 hidden h-4 w-full max-w-4xl rounded bg-muted sm:block" />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[270px_minmax(0,1fr)]">
        <div className="hidden rounded-lg border border-border bg-card p-4 lg:block">
          <div className="h-4 w-24 rounded bg-muted" />
          <div className="mt-5 space-y-3">
            {[0, 1, 2, 3].map((item) => (
              <div className="h-12 rounded-md bg-muted" key={item} />
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="h-4 w-32 rounded bg-muted" />
          <div className="mt-4 h-6 w-full max-w-lg rounded bg-muted" />
          <div className="mt-3 h-4 w-full max-w-2xl rounded bg-muted" />
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <div className="h-20 rounded-md bg-muted" />
            <div className="h-20 rounded-md bg-muted" />
            <div className="h-20 rounded-md bg-muted" />
          </div>
        </div>
      </div>
    </div>
  );
}

function ProjectMap({
  activeAnchor,
  activeTab,
  onOpen,
  overview,
}: {
  activeAnchor: string | null;
  activeTab: ProjectTab;
  onOpen: (item: ProjectNavigationItem) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  return (
    <aside className="hidden min-w-0 max-w-full self-start overflow-hidden lg:sticky lg:top-5 lg:block">
      <div className="px-1 pb-2">
        <h2 className="text-xs font-medium text-muted-foreground">Guided mode</h2>
      </div>
      <nav
        className="grid w-full grid-cols-2 gap-1 sm:grid-cols-4 lg:grid-cols-1"
        aria-label="Project navigation"
      >
        {projectNavigationItems.map((item) => {
          const Icon = playbookIcons[item.key] ?? Route;
          const selected = item.label === activeTab;
          const current = item.label === "Current Step";
          return (
            <button
              aria-label={`Open ${item.label}: ${item.detail}.`}
              aria-current={selected ? "page" : undefined}
              className={[
                "flex min-h-12 cursor-pointer flex-col items-center justify-center gap-1 rounded-md border px-1.5 py-2 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus lg:min-h-0 lg:w-full lg:flex-row lg:items-start lg:justify-start lg:gap-3 lg:px-2 lg:py-2.5 lg:text-left",
                selected
                  ? "border-primary bg-primary/10 text-foreground"
                  : current
                    ? "border-border bg-card text-foreground hover:bg-muted"
                    : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
              ].join(" ")}
              key={item.key}
              onClick={() => onOpen(item)}
              type="button"
            >
              <Icon
                className={
                  selected || current
                    ? "h-4 w-4 shrink-0 text-primary lg:mt-0.5"
                    : "h-4 w-4 shrink-0 lg:mt-0.5"
                }
                aria-hidden="true"
              />
              <span className="min-w-0">
                <span className="flex min-w-0 flex-wrap items-center justify-center gap-1.5 lg:justify-start">
                  <span className="block truncate text-xs font-medium lg:text-sm">{item.label}</span>
                  {current ? (
                    <span className="hidden rounded-md bg-primary/10 px-1.5 py-0.5 text-[0.68rem] font-medium text-primary lg:inline-flex">
                      now
                    </span>
                  ) : null}
                </span>
                <span
                  aria-hidden="true"
                  className="mt-0.5 hidden text-xs leading-5 text-muted-foreground xl:block"
                >
                  {item.detail}
                </span>
              </span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

function MobileProjectMenu({
  activeTab,
  onOpen,
}: {
  activeTab: ProjectTab;
  onOpen: (item: ProjectNavigationItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const selectedItem =
    projectNavigationItems.find((item) => item.label === activeTab) ?? projectNavigationItems[0];
  return (
    <>
      <button
        aria-controls="mobile-project-menu"
        aria-expanded={open}
        aria-label="Open project menu"
        className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-md border border-border bg-card text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus lg:hidden"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <Menu className="h-5 w-5 text-primary" aria-hidden="true" />
      </button>
      {open ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close project menu backdrop"
            className="absolute inset-0 cursor-default bg-background/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            type="button"
          />
          <aside
            aria-label="Project menu"
            aria-modal="true"
            className="absolute right-0 top-0 flex h-full w-[min(22rem,calc(100vw-2rem))] flex-col border-l border-border bg-card shadow-2xl"
            id="mobile-project-menu"
            role="dialog"
          >
            <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-4">
              <div className="min-w-0">
                <p className="text-xs font-medium text-muted-foreground">Project menu</p>
                <h2 className="truncate text-base font-semibold">{selectedItem.label}</h2>
              </div>
              <button
                aria-label="Close project menu"
                className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                onClick={() => setOpen(false)}
                type="button"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <nav aria-label="Project navigation" className="grid gap-1 p-3">
              {projectNavigationItems.map((item) => {
                const Icon = playbookIcons[item.key] ?? Route;
                const selected = item.label === activeTab;
                const current = item.label === "Current Step";
                return (
                  <button
                    aria-current={selected ? "page" : undefined}
                    aria-label={`Open ${item.label}: ${item.detail}.`}
                    className={[
                      "flex min-h-14 cursor-pointer items-start gap-3 rounded-md border px-3 py-3 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                      selected
                        ? "border-primary bg-primary/10 text-foreground"
                        : current
                          ? "border-warning-border bg-warning-muted text-foreground"
                          : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
                    ].join(" ")}
                    key={item.key}
                    onClick={() => {
                      onOpen(item);
                      setOpen(false);
                    }}
                    type="button"
                  >
                    <Icon
                      className={
                        selected || current
                          ? "mt-0.5 h-4 w-4 shrink-0 text-primary"
                          : "mt-0.5 h-4 w-4 shrink-0"
                      }
                      aria-hidden="true"
                    />
                    <span className="min-w-0">
                      <span className="flex min-w-0 flex-wrap items-center gap-2">
                        <span className="block truncate font-medium">{item.label}</span>
                        {current ? (
                          <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-[0.68rem] font-medium text-primary">
                            now
                          </span>
                        ) : null}
                      </span>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                        {item.detail}
                      </span>
                    </span>
                  </button>
                );
              })}
            </nav>
          </aside>
        </div>
      ) : null}
    </>
  );
}
function GuideActionDrawer({
  onAction,
  projectId,
}: {
  onAction: (action: GuideAction) => void;
  projectId: string;
}) {
  const [open, setOpen] = useState(false);
  function routeAction(action: GuideAction) {
    onAction(action);
    setOpen(false);
  }

  return (
    <>
      <Button
        aria-controls="project-guide-drawer"
        aria-expanded={open}
        aria-label={open ? "Hide Thesys guide" : "Open Thesys guide"}
        className="fixed bottom-4 right-4 z-40 min-h-12 rounded-full px-4 shadow-lg print:hidden"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <Compass className="h-4 w-4" aria-hidden="true" />
        Ask Thesys
      </Button>

      {open ? (
        <div className="fixed inset-0 z-50 print:hidden">
          <button
            aria-label="Close Thesys guide backdrop"
            className="absolute inset-0 cursor-default bg-background/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            type="button"
          />
          <section
            aria-label="Thesys guide action drawer"
            aria-modal="true"
            className="absolute inset-x-3 bottom-3 mx-auto max-h-[82vh] max-w-3xl overflow-hidden rounded-xl border border-border bg-card shadow-2xl sm:inset-x-6"
            id="project-guide-drawer"
            role="dialog"
          >
            <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
              <div className="min-w-0">
                <p className="text-xs font-medium text-muted-foreground">Thesys Guide</p>
                <h2 className="text-base font-semibold">Tell me where to go next</h2>
              </div>
              <button
                aria-label="Close Thesys guide"
                className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                onClick={() => setOpen(false)}
                type="button"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <div className="max-h-[calc(82vh-64px)] overflow-y-auto p-4">
              <GuidePanel
                className="border-0 bg-transparent p-0 lg:static lg:top-auto"
                onAction={routeAction}
                projectId={projectId}
              />
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

function MobileWorkspaceAction({
  activeTab,
  actionPending,
  onAction,
  onOpenWorkspace,
  overview,
}: {
  activeTab: ProjectTab;
  actionPending: boolean;
  onAction: (action: NextBestAction) => void;
  onOpenWorkspace: (tab: ProjectTab, anchor?: string | null) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const nextActionLabel = clarifyActionLabel(overview.next_best_action.label);
  const decisionReady = decisionGradeEvidence(overview).value === "Ready to decide";
  const config =
    activeTab === "Current Step"
      ? {
          action: () => onAction(overview.next_best_action),
          button: nextActionLabel,
          description: "Use the next validation move before reading the full decision context.",
          icon: Target,
          title: "Next move",
        }
      : activeTab === "Shape"
        ? {
            action: () => onOpenWorkspace("Shape", "thesis-canvas"),
            button: "Open thesis",
            description: "Review the current thesis, rejected directions, and evolution trail.",
            icon: GitBranch,
            title: "Idea shape",
          }
      : activeTab === "Research"
        ? {
            action: () => onOpenWorkspace("Research", "research-sprint"),
            button: "Inspect research",
            description: "Open the evidence workbench only when the current basis needs review.",
            icon: FileSearch,
            title: "Research details",
          }
        : activeTab === "Test"
          ? {
              action: () => onOpenWorkspace("Test", "validation-mission"),
              button: "Open mission",
              description: "Run or log the one proof that can change the verdict.",
              icon: Beaker,
              title: "Active test",
            }
          : activeTab === "History"
            ? {
                action: () => onOpenWorkspace("History", "history"),
                button: "Inspect history",
                description: "Review lifecycle status, risks, and recent decision updates.",
                icon: ScrollText,
                title: "History",
              }
          : decisionReady
            ? {
                action: () => onOpenWorkspace("Decide", "record-decision-panel"),
                button: "Prepare record",
                description: "Validation is ready enough to draft the durable decision record.",
                icon: ScrollText,
                title: "Decision record",
              }
            : {
                action: () => onOpenWorkspace("Test", "validation-mission"),
                button: "Log mission result",
                description: "Record is guarded until validation evidence exists. Complete the proof first.",
                icon: Beaker,
                title: "Guardrail",
              };
  const Icon = config.icon;

  return (
    <section className="mt-3 rounded-lg border border-border bg-card p-3 lg:hidden">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-md bg-primary/10 p-2 text-primary">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{config.title}</h2>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{config.description}</p>
          <Button
            className="mt-3 min-h-11 w-full"
            disabled={actionPending}
            onClick={config.action}
            type="button"
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {actionPending ? "Opening..." : config.button}
          </Button>
        </div>
      </div>
    </section>
  );
}

function GuidedOverview({
  actionPending,
  onAction,
  onGuideAction,
  onIntakeFinalized,
  onOpenWorkspace,
  overview,
}: {
  actionPending: boolean;
  onAction: (action: NextBestAction) => void;
  onGuideAction: (action: GuideAction) => void;
  onIntakeFinalized: () => Promise<string | null>;
  onOpenWorkspace: (tab: ProjectTab, anchor?: string | null) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const { current_recommendation, next_best_action } = overview;
  const snapshot = overview.strategic_snapshot;
  const [recordOpen, setRecordOpen] = useState(false);
  const showInitialIntake =
    snapshot.current_stage === "draft_idea" ||
    snapshot.current_stage === "structured_intake" ||
    (!snapshot.current_thesis &&
      !snapshot.target_user &&
      !snapshot.primary_problem &&
      overview.evidence_health.source_count === 0 &&
      overview.key_assumptions.length === 0);
  const contextGaps = decisionContextGaps(overview);
  const missingContextCount = contextGaps.filter((item) => item.status !== "complete").length;

  return (
    <section className="space-y-4 lg:space-y-6">
      <div id="next-best-action">
        <MobileDecisionSpine
          currentRecommendation={current_recommendation}
          missingContextCount={missingContextCount}
          overview={overview}
        />
        <div className="hidden lg:block">
          <CurrentStepPanel
            actionPending={actionPending}
            currentRecommendation={current_recommendation}
            missingContextCount={missingContextCount}
            nextBestAction={next_best_action}
            onAction={onAction}
            onOpenWorkspace={onOpenWorkspace}
            overview={overview}
          />
        </div>
      </div>

      <OverviewNudges onAction={onGuideAction} projectId={overview.project.id} />

      <DecisionContextDrawer
        contextGaps={contextGaps}
        missingContextCount={missingContextCount}
        onIntakeFinalized={onIntakeFinalized}
        overview={overview}
        showInitialIntake={showInitialIntake}
      />

      <details
        className="hidden rounded-lg border border-border bg-card p-5 lg:block"
        onToggle={(event) => setRecordOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer list-none">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold">Decision history</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Lifecycle status, active risks, and recent decision updates.
              </p>
            </div>
            <DisclosureLabel closedLabel="Inspect history" open={recordOpen} openLabel="Hide history" />
          </div>
        </summary>
        <div className="mt-5 grid gap-5 border-t border-border pt-5">
          <LifecycleProgressCard overview={overview} />
          <TopRisksCard risks={overview.key_risks} />
          <RecentUpdatesCard updates={overview.recent_strategic_updates} />
        </div>
      </details>
    </section>
  );
}

function OverviewNudges({
  onAction,
  projectId,
}: {
  onAction: (action: GuideAction) => void;
  projectId: string;
}) {
  const queryClient = useQueryClient();
  const nudgesQuery = useQuery({
    queryKey: ["projects", projectId, "nudges"],
    queryFn: () => getProjectNudges(projectId),
  });
  const dismissMutation = useMutation({
    mutationFn: (nudgeId: string) => dismissProjectNudge(projectId, nudgeId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "nudges"] });
    },
  });
  const nudges = nudgesQuery.data ?? [];
  if (nudges.length === 0) {
    return null;
  }
  return (
    <section aria-label="Project nudges" className="grid gap-2 lg:grid-cols-2">
      {nudges.slice(0, 2).map((nudge) => (
        <CompactNudge
          disabled={dismissMutation.isPending}
          key={nudge.id}
          nudge={nudge}
          onAction={() => onAction(nudge.action)}
          onDismiss={() => dismissMutation.mutate(nudge.id)}
        />
      ))}
    </section>
  );
}

function CompactNudge({
  disabled,
  nudge,
  onAction,
  onDismiss,
}: {
  disabled: boolean;
  nudge: ProjectNudge;
  onAction: () => void;
  onDismiss: () => void;
}) {
  return (
    <section className={cn("rounded-lg border p-3", compactNudgeClass(nudge.severity))}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-md bg-background p-2 text-primary">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">{nudge.title}</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{nudge.message}</p>
            </div>
            <button
              aria-label={`Dismiss ${nudge.title}`}
              className="rounded-md p-1 text-muted-foreground hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              disabled={disabled}
              onClick={onDismiss}
              type="button"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="line-clamp-2 text-xs leading-5 text-muted-foreground">
              {nudge.why_it_matters}
            </p>
            <Button
              className="min-h-10 shrink-0"
              onClick={onAction}
              size="sm"
              type="button"
              variant={nudge.severity === "action_required" ? "default" : "secondary"}
            >
              {nudge.action.label}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function compactNudgeClass(severity: ProjectNudge["severity"]) {
  if (severity === "action_required") {
    return "border-warning-border bg-warning-muted";
  }
  if (severity === "warning") {
    return "border-warning-border bg-card";
  }
  return "border-border bg-card";
}

function MobileDecisionSpine({
  currentRecommendation,
  missingContextCount,
  overview,
}: {
  currentRecommendation: StrategicRecommendation;
  missingContextCount: number;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const blocker = riskiestAssumption(overview);
  const recovery = recoveryGuidance(overview, missingContextCount);

  return (
    <section
      aria-labelledby="mobile-decision-spine-title"
      className="rounded-lg border border-border bg-card lg:hidden"
    >
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="mobile-decision-spine-title" className="text-sm font-semibold">
            Decision context
          </h2>
        </div>
      </div>

      <div className="divide-y divide-border">
        <MobileDecisionSpineRow
          body={
            blocker
              ? decisionBlockerText(blocker)
              : "No decision blocker has been ranked yet. Structure context or extract assumptions before treating the verdict as durable."
          }
          icon={<ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />}
          label="Blocker"
          meta={
            blocker ? (
              <div className="flex flex-wrap gap-2">
                <AssumptionCompactSignal
                  label="Risk"
                  tone={
                    blocker.kill_risk ||
                    blocker.importance === "critical" ||
                    blocker.importance === "high"
                      ? "warning"
                      : "neutral"
                  }
                  value={blocker.kill_risk ? "High" : formatLabel(blocker.importance)}
                />
                <AssumptionCompactSignal
                  label="Evidence"
                  tone={blocker.evidence_links.length > 0 ? "neutral" : "warning"}
                  value={evidenceReadinessText(blocker)}
                />
              </div>
            ) : null
          }
          title={blocker ? assumptionBeliefText(blocker.text) : "Blocker missing"}
        />

        <MobileDecisionSpineRow
          body={clarifyDecisionNarrative(currentRecommendation.rationale)}
          icon={<Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />}
          label="Rationale"
          title="Why the decision waits"
        />

        <MobileDecisionSpineRow
          body={recovery.detail}
          icon={<ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />}
          label="Recovery"
          meta={<span className={tonePillClass(recovery.tone)}>{recovery.label}</span>}
          title={recovery.title}
        />
      </div>
    </section>
  );
}

function MobileDecisionSpineRow({
  action,
  body,
  icon,
  label,
  meta,
  title,
}: {
  action?: ReactNode;
  body: string;
  icon: ReactNode;
  label: string;
  meta?: ReactNode;
  title: string;
}) {
  return (
    <section className="px-4 py-4">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-xs font-medium text-muted-foreground">{label}</h3>
      </div>
      <MarkdownContent
        className="mt-2 line-clamp-3 space-y-2 text-base font-semibold leading-6 text-foreground"
        markdown={title}
      />
      <MarkdownContent
        className="mt-2 line-clamp-4 space-y-2 text-sm leading-6 text-muted-foreground"
        markdown={body}
      />
      {meta ? <div className="mt-3">{meta}</div> : null}
      {action ? <div className="mt-4 space-y-2">{action}</div> : null}
    </section>
  );
}

function AssumptionCompactSignal({
  label,
  tone,
  value,
}: {
  label: string;
  tone: HealthTone;
  value: string;
}) {
  return (
    <span className={tonePillClass(tone)}>
      {label}: {value}
    </span>
  );
}

function DecisionContextDrawer({
  contextGaps,
  missingContextCount,
  onIntakeFinalized,
  overview,
  showInitialIntake,
}: {
  contextGaps: DecisionContextItem[];
  missingContextCount: number;
  onIntakeFinalized: () => Promise<string | null>;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
  showInitialIntake: boolean;
}) {
  const [open, setOpen] = useState(false);
  const closedLabel = showInitialIntake
    ? "Structure context"
    : missingContextCount > 0
      ? "Add context"
      : "Open context";

  return (
    <details
      className="rounded-lg border border-border bg-card p-4 lg:p-5"
      id="structured-intake"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer list-none rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ListChecks className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Decision context</h2>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {missingContextCount > 0
                ? `${missingContextCount} context item${missingContextCount === 1 ? "" : "s"} still need detail.`
                : "Thesis, project context, history, and progress stay behind this secondary drawer."}
            </p>
          </div>
          <DisclosureLabel
            closedLabel={closedLabel}
            open={open}
            openLabel="Hide context"
          />
        </div>
      </summary>
      <div className="mt-5 border-t border-border pt-5">
        <ContextGapList items={contextGaps} />
        <MobileDecisionSupport overview={overview} />
        <StructuredIntakeWizard
          onFinalized={onIntakeFinalized}
          project={overview.project}
          sectionId="structured-intake-form"
        />
      </div>
    </details>
  );
}

function MobileDecisionSupport({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const focus = stageFocusCopy(overview.strategic_snapshot.current_stage);
  const rows = lifecycleRows(overview);
  const health = overview.evidence_health;

  return (
    <div className="mt-5 space-y-5 lg:hidden">
      <MobileSupportSection
        icon={<Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />}
        title={focus.title}
      >
        <p className="text-sm leading-6 text-muted-foreground">{focus.summary}</p>
        <div className="mt-4 grid gap-4">
          <SnapshotField label="Current thesis" value={overview.strategic_snapshot.current_thesis} />
          <SnapshotField label="Target user" value={overview.strategic_snapshot.target_user} />
          <SnapshotField label="Primary problem" value={overview.strategic_snapshot.primary_problem} />
          <SnapshotField label="Possible wedge" value={overview.strategic_snapshot.proposed_wedge} />
          <SnapshotField label="Main risk" value={overview.strategic_snapshot.main_risk} />
        </div>
      </MobileSupportSection>

      <MobileSupportSection
        icon={<Route className="h-4 w-4 text-primary" aria-hidden="true" />}
        title="Progress"
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            {overview.idea_readiness.score}% workflow complete
          </span>
          <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            {formatStage(overview.strategic_snapshot.current_stage)}
          </span>
        </div>
        <div className="mt-3 space-y-2">
          {rows.map((row) => (
            <div className="border-t border-border py-2 first:border-t-0 first:pt-0" key={row.key}>
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-sm font-semibold">{row.label}</h4>
                <LifecycleStatusBadge status={row.status} />
              </div>
              <p className="mt-1 text-sm leading-5 text-muted-foreground">{row.signal}</p>
            </div>
          ))}
        </div>
      </MobileSupportSection>

      <MobileSupportSection
        icon={<Database className="h-4 w-4 text-primary" aria-hidden="true" />}
        title="Evidence summary"
      >
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <MobileMetric label="Sources" value={health.source_count} />
          <MobileMetric label="Competitors" value={health.competitor_count} />
          <MobileMetric label="Supported findings" value={health.cited_claim_count} />
          <MobileMetric label="Open questions" value={health.unsupported_claim_count} />
        </dl>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Weakest evidence area: {health.weakest_evidence_area}
        </p>
      </MobileSupportSection>

      <MobileSupportSection
        icon={<ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />}
        title="History"
      >
        <MobileHistoryPreview overview={overview} />
      </MobileSupportSection>
    </div>
  );
}

function MobileSupportSection({
  children,
  icon,
  title,
}: {
  children: ReactNode;
  icon: ReactNode;
  title: string;
}) {
  return (
    <section className="border-t border-border pt-5">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function MobileMetric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-lg font-semibold">{value}</dd>
    </div>
  );
}

function MobileHistoryPreview({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const topRisk = overview.key_risks[0] ?? null;
  const updates = overview.recent_strategic_updates.slice(0, 3);

  return (
    <div className="space-y-4">
      {topRisk ? (
        <div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
              {topRisk.severity} risk
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
              {topRisk.likelihood} likelihood
            </span>
          </div>
          <MarkdownContent
            className="mt-2 line-clamp-3 space-y-2 text-sm leading-6 text-foreground"
            markdown={topRisk.text}
          />
        </div>
      ) : (
        <p className="text-sm leading-6 text-muted-foreground">
          No risks recorded yet. Run evidence review or extract assumptions to build the history trail.
        </p>
      )}

      {updates.length > 0 ? (
        <div className="divide-y divide-border">
          {updates.map((update) => (
            <div className="py-3 first:pt-0" key={update.id}>
              <h4 className="text-sm font-semibold">{clarifyWorkspaceTerm(update.title)}</h4>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                {truncate(clarifyWorkspaceTerm(update.summary), 180)}
              </p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

type DecisionContextItem = {
  detail: string;
  label: string;
  status: "complete" | "missing";
};

function decisionContextGaps(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
): DecisionContextItem[] {
  const snapshot = overview.strategic_snapshot;
  return [
    {
      detail: snapshot.target_user ?? "Define who must feel the problem.",
      label: "Target user",
      status: snapshot.target_user ? "complete" : "missing",
    },
    {
      detail: snapshot.primary_problem ?? "Name the problem this project is testing.",
      label: "Primary problem",
      status: snapshot.primary_problem ? "complete" : "missing",
    },
    {
      detail: snapshot.current_thesis ?? "Capture the current working thesis.",
      label: "Current thesis",
      status: snapshot.current_thesis ? "complete" : "missing",
    },
    {
      detail: snapshot.proposed_wedge ?? "Describe why this could win against alternatives.",
      label: "Possible wedge",
      status: snapshot.proposed_wedge ? "complete" : "missing",
    },
  ];
}

function ContextGapList({ items }: { items: DecisionContextItem[] }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div
          className={
            item.status === "complete"
              ? "rounded-md bg-surface px-3 py-2"
              : "rounded-md border border-warning-border bg-warning-muted px-3 py-2"
          }
          key={item.label}
        >
          <div className="flex items-center gap-2">
            {item.status === "complete" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-success-foreground" aria-hidden="true" />
            ) : (
              <CircleAlert className="h-4 w-4 shrink-0 text-warning-foreground" aria-hidden="true" />
            )}
            <h3 className="text-xs font-medium text-muted-foreground">{item.label}</h3>
          </div>
          <p className="mt-2 line-clamp-3 text-sm leading-6 text-foreground">{item.detail}</p>
        </div>
      ))}
    </div>
  );
}

function ProjectStatusBar({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const status = canonicalProjectStatus(overview);
  return (
    <section
      aria-label="Project status"
      className="mt-3 border-b border-border pb-3 text-card-foreground sm:mt-4 sm:pb-4"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <div className="text-xs font-medium text-muted-foreground">Status</div>
          <span className={tonePillClass(status.tone)}>{status.label}</span>
        </div>
        <p className="mt-0.5 max-w-[84ch] text-sm font-semibold leading-5 text-foreground sm:hidden">
          {status.mobileSentence}
        </p>
        <p className="mt-1 hidden max-w-[84ch] text-sm font-semibold leading-6 text-foreground sm:block">
          {status.sentence}
        </p>
        <p className="mt-1 hidden max-w-[84ch] text-xs leading-5 text-muted-foreground sm:block">
          {status.detail}
        </p>
      </div>
    </section>
  );
}

function CurrentStepPanel({
  actionPending,
  currentRecommendation,
  missingContextCount,
  nextBestAction,
  onAction,
  onOpenWorkspace,
  overview,
}: {
  actionPending: boolean;
  currentRecommendation: StrategicRecommendation;
  missingContextCount: number;
  nextBestAction: NextBestAction;
  onAction: (action: NextBestAction) => void;
  onOpenWorkspace: (tab: ProjectTab, anchor?: string | null) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const nextActionLabel = clarifyActionLabel(nextBestAction.label);
  const blocker = riskiestAssumption(overview);
  const decisionGrade = decisionGradeEvidence(overview);
  const health = overview.evidence_health;
  const recovery = recoveryGuidance(overview, missingContextCount);
  const status = canonicalProjectStatus(overview);
  const biggestUnknown = blocker
    ? assumptionBeliefText(blocker.text)
    : overview.strategic_snapshot.main_risk ?? health.weakest_evidence_area;
  const nextProof = blocker?.recommended_test
    ? stripLeadingSignalLabel(nextProofText(blocker))
    : clarifyActionText(nextBestAction.description);
  const [signalsOpen, setSignalsOpen] = useState(false);
  const ideaStoryQuery = useQuery({
    queryKey: ["projects", overview.project.id, "idea-story"],
    queryFn: () => getIdeaStory(overview.project.id),
  });

  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="p-5 lg:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
                <span>Current Step</span>
              </div>
              <span className={tonePillClass(status.tone)}>{status.label}</span>
              <span className={tonePillClass(decisionGrade.tone)}>{decisionGrade.value}</span>
            </div>
            <h2 className="mt-4 max-w-4xl text-2xl font-semibold tracking-normal">
              {nextActionLabel}
            </h2>
            <p className="mt-3 max-w-[72ch] text-sm leading-6 text-muted-foreground">
              {clarifyActionText(nextBestAction.why_it_matters)}
            </p>
          </div>
          <Button
            className="min-h-11 shrink-0"
            disabled={actionPending}
            onClick={() => onAction(nextBestAction)}
            type="button"
          >
            <Target className="h-4 w-4" aria-hidden="true" />
            {actionPending ? "Opening step..." : nextActionLabel}
          </Button>
        </div>

        <IdeaStorySection
          currentRecommendation={currentRecommendation}
          fallbackBiggestUnknown={biggestUnknown}
          fallbackNextProof={nextProof}
          ideaStory={ideaStoryQuery.data ?? null}
          isError={ideaStoryQuery.isError}
          isLoading={ideaStoryQuery.isLoading}
          onOpenWorkspace={onOpenWorkspace}
          overview={overview}
        />

        <details
          className="mt-5 border-t border-border pt-4"
          onToggle={(event) => setSignalsOpen(event.currentTarget.open)}
        >
          <summary className="cursor-pointer list-none rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-semibold">Inspect supporting signals</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Evidence, recovery, and blocker details stay available when you need the receipts.
                </p>
              </div>
              <DisclosureLabel closedLabel="Inspect details" open={signalsOpen} openLabel="Hide details" />
            </div>
          </summary>
          <div className="mt-4 grid gap-5 xl:grid-cols-3">
            <DecisionSignal
              body={
                blocker
                  ? decisionBlockerText(blocker)
                  : "No ranked blocker yet. Structure context or extract assumptions before treating the verdict as durable."
              }
              icon={<ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />}
              label="Biggest unknown"
              title={blocker ? assumptionBeliefText(blocker.text) : "Blocker missing"}
            />
            <DecisionSignal
              body={`Weakest area: ${health.weakest_evidence_area}`}
              icon={<Database className="h-4 w-4 text-primary" aria-hidden="true" />}
              label="Evidence summary"
              meta={
                <div className="flex flex-wrap gap-2">
                  <DecisionMetric label="Sources" value={health.source_count} />
                  <DecisionMetric label="Open" value={health.unsupported_claim_count} />
                  <DecisionMetric label="Validated" value={health.validated_assumption_count} />
                </div>
              }
              title={decisionGrade.detail}
            />
            <DecisionSignal
              body={recovery.detail}
              icon={<ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />}
              label="After this step"
              meta={<span className={tonePillClass(recovery.tone)}>{recovery.label}</span>}
              title={recovery.title}
            />
          </div>
        </details>

        <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-5">
          <Button
            onClick={() => onOpenWorkspace("Test", "validation-mission")}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Beaker className="h-4 w-4" aria-hidden="true" />
            Show test plan
          </Button>
          <Button
            onClick={() => onOpenWorkspace("Research", "evidence")}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Database className="h-4 w-4" aria-hidden="true" />
            Show evidence
          </Button>
          <Button
            onClick={() => onOpenWorkspace("Shape", "wedge-explorer")}
            size="sm"
            type="button"
            variant="secondary"
          >
            <GitBranch className="h-4 w-4" aria-hidden="true" />
            Compare wedges
          </Button>
          <Button
            onClick={() => onOpenWorkspace("Current Step", "project-guide")}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Compass className="h-4 w-4" aria-hidden="true" />
            Ask Thesys
          </Button>
        </div>
      </div>
    </section>
  );
}

function IdeaStorySection({
  currentRecommendation,
  fallbackBiggestUnknown,
  fallbackNextProof,
  ideaStory,
  isError,
  isLoading,
  onOpenWorkspace,
  overview,
}: {
  currentRecommendation: StrategicRecommendation;
  fallbackBiggestUnknown: string;
  fallbackNextProof: string;
  ideaStory: NonNullable<Awaited<ReturnType<typeof getIdeaStory>>> | null;
  isError: boolean;
  isLoading: boolean;
  onOpenWorkspace: (tab: ProjectTab, anchor?: string | null) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const story = ideaStory ?? {
    current_blocker: fallbackBiggestUnknown,
    current_thesis: overview.strategic_snapshot.current_thesis ?? currentRecommendation.recommendation,
    latest_change_reason: null,
    latest_change_title: null,
    next_proof: fallbackNextProof,
    original_idea: overview.project.short_description ?? overview.project.name,
    project_id: overview.project.id,
    rejected_directions: [] as string[],
    selected_wedge:
      overview.strategic_snapshot.proposed_wedge ??
      "Choose or refine the wedge before expanding validation.",
    why_it_changed:
      "The idea story is being assembled from thesis, wedge, evidence, validation, and decision history.",
  };
  const rejectedDirection = story.rejected_directions[0] ?? "No rejected direction yet.";
  const [storyOpen, setStoryOpen] = useState(false);

  return (
    <section className="mt-5 border-t border-border pt-5" id="idea-story">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-base font-semibold">Current test path</h3>
          </div>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            {isLoading
              ? "Loading thesis, wedge, blocker, and next proof..."
              : isError
                ? "Showing the available project story while the evolution trail reloads."
                : `Started as: ${truncate(story.original_idea, 180)}`}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <IdeaStoryRow label="Current thesis" value={story.current_thesis} emphasis />
        <IdeaStoryRow label="Selected wedge" value={story.selected_wedge} emphasis />
        <IdeaStoryRow label="Biggest unknown" value={story.current_blocker} />
        <IdeaStoryRow label="Next proof" value={story.next_proof} emphasis />
      </div>

      <details
        className="mt-4 border-t border-border pt-4"
        onToggle={(event) => setStoryOpen(event.currentTarget.open)}
      >
        <summary className="cursor-pointer list-none rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h4 className="text-sm font-semibold">Inspect idea growth</h4>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                See what changed, what was rejected, and why this wedge is the current path.
              </p>
            </div>
            <DisclosureLabel closedLabel="Inspect story" open={storyOpen} openLabel="Hide story" />
          </div>
        </summary>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <IdeaStoryRow label="Original idea" value={story.original_idea} />
          <IdeaStoryRow label="Rejected direction" value={rejectedDirection} />
          <IdeaStoryRow label="Why it changed" value={story.why_it_changed} />
          <IdeaStoryRow
            label={story.latest_change_title ?? "Latest change"}
            value={story.latest_change_reason ?? "No additional change reason recorded yet."}
          />
        </div>
        <Button
          className="mt-4 min-h-10"
          onClick={() => onOpenWorkspace("Shape", "thesis-evolution")}
          size="sm"
          type="button"
          variant="secondary"
        >
          <ScrollText className="h-4 w-4" aria-hidden="true" />
          Inspect full evolution
        </Button>
      </details>
    </section>
  );
}

function IdeaStoryRow({
  emphasis = false,
  label,
  value,
}: {
  emphasis?: boolean;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <MarkdownContent
        className={[
          "mt-1 line-clamp-4 space-y-2 text-sm leading-6 text-foreground",
          emphasis ? "font-semibold" : "",
        ].join(" ")}
        markdown={value}
      />
    </div>
  );
}

function DecisionSignal({
  body,
  icon,
  label,
  meta,
  title,
}: {
  body: string;
  icon: ReactNode;
  label: string;
  meta?: ReactNode;
  title: string;
}) {
  return (
    <section className="min-w-0">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="text-xs font-medium text-muted-foreground">{label}</h3>
      </div>
      <MarkdownContent
        className="mt-2 line-clamp-3 space-y-2 text-sm font-semibold leading-6 text-foreground"
        markdown={title}
      />
      <MarkdownContent
        className="mt-2 line-clamp-3 space-y-2 text-sm leading-6 text-muted-foreground"
        markdown={body}
      />
      {meta ? <div className="mt-3">{meta}</div> : null}
    </section>
  );
}

function DecisionMetric({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
      {label}: {value}
    </span>
  );
}

function RiskiestAssumptionCard({
  onAction,
  overview,
}: {
  onAction: (action: NextBestAction) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const assumption = riskiestAssumption(overview);
  if (!assumption) {
    return null;
  }

  return (
    <DomainPanel>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-[72ch]">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Assumptions behind the decision</h2>
          </div>
          <p className="mt-3 text-xs font-medium text-muted-foreground">
            Belief to validate
          </p>
          <MarkdownContent
            className="mt-3 space-y-2 text-lg font-semibold leading-7 text-foreground"
            markdown={assumptionBeliefText(assumption.text)}
          />
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {decisionBlockerText(assumption)}
          </p>
          {assumption.recommended_test ? (
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              {nextProofText(assumption)}
            </p>
          ) : null}
        </div>
        <div className="grid min-w-64 gap-2 sm:grid-cols-3 lg:grid-cols-1">
          <AssumptionSignal
            label="Risk"
            value={assumption.kill_risk ? "High" : formatLabel(assumption.importance)}
            tone={
              assumption.kill_risk ||
              assumption.importance === "critical" ||
              assumption.importance === "high"
                ? "warning"
                : "neutral"
            }
          />
          <AssumptionSignal
            label="Confidence"
            value={assumptionConfidenceLabel(assumption.confidence_score)}
            tone={
              assumption.confidence_score && Number(assumption.confidence_score) >= 0.65
                ? "good"
                : "warning"
            }
          />
          <AssumptionSignal
            label="Evidence"
            value={evidenceReadinessText(assumption)}
            tone={assumption.evidence_links.length > 0 ? "neutral" : "warning"}
          />
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button
          onClick={() => onAction(overview.next_best_action)}
          type="button"
          variant="secondary"
        >
          <Target className="h-4 w-4" aria-hidden="true" />
          {clarifyActionLabel(overview.next_best_action.label)}
        </Button>
      </div>
    </DomainPanel>
  );
}

function AssumptionSignal({
  label,
  tone,
  value,
}: {
  label: string;
  tone: HealthTone;
  value: string;
}) {
  return (
    <div className="border-t border-border py-2 first:border-t-0 lg:first:border-t">
      <div className="text-xs text-muted-foreground">{label}</div>
      <span className={`${tonePillClass(tone)} mt-1`}>{value}</span>
    </div>
  );
}

function IntelligenceWorkspace({
  activeAnchor,
  overview,
  projectId,
}: {
  activeAnchor: string | null;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
  projectId: string;
}) {
  const [detailMode, setDetailMode] = useState<IntelligenceDetailMode | null>(null);

  useEffect(() => {
    if (!activeAnchor) {
      return;
    }
    if (["research", "research-sprint", "research-operations"].includes(activeAnchor)) {
      setDetailMode("review");
    } else if (activeAnchor.includes("competitor")) {
      setDetailMode("competitors");
    } else if (activeAnchor.includes("brief")) {
      setDetailMode("brief");
    } else if (activeAnchor.includes("evidence") || activeAnchor.includes("source")) {
      setDetailMode("evidence");
    }
  }, [activeAnchor]);

  return (
    <section className="space-y-6">
      <DomainHeader
        action={
          <Button onClick={() => setDetailMode("review")} type="button">
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            Plan evidence review
          </Button>
        }
        description="Inspect the sources, competitors, and findings only when the current evidence basis needs review."
        icon={<FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="Inspect research details"
        title="Research"
      />

      <ResearchResultCard overview={overview} />

      <WorkbenchAccessPanel<IntelligenceDetailMode>
        activeMode={detailMode}
        description="Open one advanced evidence surface at a time. The verdict stays readable until you need the deeper table or control surface."
        options={[
          {
            description: "Source coverage, citations, and open questions.",
            icon: Database,
            label: "Evidence summary",
            mode: "evidence",
          },
          {
            description: "Direct competitors, substitutes, and incumbents.",
            icon: Building2,
            label: "Competitors and substitutes",
            mode: "competitors",
          },
          {
            description: "Plan, discover, approve, and memo evidence.",
            icon: FileSearch,
            label: "Evidence review",
            mode: "review",
          },
          {
            description: "Longer generated thesis record.",
            icon: FileText,
            label: "Full research memo",
            mode: "brief",
          },
        ]}
        title="Inspect research details"
        onSelect={setDetailMode}
      />

      {detailMode ? (
        <ActiveWorkbenchPanel
          description={intelligenceDetailDescription(detailMode)}
          id={detailMode === "review" ? "research-sprint" : undefined}
          onClose={() => setDetailMode(null)}
          title={intelligenceDetailTitle(detailMode)}
        >
          {detailMode === "evidence" ? (
            <EvidenceTab projectId={projectId} />
          ) : detailMode === "competitors" ? (
            <CompetitorsTab projectId={projectId} />
          ) : detailMode === "review" ? (
            <>
              <ResearchSprintSummary projectId={overview.project.id} />
              <ResearchSprintCard projectId={projectId} />
            </>
          ) : (
            <BriefTab projectId={projectId} />
          )}
        </ActiveWorkbenchPanel>
      ) : null}
    </section>
  );
}

function ValidationWorkspace({
  activeAnchor,
  onAction,
  overview,
  projectId,
}: {
  activeAnchor: string | null;
  onAction: (action: NextBestAction) => void;
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
  projectId: string;
}) {
  const [detailMode, setDetailMode] = useState<ValidationDetailMode | null>(null);

  useEffect(() => {
    if (!activeAnchor) {
      return;
    }
    if (
      activeAnchor.includes("experiment") ||
      activeAnchor.includes("validation") ||
      activeAnchor.includes("result")
    ) {
      setDetailMode("tests");
    } else if (activeAnchor.includes("assumption") || activeAnchor.includes("blocker")) {
      setDetailMode("blockers");
    }
  }, [activeAnchor]);

  return (
    <section className="space-y-6">
      <DomainHeader
        action={
          <Button onClick={() => setDetailMode("tests")} type="button">
            <Beaker className="h-4 w-4" aria-hidden="true" />
            Open mission
          </Button>
        }
        description="Run or log the current proof that can change the project decision."
        icon={<Beaker className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="Run the current proof"
        title="Validation Mission"
      />

      <RiskiestAssumptionCard overview={overview} onAction={onAction} />

      <WorkbenchAccessPanel<ValidationDetailMode>
        activeMode={detailMode}
        description="Keep validation focused on the current blocker. Open one supporting surface only when you are ready to plan, log, or re-rank."
        options={[
          {
            description: "Open the active proof, assets, steps, and result logging.",
            icon: Beaker,
            label: "Active test",
            mode: "tests",
          },
          {
            description: "Review and re-rank the beliefs behind the verdict.",
            icon: ShieldAlert,
            label: "Assumptions behind the decision",
            mode: "blockers",
          },
        ]}
        title="Inspect test details"
        onSelect={setDetailMode}
      />

      {detailMode ? (
        <ActiveWorkbenchPanel
          description={detailMode === "tests" ? "Plan or log the one validation loop that can change the verdict." : "Inspect the ranked beliefs only when the active blocker needs review."}
          id={detailMode === "tests" ? "validation-mission" : undefined}
          onClose={() => setDetailMode(null)}
          title={detailMode === "tests" ? "Active test" : "Assumptions behind the decision"}
        >
          {detailMode === "tests" ? (
            <ExperimentsTab projectId={projectId} />
          ) : (
            <AssumptionsTab
              onOpenExperiments={() => {
                setDetailMode("tests");
                window.setTimeout(() => {
                  document.getElementById("log-results-panel")?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
                }, 50);
              }}
              projectId={projectId}
            />
          )}
        </ActiveWorkbenchPanel>
      ) : null}
    </section>
  );
}

function RecordWorkspace({
  activeAnchor,
  onOpenValidation,
  projectId,
}: {
  activeAnchor: string | null;
  onOpenValidation: () => void;
  projectId: string;
}) {
  const [detailMode, setDetailMode] = useState<RecordDetailMode | null>(null);

  useEffect(() => {
    if (!activeAnchor) {
      return;
    }
    if (activeAnchor.includes("brief")) {
      setDetailMode("brief");
    }
  }, [activeAnchor]);

  return (
    <section className="space-y-6">
      <DecisionsTab
        activeAnchor={activeAnchor}
        onOpenValidation={onOpenValidation}
        projectId={projectId}
      />

      <WorkbenchAccessPanel<RecordDetailMode>
        activeMode={detailMode}
        description="Record the decision first. Open the longer brief only when you need supporting narrative."
        options={[
          {
            description: "Generated thesis record and supporting narrative.",
            icon: FileText,
            label: "Full research memo",
            mode: "brief",
          },
        ]}
        title="Inspect record details"
        onSelect={setDetailMode}
      />

      {detailMode ? (
        <ActiveWorkbenchPanel
          description="Use the brief as the longer record after the decision work is clear."
          onClose={() => setDetailMode(null)}
          title="Full research memo"
        >
          <BriefTab projectId={projectId} />
        </ActiveWorkbenchPanel>
      ) : null}
    </section>
  );
}

function HistoryWorkspace({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  return (
    <section className="space-y-6">
      <DomainHeader
        description="Audit how the project reached its current decision state."
        icon={<ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="Review the evidence trail"
        signals={[
          { label: "Workflow", value: `${overview.idea_readiness.score}% complete` },
          { label: "Risks", value: overview.key_risks.length },
          { label: "Updates", value: overview.recent_strategic_updates.length },
        ]}
        title="History"
      />
      <LifecycleProgressCard overview={overview} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <TopRisksCard risks={overview.key_risks} />
        <RecentUpdatesCard updates={overview.recent_strategic_updates} />
      </div>
    </section>
  );
}

function WorkbenchAccessPanel<TMode extends string>({
  activeMode,
  description,
  options,
  title,
  onSelect,
}: {
  activeMode: TMode | null;
  description: string;
  options: Array<{
    description: string;
    icon: LucideIcon;
    label: string;
    mode: TMode;
  }>;
  title: string;
  onSelect: (mode: TMode) => void;
}) {
  const [open, setOpen] = useState(Boolean(activeMode));

  useEffect(() => {
    if (activeMode) {
      setOpen(true);
    }
  }, [activeMode]);

  return (
    <details
      className="rounded-lg border border-border bg-card p-5"
      onToggle={(event) => setOpen(event.currentTarget.open)}
      open={open}
    >
      <summary className="cursor-pointer list-none rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-base font-semibold">{title}</h3>
            <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
              {description}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {activeMode ? (
              <span className="w-fit rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                {options.find((option) => option.mode === activeMode)?.label}
              </span>
            ) : null}
            <DisclosureLabel closedLabel="Inspect details" open={open} openLabel="Hide details" />
          </div>
        </div>
      </summary>
      <div className="mt-4 grid gap-2 border-t border-border pt-4 sm:grid-cols-2 xl:grid-cols-4">
        {options.map((option) => {
          const Icon = option.icon;
          const selected = option.mode === activeMode;
          return (
            <button
              aria-pressed={selected}
              className={[
                "min-h-24 rounded-md border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                selected
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-border bg-surface text-foreground hover:bg-muted",
              ].join(" ")}
              key={option.mode}
              onClick={() => onSelect(option.mode)}
              type="button"
            >
              <div className="flex items-center gap-2">
                <Icon
                  className={selected ? "h-4 w-4 text-primary" : "h-4 w-4 text-muted-foreground"}
                  aria-hidden="true"
                />
                <span className="text-sm font-semibold">{option.label}</span>
              </div>
              <p className="mt-2 text-sm leading-5 text-muted-foreground">
                {option.description}
              </p>
            </button>
          );
        })}
      </div>
    </details>
  );
}

function ActiveWorkbenchPanel({
  children,
  description,
  id,
  onClose,
  title,
}: {
  children: ReactNode;
  description: string;
  id?: string;
  onClose: () => void;
  title: string;
}) {
  return (
    <section className="border-t border-border pt-5" id={id}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold">{title}</h3>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        <Button onClick={onClose} size="sm" type="button" variant="secondary">
          Close details
        </Button>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function intelligenceDetailTitle(mode: IntelligenceDetailMode) {
  if (mode === "evidence") {
    return "Evidence summary";
  }
  if (mode === "competitors") {
    return "Competitors and substitutes";
  }
  if (mode === "review") {
    return "Evidence review controls";
  }
  return "Full research memo";
}

function intelligenceDetailDescription(mode: IntelligenceDetailMode) {
  if (mode === "evidence") {
    return "Review citations, source coverage, and open questions behind the current verdict.";
  }
  if (mode === "competitors") {
    return "Review direct products, substitutes, incumbents, and manual alternatives behind the wedge.";
  }
  if (mode === "review") {
    return "Plan an evidence review, approve discovered sources, inspect source checks, and review the generated memo.";
  }
  return "Review the full generated research memo when you need the longer thesis record.";
}

function DisclosureLabel({
  closedLabel,
  open,
  openLabel,
}: {
  closedLabel: string;
  open: boolean;
  openLabel: string;
}) {
  return (
    <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
      <ChevronDown
        className={open ? "h-3.5 w-3.5 rotate-180 transition-transform" : "h-3.5 w-3.5 transition-transform"}
        aria-hidden="true"
      />
      {open ? openLabel : closedLabel}
    </span>
  );
}

function ResearchResultCard({
  overview,
}: {
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>;
}) {
  const assumption = riskiestAssumption(overview);
  const topSubstitute =
    overview.evidence_health.competitor_count > 0
      ? "See mapped competitors and substitutes"
      : "Competitors still need to be mapped";

  return (
    <DomainPanel>
      <div className="flex items-center gap-2">
        <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
        <h3 className="text-base font-semibold">Evidence summary</h3>
      </div>
      <div className="mt-4 grid gap-x-8 lg:grid-cols-2">
        <ResultBlock title="Verdict" value={overview.current_recommendation.recommendation} />
        <ResultBlock title="Possible wedge" value={overview.strategic_snapshot.proposed_wedge ?? "Wedge still needs evidence."} />
        <ResultBlock title="Competitive pressure" value={topSubstitute} />
        <ResultBlock title="Main risk" value={overview.strategic_snapshot.main_risk ?? "The largest risk has not been identified yet."} />
        <ResultBlock title="Assumptions behind the decision" value={assumption ? decisionBlockerText(assumption) : "No decision blocker ranked yet."} />
        <ResultBlock title="Next proof" value={assumption ? nextProofText(assumption) : clarifyActionText(overview.next_best_action.description)} />
        <ResultBlock title="Scope guardrail" value="Do not expand product scope until the decision blocker has real validation evidence." />
        <ResultBlock title="Decision rationale" value={clarifyDecisionNarrative(overview.current_recommendation.rationale)} />
      </div>
    </DomainPanel>
  );
}

function ResultBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="border-t border-border py-3">
      <p className="text-xs font-medium text-muted-foreground">
        {title}
      </p>
      <MarkdownContent className="mt-1 max-w-[72ch] text-sm leading-6 text-foreground" markdown={value} />
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
      label: "Review plan",
      complete: true,
      detail: `${sprint.plan.research_questions.length} research question${
        sprint.plan.research_questions.length === 1 ? "" : "s"
      }`,
    },
    {
      label: "Source discovery",
      complete: (history?.source_candidate_count ?? 0) > 0,
      detail: `${history?.source_candidate_count ?? 0} source${
        (history?.source_candidate_count ?? 0) === 1 ? "" : "s"
      } found`,
    },
    {
      label: "Competitor discovery",
      complete: (history?.competitor_candidate_count ?? 0) > 0,
      detail: `${history?.competitor_candidate_count ?? 0} competitor${
        (history?.competitor_candidate_count ?? 0) === 1 ? "" : "s"
      } found`,
    },
    {
      label: "Evidence added",
      complete: (history?.ingested_source_count ?? 0) > 0,
      detail: `${history?.ingested_source_count ?? 0} source${
        (history?.ingested_source_count ?? 0) === 1 ? "" : "s"
      } added`,
    },
    {
      label: "Evidence memo",
      complete: Boolean(history?.memo_artifact_id),
      detail: history?.memo_artifact_id ? "Memo ready" : "Not generated",
    },
    {
      label: "Decision update",
      complete: history?.memory_update_status === "approved",
      detail: history?.memory_update_status
        ? formatLabel(history.memory_update_status)
        : "Awaiting approval",
    },
  ];
  return (
    <div className="mt-5 border-t border-border pt-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold">Evidence review steps</h4>
          <p className="mt-1 text-xs text-muted-foreground">
            Review the steps before approving any decision updates.
          </p>
        </div>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          Evidence steps
        </span>
      </div>
      <div className="mt-4 grid gap-2 sm:hidden">
        {steps.map((step, index) => (
          <div className="rounded-md bg-surface px-3 py-3" key={step.label}>
            <div className="flex items-start gap-3">
              <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h5 className="text-sm font-semibold">{step.label}</h5>
                  <span
                    className={
                      step.complete
                        ? "inline-flex items-center gap-1 rounded-md bg-success-muted px-2 py-1 text-xs text-success-foreground"
                        : "inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                    }
                  >
                    {step.complete ? (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {step.complete ? "Complete" : "Incomplete"}
                  </span>
                </div>
                <dl className="mt-3 grid gap-2 text-sm">
                  <div>
                    <dt className="text-xs text-muted-foreground">Output</dt>
                    <dd className="mt-1 break-words text-foreground">{step.detail}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Next step</dt>
                    <dd className="mt-1 text-foreground">
                      {step.complete ? "Review" : "Continue review"}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 hidden overflow-x-auto sm:block">
        <table className="w-full min-w-[680px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs  text-muted-foreground">
              <th className="px-3 py-2 font-medium">Step</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Output</th>
              <th className="px-3 py-2 font-medium">Next step</th>
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
                        ? "inline-flex items-center gap-1 rounded-md bg-success-muted px-2 py-1 text-xs text-success-foreground"
                        : "inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                    }
                  >
                    {step.complete ? (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {step.complete ? "Complete" : "Incomplete"}
                  </span>
                </td>
                <td className="px-3 py-3 text-muted-foreground">{step.detail}</td>
                <td className="px-3 py-3 text-muted-foreground">
                  {step.complete ? "Review" : "Continue review"}
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
    return <DomainPanel className="text-sm text-muted-foreground">Loading evidence review...</DomainPanel>;
  }

  if (!latestSprint) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card p-5">
        <h3 className="text-sm font-semibold">No evidence review planned yet.</h3>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Plan source review to find sources, identify competitors, gather evidence,
          and draft an evidence memo.
        </p>
      </div>
    );
  }

  const metrics = [
    ["Status", formatLabel(latestSprint.status)],
    ["Sources found", latestHistory?.source_candidate_count ?? 0],
    ["Sources approved", latestHistory?.ingested_source_count ?? 0],
    ["Competitors found", latestHistory?.competitor_candidate_count ?? 0],
    ["Competitors saved", latestHistory?.merged_competitor_count ?? 0],
    ["Decision record", latestHistory?.memory_update_status ? formatLabel(latestHistory.memory_update_status) : "pending"],
  ] as const;

  return (
    <DomainPanel>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-base font-semibold">Latest evidence review</h3>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            {latestSprint.plan.objective}
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {formatDateTime(latestSprint.updated_at)}
        </span>
      </div>
      <dl className="mt-4 grid gap-x-6 gap-y-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-3">
        {metrics.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
            <dd className="mt-1 text-sm font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      {latestHistory?.recommendation_change ? (
        <div className="mt-4 border-t border-border pt-3">
          <h4 className="text-xs font-medium text-muted-foreground">
            Decision change
          </h4>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            {truncate(latestHistory.recommendation_change, 260)}
          </p>
        </div>
      ) : null}
      <details className="mt-4 border-t border-border pt-3">
        <summary className="cursor-pointer text-sm font-medium">Show evidence review steps</summary>
        <ResearchWorkflowTimeline sprint={latestSprint} history={latestHistory} />
      </details>
    </DomainPanel>
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

async function invalidateGovernanceQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["projects", projectId, "approvals"] }),
    queryClient.invalidateQueries({ queryKey: ["projects", projectId, "audit-events"] }),
    queryClient.invalidateQueries({ queryKey: ["projects", projectId, "tool-invocations"] }),
  ]);
}

async function refreshAfterGovernanceAction(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string,
) {
  await Promise.all([
    invalidateGovernanceQueries(queryClient, projectId),
    queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-sprints"] }),
    queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-history"] }),
    queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] }),
  ]);
}

function ResearchSprintCard({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [objective, setObjective] = useState("");
  const [draft, setDraft] = useState<ResearchPlanDraftState | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const sprintsQuery = useQuery({
    queryKey: ["projects", projectId, "research-sprints"],
    queryFn: () => listResearchSprints(projectId),
  });
  const latestSprint = sprintsQuery.data?.[0] ?? null;

  useEffect(() => {
    if (
      !latestSprint ||
      !["planned", "waiting_for_approval"].includes(latestSprint.status)
    ) {
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
      await invalidateGovernanceQueries(queryClient, projectId);
      await sprintsQuery.refetch();
    },
  });
  const saveMutation = useMutation({
    mutationFn: () => {
      if (!latestSprint || !draft) {
        throw new Error("No draft evidence plan to save.");
      }
      return updateResearchPlan(projectId, latestSprint.plan.id, draftToUpdate(draft));
    },
    onSuccess: async (plan) => {
      setDraft(planToDraftState(plan));
      await invalidateGovernanceQueries(queryClient, projectId);
      await sprintsQuery.refetch();
    },
  });
  const approveMutation = useMutation({
    mutationFn: () => {
      if (!latestSprint) {
        throw new Error("No evidence review to approve.");
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
      await invalidateGovernanceQueries(queryClient, projectId);
      await sprintsQuery.refetch();
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => {
      if (!latestSprint) {
        throw new Error("No evidence review to reject.");
      }
      return rejectResearchSprint(projectId, latestSprint.id);
    },
    onSuccess: async (result) => {
      setLastRunId(result.ai_run_id);
      await invalidateGovernanceQueries(queryClient, projectId);
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
  const activePlan =
    latestSprint && ["planned", "waiting_for_approval"].includes(latestSprint.status) && draft
      ? draft
      : null;
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
    [
      "approved",
      "running",
      "needs_review",
      "waiting_for_memory_approval",
      "completed",
    ].includes(latestSprint.status);

  return (
    <DomainPanel id="research-sprint">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Plan evidence review</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Create the source-review plan before finding sources or competitors. Nothing is added
            to the project until you approve the plan.
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
            <span className="text-sm font-medium">Evidence objective</span>
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
                The latest plan is approved. Find sources and competitors before drafting
                the evidence memo.
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
              {startMutation.isPending ? "Planning review..." : "Plan evidence review"}
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

      {latestSprint ? (
        <DurableResearchWorkflowPanel
          projectId={projectId}
          sprint={latestSprint}
          onSprintUpdated={() => sprintsQuery.refetch()}
        />
      ) : null}

      {canReviewDiscovery && latestSprint ? (
        <ResearchDiscoveryPanel
          onRunTrace={setLastRunId}
          onSprintUpdated={() => sprintsQuery.refetch()}
          projectId={projectId}
          sprint={latestSprint}
        />
      ) : null}

      <GovernanceApprovalPanel projectId={projectId} />
      <ResearchHistoryPanel projectId={projectId} />
      <ResearchQualityPanel projectId={projectId} />

      {error ? (
        <div
          className="mt-4 break-words rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground"
          role="alert"
        >
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
          <h3 className="text-sm font-semibold">Recent evidence plans</h3>
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
    </DomainPanel>
  );
}

function DurableResearchWorkflowPanel({
  onSprintUpdated,
  projectId,
  sprint,
}: {
  onSprintUpdated: () => Promise<unknown>;
  projectId: string;
  sprint: ResearchSprint;
}) {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({
    queryKey: ["projects", projectId, "research-sprints", sprint.id, "durable"],
    queryFn: () => getDurableResearchStatus(projectId, sprint.id),
    refetchInterval: (query) => {
      const status = query.state.data?.status ?? sprint.status;
      return ["running", "waiting_for_approval", "waiting_for_memory_approval"].includes(status)
        ? 2500
        : false;
    },
  });
  const execution = statusQuery.data;
  const displayedSprint = execution?.sprint ?? sprint;
  const temporalEnabled = execution?.temporal_enabled ?? false;
  const workflowId = execution?.temporal_workflow_id ?? displayedSprint.temporal_workflow_id;
  const currentStep = execution?.current_step ?? displayedSprint.current_step;
  const failedStep = execution?.failed_step ?? displayedSprint.failed_step;
  const failureMessage = execution?.failure_message ?? displayedSprint.failure_message;
  const actionRequired = execution?.action_required;
  const active = ["running", "waiting_for_approval", "waiting_for_memory_approval"].includes(
    displayedSprint.status,
  );

  async function refresh() {
    await Promise.all([
      statusQuery.refetch(),
      onSprintUpdated(),
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-history"] }),
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] }),
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "artifacts", "research_memo"],
      }),
    ]);
  }

  const startMutation = useMutation({
    mutationFn: () => startDurableResearchWorkflow(projectId, sprint.id),
    onSuccess: refresh,
  });
  const retryMutation = useMutation({
    mutationFn: () => retryDurableResearchWorkflow(projectId, sprint.id),
    onSuccess: refresh,
  });
  const cancelMutation = useMutation({
    mutationFn: () => cancelDurableResearchWorkflow(projectId, sprint.id),
    onSuccess: refresh,
  });

  const busy = startMutation.isPending || retryMutation.isPending || cancelMutation.isPending;
  const error =
    startMutation.error ??
    retryMutation.error ??
    cancelMutation.error ??
    (statusQuery.error as Error | null);

  return (
    <div className="mt-5 rounded-md border border-border bg-surface px-4 py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Durable workflow status</h3>
          </div>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            Temporal coordinates long-running evidence review, retries, approval waits,
            and recovery while memo reasoning stays inside LangGraph.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
          {temporalEnabled ? "Temporal enabled" : "Temporal disabled"}
        </span>
      </div>

      <dl className="mt-4 grid gap-x-6 gap-y-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-xs font-medium text-muted-foreground">Status</dt>
          <dd className="mt-1 text-sm font-semibold">{formatLabel(displayedSprint.status)}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted-foreground">Current step</dt>
          <dd className="mt-1 text-sm font-semibold">
            {currentStep ? formatLabel(currentStep) : "Not started"}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted-foreground">Started</dt>
          <dd className="mt-1 text-sm font-semibold">
            {displayedSprint.started_at ? formatDateTime(displayedSprint.started_at) : "Pending"}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-muted-foreground">Workflow ID</dt>
          <dd className="mt-1 break-all font-mono text-xs">{workflowId ?? "None"}</dd>
        </div>
      </dl>

      {actionRequired ? (
        <div className="mt-4 rounded-md bg-warning-muted px-3 py-2 text-sm text-warning-foreground">
          Action required: {actionRequired}
        </div>
      ) : null}
      {displayedSprint.status === "failed" ? (
        <div className="mt-4 rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground">
          Failed step: {failedStep ? formatLabel(failedStep) : "Unknown"}
          {failureMessage ? <span className="block break-words">{failureMessage}</span> : null}
        </div>
      ) : null}
      {error ? (
        <div
          className="mt-4 break-words rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground"
          role="alert"
        >
          {error.message}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {!workflowId && temporalEnabled ? (
          <Button disabled={busy} onClick={() => startMutation.mutate()} size="sm" type="button">
            <Route className="h-4 w-4" aria-hidden="true" />
            {startMutation.isPending ? "Starting..." : "Start durable workflow"}
          </Button>
        ) : null}
        {displayedSprint.status === "failed" ? (
          <Button disabled={busy} onClick={() => retryMutation.mutate()} size="sm" type="button">
            Retry workflow
          </Button>
        ) : null}
        {workflowId && active ? (
          <Button
            disabled={busy}
            onClick={() => cancelMutation.mutate()}
            size="sm"
            type="button"
            variant="secondary"
          >
            Cancel workflow
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function GovernanceApprovalPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const approvalsQuery = useQuery({
    queryKey: ["projects", projectId, "approvals", "pending"],
    queryFn: () => listApprovalRequests(projectId, "pending"),
  });
  const auditEventsQuery = useQuery({
    queryKey: ["projects", projectId, "audit-events"],
    queryFn: () => listAuditEvents(projectId),
  });
  const approveMutation = useMutation({
    mutationFn: (approvalId: string) => approveApprovalRequest(projectId, approvalId),
    onSuccess: () => refreshAfterGovernanceAction(queryClient, projectId),
  });
  const rejectMutation = useMutation({
    mutationFn: (approvalId: string) => rejectApprovalRequest(projectId, approvalId),
    onSuccess: () => refreshAfterGovernanceAction(queryClient, projectId),
  });

  const approvals = approvalsQuery.data ?? [];
  const events = auditEventsQuery.data ?? [];
  const busy = approveMutation.isPending || rejectMutation.isPending;
  const error =
    approveMutation.error ??
    rejectMutation.error ??
    (approvalsQuery.error as Error | null) ??
    (auditEventsQuery.error as Error | null);

  return (
    <details className="mt-6 border-t border-border pt-5">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Governance approvals</h3>
            </div>
            <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
              Review human gates for research plans, project memory updates, tool proposals,
              validation plans, and decision records.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-md bg-muted px-2 py-1">
              {approvals.length} pending
            </span>
            <span className="rounded-md bg-muted px-2 py-1">
              {events.length} audit event{events.length === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </summary>

      {error ? (
        <p className="mt-3 text-sm text-danger-foreground">{error.message}</p>
      ) : approvalsQuery.isLoading ? (
        <p className="mt-3 text-sm text-muted-foreground">Loading approvals...</p>
      ) : approvals.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No pending approvals. Recent audit events remain available below.
        </p>
      ) : (
        <ol className="mt-4 space-y-3" aria-label="Pending governance approvals">
          {approvals.map((approval) => (
            <li className="rounded-md border border-border px-3 py-3" key={approval.id}>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <EvidenceReviewPill>{formatLabel(approval.request_type)}</EvidenceReviewPill>
                    <span className={toolRiskClass(approval.risk_level)}>
                      {formatLabel(approval.risk_level)} risk
                    </span>
                    <EvidenceReviewPill>
                      Requested by {formatLabel(approval.requested_by)}
                    </EvidenceReviewPill>
                  </div>
                  <h4 className="mt-2 text-sm font-semibold">
                    {clarifyWorkspaceTerm(approval.summary)}
                  </h4>
                  <p className="mt-2 max-w-[72ch] text-xs leading-5 text-muted-foreground">
                    {approvalWhyItMatters(approval)}
                  </p>
                  {approval.proposed_change ? (
                    <pre className="mt-3 max-h-48 overflow-auto rounded-md bg-muted px-3 py-2 text-xs leading-5 text-muted-foreground">
                      {formatJsonPreview(approval.proposed_change)}
                    </pre>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button
                    disabled={busy}
                    onClick={() => approveMutation.mutate(approval.id)}
                    size="sm"
                    type="button"
                  >
                    <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                    Approve
                  </Button>
                  <Button
                    disabled={busy}
                    onClick={() => rejectMutation.mutate(approval.id)}
                    size="sm"
                    type="button"
                    variant="secondary"
                  >
                    <CircleAlert className="h-4 w-4" aria-hidden="true" />
                    Reject
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}

      <div className="mt-5 border-t border-border pt-4">
        <h4 className="text-sm font-semibold">Recent audit events</h4>
        {auditEventsQuery.isLoading ? (
          <p className="mt-3 text-sm text-muted-foreground">Loading audit events...</p>
        ) : events.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            No governance events have been recorded for this project yet.
          </p>
        ) : (
          <ol className="mt-3 space-y-2" aria-label="Recent audit events">
            {events.slice(0, 8).map((event) => (
              <li className="rounded-md bg-muted px-3 py-2" key={event.id}>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{formatLabel(event.event_type)}</span>
                      {event.risk_level ? <span>{formatLabel(event.risk_level)} risk</span> : null}
                      <span>{formatLabel(event.actor_type)}</span>
                    </div>
                    {event.summary ? (
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">
                        {clarifyWorkspaceTerm(event.summary)}
                      </p>
                    ) : null}
                  </div>
                  <time className="shrink-0 text-xs text-muted-foreground">
                    {formatDateTime(event.created_at)}
                  </time>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
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
            <h3 className="text-sm font-semibold">Evidence history</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Review what changed across previous evidence reviews.
            </p>
          </div>
          {history ? (
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-md bg-muted px-2 py-1">
                {history.sprint_count} review{history.sprint_count === 1 ? "" : "s"}
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
        <p className="mt-3 text-sm text-danger-foreground">{(historyQuery.error as Error).message}</p>
      ) : !history || history.sprints.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No evidence reviews yet. Run an evidence review to create a history trail.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          {history.sprints.slice(0, 3).map((sprintHistory) => (
            <div className="border-t border-border pt-4 first:border-t-0 first:pt-0" key={sprintHistory.sprint.id}>
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
                  <span className="rounded-md bg-muted px-2 py-1">
                    {sprintHistory.ingested_source_count}/{sprintHistory.source_candidate_count} sources
                  </span>
                  <span className="rounded-md bg-muted px-2 py-1">
                    {sprintHistory.merged_competitor_count}/
                    {sprintHistory.competitor_candidate_count} competitors
                  </span>
                  {sprintHistory.memory_update_status ? (
                    <span className="rounded-md bg-muted px-2 py-1">
                      {formatLabel(sprintHistory.memory_update_status)}
                    </span>
                  ) : null}
                  {sprintHistory.sprint.langsmith_trace_url ? (
                    <a
                      className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-primary hover:underline"
                      href={sprintHistory.sprint.langsmith_trace_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      View trace
                    </a>
                  ) : null}
                </div>
              </div>
              {sprintHistory.recommendation_change ? (
                <p className="mt-3 max-w-[72ch] text-sm leading-6 text-muted-foreground">
                  Recommendation: {truncate(sprintHistory.recommendation_change, 220)}
                </p>
              ) : null}
              <div className="mt-4 divide-y divide-border">
                {sprintHistory.events.slice(-5).map((event) => (
                  <div className="py-2" key={event.id}>
                    <p className="text-sm font-medium">{clarifyWorkspaceTerm(event.title)}</p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {clarifyWorkspaceTerm(event.summary)}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      Why it matters: {clarifyWorkspaceTerm(event.why_it_matters)}
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
  const traceMetric = evaluation?.metrics.find((metric) => metric.key === "langsmith_trace_ids");
  const spanMetric = evaluation?.metrics.find((metric) => metric.key === "langsmith_span_coverage");

  return (
    <details className="mt-6 border-t border-border pt-5">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Evidence checks</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              View source, citation, traceability, cost, and latency checks.
            </p>
          </div>
          {evaluation ? (
            <span
              className={
                evaluation.passed
                  ? "w-fit rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground"
                  : "w-fit rounded-md bg-warning-muted px-2 py-1 text-xs font-medium text-warning-foreground"
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
        <p className="mt-3 text-sm text-danger-foreground">{(evalQuery.error as Error).message}</p>
      ) : evaluation ? (
        <>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {evaluation.metrics.map((metric) => (
              <div className="rounded-md bg-muted px-3 py-2" key={metric.key}>
                <div className="flex items-center gap-2">
                  {metric.passed ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-success-foreground" />
                  ) : (
                    <CircleAlert className="h-4 w-4 shrink-0 text-warning-foreground" />
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
            {traceMetric && spanMetric ? (
              <span>
                {" "}
                Traceability: {String(traceMetric.observed)}, {String(spanMetric.observed)} traced steps.
              </span>
            ) : null}
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
          label="Expected outputs"
          onChange={(value) => updateField("expected_outputs", value)}
          value={draft.expected_outputs}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={onApprove} type="button">
          Approve evidence plan
        </Button>
        <Button disabled={busy} onClick={onSave} type="button" variant="secondary">
          Save draft
        </Button>
        <Button disabled={busy} onClick={onReject} type="button" variant="secondary">
          Reject plan
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
  const toolInvocationsQuery = useQuery({
    queryKey: ["projects", projectId, "tool-invocations", sprint.id],
    queryFn: () => listToolInvocations(projectId, sprint.id),
  });

  const discoverSourcesMutation = useMutation({
    mutationFn: () => discoverSources(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await invalidateGovernanceQueries(queryClient, projectId);
      await sourcesQuery.refetch();
      await toolInvocationsQuery.refetch();
    },
  });
  const discoverCompetitorsMutation = useMutation({
    mutationFn: () => discoverCompetitorCandidates(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await invalidateGovernanceQueries(queryClient, projectId);
      await candidatesQuery.refetch();
      await toolInvocationsQuery.refetch();
    },
  });
  const agenticResearchMutation = useMutation({
    mutationFn: () => runAgenticResearch(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await invalidateGovernanceQueries(queryClient, projectId);
      await researchMemosQuery.refetch();
      await toolInvocationsQuery.refetch();
      await onSprintUpdated();
    },
  });
  const approveMemoMutation = useMutation({
    mutationFn: () => approveAgenticResearchMemo(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await invalidateGovernanceQueries(queryClient, projectId);
      await researchMemosQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assumptions"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "risks"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "experiments"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-history"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "v1-research"] });
      await toolInvocationsQuery.refetch();
      await onSprintUpdated();
    },
  });
  const rejectMemoMutation = useMutation({
    mutationFn: () => rejectAgenticResearchMemo(projectId, sprint.id),
    onSuccess: async (result) => {
      onRunTrace(result.ai_run_id);
      await invalidateGovernanceQueries(queryClient, projectId);
      await researchMemosQuery.refetch();
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "research-history"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "v1-research"] });
      await toolInvocationsQuery.refetch();
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
  const [activeReviewId, setActiveReviewId] = useState<string | null>(null);

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
  const sourceReviewItems = sources.filter(
    (source) => source.status === "candidate" || source.status === "failed",
  );
  const competitorReviewItems = candidates.filter(
    (candidate) => candidate.status === "candidate",
  );
  const memoNeedsReview =
    Boolean(memoArtifact && memoVersion) &&
    memoryUpdateStatus !== "approved" &&
    memoryUpdateStatus !== "rejected";
  const reviewQueue: EvidenceReviewQueueItem[] = [
    ...sourceReviewItems.map((source) => ({
      id: `source:${source.id}`,
      kind: "source" as const,
      source,
    })),
    ...competitorReviewItems.map((candidate) => ({
      candidate,
      id: `competitor:${candidate.id}`,
      kind: "competitor" as const,
    })),
    ...(memoNeedsReview && memoArtifact && memoVersion
      ? [
          {
            artifact: memoArtifact,
            id: `memo:${memoArtifact.id}:${memoVersion.id}`,
            kind: "memo" as const,
            version: memoVersion,
          },
        ]
      : []),
  ];
  const reviewQueueKey = reviewQueue.map((item) => item.id).join("|");
  useEffect(() => {
    if (reviewQueue.length === 0) {
      if (activeReviewId !== null) {
        setActiveReviewId(null);
      }
      return;
    }
    if (!activeReviewId || !reviewQueue.some((item) => item.id === activeReviewId)) {
      setActiveReviewId(reviewQueue[0].id);
    }
  }, [activeReviewId, reviewQueueKey, reviewQueue.length]);
  const activeReviewItem =
    reviewQueue.find((item) => item.id === activeReviewId) ?? reviewQueue[0] ?? null;
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
    (candidatesQuery.error as Error | null) ??
    (toolInvocationsQuery.error as Error | null);
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
          <h3 className="text-sm font-semibold">Evidence review queue</h3>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            Decide one evidence item at a time. Add useful sources and competitors, then review
            the cited memo before it changes the project.
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
            {discoverSourcesMutation.isPending ? "Finding sources..." : "Find sources"}
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
              ? "Finding competitors..."
              : "Find competitors"}
          </Button>
          <Button
            className="w-full whitespace-nowrap"
            disabled={busy || sprint.status === "completed"}
            onClick={() => agenticResearchMutation.mutate()}
            type="button"
          >
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            {agenticResearchMutation.isPending ? "Drafting memo..." : "Draft evidence memo"}
          </Button>
        </div>
      </div>

      {error ? (
        <div
          className="mt-4 break-words rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground"
          role="alert"
        >
          {error.message}
        </div>
      ) : null}

      <EvidenceReviewQueue
        activeItem={activeReviewItem}
        approveMemoPending={approveMemoMutation.isPending}
        busy={busy}
        candidates={candidates}
        citations={citations}
        discoverCompetitorsPending={discoverCompetitorsMutation.isPending}
        discoverSourcesPending={discoverSourcesMutation.isPending}
        draftMemoPending={agenticResearchMutation.isPending}
        evidenceGapCount={evidenceGapCount}
        memoryUpdateStatus={memoryUpdateStatus}
        memoryUpdateSummary={memoryUpdateSummary}
        onApproveCandidate={(candidateId) => approveCandidateMutation.mutate(candidateId)}
        onApproveMemo={() => approveMemoMutation.mutate()}
        onApproveSource={(sourceId) => approveSourceMutation.mutate(sourceId)}
        onDraftMemo={() => agenticResearchMutation.mutate()}
        onFindCompetitors={() => discoverCompetitorsMutation.mutate()}
        onFindSources={() => discoverSourcesMutation.mutate()}
        onRejectCandidate={(candidateId) => rejectCandidateMutation.mutate(candidateId)}
        onRejectMemo={() => rejectMemoMutation.mutate()}
        onRejectSource={(sourceId) => rejectSourceMutation.mutate(sourceId)}
        onSelectItem={setActiveReviewId}
        queue={reviewQueue}
        rejectMemoPending={rejectMemoMutation.isPending}
        retrievalToolCallCount={retrievalToolCallCount}
        sources={sources}
        unsupportedClaims={unsupportedClaims}
      />

      <ToolActivityPanel
        error={toolInvocationsQuery.error as Error | null}
        invocations={toolInvocationsQuery.data ?? []}
        isLoading={toolInvocationsQuery.isLoading}
      />

      <details className="mt-5 border-t border-border pt-4">
        <summary className="cursor-pointer text-sm font-medium">
          Open full evidence lists
        </summary>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Use the full lists when you need provenance, bulk scanning, or competitor edits.
        </p>
        <div className="mt-4 grid gap-5 xl:grid-cols-2">
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
      </details>
    </div>
  );
}

function ToolActivityPanel({
  error,
  invocations,
  isLoading,
}: {
  error: Error | null;
  invocations: ToolInvocation[];
  isLoading: boolean;
}) {
  const recent = invocations.slice(0, 12);
  const pendingProposalCount = invocations.filter(
    (invocation) => invocation.access_mode === "proposal" && invocation.status === "requested",
  ).length;

  return (
    <details className="mt-5 border-t border-border pt-4">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h4 className="text-sm font-semibold">Tool activity</h4>
            <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
              Inspect the bounded tools the agent used to read project context, search
              evidence, and propose updates.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-md bg-muted px-2 py-1">
              {invocations.length} call{invocations.length === 1 ? "" : "s"}
            </span>
            {pendingProposalCount > 0 ? (
              <span className="rounded-md bg-warning-muted px-2 py-1 text-warning-foreground">
                {pendingProposalCount} pending proposal
                {pendingProposalCount === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>
        </div>
      </summary>

      {isLoading ? (
        <p className="mt-3 text-sm text-muted-foreground">Loading tool activity...</p>
      ) : error ? (
        <p className="mt-3 text-sm text-danger-foreground">{error.message}</p>
      ) : recent.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No tool activity has been recorded for this evidence review yet.
        </p>
      ) : (
        <ol className="mt-4 space-y-2" aria-label="Tool activity">
          {recent.map((invocation) => (
            <li className="rounded-md border border-border px-3 py-3" key={invocation.id}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <EvidenceReviewPill>{formatLabel(invocation.access_mode)}</EvidenceReviewPill>
                    <span className={toolRiskClass(invocation.risk_level)}>
                      {formatLabel(invocation.risk_level)} risk
                    </span>
                    <EvidenceReviewPill>{formatLabel(invocation.status)}</EvidenceReviewPill>
                  </div>
                  <h5 className="mt-2 text-sm font-semibold">
                    {toolActivityTitle(invocation)}
                  </h5>
                  <p className="mt-1 max-w-[72ch] text-xs leading-5 text-muted-foreground">
                    Tool: <span className="font-mono">{invocation.tool_name}</span>
                  </p>
                  {invocation.output_summary ? (
                    <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
                      {clarifyWorkspaceTerm(invocation.output_summary)}
                    </p>
                  ) : null}
                </div>
                <time className="shrink-0 text-xs text-muted-foreground">
                  {formatDateTime(invocation.executed_at ?? invocation.created_at)}
                </time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

function EvidenceReviewQueue({
  activeItem,
  approveMemoPending,
  busy,
  candidates,
  citations,
  discoverCompetitorsPending,
  discoverSourcesPending,
  draftMemoPending,
  evidenceGapCount,
  memoryUpdateStatus,
  memoryUpdateSummary,
  onApproveCandidate,
  onApproveMemo,
  onApproveSource,
  onDraftMemo,
  onFindCompetitors,
  onFindSources,
  onRejectCandidate,
  onRejectMemo,
  onRejectSource,
  onSelectItem,
  queue,
  rejectMemoPending,
  retrievalToolCallCount,
  sources,
  unsupportedClaims,
}: {
  activeItem: EvidenceReviewQueueItem | null;
  approveMemoPending: boolean;
  busy: boolean;
  candidates: CompetitorCandidate[];
  citations: Citation[];
  discoverCompetitorsPending: boolean;
  discoverSourcesPending: boolean;
  draftMemoPending: boolean;
  evidenceGapCount: number;
  memoryUpdateStatus: string | null;
  memoryUpdateSummary: MemoryUpdateSummary | null;
  onApproveCandidate: (candidateId: string) => void;
  onApproveMemo: () => void;
  onApproveSource: (sourceId: string) => void;
  onDraftMemo: () => void;
  onFindCompetitors: () => void;
  onFindSources: () => void;
  onRejectCandidate: (candidateId: string) => void;
  onRejectMemo: () => void;
  onRejectSource: (sourceId: string) => void;
  onSelectItem: (itemId: string) => void;
  queue: EvidenceReviewQueueItem[];
  rejectMemoPending: boolean;
  retrievalToolCallCount: number;
  sources: DiscoveredSource[];
  unsupportedClaims: string[];
}) {
  const addedSourceCount = sources.filter(
    (source) => source.status === "approved" || source.status === "ingested",
  ).length;
  const addedCompetitorCount = candidates.filter(
    (candidate) => candidate.status === "approved" || candidate.status === "merged",
  ).length;
  const rejectedCount =
    sources.filter((source) => source.status === "rejected").length +
    candidates.filter((candidate) => candidate.status === "rejected").length;

  return (
    <section className="mt-5 border-t border-border pt-4" aria-label="Evidence review queue">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold">Review next item</h4>
          <p className="mt-1 max-w-[64ch] text-sm leading-6 text-muted-foreground">
            Work down the queue, one decision at a time. Full candidate lists stay below for audit
            and edits.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs text-muted-foreground sm:w-[20rem]">
          <div className="rounded-md bg-muted px-2 py-2">
            <div className="text-sm font-semibold text-foreground">{queue.length}</div>
            <div>to review</div>
          </div>
          <div className="rounded-md bg-muted px-2 py-2">
            <div className="text-sm font-semibold text-foreground">
              {addedSourceCount + addedCompetitorCount}
            </div>
            <div>added</div>
          </div>
          <div className="rounded-md bg-muted px-2 py-2">
            <div className="text-sm font-semibold text-foreground">{rejectedCount}</div>
            <div>rejected</div>
          </div>
        </div>
      </div>

      {queue.length === 0 ? (
        <EvidenceReviewEmptyState
          busy={busy}
          candidates={candidates}
          citations={citations}
          discoverCompetitorsPending={discoverCompetitorsPending}
          discoverSourcesPending={discoverSourcesPending}
          draftMemoPending={draftMemoPending}
          memoryUpdateStatus={memoryUpdateStatus}
          onDraftMemo={onDraftMemo}
          onFindCompetitors={onFindCompetitors}
          onFindSources={onFindSources}
          sources={sources}
        />
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <ol className="space-y-2" aria-label="Evidence items to review">
            {queue.map((item, index) => (
              <li key={item.id}>
                <EvidenceReviewQueueButton
                  active={item.id === activeItem?.id}
                  item={item}
                  number={index + 1}
                  onSelect={onSelectItem}
                />
              </li>
            ))}
          </ol>
          <EvidenceReviewActiveItem
            activeItem={activeItem}
            approveMemoPending={approveMemoPending}
            busy={busy}
            citations={citations}
            evidenceGapCount={evidenceGapCount}
            memoryUpdateStatus={memoryUpdateStatus}
            memoryUpdateSummary={memoryUpdateSummary}
            onApproveCandidate={onApproveCandidate}
            onApproveMemo={onApproveMemo}
            onApproveSource={onApproveSource}
            onRejectCandidate={onRejectCandidate}
            onRejectMemo={onRejectMemo}
            onRejectSource={onRejectSource}
            rejectMemoPending={rejectMemoPending}
            retrievalToolCallCount={retrievalToolCallCount}
            unsupportedClaims={unsupportedClaims}
          />
        </div>
      )}
    </section>
  );
}

function EvidenceReviewQueueButton({
  active,
  item,
  number,
  onSelect,
}: {
  active: boolean;
  item: EvidenceReviewQueueItem;
  number: number;
  onSelect: (itemId: string) => void;
}) {
  return (
    <button
      aria-current={active ? "step" : undefined}
      className={
        active
          ? "w-full rounded-md border border-primary bg-surface px-3 py-3 text-left"
          : "w-full rounded-md border border-border px-3 py-3 text-left hover:border-primary"
      }
      onClick={() => onSelect(item.id)}
      type="button"
    >
      <div className="flex items-start gap-3">
        <span
          className={
            active
              ? "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
              : "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground"
          }
        >
          {number}
        </span>
        <span className="min-w-0">
          <span className="block text-xs font-medium text-muted-foreground">
            {evidenceReviewItemKind(item)}
          </span>
          <span className="mt-1 block truncate text-sm font-semibold">
            {evidenceReviewItemTitle(item)}
          </span>
          <span className="mt-1 block truncate text-xs text-muted-foreground">
            {evidenceReviewItemSignal(item)}
          </span>
        </span>
      </div>
    </button>
  );
}

function EvidenceReviewActiveItem({
  activeItem,
  approveMemoPending,
  busy,
  citations,
  evidenceGapCount,
  memoryUpdateStatus,
  memoryUpdateSummary,
  onApproveCandidate,
  onApproveMemo,
  onApproveSource,
  onRejectCandidate,
  onRejectMemo,
  onRejectSource,
  rejectMemoPending,
  retrievalToolCallCount,
  unsupportedClaims,
}: {
  activeItem: EvidenceReviewQueueItem | null;
  approveMemoPending: boolean;
  busy: boolean;
  citations: Citation[];
  evidenceGapCount: number;
  memoryUpdateStatus: string | null;
  memoryUpdateSummary: MemoryUpdateSummary | null;
  onApproveCandidate: (candidateId: string) => void;
  onApproveMemo: () => void;
  onApproveSource: (sourceId: string) => void;
  onRejectCandidate: (candidateId: string) => void;
  onRejectMemo: () => void;
  onRejectSource: (sourceId: string) => void;
  rejectMemoPending: boolean;
  retrievalToolCallCount: number;
  unsupportedClaims: string[];
}) {
  if (!activeItem) {
    return null;
  }

  if (activeItem.kind === "source") {
    const source = activeItem.source;
    return (
      <article className="min-w-0 border-t border-border pt-4 lg:border-t-0 lg:pt-0">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2 text-xs">
              <EvidenceReviewPill>{formatLabel(source.source_type)}</EvidenceReviewPill>
              <EvidenceReviewPill>{formatLabel(source.status)}</EvidenceReviewPill>
              <EvidenceReviewPill>score {formatScore(source.relevance_score)}</EvidenceReviewPill>
            </div>
            <h5 className="mt-3 text-base font-semibold">
              {clarifyWorkspaceTerm(source.title ?? "Untitled source")}
            </h5>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() => onApproveSource(source.id)}
              size="sm"
              type="button"
            >
              Add source
            </Button>
            <Button
              disabled={busy}
              onClick={() => onRejectSource(source.id)}
              size="sm"
              type="button"
              variant="secondary"
            >
              Reject source
            </Button>
          </div>
        </div>
        <a
          className="mt-3 block break-all text-xs text-primary hover:underline"
          href={source.url}
          rel="noreferrer"
          target="_blank"
        >
          {source.url}
        </a>
        {source.snippet ? (
          <p className="mt-4 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            {clarifyWorkspaceTerm(source.snippet)}
          </p>
        ) : null}
        <p className="mt-3 max-w-[72ch] text-sm leading-6 text-muted-foreground">
          <span className="font-medium text-foreground">Why review it:</span>{" "}
          {clarifyWorkspaceTerm(source.reason_selected)}
        </p>
        {source.associated_research_question ? (
          <p className="mt-3 max-w-[72ch] text-xs leading-5 text-muted-foreground">
            Research question: {clarifyWorkspaceTerm(source.associated_research_question)}
          </p>
        ) : null}
        {source.ingestion_error ? (
          <p className="mt-3 text-xs text-danger-foreground">{source.ingestion_error}</p>
        ) : null}
      </article>
    );
  }

  if (activeItem.kind === "competitor") {
    const candidate = activeItem.candidate;
    return (
      <article className="min-w-0 border-t border-border pt-4 lg:border-t-0 lg:pt-0">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2 text-xs">
              <EvidenceReviewPill>{formatLabel(candidate.category)}</EvidenceReviewPill>
              <EvidenceReviewPill>threat {candidate.threat_level}</EvidenceReviewPill>
              <EvidenceReviewPill>score {formatScore(candidate.relevance_score)}</EvidenceReviewPill>
            </div>
            <h5 className="mt-3 text-base font-semibold">
              {clarifyWorkspaceTerm(candidate.name)}
            </h5>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button
              disabled={busy}
              onClick={() => onApproveCandidate(candidate.id)}
              size="sm"
              type="button"
            >
              Add competitor
            </Button>
            <Button
              disabled={busy}
              onClick={() => onRejectCandidate(candidate.id)}
              size="sm"
              type="button"
              variant="secondary"
            >
              Reject competitor
            </Button>
          </div>
        </div>
        {candidate.url ? (
          <a
            className="mt-3 block break-all text-xs text-primary hover:underline"
            href={candidate.url}
            rel="noreferrer"
            target="_blank"
          >
            {candidate.url}
          </a>
        ) : null}
        <p className="mt-4 max-w-[72ch] text-sm leading-6 text-muted-foreground">
          {clarifyWorkspaceTerm(candidate.positioning ?? "No positioning note yet.")}
        </p>
        <p className="mt-3 max-w-[72ch] text-sm leading-6 text-muted-foreground">
          <span className="font-medium text-foreground">Why it matters:</span>{" "}
          {clarifyWorkspaceTerm(candidate.why_it_matters)}
        </p>
        {candidate.core_features.length > 0 ? (
          <p className="mt-3 max-w-[72ch] text-xs leading-5 text-muted-foreground">
            Features: {candidate.core_features.join(", ")}
          </p>
        ) : null}
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Need to rename or recategorize it? Open the full evidence lists below.
        </p>
      </article>
    );
  }

  return (
    <article className="min-w-0 border-t border-border pt-4 lg:border-t-0 lg:pt-0">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap gap-2 text-xs">
            <EvidenceReviewPill>
              {clarifyWorkspaceTerm(formatLabel(activeItem.artifact.artifact_type))}
            </EvidenceReviewPill>
            <EvidenceReviewPill>Version {activeItem.version.version}</EvidenceReviewPill>
          </div>
          <h5 className="mt-3 text-base font-semibold">Review project updates</h5>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
            The memo used {retrievalToolCallCount} retrieval passes and found {evidenceGapCount}{" "}
            evidence gap{evidenceGapCount === 1 ? "" : "s"}. Approve only if the summary should
            update assumptions, risks, and validation actions.
          </p>
        </div>
        {memoryUpdateStatus ? (
          <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            {formatLabel(memoryUpdateStatus)}
          </span>
        ) : null}
      </div>
      {unsupportedClaims.length > 0 ? (
        <p className="mt-3 max-w-[72ch] text-xs leading-5 text-muted-foreground">
          First open question: {clarifyWorkspaceTerm(truncate(unsupportedClaims[0], 180))}
        </p>
      ) : null}
      <ResearchMemoReview
        artifact={activeItem.artifact}
        approvalPending={approveMemoPending}
        citations={citations}
        memoryUpdateStatus={memoryUpdateStatus}
        memoryUpdateSummary={memoryUpdateSummary}
        onApprove={onApproveMemo}
        onReject={onRejectMemo}
        rejectionPending={rejectMemoPending}
        unsupportedClaims={unsupportedClaims}
        version={activeItem.version}
      />
    </article>
  );
}

function EvidenceReviewEmptyState({
  busy,
  candidates,
  citations,
  discoverCompetitorsPending,
  discoverSourcesPending,
  draftMemoPending,
  memoryUpdateStatus,
  onDraftMemo,
  onFindCompetitors,
  onFindSources,
  sources,
}: {
  busy: boolean;
  candidates: CompetitorCandidate[];
  citations: Citation[];
  discoverCompetitorsPending: boolean;
  discoverSourcesPending: boolean;
  draftMemoPending: boolean;
  memoryUpdateStatus: string | null;
  onDraftMemo: () => void;
  onFindCompetitors: () => void;
  onFindSources: () => void;
  sources: DiscoveredSource[];
}) {
  const hasSources = sources.length > 0;
  const hasCompetitors = candidates.length > 0;
  const memoReviewed = memoryUpdateStatus === "approved" || memoryUpdateStatus === "rejected";
  const nextAction =
    !hasSources
      ? "sources"
      : !hasCompetitors
        ? "competitors"
        : citations.length === 0 && !memoReviewed
          ? "memo"
          : null;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h5 className="text-sm font-semibold">Review queue clear</h5>
          <p className="mt-2 max-w-[64ch] text-sm leading-6 text-muted-foreground">
            There are no pending source, competitor, or memo decisions. Generate the next evidence
            batch when you need more proof.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {nextAction === "sources" ? (
            <Button
              disabled={busy}
              onClick={onFindSources}
              size="sm"
              type="button"
              variant="secondary"
            >
              <Globe2 className="h-4 w-4" aria-hidden="true" />
              {discoverSourcesPending ? "Finding sources..." : "Find sources"}
            </Button>
          ) : null}
          {nextAction === "competitors" ? (
            <Button
              disabled={busy}
              onClick={onFindCompetitors}
              size="sm"
              type="button"
              variant="secondary"
            >
              <Building2 className="h-4 w-4" aria-hidden="true" />
              {discoverCompetitorsPending ? "Finding competitors..." : "Find competitors"}
            </Button>
          ) : null}
          {nextAction === "memo" ? (
            <Button disabled={busy} onClick={onDraftMemo} size="sm" type="button">
              <FileSearch className="h-4 w-4" aria-hidden="true" />
              {draftMemoPending ? "Drafting memo..." : "Draft evidence memo"}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function EvidenceReviewPill({ children }: { children: ReactNode }) {
  return (
    <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
      {children}
    </span>
  );
}

function toolRiskClass(riskLevel: ToolInvocation["risk_level"]) {
  if (riskLevel === "high") {
    return "w-fit rounded-md bg-danger-muted px-2 py-1 text-xs text-danger-foreground";
  }
  if (riskLevel === "medium") {
    return "w-fit rounded-md bg-warning-muted px-2 py-1 text-xs text-warning-foreground";
  }
  return "w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground";
}

function toolActivityTitle(invocation: ToolInvocation) {
  const query = typeof invocation.input_json.query === "string" ? invocation.input_json.query : "";
  const summary = invocation.output_summary;
  if (invocation.tool_name === "search_project_evidence" && query) {
    return `Searched project evidence for "${truncate(query, 80)}"`;
  }
  if (invocation.access_mode === "proposal") {
    return summary ? truncate(summary, 110) : "Project update proposed";
  }
  if (summary) {
    return truncate(summary, 110);
  }
  return formatLabel(invocation.tool_name);
}

function approvalWhyItMatters(approval: ApprovalRequest) {
  const entityLabel = approval.entity_type ? formatLabel(approval.entity_type) : "project state";
  if (approval.request_type === "research_plan") {
    return `Approving this gate controls whether the evidence review plan can advance. Entity: ${entityLabel}.`;
  }
  if (approval.request_type === "memory_update") {
    return `Approving this gate controls changes to project memory, assumptions, risks, and recommendations. Entity: ${entityLabel}.`;
  }
  if (approval.request_type === "tool_invocation") {
    return `Approving this gate controls whether a proposed tool action is accepted. Entity: ${entityLabel}.`;
  }
  if (approval.request_type === "validation_plan") {
    return `Approving this gate controls validation experiments and related project evidence. Entity: ${entityLabel}.`;
  }
  return `Approving this gate controls a recorded project decision. Entity: ${entityLabel}.`;
}

function formatJsonPreview(value: Record<string, unknown>) {
  return truncate(JSON.stringify(value, null, 2), 1600);
}

function evidenceReviewItemKind(item: EvidenceReviewQueueItem) {
  if (item.kind === "source") {
    return "Source candidate";
  }
  if (item.kind === "competitor") {
    return "Competitor candidate";
  }
  return "Evidence memo";
}

function evidenceReviewItemTitle(item: EvidenceReviewQueueItem) {
  if (item.kind === "source") {
    return clarifyWorkspaceTerm(item.source.title ?? item.source.url);
  }
  if (item.kind === "competitor") {
    return clarifyWorkspaceTerm(item.candidate.name);
  }
  return clarifyWorkspaceTerm(item.artifact.title);
}

function evidenceReviewItemSignal(item: EvidenceReviewQueueItem) {
  if (item.kind === "source") {
    return `${formatLabel(item.source.source_type)} · score ${formatScore(item.source.relevance_score)}`;
  }
  if (item.kind === "competitor") {
    return `${formatLabel(item.candidate.category)} · threat ${item.candidate.threat_level}`;
  }
  return `Version ${item.version.version} · approve or reject updates`;
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
            <h3 className="text-sm font-semibold">Approve memo updates</h3>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-md bg-card px-2 py-1">
              {clarifyWorkspaceTerm(artifact.title)}
            </span>
            <span className="rounded-md bg-muted px-2 py-1">Version {version.version}</span>
            <span className="rounded-md bg-muted px-2 py-1">
              {formatDateTime(version.created_at)}
            </span>
            {version.langsmith_trace_url ? (
              <a
                className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-1 text-primary hover:underline"
                href={version.langsmith_trace_url}
                rel="noreferrer"
                target="_blank"
              >
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
                View trace
              </a>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={
              approved
                ? "w-fit rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground"
                : rejected
                  ? "w-fit rounded-md bg-danger-muted px-2 py-1 text-xs font-medium text-danger-foreground"
                : "w-fit rounded-md bg-warning-muted px-2 py-1 text-xs font-medium text-warning-foreground"
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
            {approved ? "Approved" : approvalPending ? "Approving updates..." : "Approve decision updates"}
          </Button>
          <Button
            disabled={reviewed || approvalPending || rejectionPending}
            onClick={onReject}
            size="sm"
            type="button"
            variant="secondary"
          >
            {rejected ? "Rejected" : rejectionPending ? "Rejecting updates..." : "Reject decision updates"}
          </Button>
        </div>
      </div>

      {memoryUpdateSummary ? (
        <div className="mt-4 rounded-md bg-card px-4 py-3 text-sm leading-6 text-muted-foreground">
          <span className="font-medium text-foreground">Decision updates:</span>{" "}
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
        <div className="rounded-md bg-card px-3 py-2">
          <div className="text-xs text-muted-foreground">Supported findings</div>
          <div className="mt-1 text-sm font-semibold">{supportedClaims.length}</div>
        </div>
        <div className="rounded-md bg-card px-3 py-2">
          <div className="text-xs text-muted-foreground">Sources</div>
          <div className="mt-1 text-sm font-semibold">{citations.length}</div>
        </div>
        <div className="rounded-md bg-card px-3 py-2">
          <div className="text-xs text-muted-foreground">Open questions</div>
          <div className="mt-1 text-sm font-semibold">{displayUnsupported.length}</div>
        </div>
      </div>

      <SourceGroundedMemo
        citations={citations}
        markdown={version.markdown_content}
        unsupportedClaims={displayUnsupported}
      />

      <details className="mt-3 rounded-md bg-card p-3">
        <summary className="cursor-pointer text-sm font-medium">
          Show evidence and open questions
        </summary>
        <div className="mt-3 grid gap-5 border-t border-border pt-3 lg:grid-cols-3">
          <section>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h4 className="text-sm font-semibold">Supported Findings</h4>
            </div>
            <div className="mt-4 space-y-3">
              {supportedClaims.length === 0 ? (
                <p className="text-sm text-muted-foreground">No supported findings recorded.</p>
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
              <h4 className="text-sm font-semibold">Open Questions</h4>
            </div>
            <div className="mt-4 space-y-2">
              {displayUnsupported.length === 0 ? (
                <p className="text-sm text-muted-foreground">No open questions recorded.</p>
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
                        {clarifyWorkspaceTerm(citation.title ?? citation.url)}
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </a>
                    ) : (
                      <p className="text-sm font-medium">
                        {clarifyWorkspaceTerm(citation.title ?? citation.source_id)}
                      </p>
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
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold">Evidence memo</h4>
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
        <div className="mt-4 grid gap-x-6 lg:grid-cols-2">
          {primarySections.map((section) => (
            <section className="border-t border-border py-3" key={section.title}>
              <h5 className="text-xs font-medium text-muted-foreground">
                {clarifyWorkspaceTerm(section.title)}
              </h5>
              <MarkdownContent
                className="mt-2 line-clamp-6 space-y-2 text-sm leading-6 text-foreground"
                markdown={clarifyWorkspaceTerm(section.body)}
              />
            </section>
          ))}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 border-t border-border pt-3 lg:grid-cols-2">
        <details>
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
                      {clarifyWorkspaceTerm(citation.title ?? citation.url)}
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                  ) : (
                    <p className="text-sm font-medium">
                      {clarifyWorkspaceTerm(citation.title ?? citation.source_id)}
                    </p>
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

        <details>
          <summary className="cursor-pointer text-sm font-medium">
            What We Still Do Not Know
          </summary>
          <div className="mt-3 max-h-72 space-y-2 overflow-auto border-t border-border pt-3">
            {unsupportedClaims.length === 0 ? (
              <p className="text-sm text-muted-foreground">No open questions recorded.</p>
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

      <details className="mt-3 border-t border-border pt-3">
        <summary className="cursor-pointer text-sm font-medium">Full Details</summary>
        <article className="mt-3 max-h-[28rem] min-w-0 overflow-auto border-t border-border pt-3">
          <MarkdownContent markdown={clarifyWorkspaceTerm(markdown)} />
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
        <h4 className="text-sm font-semibold">Source candidates</h4>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {sources.length}
        </span>
      </div>
      {sources.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No source candidates yet. Find sources after approving the evidence plan.
        </p>
      ) : (
        <div className="mt-3 divide-y divide-border">
          {sources.map((source) => (
            <details className="py-3 first:pt-0" key={source.id}>
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
                        Add source
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
                        Reject source
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
                  <p className="mt-2 text-xs text-danger-foreground">{source.ingestion_error}</p>
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
        <h4 className="text-sm font-semibold">Competitor candidates</h4>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {candidates.length}
        </span>
      </div>
      {candidates.length === 0 ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          No competitor candidates yet. Find competitors to review direct competitors,
          substitutes, and incumbents.
        </p>
      ) : (
        <div className="mt-3 divide-y divide-border">
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
    <details className="border-t border-border py-3 first:border-t-0 first:pt-0">
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
                Add competitor
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
                Reject competitor
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
          <p className="mt-2 text-xs text-danger-foreground">{candidate.ingestion_error}</p>
        ) : null}

      {canEdit ? (
        <details className="mt-3 border-t border-border pt-3">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
            Edit competitor found
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
              Save Competitor
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
    <details className="rounded-lg border border-border bg-card p-5">
      <summary className="cursor-pointer list-none">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Route className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Decision progress</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {overview.idea_readiness.score}% complete. This is workflow progress, not a score for idea quality.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {formatStage(overview.strategic_snapshot.current_stage)}
        </span>
      </div>
      </summary>
      <div className="mt-5 grid gap-3 sm:hidden">
        {rows.map((row) => (
          <div className="rounded-md bg-surface px-3 py-3" key={row.key}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">{row.label}</h3>
              <LifecycleStatusBadge status={row.status} />
            </div>
            <dl className="mt-3 grid gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Signal</dt>
                <dd className="mt-1 text-foreground">{row.signal}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Next</dt>
                <dd className="mt-1 text-foreground">{row.next}</dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
      <div className="mt-5 hidden overflow-x-auto sm:block">
        <table className="min-w-[720px] w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs  text-muted-foreground">
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
    </details>
  );
}

function TopRisksCard({
  risks,
}: {
  risks: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["key_risks"];
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
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
        <div className="mt-4 grid gap-x-5 gap-y-4 border-t border-border pt-4 md:grid-cols-3">
          {risks.slice(0, 3).map((risk) => (
            <div key={risk.id}>
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
              <p className="mt-3 text-xs font-medium text-muted-foreground">
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

function SnapshotField({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <h3 className="text-xs font-medium text-muted-foreground">
        {label}
      </h3>
      {value ? (
        <MarkdownContent
          className="mt-1 line-clamp-4 space-y-2 text-sm leading-6 text-foreground"
          markdown={value}
        />
      ) : (
        <a className="mt-1 block text-sm text-warning-foreground hover:underline" href="#structured-intake">
          Add in project context
        </a>
      )}
    </div>
  );
}

function RecentUpdatesCard({
  updates,
}: {
  updates: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["recent_strategic_updates"];
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
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
                <h3 className="text-sm font-semibold">{clarifyWorkspaceTerm(update.title)}</h3>
                <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                  {formatLabel(update.related_entity_type)}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {truncate(clarifyWorkspaceTerm(update.summary), 220)}
              </p>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Why it matters: {truncate(clarifyWorkspaceTerm(update.why_it_matters), 180)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function tabForAction(action: NextBestAction): ProjectTab {
  const hash = action.target_route?.split("#")[1];
  return tabFromHash(hash ? `#${hash}` : "") ?? tabFromAnchor(hash ?? "") ?? routeTabForActionType(action.action_type);
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

function formatStage(stage: ProjectStage) {
  const labels: Record<ProjectStage, string> = {
    draft_idea: "Draft idea",
    structured_intake: "Structured intake",
    brief_generated: "Research ready",
    competitors_analyzed: "Competitors mapped",
    assumptions_identified: "Assumptions identified",
    validation_plan_created: "Validation planned",
    experiment_running: "Validation running",
    decision_ready: "Recommendation drafted",
    paused: "Paused",
    killed: "Killed",
    proceeding: "Decision recorded",
  };
  return labels[stage] ?? formatLabel(stage);
}

function stageBadgeClass(stage: ProjectStage) {
  if (stage === "proceeding") {
    return "rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground";
  }
  if (stage === "decision_ready" || stage === "validation_plan_created" || stage === "experiment_running") {
    return "rounded-md bg-warning-muted px-2 py-1 text-xs font-medium text-warning-foreground";
  }
  if (stage === "paused" || stage === "killed") {
    return "rounded-md bg-danger-muted px-2 py-1 text-xs font-medium text-danger-foreground";
  }
  return "rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground";
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

type DecisionGradeSignal = {
  detail: string;
  tone: HealthTone;
  value: string;
};

type CanonicalProjectStatus = {
  detail: string;
  label: string;
  mobileSentence: string;
  sentence: string;
  tone: HealthTone;
};

type LifecycleStatus = "complete" | "current" | "needs_work" | "blocked";

type LifecycleRow = {
  key: string;
  label: string;
  status: LifecycleStatus;
  signal: string;
  next: string;
};

function stageFocusCopy(stage: ProjectStage) {
  if (stage === "validation_plan_created" || stage === "experiment_running") {
    return {
      summary:
        stage === "experiment_running"
          ? "Validation is active. Preserve the signal by logging results as soon as the test produces evidence."
          : "A validation plan exists. The next useful work is running the test and logging real evidence before making a build decision.",
      title: "Validation focus",
    };
  }

  if (stage === "decision_ready" || stage === "proceeding") {
    return {
      summary:
        stage === "proceeding"
          ? "A decision has been recorded. Keep the next milestone tied to the evidence and revisit trigger."
          : "Validation results exist. Use the evidence trail to decide whether to continue research, pivot, pause, kill, or proceed narrowly.",
      title: "Decision focus",
    };
  }

  if (stage === "brief_generated" || stage === "competitors_analyzed") {
    return {
      summary:
        "Use this snapshot to keep the thesis, target user, wedge, and risk in view while research is still forming.",
      title: "Research focus",
    };
  }

  if (stage === "assumptions_identified") {
    return {
      summary:
        "The next useful work is converting the decision blocker into one concrete validation test.",
      title: "Strategic snapshot",
    };
  }

  return {
    summary:
      "Use this snapshot to keep the thesis, target user, wedge, and risk in view while research is still forming.",
    title: "Strategic snapshot",
  };
}

function recoveryGuidance(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
  missingContextCount: number,
): {
  detail: string;
  label: string;
  title: string;
  tone: HealthTone;
} {
  const blocker = riskiestAssumption(overview);

  if (missingContextCount > 0) {
    return {
      detail: "Fill the missing context before expanding evidence work. A clearer target user, problem, thesis, or wedge will make the next recommendation easier to trust.",
      label: `${missingContextCount} gap${missingContextCount === 1 ? "" : "s"}`,
      title: "Recover by closing context gaps",
      tone: "warning",
    };
  }

  if (overview.evidence_health.source_count === 0) {
    return {
      detail: "Plan an evidence review before treating the verdict as durable. The project needs source coverage before it can support a strategic decision.",
      label: "No sources",
      title: "Recover by adding evidence",
      tone: "warning",
    };
  }

  if (blocker && blocker.evidence_links.length === 0) {
    return {
      detail: "Run or log the first proof for the decision blocker. Do not broaden scope until the blocker has real validation evidence.",
      label: "Proof needed",
      title: "Recover by testing the blocker",
      tone: "warning",
    };
  }

  if (overview.evidence_health.unsupported_claim_count > 0) {
    return {
      detail: "Resolve the open questions in the evidence basis before recording a stronger decision. Keep the verdict conditional until unsupported claims are handled.",
      label: `${overview.evidence_health.unsupported_claim_count} open`,
      title: "Recover by resolving open questions",
      tone: "warning",
    };
  }

  const health = projectHealth(overview);
  return {
    detail: health.detail,
    label: health.label,
    title: "Recovery path is clear",
    tone: health.tone,
  };
}

function canonicalProjectStatus(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
): CanonicalProjectStatus {
  const stage = overview.strategic_snapshot.current_stage;
  const risk = highestRiskLabel(overview);
  const decisionGrade = decisionGradeEvidence(overview);
  const confidence = formatConfidenceValue(overview.current_recommendation.confidence).toLowerCase();
  const progress = formatStage(stage).toLowerCase();
  const nextAction = sentenceFragment(clarifyActionLabel(overview.next_best_action.label));
  const missingContextCount = decisionContextGaps(overview).filter(
    (item) => item.status === "missing",
  ).length;
  const blocker = riskiestAssumption(overview);
  const badge = canonicalStatusBadge(overview, {
    blockerNeedsProof: Boolean(blocker && blocker.evidence_links.length === 0),
    decisionGrade,
    missingContextCount,
    risk,
  });
  const evidenceStatus =
    decisionGrade.value === "Ready to decide"
      ? "evidence ready to decide"
      : "evidence needing proof";

  return {
    detail: `Supporting signals: ${countLabel(overview.evidence_health.source_count, "source")}, ${countLabel(overview.evidence_health.competitor_count, "competitor")}, ${countLabel(overview.evidence_health.validated_assumption_count, "validated assumption")}, ${countLabel(overview.evidence_health.unsupported_claim_count, "open question")}. Full recommendation: ${truncate(clarifyStatusRecommendation(overview.current_recommendation.recommendation), 140)}`,
    label: badge.label,
    mobileSentence: `${canonicalVerdictPhrase(overview)}. Next: ${nextAction}.`,
    sentence: `${canonicalVerdictPhrase(overview)}, with ${risk.toLowerCase()} risk, ${confidence} confidence, ${evidenceStatus}, progress at ${progress}, and the next action is to ${nextAction}.`,
    tone: badge.tone,
  };
}

function canonicalStatusBadge(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
  {
    blockerNeedsProof,
    decisionGrade,
    missingContextCount,
    risk,
  }: {
    blockerNeedsProof: boolean;
    decisionGrade: DecisionGradeSignal;
    missingContextCount: number;
    risk: string;
  },
): { label: string; tone: HealthTone } {
  const stage = overview.strategic_snapshot.current_stage;

  if (stage === "killed" || overview.project.status === "killed") {
    return { label: "Stopped", tone: "danger" };
  }

  if (stage === "paused" || overview.project.status === "paused") {
    return { label: "Paused", tone: "neutral" };
  }

  if (stage === "proceeding") {
    return { label: "Recorded", tone: "good" };
  }

  const contextIsPrimary =
    missingContextCount > 0 &&
    (stage === "draft_idea" ||
      stage === "structured_intake" ||
      overview.evidence_health.source_count === 0);

  if (contextIsPrimary) {
    return { label: "Clarify", tone: "warning" };
  }

  if (overview.evidence_health.source_count === 0) {
    return { label: "Needs evidence", tone: "warning" };
  }

  if (blockerNeedsProof) {
    return { label: "Proof needed", tone: "warning" };
  }

  if (decisionGrade.value === "Ready to decide") {
    return { label: "Ready", tone: "good" };
  }

  if (risk === "High") {
    return { label: "Validate risk", tone: "warning" };
  }

  return { label: "On track", tone: "neutral" };
}

function canonicalVerdictPhrase(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
) {
  const recommendation = overview.current_recommendation.recommendation;
  const normalized = recommendation.toLowerCase();
  const stage = overview.strategic_snapshot.current_stage;

  if (stage === "killed" || overview.project.status === "killed") {
    return "Current verdict is stop the project";
  }

  if (stage === "paused" || overview.project.status === "paused") {
    return "Current verdict is pause active work";
  }

  if (stage === "proceeding") {
    return "Current verdict is proceed under the recorded decision";
  }

  if (normalized.includes("do not build") || normalized.includes("don't build")) {
    return "Current verdict is do not build yet";
  }

  if (normalized.includes("pivot")) {
    return "Current verdict is pivot or narrow the wedge";
  }

  if (normalized.includes("proceed")) {
    return "Current verdict is proceed narrowly";
  }

  if (normalized.includes("kill") || normalized.includes("stop")) {
    return "Current verdict is stop the project";
  }

  if (normalized.includes("pause")) {
    return "Current verdict is pause active work";
  }

  return `Current verdict is ${sentenceFragment(truncate(recommendation, 72))}`;
}

function sentenceFragment(value: string) {
  const cleaned = value.trim().replace(/[.!?]+$/u, "");
  if (!cleaned) {
    return "continue the current work";
  }
  return cleaned.charAt(0).toLowerCase() + cleaned.slice(1);
}

function clarifyStatusRecommendation(value: string) {
  return clarifyActionText(value).replace(
    /\bthe highest-risk validation test\b/gi,
    "the decision-blocker validation test",
  );
}

function countLabel(count: number, singular: string) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

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
      label: "High strategic risk",
      tone: "warning",
      detail: "There are material risks or weak evidence areas that should be validated next.",
    };
  }

  return {
    label: "Workflow on track",
    tone: "good",
    detail: "The workflow has a clear current state, supporting evidence, and a defined next action. This does not mean the idea is proven.",
  };
}

function decisionGradeEvidence(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
): DecisionGradeSignal {
  const hasSources = overview.evidence_health.source_count > 0;
  const hasValidatedBlocker = overview.evidence_health.validated_assumption_count > 0;
  const confidenceIsWeak = overview.current_recommendation.confidence === "low";
  const highRiskStillOpen = highestRiskLabel(overview) === "High";

  if (hasSources && hasValidatedBlocker && !confidenceIsWeak && !highRiskStillOpen) {
    return {
      detail:
        "Evidence is ready to support a decision: the blocker has validation support, source coverage exists, and the recommendation is not low confidence.",
      tone: "good",
      value: "Ready to decide",
    };
  }

  const reasons = [
    !hasSources ? "source coverage is missing" : null,
    !hasValidatedBlocker ? "the decision blocker has not been validated" : null,
    confidenceIsWeak ? "recommendation confidence is low" : null,
    highRiskStillOpen ? "high strategic risk remains" : null,
  ].filter((reason): reason is string => Boolean(reason));

  return {
    detail: `Evidence still needs proof because ${reasons.join(", ")}.`,
    tone: "warning",
    value: "Needs proof",
  };
}

function riskiestAssumption(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
) {
  const score = (assumption: (typeof overview.key_assumptions)[number]) => {
    const importance =
      assumption.importance === "critical"
        ? 4
        : assumption.importance === "high"
          ? 3
          : assumption.importance === "medium"
            ? 2
            : 1;
    const uncertainty =
      assumption.uncertainty === "high" ? 3 : assumption.uncertainty === "medium" ? 2 : 1;
    return importance * 3 + uncertainty * 2 + (assumption.kill_risk ? 4 : 0);
  };
  return [...overview.key_assumptions].sort((a, b) => score(b) - score(a))[0] ?? null;
}

function highestRiskLabel(
  overview: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>,
) {
  const assumption = riskiestAssumption(overview);
  const topRisk = overview.key_risks[0];
  if (
    topRisk?.severity === "critical" ||
    assumption?.importance === "critical" ||
    assumption?.kill_risk
  ) {
    return "High";
  }
  if (topRisk?.severity === "high" || assumption?.importance === "high") {
    return "High";
  }
  if (topRisk?.severity === "medium" || assumption?.importance === "medium") {
    return "Medium";
  }
  if (topRisk || assumption) {
    return "Low";
  }
  return "Unknown";
}

function tonePillClass(tone: HealthTone) {
  if (tone === "good") {
    return "inline-flex w-fit rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground";
  }
  if (tone === "warning") {
    return "inline-flex w-fit rounded-md bg-warning-muted px-2 py-1 text-xs font-medium text-warning-foreground";
  }
  if (tone === "danger") {
    return "inline-flex w-fit rounded-md bg-danger-muted px-2 py-1 text-xs font-medium text-danger-foreground";
  }
  return "inline-flex w-fit rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground";
}

function assumptionConfidenceLabel(value: string | null) {
  if (!value) {
    return "Unknown confidence";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "Unknown confidence";
  }
  if (parsed >= 0.7) {
    return "High confidence";
  }
  if (parsed >= 0.4) {
    return "Medium confidence";
  }
  return "Low confidence";
}

function formatConfidenceValue(value: RecommendationConfidence) {
  return value.charAt(0).toUpperCase() + value.slice(1);
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
      next: researchComplete ? "Review findings" : "Plan evidence review",
    },
    {
      key: "evidence",
      label: "Evidence",
      complete: overview.evidence_health.source_count > 0,
      signal: `${overview.evidence_health.cited_claim_count} supported findings`,
      next:
        overview.evidence_health.unsupported_claim_count > 0
          ? "Resolve open questions"
          : "Keep evidence current",
    },
    {
      key: "assumptions",
      label: "Assumptions",
      complete: overview.key_assumptions.length > 0,
      signal: `${overview.key_assumptions.length} ranked`,
      next: overview.key_assumptions.length > 0 ? "Validate blocker" : "Extract assumptions",
    },
    {
      key: "validation",
      label: "Validation",
      complete: validationComplete,
      signal: validationComplete ? "Validation test exists" : "Test needed",
      next: validationComplete ? "Log results" : "Create validation test",
    },
    {
      key: "decision",
      label: "Decision",
      complete: decisionComplete,
      signal: decisionComplete ? "Recommendation drafted or decision recorded" : "Needs validation signal",
      next: decisionComplete ? "Review decision rationale" : "Wait for validation signal",
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

function clarifyActionText(value: string) {
  return clarifyDecisionNarrative(value)
    .replace(/\bthe highest-risk assumption\b/gi, "the decision blocker")
    .replace(/\bthe highest risk assumption\b/gi, "the decision blocker")
    .replace(/\bthe riskiest assumption\b/gi, "the decision blocker")
    .replace(/\bhighest-risk assumption\b/gi, "decision blocker")
    .replace(/\bhighest risk assumption\b/gi, "decision blocker")
    .replace(/\briskiest assumption\b/gi, "decision blocker");
}

function clarifyActionLabel(value: string) {
  return value
    .replace(/^Add Evidence$/i, "Add source")
    .replace(/^Run Research$/i, "Plan evidence review")
    .replace(/^Review Research$/i, "Review evidence")
    .replace(/^View activity trace$/i, "Review activity trace");
}

function stripLeadingSignalLabel(value: string) {
  return value.replace(/^(Decision blocker|Next proof):\s*/i, "");
}

function clarifyWorkspaceTerm(value: string) {
  return value
    .replace(/\bAgentic Research\b/g, "Evidence review")
    .replace(/\bResearch Sprint\b/g, "Evidence Review")
    .replace(/\bResearch sprint\b/g, "Evidence review")
    .replace(/\bresearch sprint\b/g, "evidence review")
    .replace(/\bResearch Memo\b/g, "Evidence Memo")
    .replace(/\bResearch memo\b/g, "Evidence memo")
    .replace(/\bresearch memo\b/g, "evidence memo")
    .replace(/\bProject update\b/g, "Decision update")
    .replace(/\bproject update\b/g, "decision update")
    .replace(/\bMemory updates\b/g, "Decision updates")
    .replace(/\bmemory updates\b/g, "decision updates");
}

function LifecycleStatusBadge({ status }: { status: LifecycleStatus }) {
  if (status === "complete") {
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
        Complete
      </span>
    );
  }
  if (status === "current") {
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-warning-muted px-2 py-1 text-xs font-medium text-warning-foreground">
        <CircleAlert className="h-3.5 w-3.5" aria-hidden="true" />
        Current
      </span>
    );
  }
  if (status === "blocked") {
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-danger-muted px-2 py-1 text-xs font-medium text-danger-foreground">
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

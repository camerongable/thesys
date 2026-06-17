"use client";

import { ArrowRight, Database, FileSearch, RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { AiModeIndicator } from "@/features/ai/ai-mode-indicator";
import { filterHomepageProjects, isDisposableProject } from "@/features/projects/project-list-utils";
import { getMe, getProjectOverview, listProjects, seedDemoProject } from "@/lib/api";

type ProjectOverviewResult = Awaited<ReturnType<typeof getProjectOverview>>;
type ProjectListItem = Awaited<ReturnType<typeof listProjects>>[number];
type QueueStatusFilter = "all" | "draft" | "validation" | "recommendation" | "recorded";
type QueueRiskFilter = "all" | "high" | "low";
type QueueSortMode = "updated" | "risk" | "evidence";

export function ProjectList() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<QueueStatusFilter>("all");
  const [riskFilter, setRiskFilter] = useState<QueueRiskFilter>("all");
  const [sortMode, setSortMode] = useState<QueueSortMode>("updated");
  const [compactRows, setCompactRows] = useState(false);
  const [showTestProjects, setShowTestProjects] = useState(false);
  const meQuery = useQuery({ queryKey: ["me"], queryFn: getMe });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const seedMutation = useMutation({
    mutationFn: seedDemoProject,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(result.next_url);
    },
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      const target = event.target as HTMLElement | null;
      const isEditing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target?.isContentEditable;
      if (isEditing) {
        return;
      }
      if (event.key === "/") {
        event.preventDefault();
        document.getElementById("project-search")?.focus();
      } else if (event.key.toLowerCase() === "n") {
        event.preventDefault();
        router.push("/projects/new");
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);

  const projects = projectsQuery.data ?? [];
  const overviewQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["projects", project.id, "overview", "project-card"],
      queryFn: () => getProjectOverview(project.id),
    })),
  });
  const projectRows = projects.map((project, index) => ({
    overview: overviewQueries[index]?.data,
    overviewPending: overviewQueries[index]?.isLoading ?? false,
    project,
  }));
  const hiddenTestProjectCount = projectRows.filter(({ project }) => isDisposableProject(project)).length;
  const homepageRows = filterHomepageProjects(projectRows, showTestProjects);
  const activeProjects = homepageRows.filter(({ project }) => project.status === "active").length;
  const readyProjects = homepageRows.filter(
    ({ overview }) => overview?.idea_readiness.status === "decision_ready",
  ).length;
  const filteredRows = sortProjectRows(
    homepageRows.filter(({ overview, project }) =>
      projectMatchesFilters({
        overview,
        project,
        riskFilter,
        searchQuery,
        statusFilter,
      }),
    ),
    sortMode,
  );
  const visibleProjectCount = filteredRows.length;

  return (
    <main className="min-h-screen">
      <div className="mx-auto min-h-screen w-full max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-5 border-b border-border pb-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">
              {meQuery.data?.workspace.name ?? "Local workspace"}
            </p>
            <h1 className="mt-2 max-w-[68ch] text-2xl font-semibold tracking-normal sm:text-3xl">
              Turn a rough idea into the next validation test.
            </h1>
            <p className="mt-3 max-w-[68ch] text-sm leading-6 text-muted-foreground">
              Thesys shapes the idea, finds the wedge, identifies the biggest unknown,
              and tells you what proof to run next.
            </p>
          </div>
          <div className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-2 sm:flex sm:items-center sm:justify-end lg:shrink-0 lg:pt-1">
            <ThemeToggle />
            <AiModeIndicator />
            <Link
              aria-keyshortcuts="N"
              className={buttonVariants({ className: "col-span-2 w-full shrink-0 whitespace-nowrap sm:w-auto" })}
              href="/projects/new"
              title="Shortcut: N"
            >
              <FileSearch className="h-4 w-4" aria-hidden="true" />
              Start investigation
            </Link>
          </div>
        </header>

        <section className="grid gap-5 py-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0">
            <div className="rounded-lg border border-border bg-card">
              <div className="flex flex-col gap-4 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold">Ideas in progress</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Open an idea to see the thesis, biggest unknown, and next proof.
                  </p>
                </div>
                <div className="grid w-full grid-cols-3 divide-x divide-border overflow-hidden rounded-md border border-border bg-surface text-center text-xs sm:w-auto sm:min-w-64">
                  <QueueMetric label="Ideas" value={homepageRows.length} />
                  <QueueMetric label="Active" value={activeProjects} />
                  <QueueMetric label="Ready" value={readyProjects} />
                </div>
              </div>
              {projects.length > 0 ? (
                <QueueToolbar
                  compactRows={compactRows}
                  riskFilter={riskFilter}
                  searchQuery={searchQuery}
                  sortMode={sortMode}
                  statusFilter={statusFilter}
                  hiddenTestProjectCount={hiddenTestProjectCount}
                  showTestProjects={showTestProjects}
                  onCompactRowsChange={setCompactRows}
                  onRiskFilterChange={setRiskFilter}
                  onSearchQueryChange={setSearchQuery}
                  onShowTestProjectsChange={setShowTestProjects}
                  onSortModeChange={setSortMode}
                  onStatusFilterChange={setStatusFilter}
                />
              ) : null}
              <p className="sr-only" aria-live="polite">
                Showing {formatNumber(visibleProjectCount)} of {formatNumber(homepageRows.length)} ideas.
              </p>

              {projectsQuery.isLoading ? (
                <ProjectListSkeleton />
              ) : projectsQuery.isError ? (
                <div className="px-4 py-8">
                  <ErrorNotice
                    actionLabel="Retry projects"
                    message={(projectsQuery.error as Error).message}
                    onAction={() => void projectsQuery.refetch()}
                  />
                </div>
              ) : projects.length === 0 ? (
                <EmptyProjectQueue onSeed={() => seedMutation.mutate()} pending={seedMutation.isPending} />
              ) : homepageRows.length === 0 ? (
                <EmptyHiddenQueue
                  hiddenCount={hiddenTestProjectCount}
                  onShow={() => setShowTestProjects(true)}
                />
              ) : filteredRows.length === 0 ? (
                <EmptyFilteredQueue />
              ) : (
                <div className="divide-y divide-border">
                  {filteredRows.map(({ overview, overviewPending, project }) => (
                    <ProjectDecisionRow
                      key={project.id}
                      compact={compactRows}
                      overview={overview}
                      overviewPending={overviewPending}
                      project={project}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-5 lg:self-start">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Start an investigation</h2>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Add a rough idea. Thesys will ask for missing context before it plans research.
              </p>
              <Link className={buttonVariants({ className: "mt-4 w-full" })} href="/projects/new">
                <FileSearch className="h-4 w-4" aria-hidden="true" />
                Start investigation
              </Link>
            </div>

            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">Guided demo</h2>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Load the fitness coach scenario to walk through the full path: messy idea,
                thesis, wedge choice, validation mission, interpreted result, and Decision Coach.
              </p>
              <Button
                className="mt-4 w-full"
                disabled={seedMutation.isPending}
                onClick={() => seedMutation.mutate()}
                type="button"
                variant="secondary"
              >
                <Database className="h-4 w-4" aria-hidden="true" />
                {seedMutation.isPending ? "Loading demo..." : "Load guided demo"}
              </Button>
              {seedMutation.error ? (
                <div className="mt-3">
                  <ErrorNotice
                    actionLabel="Retry demo"
                    message={(seedMutation.error as Error).message}
                    onAction={() => seedMutation.mutate()}
                  />
                </div>
              ) : null}
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function QueueToolbar({
  compactRows,
  riskFilter,
  searchQuery,
  sortMode,
  statusFilter,
  hiddenTestProjectCount,
  showTestProjects,
  onCompactRowsChange,
  onRiskFilterChange,
  onSearchQueryChange,
  onShowTestProjectsChange,
  onSortModeChange,
  onStatusFilterChange,
}: {
  compactRows: boolean;
  riskFilter: QueueRiskFilter;
  searchQuery: string;
  sortMode: QueueSortMode;
  statusFilter: QueueStatusFilter;
  hiddenTestProjectCount: number;
  showTestProjects: boolean;
  onCompactRowsChange: (value: boolean) => void;
  onRiskFilterChange: (value: QueueRiskFilter) => void;
  onSearchQueryChange: (value: string) => void;
  onShowTestProjectsChange: (value: boolean) => void;
  onSortModeChange: (value: QueueSortMode) => void;
  onStatusFilterChange: (value: QueueStatusFilter) => void;
}) {
  const activeControlCount = [
    statusFilter !== "all",
    riskFilter !== "all",
    sortMode !== "updated",
    compactRows,
    showTestProjects,
  ].filter(Boolean).length;

  return (
    <div className="border-b border-border px-4 py-3">
      <div className="grid gap-2 min-[1200px]:grid-cols-[minmax(16rem,1fr)_9rem_9rem_9rem_auto_auto]">
        <label className="relative block min-w-0">
          <span className="sr-only">Search projects</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <input
            aria-keyshortcuts="/"
            className="min-h-11 w-full rounded-md border border-border bg-input pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-focus sm:h-10 sm:min-h-10"
            id="project-search"
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder="Search ideas, verdicts, or next actions"
            title="Shortcut: /"
            value={searchQuery}
          />
        </label>
        <QueueAdvancedFilters
          className="hidden min-[1200px]:contents"
          compactRows={compactRows}
          hiddenTestProjectCount={hiddenTestProjectCount}
          riskFilter={riskFilter}
          showTestProjects={showTestProjects}
          sortMode={sortMode}
          statusFilter={statusFilter}
          onCompactRowsChange={onCompactRowsChange}
          onRiskFilterChange={onRiskFilterChange}
          onShowTestProjectsChange={onShowTestProjectsChange}
          onSortModeChange={onSortModeChange}
          onStatusFilterChange={onStatusFilterChange}
        />
      </div>
      <details className="group mt-2 min-[1200px]:hidden">
        <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:min-h-10">
          <span className="inline-flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" aria-hidden="true" />
            Filters and view
          </span>
          {activeControlCount > 0 ? (
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {activeControlCount} active
            </span>
          ) : null}
        </summary>
        <QueueAdvancedFilters
          className="mt-2 hidden gap-2 group-open:grid"
          compactRows={compactRows}
          hiddenTestProjectCount={hiddenTestProjectCount}
          riskFilter={riskFilter}
          showTestProjects={showTestProjects}
          sortMode={sortMode}
          statusFilter={statusFilter}
          onCompactRowsChange={onCompactRowsChange}
          onRiskFilterChange={onRiskFilterChange}
          onShowTestProjectsChange={onShowTestProjectsChange}
          onSortModeChange={onSortModeChange}
          onStatusFilterChange={onStatusFilterChange}
        />
      </details>
    </div>
  );
}

function QueueAdvancedFilters({
  className,
  compactRows,
  hiddenTestProjectCount,
  riskFilter,
  showTestProjects,
  sortMode,
  statusFilter,
  onCompactRowsChange,
  onRiskFilterChange,
  onShowTestProjectsChange,
  onSortModeChange,
  onStatusFilterChange,
}: {
  className?: string;
  compactRows: boolean;
  hiddenTestProjectCount: number;
  riskFilter: QueueRiskFilter;
  showTestProjects: boolean;
  sortMode: QueueSortMode;
  statusFilter: QueueStatusFilter;
  onCompactRowsChange: (value: boolean) => void;
  onRiskFilterChange: (value: QueueRiskFilter) => void;
  onShowTestProjectsChange: (value: boolean) => void;
  onSortModeChange: (value: QueueSortMode) => void;
  onStatusFilterChange: (value: QueueStatusFilter) => void;
}) {
  return (
    <div className={className}>
      <label className="block">
        <span className="sr-only">Status filter</span>
        <select
          className="min-h-11 w-full rounded-md border border-border bg-input px-3 text-sm outline-none focus:ring-2 focus:ring-focus sm:h-10 sm:min-h-10"
          onChange={(event) => onStatusFilterChange(event.target.value as QueueStatusFilter)}
          value={statusFilter}
        >
          <option value="all">All stages</option>
          <option value="draft">Drafts</option>
          <option value="validation">Validation</option>
          <option value="recommendation">Recommendation drafted</option>
          <option value="recorded">Decision recorded</option>
        </select>
      </label>
      <label className="block">
        <span className="sr-only">Risk filter</span>
        <select
          className="min-h-11 w-full rounded-md border border-border bg-input px-3 text-sm outline-none focus:ring-2 focus:ring-focus sm:h-10 sm:min-h-10"
          onChange={(event) => onRiskFilterChange(event.target.value as QueueRiskFilter)}
          value={riskFilter}
        >
          <option value="all">All risks</option>
          <option value="high">High risk</option>
          <option value="low">No critical risk</option>
        </select>
      </label>
      <label className="block">
        <span className="sr-only">Sort projects</span>
        <select
          className="min-h-11 w-full rounded-md border border-border bg-input px-3 text-sm outline-none focus:ring-2 focus:ring-focus sm:h-10 sm:min-h-10"
          onChange={(event) => onSortModeChange(event.target.value as QueueSortMode)}
          value={sortMode}
        >
          <option value="updated">Recent first</option>
          <option value="risk">Highest risk</option>
          <option value="evidence">Most evidence</option>
        </select>
      </label>
      <label className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm text-muted-foreground sm:h-10 sm:min-h-10">
        <input
          checked={compactRows}
          className="h-4 w-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          onChange={(event) => onCompactRowsChange(event.target.checked)}
          type="checkbox"
        />
        Compact
      </label>
      {hiddenTestProjectCount > 0 ? (
        <label className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm text-muted-foreground sm:h-10 sm:min-h-10">
          <input
            checked={showTestProjects}
            className="h-4 w-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            onChange={(event) => onShowTestProjectsChange(event.target.checked)}
            type="checkbox"
          />
          Show test projects
        </label>
      ) : null}
    </div>
  );
}

function ProjectDecisionRow({
  compact,
  overview,
  overviewPending,
  project,
}: {
  compact: boolean;
  overview: ProjectOverviewResult | undefined;
  overviewPending: boolean;
  project: ProjectListItem;
}) {
  const stage = overview ? formatStage(overview.strategic_snapshot.current_stage) : project.status;
  const recommendation =
    overview?.current_recommendation.recommendation ??
    (overviewPending ? "Loading verdict..." : "Open the project to generate a verdict.");
  const nextAction = overview?.next_best_action.label ?? "Structure the idea";
  const thesisOrDescription =
    overview?.strategic_snapshot.current_thesis ??
    project.short_description ??
    "No thesis recorded yet.";
  const rowLabel = `${project.name}. ${stage}. Verdict: ${recommendation}. Next action: ${nextAction}.`;

  return (
    <Link
      aria-label={rowLabel}
      className={compact
        ? "group block px-4 py-2.5 transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        : "group block px-4 py-4 transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"}
      href={`/projects/${project.id}`}
    >
      <div
        className={
          compact
            ? "grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(28rem,0.58fr)_1.25rem] lg:items-center"
            : "grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.42fr)_2rem] lg:items-center"
        }
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold" title={project.name}>
              {project.name}
            </h3>
            <StatusPill>{stage}</StatusPill>
          </div>
          {!compact ? (
            <p className="mt-2 line-clamp-2 max-w-[72ch] text-sm leading-6 text-muted-foreground">
              {thesisOrDescription}
            </p>
          ) : null}
          <p
            className={
              compact
                ? "mt-2 line-clamp-1 break-words text-sm font-medium leading-5 text-foreground"
                : "mt-3 line-clamp-2 break-words text-sm font-medium leading-6 text-foreground"
            }
          >
            {recommendation}
          </p>
        </div>

        <div
          className={
            compact
            ? "grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-[minmax(10rem,1fr)_minmax(12rem,1.15fr)]"
            : "grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-1"
          }
        >
          <Signal compact={compact} label="Next action" value={nextAction} />
          <Signal compact={compact} label="Evidence summary" value={overview ? evidenceSummary(overview) : "Pending"} />
        </div>

        <ArrowRight
          className="hidden h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground lg:block"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
}

function EmptyProjectQueue({ onSeed, pending }: { onSeed: () => void; pending: boolean }) {
  return (
    <div className="px-4 py-10">
      <div className="max-w-2xl">
        <h3 className="text-base font-semibold">No ideas in progress.</h3>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Start with a rough idea. Thesys will shape it into a thesis, identify the
          biggest unknown, and recommend the next proof to run.
        </p>
        <div className="mt-5 flex flex-col gap-2 sm:flex-row">
          <Link className={buttonVariants()} href="/projects/new">
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            Start investigation
          </Link>
          <Button disabled={pending} onClick={onSeed} type="button" variant="secondary">
            <Database className="h-4 w-4" aria-hidden="true" />
            {pending ? "Loading demo..." : "Load demo"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function EmptyHiddenQueue({
  hiddenCount,
  onShow,
}: {
  hiddenCount: number;
  onShow: () => void;
}) {
  return (
    <div className="px-4 py-8">
      <h3 className="text-sm font-semibold">Only test/demo projects are hidden.</h3>
      <p className="mt-2 max-w-[65ch] text-sm leading-6 text-muted-foreground">
        {formatNumber(hiddenCount)} test, demo, or audit project{hiddenCount === 1 ? "" : "s"} are
        hidden so the default queue stays focused on real ideas and the guided demo.
      </p>
      <Button className="mt-4" onClick={onShow} type="button" variant="secondary">
        Show test projects
      </Button>
    </div>
  );
}

function EmptyFilteredQueue() {
  return (
    <div className="px-4 py-8">
      <h3 className="text-sm font-semibold">No projects match those filters.</h3>
      <p className="mt-2 max-w-[65ch] text-sm leading-6 text-muted-foreground">
        Change the search, stage, or risk filter to bring projects back into the queue.
      </p>
    </div>
  );
}

function ProjectListSkeleton() {
  return (
    <div className="divide-y divide-border">
      {[0, 1, 2].map((item) => (
        <div className="px-4 py-4" key={item}>
          <div className="h-4 w-48 rounded bg-muted" />
          <div className="mt-3 h-3 w-3/4 rounded bg-muted" />
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <div className="h-10 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
            <div className="h-10 rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

function QueueMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-0 px-4 py-2">
      <div className="font-semibold text-foreground">{formatNumber(value)}</div>
      <div className="mt-0.5 text-muted-foreground">{label}</div>
    </div>
  );
}

function Signal({
  compact = false,
  label,
  value,
}: {
  compact?: boolean;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={compact
          ? "mt-0.5 truncate text-sm font-medium leading-5 text-foreground"
          : "mt-1 line-clamp-2 break-words text-sm font-medium leading-5 text-foreground"}
        title={value}
      >
        {value}
      </div>
    </div>
  );
}

function StatusPill({ children }: { children: string }) {
  return (
    <span className="inline-flex max-w-full items-center rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
      {children}
    </span>
  );
}

function ErrorNotice({
  actionLabel,
  message,
  onAction,
}: {
  actionLabel?: string;
  message: string;
  onAction?: () => void;
}) {
  return (
    <div
      className="rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground"
      role="alert"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="break-words">{message}</p>
        {onAction ? (
          <Button
            className="w-fit border-danger-border text-danger-foreground hover:bg-danger-muted"
            onClick={onAction}
            size="sm"
            type="button"
            variant="secondary"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            {actionLabel ?? "Retry"}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function evidenceSummary(overview: ProjectOverviewResult) {
  const highRiskAssumptions = overview.key_assumptions.filter(
    (assumption) =>
      assumption.kill_risk ||
      assumption.importance === "critical" ||
      assumption.importance === "high",
  ).length;
  return `${formatNumber(overview.evidence_health.source_count)} sources, ${formatNumber(overview.evidence_health.competitor_count)} competitors, ${formatNumber(highRiskAssumptions)} high-risk assumptions`;
}

function highestProjectRisk(overview: ProjectOverviewResult) {
  const highRisk = overview.key_risks.find(
    (risk) => risk.severity === "critical" || risk.severity === "high",
  );
  return highRisk ? formatLabel(highRisk.severity) : "No critical risk";
}

function projectMatchesFilters({
  overview,
  project,
  riskFilter,
  searchQuery,
  statusFilter,
}: {
  overview: ProjectOverviewResult | undefined;
  project: ProjectListItem;
  riskFilter: QueueRiskFilter;
  searchQuery: string;
  statusFilter: QueueStatusFilter;
}) {
  const query = searchQuery.trim().toLowerCase();
  const recommendation = overview?.current_recommendation.recommendation ?? "";
  const nextAction = overview?.next_best_action.label ?? "";
  if (
    query.length > 0 &&
    !`${project.name} ${project.short_description ?? ""} ${recommendation} ${nextAction}`
      .toLowerCase()
      .includes(query)
  ) {
    return false;
  }

  if (statusFilter !== "all" && queueStatus(project, overview) !== statusFilter) {
    return false;
  }

  if (riskFilter !== "all") {
    const risk = overview ? highestProjectRisk(overview) : "Unknown";
    const highRisk = /critical|high/i.test(risk);
    if (riskFilter === "high" && !highRisk) {
      return false;
    }
    if (riskFilter === "low" && highRisk) {
      return false;
    }
  }

  return true;
}

function sortProjectRows(
  rows: { overview: ProjectOverviewResult | undefined; overviewPending: boolean; project: ProjectListItem }[],
  sortMode: QueueSortMode,
) {
  return [...rows].sort((a, b) => {
    if (sortMode === "risk") {
      return riskRank(b.overview) - riskRank(a.overview);
    }
    if (sortMode === "evidence") {
      return (b.overview?.evidence_health.source_count ?? 0) - (a.overview?.evidence_health.source_count ?? 0);
    }
    return new Date(b.project.updated_at).getTime() - new Date(a.project.updated_at).getTime();
  });
}

function queueStatus(
  project: ProjectListItem,
  overview: ProjectOverviewResult | undefined,
): QueueStatusFilter {
  const stage = overview?.strategic_snapshot.current_stage;
  if (stage === "decision_ready") {
    return "recommendation";
  }
  if (stage === "proceeding" || stage === "paused" || stage === "killed") {
    return "recorded";
  }
  if (stage === "validation_plan_created" || stage === "experiment_running") {
    return "validation";
  }
  if (project.status !== "active") {
    return "recorded";
  }
  return "draft";
}

function riskRank(overview: ProjectOverviewResult | undefined) {
  if (!overview) {
    return 0;
  }
  const risk = highestProjectRisk(overview);
  if (/critical|high/i.test(risk)) {
    return 3;
  }
  if (/medium/i.test(risk)) {
    return 2;
  }
  if (/low/i.test(risk)) {
    return 1;
  }
  return 0;
}

function formatStage(value: string) {
  const labels: Record<string, string> = {
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
  return labels[value] ?? formatLabel(value);
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined).format(value);
}

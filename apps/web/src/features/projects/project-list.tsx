"use client";

import { Database, FileSearch } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button, buttonVariants } from "@/components/ui/button";
import { AiModeIndicator } from "@/features/ai/ai-mode-indicator";
import { getMe, getProjectOverview, listProjects, seedDemoProject } from "@/lib/api";

export function ProjectList() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const meQuery = useQuery({ queryKey: ["me"], queryFn: getMe });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const seedMutation = useMutation({
    mutationFn: seedDemoProject,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(result.next_url);
    },
  });

  const projects = projectsQuery.data ?? [];
  const overviewQueries = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["projects", project.id, "overview", "project-card"],
      queryFn: () => getProjectOverview(project.id),
    })),
  });

  return (
    <main className="min-h-screen">
      <div className="mx-auto min-h-screen w-full max-w-6xl px-5 py-6 md:px-8">
        <section>
          <header className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {meQuery.data?.workspace.name ?? "Local workspace"}
              </p>
              <h1 className="mt-2 max-w-2xl text-3xl font-semibold tracking-normal">
                Validate an idea before you build.
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">
                Stop guessing whether to build. Paste a rough idea and Thesys will return a
                verdict, competitors, the riskiest assumption, and the first validation test.
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center lg:pt-1">
              <ThemeToggle />
              <AiModeIndicator />
              <Link className={buttonVariants()} href="/projects/new">
                <FileSearch className="h-4 w-4" aria-hidden="true" />
                Investigate New Idea
              </Link>
            </div>
          </header>

          {seedMutation.error ? (
            <div className="mt-5 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {(seedMutation.error as Error).message}
            </div>
          ) : null}

          <section className="my-6 rounded-lg border border-border bg-white p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-semibold">Start with a complete demo</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                  Load the independent fitness coach scenario to see the full loop: research,
                  evidence, competitors, assumptions, validation plan, result, and decision.
                </p>
              </div>
              <Button
                disabled={seedMutation.isPending}
                onClick={() => seedMutation.mutate()}
                type="button"
                variant="secondary"
              >
                <Database className="h-4 w-4" aria-hidden="true" />
                {seedMutation.isPending ? "Seeding..." : "Seed Demo"}
              </Button>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-white">
            <div className="border-b border-border px-5 py-4">
              <h2 className="text-base font-semibold">Ideas under validation</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Each project shows the current verdict, next action, evidence state, and stage.
              </p>
            </div>

            {projectsQuery.isLoading ? (
              <div className="px-5 py-10 text-sm text-muted-foreground">Loading projects...</div>
            ) : projectsQuery.isError ? (
              <div className="px-5 py-10 text-sm text-red-700">
                {(projectsQuery.error as Error).message}
              </div>
            ) : projects.length === 0 ? (
              <div className="px-5 py-10">
                <p className="text-sm text-muted-foreground">
                  No ideas under validation yet. Start with a rough idea and let the app turn it
                  into a research-backed validation decision.
                </p>
                <Link
                  className={buttonVariants({ className: "mt-4", variant: "secondary" })}
                  href="/projects/new"
                >
                  <FileSearch className="h-4 w-4" aria-hidden="true" />
                  Investigate New Idea
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {projects.map((project, index) => {
                  const overview = overviewQueries[index]?.data;
                  return (
                  <Link
                    key={project.id}
                    className="block px-5 py-5 hover:bg-muted"
                    href={`/projects/${project.id}`}
                  >
                    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem] lg:items-start">
                      <div className="min-w-0">
                        <div className="font-semibold">{project.name}</div>
                        <div className="mt-1 max-w-3xl text-sm text-muted-foreground">
                          {project.short_description ?? "No description"}
                        </div>
                        <div className="mt-4 rounded-md bg-muted px-3 py-2">
                          <div className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                            Verdict
                          </div>
                          <p className="mt-1 text-sm font-medium leading-6">
                            {overview?.current_recommendation.recommendation ??
                              "Open the project to generate the first strategic verdict."}
                          </p>
                        </div>
                        <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
                          <ProjectCardSignal
                            label="Next action"
                            value={overview?.next_best_action.label ?? "Structure the idea"}
                          />
                          <ProjectCardSignal
                            label="Evidence"
                            value={
                              overview
                                ? evidenceSummary(overview)
                                : "Evidence appears after research"
                            }
                          />
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 lg:flex-col lg:items-end">
                        <span className="w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                          {overview ? formatStage(overview.strategic_snapshot.current_stage) : project.status}
                        </span>
                        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                          Updated {formatRelativeDate(project.updated_at)}
                        </span>
                      </div>
                    </div>
                  </Link>
                  );
                })}
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}

function ProjectCardSignal({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

type ProjectOverviewResult = Awaited<ReturnType<typeof getProjectOverview>>;

function evidenceSummary(overview: ProjectOverviewResult) {
  const highRiskAssumptions = overview.key_assumptions.filter(
    (assumption) =>
      assumption.kill_risk ||
      assumption.importance === "critical" ||
      assumption.importance === "high",
  ).length;
  return `${overview.evidence_health.source_count} sources · ${overview.evidence_health.competitor_count} competitors · ${highRiskAssumptions} high-risk assumptions`;
}

function formatStage(value: string) {
  const labels: Record<string, string> = {
    draft_idea: "Draft idea",
    structured_intake: "Structured intake",
    brief_generated: "Research ready",
    competitors_analyzed: "Competitors mapped",
    assumptions_identified: "Assumptions identified",
    validation_plan_created: "Validation plan ready",
    experiment_running: "Validation running",
    decision_ready: "Decision recommended",
    paused: "Paused",
    killed: "Killed",
    proceeding: "Decision recorded",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

function formatRelativeDate(value: string) {
  const date = new Date(value);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / 86_400_000);
  if (diffDays <= 0) {
    return "today";
  }
  if (diffDays === 1) {
    return "yesterday";
  }
  if (diffDays < 7) {
    return `${diffDays} days ago`;
  }
  return date.toLocaleDateString();
}

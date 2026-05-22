"use client";

import { ArrowLeft, Beaker, FileText, ShieldAlert, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getProject } from "@/lib/api";
import { BriefTab } from "@/features/projects/brief-tab";
import { EvidenceTab } from "@/features/projects/evidence-tab";
import { StructuredIntakeWizard } from "@/features/projects/structured-intake-wizard";

const emptyStates = [
  { label: "Opportunity Brief", detail: "No brief generated yet.", icon: FileText },
  { label: "Competitors", detail: "No competitors analyzed yet.", icon: Users },
  { label: "Assumptions", detail: "No assumptions extracted yet.", icon: ShieldAlert },
  { label: "Experiments", detail: "No validation plans generated yet.", icon: Beaker },
];

const tabs = ["Overview", "Brief", "Evidence"] as const;
type ProjectTab = (typeof tabs)[number];

export function ProjectOverview() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [activeTab, setActiveTab] = useState<ProjectTab>("Overview");
  const projectQuery = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => getProject(projectId),
  });

  const project = projectQuery.data;

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
                <span className="w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                  {project.status}
                </span>
              </div>
            </header>

            <nav className="mt-5 flex gap-2 border-b border-border" aria-label="Project sections">
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
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">
                    {project.current_thesis?.thesis_text ?? "No thesis recorded yet."}
                  </p>
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
                            <p className="mt-1 text-sm text-muted-foreground">
                              {segment.description ?? "No segment notes yet."}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-lg border border-border bg-white p-5">
                      <h2 className="text-base font-semibold">Problem Hypotheses</h2>
                      <div className="mt-3 space-y-3">
                        {project.problems.map((problem) => (
                          <div key={problem.id}>
                            <div className="text-sm font-medium">{problem.description}</div>
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

                <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {emptyStates.map((item) => {
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
            ) : (
              <EvidenceTab projectId={project.id} />
            )}
          </>
        ) : null}
      </div>
    </main>
  );
}

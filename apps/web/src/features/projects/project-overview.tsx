"use client";

import { ArrowLeft, Beaker, FileText, Library, ShieldAlert, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { getProject } from "@/lib/api";

const emptyStates = [
  { label: "Opportunity Brief", detail: "No brief generated yet.", icon: FileText },
  { label: "Evidence", detail: "No sources added yet.", icon: Library },
  { label: "Competitors", detail: "No competitors analyzed yet.", icon: Users },
  { label: "Assumptions", detail: "No assumptions extracted yet.", icon: ShieldAlert },
  { label: "Experiments", detail: "No validation plans generated yet.", icon: Beaker },
];

export function ProjectOverview() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
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

            <section className="mt-6 rounded-lg border border-border bg-white p-5">
              <h2 className="text-base font-semibold">Current Thesis</h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {project.current_thesis?.thesis_text ?? "No thesis recorded yet."}
              </p>
            </section>

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
        ) : null}
      </div>
    </main>
  );
}

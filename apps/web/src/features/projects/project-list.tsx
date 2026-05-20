"use client";

import { Database, FileText, GitBranch, Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { buttonVariants } from "@/components/ui/button";
import { getMe, listProjects } from "@/lib/api";

const summaryItems = [
  { label: "Evidence Sources", value: "0", icon: Database },
  { label: "Artifacts", value: "0", icon: FileText },
  { label: "Decisions", value: "0", icon: ShieldCheck },
];

export function ProjectList() {
  const meQuery = useQuery({ queryKey: ["me"], queryFn: getMe });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: listProjects });

  const projects = projectsQuery.data ?? [];

  return (
    <main className="min-h-screen">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl">
        <aside className="hidden w-64 border-r border-border bg-white px-5 py-6 md:block">
          <div className="text-sm font-semibold">Thesys</div>
          <nav className="mt-8 space-y-1 text-sm text-muted-foreground">
            <Link className="block rounded-md bg-muted px-3 py-2 text-foreground" href="/projects">
              Projects
            </Link>
            <span className="block rounded-md px-3 py-2 text-muted-foreground">Evidence</span>
            <span className="block rounded-md px-3 py-2 text-muted-foreground">Settings</span>
          </nav>
        </aside>

        <section className="flex-1 px-5 py-6 md:px-8">
          <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {meQuery.data?.workspace.name ?? "Local workspace"}
              </p>
              <h1 className="mt-1 text-2xl font-semibold tracking-normal">Projects</h1>
            </div>
            <Link className={buttonVariants()} href="/projects/new">
              <Plus className="h-4 w-4" aria-hidden="true" />
              New Project
            </Link>
          </header>

          <div className="grid gap-4 py-6 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border border-border bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Projects</span>
                <GitBranch className="h-4 w-4 text-primary" aria-hidden="true" />
              </div>
              <div className="mt-3 text-3xl font-semibold">{projects.length}</div>
            </div>
            {summaryItems.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.label} className="rounded-lg border border-border bg-white p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{item.label}</span>
                    <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                  </div>
                  <div className="mt-3 text-3xl font-semibold">{item.value}</div>
                </div>
              );
            })}
          </div>

          <section className="rounded-lg border border-border bg-white">
            <div className="border-b border-border px-5 py-4">
              <h2 className="text-base font-semibold">Project List</h2>
            </div>

            {projectsQuery.isLoading ? (
              <div className="px-5 py-10 text-sm text-muted-foreground">Loading projects...</div>
            ) : projectsQuery.isError ? (
              <div className="px-5 py-10 text-sm text-red-700">
                {(projectsQuery.error as Error).message}
              </div>
            ) : projects.length === 0 ? (
              <div className="px-5 py-10">
                <p className="text-sm text-muted-foreground">No projects yet.</p>
                <Link
                  className={buttonVariants({ className: "mt-4", variant: "secondary" })}
                  href="/projects/new"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Create Project
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {projects.map((project) => (
                  <Link
                    key={project.id}
                    className="block px-5 py-4 hover:bg-muted"
                    href={`/projects/${project.id}`}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="font-medium">{project.name}</div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {project.short_description ?? "No description"}
                        </div>
                      </div>
                      <span className="w-fit rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                        {project.status}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}

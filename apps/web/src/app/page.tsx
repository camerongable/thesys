import { Activity, Database, FileText, GitBranch, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";

const workspaceItems = [
  { label: "Projects", value: "0", icon: GitBranch },
  { label: "Evidence Sources", value: "0", icon: Database },
  { label: "Artifacts", value: "0", icon: FileText },
  { label: "Decisions", value: "0", icon: ShieldCheck },
];

export default function Home() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl">
        <aside className="hidden w-64 border-r border-border bg-white px-5 py-6 md:block">
          <div className="text-sm font-semibold">Thesys</div>
          <nav className="mt-8 space-y-1 text-sm text-muted-foreground">
            <a className="block rounded-md bg-muted px-3 py-2 text-foreground" href="#">
              Dashboard
            </a>
            <a className="block rounded-md px-3 py-2 hover:bg-muted" href="#">
              Projects
            </a>
            <a className="block rounded-md px-3 py-2 hover:bg-muted" href="#">
              Evidence
            </a>
            <a className="block rounded-md px-3 py-2 hover:bg-muted" href="#">
              Settings
            </a>
          </nav>
        </aside>

        <section className="flex-1 px-5 py-6 md:px-8">
          <header className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Local workspace</p>
              <h1 className="mt-1 text-2xl font-semibold tracking-normal">Thesys</h1>
            </div>
            <Button>
              <Activity className="h-4 w-4" aria-hidden="true" />
              New Project
            </Button>
          </header>

          <div className="grid gap-4 py-6 sm:grid-cols-2 xl:grid-cols-4">
            {workspaceItems.map((item) => {
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

          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <section className="rounded-lg border border-border bg-white p-5">
              <h2 className="text-base font-semibold">Project Graph</h2>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                {["Thesis", "Evidence", "Assumptions", "Experiments", "Decisions", "Artifacts"].map(
                  (node) => (
                    <div
                      key={node}
                      className="rounded-md border border-border px-3 py-3 text-sm text-muted-foreground"
                    >
                      {node}
                    </div>
                  ),
                )}
              </div>
            </section>

            <section className="rounded-lg border border-border bg-white p-5">
              <h2 className="text-base font-semibold">Service Status</h2>
              <div className="mt-5 space-y-3 text-sm">
                {["Web shell", "API healthcheck", "Postgres + pgvector", "Redis", "MinIO", "LiteLLM"].map(
                  (service) => (
                    <div key={service} className="flex items-center justify-between">
                      <span>{service}</span>
                      <span className="rounded-md bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                        Configured
                      </span>
                    </div>
                  ),
                )}
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

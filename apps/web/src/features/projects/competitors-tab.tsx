"use client";

import {
  AlertTriangle,
  ExternalLink,
  Map,
  Plus,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  analyzeCompetitors,
  Artifact,
  Competitor,
  CompetitorAnalysisResult,
  CompetitorCategory,
  createCompetitor,
  listArtifacts,
  listCompetitors,
  listProjectWorkflows,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

type CompetitorsTabProps = {
  projectId: string;
};

const categories: CompetitorCategory[] = [
  "unknown",
  "direct",
  "adjacent",
  "incumbent",
  "substitute",
  "manual_alternative",
];

export function CompetitorsTab({ projectId }: CompetitorsTabProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState<CompetitorCategory>("unknown");

  const competitorsQuery = useQuery({
    queryKey: ["projects", projectId, "competitors"],
    queryFn: () => listCompetitors(projectId),
  });

  const artifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts", "competitor_landscape"],
    queryFn: () => listArtifacts(projectId, "competitor_landscape"),
  });

  const invalidateCompetitorData = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "competitors"] });
    await queryClient.invalidateQueries({
      queryKey: ["projects", projectId, "artifacts", "competitor_landscape"],
    });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "workflows"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createCompetitor(projectId, {
        name,
        url: url.trim().length > 0 ? url : undefined,
        category,
      }),
    onSuccess: async () => {
      setName("");
      setUrl("");
      setCategory("unknown");
      await invalidateCompetitorData();
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeCompetitors(projectId, { ingest_urls: true }),
    onSuccess: invalidateCompetitorData,
  });
  const activeWorkflowQuery = useQuery({
    queryKey: ["projects", projectId, "workflows", "competitor_analysis", "active"],
    queryFn: () => listProjectWorkflows(projectId, 5),
    enabled: analyzeMutation.isPending,
    refetchInterval: analyzeMutation.isPending ? 1000 : false,
  });

  const competitors = analyzeMutation.data?.competitors ?? competitorsQuery.data ?? [];
  const artifacts = artifactsQuery.data ?? [];
  const currentArtifact = analyzeMutation.data?.artifact ?? artifacts[0] ?? null;
  const currentVersion = currentArtifact?.current_version ?? null;
  const unsupportedClaims = unsupportedFromResult(analyzeMutation.data, currentArtifact);
  const claims = analyzeMutation.data?.claims ?? currentVersion?.claims ?? [];
  const activeCompetitorRun = analyzeMutation.isPending
    ? activeWorkflowQuery.data?.find(
        (run) =>
          run.workflow_type === "competitor_analysis" &&
          (run.status === "queued" || run.status === "running"),
      )
    : null;
  const error =
    competitorsQuery.error ??
    artifactsQuery.error ??
    createMutation.error ??
    analyzeMutation.error ??
    null;

  return (
    <section className="mt-6 space-y-6">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Add Competitor</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">Name</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setName(event.target.value)}
              value={name}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-sm font-medium">URL</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com"
              type="url"
              value={url}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-sm font-medium">Category</span>
            <select
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setCategory(event.target.value as CompetitorCategory)}
              value={category}
            >
              {categories.map((item) => (
                <option key={item} value={item}>
                  {formatLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <Button
            className="mt-4"
            disabled={createMutation.isPending || name.trim().length === 0}
            onClick={() => createMutation.mutate()}
            type="button"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            {createMutation.isPending ? "Adding..." : "Add"}
          </Button>
        </div>

        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Map className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-base font-semibold">Landscape</h2>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {currentVersion
                  ? `Current artifact version ${currentVersion.version}.`
                  : "No competitor landscape generated yet."}
              </p>
            </div>
            <Button
              disabled={analyzeMutation.isPending}
              onClick={() => analyzeMutation.mutate()}
              type="button"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              {analyzeMutation.isPending ? "Analyzing..." : "Analyze Competitors"}
            </Button>
          </div>
          {analyzeMutation.data ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Metric label="Sources" value={analyzeMutation.data.ingested_source_count} />
              <Metric label="Retrieved" value={analyzeMutation.data.retrieval_result_count} />
              <Metric label="Profiles" value={analyzeMutation.data.competitors.length} />
            </div>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {readableErrorMessage(error)}
        </div>
      ) : null}

      <WorkflowTrace
        pending={analyzeMutation.isPending}
        pendingSteps={[
          "load_project_state",
          "load_user_seeded_competitors",
          "fetch_competitor_sources",
          "retrieve_competitor_evidence",
          "extract_competitor_profiles",
          "citation_audit",
          "write_competitor_landscape",
        ]}
        runId={analyzeMutation.data?.ai_run_id ?? activeCompetitorRun?.id ?? null}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Profiles</h2>
            </div>
            <span className="text-sm text-muted-foreground">{competitors.length} total</span>
          </div>

          {competitorsQuery.isLoading ? (
            <div className="mt-4 text-sm text-muted-foreground">Loading competitors...</div>
          ) : competitors.length === 0 ? (
            <div className="mt-4 rounded-md border border-dashed border-border p-4">
              <h3 className="text-sm font-semibold">No competitors analyzed yet.</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Competitor analysis helps identify substitutes, crowded areas, positioning
                gaps, and potential wedges.
              </p>
              <Button
                className="mt-3"
                disabled={analyzeMutation.isPending}
                onClick={() => analyzeMutation.mutate()}
                size="sm"
                type="button"
                variant="secondary"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                {analyzeMutation.isPending ? "Analyzing..." : "Analyze Competitors"}
              </Button>
            </div>
          ) : (
            <div className="mt-4 grid gap-4">
              {competitors.map((competitor) => (
                <CompetitorProfile key={competitor.id} competitor={competitor} />
              ))}
            </div>
          )}
        </div>

        <aside className="space-y-5">
          <div className="rounded-lg border border-border bg-white p-5">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Cited Claims</h3>
            </div>
            <div className="mt-4 space-y-3">
              {claims.length === 0 ? (
                <p className="text-sm text-muted-foreground">No claims recorded.</p>
              ) : (
                claims.map((claim) => (
                  <div key={claim.id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        {claim.support_level}
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
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-white p-5">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Unsupported Claims</h3>
            </div>
            <div className="mt-4 space-y-2">
              {unsupportedClaims.length === 0 ? (
                <p className="text-sm text-muted-foreground">None recorded.</p>
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
          </div>

          {currentVersion ? (
            <div className="rounded-lg border border-border bg-white p-5">
              <h3 className="text-sm font-semibold">Artifact</h3>
              <div className="mt-4 max-h-96 overflow-auto rounded-md bg-muted p-3">
                <MarkdownContent
                  className="space-y-3 text-sm leading-6 text-foreground"
                  markdown={currentVersion.markdown_content}
                />
              </div>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

function CompetitorProfile({ competitor }: { competitor: Competitor }) {
  return (
    <div className="rounded-md border border-border p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{competitor.name}</h3>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {formatLabel(competitor.category)}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              threat {competitor.threat_level}
            </span>
          </div>
          {competitor.url ? (
            <a
              className="mt-2 inline-flex max-w-full items-center gap-1 truncate text-sm text-primary hover:underline"
              href={competitor.url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span className="truncate">{competitor.url}</span>
            </a>
          ) : null}
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {competitor.evidence_links.length} source
          {competitor.evidence_links.length === 1 ? "" : "s"}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <ProfileBlock title="Positioning" value={competitor.positioning} />
        <ProfileBlock title="Pricing" value={competitor.pricing_summary} />
        <ProfileBlock title="Strengths" value={competitor.strengths} />
        <ProfileBlock title="Weaknesses" value={competitor.weaknesses} />
      </div>

      {competitor.key_features.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {competitor.key_features.map((feature) => (
            <span
              className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
              key={feature}
            >
              {feature}
            </span>
          ))}
        </div>
      ) : null}

      {competitor.differentiation_notes ? (
        <MarkdownContent
          className="mt-4 space-y-2 text-sm leading-6 text-muted-foreground"
          markdown={competitor.differentiation_notes}
        />
      ) : null}
    </div>
  );
}

function ProfileBlock({ title, value }: { title: string; value: string | null }) {
  return (
    <div>
      <h4 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
        {title}
      </h4>
      <MarkdownContent
        className="mt-1 space-y-2 text-sm leading-6 text-muted-foreground"
        markdown={value ?? "Unknown"}
      />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}

function unsupportedFromResult(
  result: CompetitorAnalysisResult | undefined,
  artifact: Artifact | null,
) {
  if (result) {
    return result.unsupported_claims;
  }
  const unsupported = artifact?.current_version?.structured_content.unsupported_claims;
  return Array.isArray(unsupported) ? unsupported.filter((item) => typeof item === "string") : [];
}

function readableErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("Structured output generation failed")) {
    return "Structured output generation failed. The local model returned malformed JSON; retry the analysis, or switch to a stronger model if it repeats.";
  }
  return message;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

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
  const [selectedCompetitorId, setSelectedCompetitorId] = useState<string | null>(null);

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
  const selectedCompetitor =
    competitors.find((competitor) => competitor.id === selectedCompetitorId) ??
    competitors[0] ??
    null;
  const directCount = competitors.filter((competitor) => competitor.category === "direct").length;
  const substituteCount = competitors.filter(
    (competitor) =>
      competitor.category === "substitute" || competitor.category === "manual_alternative",
  ).length;
  const highThreatCount = competitors.filter(
    (competitor) => competitor.threat_level === "high",
  ).length;
  const selectCompetitor = (competitorId: string) => {
    setSelectedCompetitorId(competitorId);
    if (window.innerWidth < 1024) {
      window.requestAnimationFrame(() => {
        document
          .getElementById("competitor-detail-panel")
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  };
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
      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Competitors
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-normal">
              Who are we up against?
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Scan competitors, substitutes, and adjacent alternatives by category. The goal
              is to identify crowded areas and the strongest wedge.
            </p>
          </div>
          <Button
            className="w-full whitespace-nowrap sm:w-64"
            disabled={analyzeMutation.isPending}
            onClick={() => analyzeMutation.mutate()}
            type="button"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {analyzeMutation.isPending ? "Analyzing..." : "Analyze Landscape"}
          </Button>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          <Metric label="Competitors" value={competitors.length} />
          <Metric label="Direct" value={directCount} />
          <Metric label="Substitutes" value={substituteCount} />
          <Metric label="High threat" value={highThreatCount} />
        </div>
        {currentVersion || competitors.length > 0 ? (
          <div className="mt-5 grid gap-4 rounded-md border border-border bg-muted/50 p-4 lg:grid-cols-2">
            <div>
              <div className="flex items-center gap-2">
                <Map className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Competitor Landscape Summary</h3>
              </div>
              {currentVersion ? (
                <MarkdownContent
                  className="mt-2 line-clamp-5 space-y-2 text-sm leading-6 text-muted-foreground"
                  markdown={firstMeaningfulParagraph(currentVersion.markdown_content)}
                />
              ) : (
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  The page has competitors recorded, but no synthesized landscape memo yet.
                  Analyze the landscape to turn profiles into a strategic read.
                </p>
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold">Strategic Implication</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {competitorImplication(competitors)}
              </p>
            </div>
          </div>
        ) : null}
      </div>

      <details className="rounded-lg border border-border bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold">Add competitor manually</summary>
        <div className="mt-5 border-t border-border pt-5">
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
      </details>

      {error ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {readableErrorMessage(error)}
        </div>
      ) : null}

      <details className="rounded-lg border border-border bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold">View research trace</summary>
        <div className="mt-4 border-t border-border pt-4">
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
        </div>
      </details>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Grouped Competitors</h2>
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
                {analyzeMutation.isPending ? "Analyzing..." : "Analyze Landscape"}
              </Button>
            </div>
          ) : (
            <CompetitorGroups
              competitors={competitors}
              onSelect={selectCompetitor}
              selectedCompetitorId={selectedCompetitor?.id ?? null}
            />
          )}
        </div>

        <aside className="self-start space-y-5 lg:sticky lg:top-4">
          <CompetitorDetailPanel competitor={selectedCompetitor} />

          <details className="rounded-lg border border-border bg-white p-5">
            <summary className="cursor-pointer list-none">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
                  <h3 className="text-sm font-semibold">Supported Findings</h3>
                </div>
                <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                  {claims.length}
                </span>
              </div>
            </summary>
            <div className="mt-4 space-y-3">
              {claims.length === 0 ? (
                <p className="text-sm text-muted-foreground">No supported findings recorded.</p>
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
          </details>

          <details className="rounded-lg border border-border bg-white p-5">
            <summary className="cursor-pointer list-none">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-primary" aria-hidden="true" />
                  <h3 className="text-sm font-semibold">Open Questions</h3>
                </div>
                <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                  {unsupportedClaims.length}
                </span>
              </div>
            </summary>
            <div className="mt-4 space-y-2">
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

          {currentVersion ? (
            <div className="rounded-lg border border-border bg-white p-5">
              <h3 className="text-sm font-semibold">Full Landscape Details</h3>
              <details className="mt-4 rounded-md bg-muted p-3">
                <summary className="cursor-pointer text-sm font-medium">Show generated analysis</summary>
                <MarkdownContent
                  className="mt-3 max-h-96 space-y-3 overflow-auto text-sm leading-6 text-foreground"
                  markdown={currentVersion.markdown_content}
                />
              </details>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

function CompetitorGroups({
  competitors,
  onSelect,
  selectedCompetitorId,
}: {
  competitors: Competitor[];
  onSelect: (competitorId: string) => void;
  selectedCompetitorId: string | null;
}) {
  const groups: Array<[string, Competitor[]]> = [
    ["Direct Competitors", competitors.filter((item) => item.category === "direct")],
    [
      "Substitute Behaviors",
      competitors.filter(
        (item) => item.category === "substitute" || item.category === "manual_alternative",
      ),
    ],
    ["Incumbent Platforms", competitors.filter((item) => item.category === "incumbent")],
    ["Adjacent Solutions", competitors.filter((item) => item.category === "adjacent")],
    ["Unknown / Needs Review", competitors.filter((item) => item.category === "unknown")],
  ];
  return (
    <div className="mt-4 space-y-5">
      {groups
        .filter(([, items]) => items.length > 0)
        .map(([label, items]) => (
          <section key={label}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">{label}</h3>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {items.length}
              </span>
            </div>
            <div className="mt-3 grid gap-3">
              {items.map((competitor) => (
                <CompetitorProfile
                  competitor={competitor}
                  key={competitor.id}
                  onSelect={() => onSelect(competitor.id)}
                  selected={selectedCompetitorId === competitor.id}
                />
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}

function CompetitorProfile({
  competitor,
  onSelect,
  selected,
}: {
  competitor: Competitor;
  onSelect: () => void;
  selected: boolean;
}) {
  return (
    <details
      className={
        selected
          ? "rounded-md border border-action bg-action/10 p-4"
          : "rounded-md border border-border p-4"
      }
    >
      <summary className="cursor-pointer list-none" onClick={onSelect}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold">{competitorDisplayName(competitor)}</h3>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {formatLabel(competitor.category)}
              </span>
              <span className={threatBadgeClass(competitor.threat_level)}>
                threat {competitor.threat_level}
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {competitor.evidence_links.length} source
              {competitor.evidence_links.length === 1 ? "" : "s"}
            </span>
            <button
              className="text-xs font-medium text-primary hover:underline"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onSelect();
              }}
              type="button"
            >
              View detail
            </button>
            <span className="text-xs font-medium text-muted-foreground">Expand profile</span>
          </div>
        </div>
      </summary>

      <div className="mt-4 border-t border-border pt-4">
        {competitor.url ? (
          <a
            className="inline-flex max-w-full items-center gap-1 truncate text-sm text-primary hover:underline"
            href={competitor.url}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{competitor.url}</span>
          </a>
        ) : null}

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
    </details>
  );
}

function CompetitorDetailPanel({ competitor }: { competitor: Competitor | null }) {
  if (!competitor) {
    return (
      <div
        className="rounded-lg border border-dashed border-border bg-white p-5"
        id="competitor-detail-panel"
      >
        <h3 className="text-sm font-semibold">Competitor detail</h3>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Select a competitor to review positioning, target user, threat level, and evidence.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-white p-5" id="competitor-detail-panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
            Competitor detail
          </p>
          <h3 className="mt-2 text-base font-semibold">{competitorDisplayName(competitor)}</h3>
        </div>
        <span className={threatBadgeClass(competitor.threat_level)}>
          {competitor.threat_level} threat
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <DetailMetric label="Category" value={formatLabel(competitor.category)} />
        <DetailMetric label="Sources" value={String(competitor.evidence_links.length)} />
        <DetailMetric label="Watchlist" value={formatLabel(competitor.watchlist_status)} />
        <DetailMetric
          label="Analyzed"
          value={competitor.last_analyzed_at ? new Date(competitor.last_analyzed_at).toLocaleDateString() : "Unknown"}
        />
      </div>

      {competitor.url ? (
        <a
          className="mt-4 inline-flex max-w-full items-center gap-1 truncate text-sm text-primary hover:underline"
          href={competitor.url}
          rel="noreferrer"
          target="_blank"
        >
          <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="truncate">{competitor.url}</span>
        </a>
      ) : null}

      <div className="mt-4 space-y-4 border-t border-border pt-4">
        <ProfileBlock title="Target User" value={competitor.target_user} />
        <ProfileBlock title="Positioning" value={competitor.positioning} />
        <ProfileBlock title="Why it matters" value={competitor.differentiation_notes} />
      </div>
    </div>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-muted px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
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

function threatBadgeClass(value: string) {
  if (value === "high") {
    return "rounded-md bg-red-50 px-2 py-1 text-xs text-red-700";
  }
  if (value === "medium") {
    return "rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-700";
  }
  return "rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-700";
}

function firstMeaningfulParagraph(markdown: string) {
  const paragraph = markdown
    .split(/\n\s*\n/)
    .map((part) => part.replace(/^#{1,3}\s+/gm, "").trim())
    .find((part) => part.length > 40);
  return paragraph ?? markdown;
}

function competitorImplication(competitors: Competitor[]) {
  if (competitors.length === 0) {
    return "No landscape has been established yet. Run competitor analysis before making a build decision.";
  }
  const substituteCount = competitors.filter(
    (competitor) =>
      competitor.category === "substitute" || competitor.category === "manual_alternative",
  ).length;
  const highThreatCount = competitors.filter(
    (competitor) => competitor.threat_level === "high",
  ).length;
  if (substituteCount > 0) {
    return "The hardest competitor may be the current workaround, not another startup. Validate that users will switch from existing tools or manual behavior before building more product.";
  }
  if (highThreatCount > 0) {
    return "High-threat alternatives are already present. The wedge needs to be narrow enough that the product is chosen for a specific painful job, not as a broad replacement.";
  }
  return "The landscape does not yet show a clear blocker, but switching behavior and willingness to pay still need evidence before proceeding.";
}

function competitorDisplayName(competitor: Competitor) {
  const name = competitor.name.trim();
  const normalized = name.toLowerCase();
  if (normalized.includes("demand") && normalized.includes("plant")) {
    if (normalized.includes("social") || normalized.includes("educational")) {
      return "Local plant workshops and plant communities";
    }
    return "Plant-care content and community substitutes";
  }
  if (normalized.includes("social-educational")) {
    return "Social learning communities";
  }
  if (normalized.includes("manual") || competitor.category === "manual_alternative") {
    return name.includes("plus") ? name : "Manual workflow and existing workaround";
  }
  if (normalized.includes("chatgpt") || normalized.includes("perplexity")) {
    return name;
  }
  return name;
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

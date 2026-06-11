"use client";

import {
  Database,
  FileUp,
  Link as LinkIcon,
  RefreshCw,
  Search,
  Trash2,
  Type,
} from "lucide-react";
import { ChangeEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import {
  addEvidenceNote,
  addEvidenceUrl,
  Claim,
  deleteEvidenceSource,
  EvidenceSource,
  getProjectOverview,
  listArtifacts,
  listEvidenceSources,
  RetrievalMode,
  retrieveEvidence,
  reprocessEvidenceSource,
  uploadEvidenceFile,
} from "@/lib/api";

type EvidenceTabProps = {
  projectId: string;
};

export function EvidenceTab({ projectId }: EvidenceTabProps) {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState("");
  const [urlTitle, setUrlTitle] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteText, setNoteText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>("hybrid");
  const [sourceFilter, setSourceFilter] = useState<"all" | EvidenceSource["source_type"]>("all");
  const [sourceSearch, setSourceSearch] = useState("");
  const [showAllSources, setShowAllSources] = useState(false);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["projects", projectId, "evidence"],
    queryFn: () => listEvidenceSources(projectId),
  });
  const overviewQuery = useQuery({
    queryKey: ["projects", projectId, "overview", "evidence-health"],
    queryFn: () => getProjectOverview(projectId),
  });
  const artifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts", "evidence-claims"],
    queryFn: () => listArtifacts(projectId),
  });

  const invalidateSources = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evidence"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
  };

  const urlMutation = useMutation({
    mutationFn: () =>
      addEvidenceUrl(projectId, {
        url,
        title: urlTitle.trim().length > 0 ? urlTitle : undefined,
      }),
    onSuccess: async () => {
      setUrl("");
      setUrlTitle("");
      await invalidateSources();
    },
  });

  const noteMutation = useMutation({
    mutationFn: () => addEvidenceNote(projectId, { title: noteTitle, text: noteText }),
    onSuccess: async () => {
      setNoteTitle("");
      setNoteText("");
      await invalidateSources();
    },
  });

  const fileMutation = useMutation({
    mutationFn: () => uploadEvidenceFile(projectId, file as File),
    onSuccess: async () => {
      setFile(null);
      await invalidateSources();
    },
  });

  const retrievalMutation = useMutation({
    mutationFn: () =>
      retrieveEvidence(projectId, {
        query: retrievalQuery,
        mode: retrievalMode,
        top_k: 8,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => deleteEvidenceSource(projectId, sourceId),
    onSuccess: invalidateSources,
  });

  const reprocessMutation = useMutation({
    mutationFn: (sourceId: string) => reprocessEvidenceSource(projectId, sourceId),
    onSuccess: invalidateSources,
  });

  const pending =
    urlMutation.isPending || noteMutation.isPending || fileMutation.isPending;
  const error =
    urlMutation.error ??
    noteMutation.error ??
    fileMutation.error ??
    retrievalMutation.error ??
    deleteMutation.error ??
    reprocessMutation.error ??
    null;
  const sources = sourcesQuery.data ?? [];
  const visibleSources = sources.filter((source) => {
    const matchesFilter = sourceFilter === "all" || source.source_type === sourceFilter;
    const search = sourceSearch.trim().toLowerCase();
    const matchesSearch =
      search.length === 0 ||
      [source.title, source.url, source.summary, source.classification]
        .filter(Boolean)
        .some((value) => value?.toLowerCase().includes(search));
    return matchesFilter && matchesSearch;
  });
  const displayedSources = showAllSources ? visibleSources : visibleSources.slice(0, 8);
  const hiddenSourceCount = visibleSources.length - displayedSources.length;
  const health = overviewQuery.data?.evidence_health;
  const selectedSource = sources.find((source) => source.id === selectedSourceId) ?? null;
  const artifactClaims =
    artifactsQuery.data?.flatMap((artifact) => artifact.current_version?.claims ?? []) ?? [];
  const citedClaims = artifactClaims.filter((claim) => claim.support_level !== "unsupported");
  const unsupportedClaims = [
    ...artifactClaims
      .filter((claim) => claim.support_level === "unsupported")
      .map((claim) => claim.text),
    ...(artifactsQuery.data?.flatMap((artifact) =>
      stringsFromUnknown(artifact.current_version?.structured_content.unsupported_claims),
    ) ?? []),
  ];

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
  }

  function openAddEvidence() {
    const panel = document.getElementById("add-evidence-panel");
    panel?.setAttribute("open", "true");
    panel?.scrollIntoView();
  }

  return (
    <section className="mt-6 space-y-6">
      <DomainHeader
        action={
          <Button onClick={openAddEvidence} type="button">
            <LinkIcon className="h-4 w-4" aria-hidden="true" />
            Add source
          </Button>
        }
        description="Keep the idea tied to source-backed claims. Start with what is cited, then open raw chunks only when the decision needs a receipt."
        icon={<Database className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="What can we cite before deciding?"
        signals={[
          { label: "Sources", value: health?.source_count ?? sources.length },
          { label: "Competitors", value: health?.competitor_count ?? 0 },
          { label: "Supported findings", value: health?.cited_claim_count ?? 0 },
          {
            label: "Open questions",
            tone: health && health.unsupported_claim_count > 0 ? "warning" : "neutral",
            value: health?.unsupported_claim_count ?? 0,
          },
          { label: "Weakest area", value: health?.weakest_evidence_area ?? "Unknown" },
        ]}
        title="Evidence"
      />

      <EvidenceFindingsPanel
        citedClaims={citedClaims}
        health={health}
        onAddEvidence={openAddEvidence}
        sourceCount={sources.length}
        unsupportedClaims={unsupportedClaims}
      />

      <details id="add-evidence-panel" className="rounded-lg border border-border bg-card p-5">
        <summary className="cursor-pointer text-sm font-semibold">
          Add source manually
        </summary>
      <div className="mt-5 grid gap-5 border-t border-border pt-5 lg:grid-cols-3 lg:divide-x lg:divide-border">
        <div className="self-start lg:pr-5">
          <div className="flex items-center gap-2">
            <LinkIcon className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Add source URL</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">URL</span>
            <input
              id="evidence-url"
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com"
              type="url"
              value={url}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-sm font-medium">Source title</span>
            <input
              id="evidence-note-title"
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setUrlTitle(event.target.value)}
              value={urlTitle}
            />
          </label>
          <Button
            className="mt-4"
            disabled={pending || url.trim().length === 0}
            onClick={() => urlMutation.mutate()}
            type="button"
          >
            <LinkIcon className="h-4 w-4" aria-hidden="true" />
            {urlMutation.isPending ? "Adding URL..." : "Add source URL"}
          </Button>
        </div>

        <div className="border-t border-border pt-5 lg:border-t-0 lg:px-5 lg:pt-0">
          <div className="flex items-center gap-2">
            <Type className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Add evidence note</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">Note title</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setNoteTitle(event.target.value)}
              value={noteTitle}
            />
          </label>
          <label className="mt-3 block">
                <span className="text-sm font-medium">Note text</span>
            <textarea
              className="mt-2 min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setNoteText(event.target.value)}
              value={noteText}
            />
          </label>
          <Button
            className="mt-4"
            disabled={pending || noteTitle.trim().length === 0 || noteText.trim().length === 0}
            onClick={() => noteMutation.mutate()}
            type="button"
          >
            <Type className="h-4 w-4" aria-hidden="true" />
            {noteMutation.isPending ? "Adding note..." : "Add evidence note"}
          </Button>
        </div>

        <div className="border-t border-border pt-5 lg:border-t-0 lg:pl-5 lg:pt-0">
          <div className="flex items-center gap-2">
            <FileUp className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Upload evidence file</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">PDF, text, or Markdown</span>
            <input
              accept=".pdf,.txt,.md,.markdown,text/plain,text/markdown,application/pdf"
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-1 file:text-sm"
              onChange={handleFileChange}
              type="file"
            />
          </label>
          <Button
            className="mt-4"
            disabled={pending || !file}
            onClick={() => fileMutation.mutate()}
            type="button"
          >
            <FileUp className="h-4 w-4" aria-hidden="true" />
            {fileMutation.isPending ? "Uploading file..." : "Upload file"}
          </Button>
        </div>
      </div>
      </details>

      {error ? (
        <DomainError message={(error as Error).message} />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <DomainPanel className="self-start">
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Evidence sources</h2>
            </div>
            <span className="text-sm text-muted-foreground">{sources.length} total</span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]">
            <input
              className="rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setSourceSearch(event.target.value)}
              placeholder="Search sources"
              value={sourceSearch}
            />
            <select
              className="rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) =>
                setSourceFilter(event.target.value as "all" | EvidenceSource["source_type"])
              }
              value={sourceFilter}
            >
              <option value="all">All types</option>
              <option value="url">URLs</option>
              <option value="file">Files</option>
              <option value="note">Notes</option>
              <option value="transcript">Transcripts</option>
              <option value="manual">Manual</option>
            </select>
          </div>

          {sourcesQuery.isLoading ? (
            <div className="mt-4 text-sm text-muted-foreground">Loading sources...</div>
          ) : sourcesQuery.isError ? (
            <DomainError message={(sourcesQuery.error as Error).message} />
          ) : sources.length === 0 ? (
            <div className="mt-4 border-t border-dashed border-border pt-4">
              <h3 className="text-sm font-semibold">No sources yet.</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Evidence keeps this from becoming generic AI advice. Plan an evidence review
                or add competitor pages, customer notes, market research, reviews, forum
                threads, or interview notes.
              </p>
              <Button
                className="mt-3"
                onClick={openAddEvidence}
                size="sm"
                type="button"
                variant="secondary"
              >
                <LinkIcon className="h-4 w-4" aria-hidden="true" />
                Add source
              </Button>
            </div>
          ) : (
            <div className="mt-4 divide-y divide-border">
              {displayedSources.map((source) => (
                <SourceRow
                  deletePending={deleteMutation.isPending}
                  key={source.id}
                  onDelete={() => deleteMutation.mutate(source.id)}
                  onReprocess={() => reprocessMutation.mutate(source.id)}
                  onSelect={() => setSelectedSourceId(source.id)}
                  reprocessPending={reprocessMutation.isPending}
                  selected={source.id === selectedSourceId}
                  source={source}
                />
              ))}
              {hiddenSourceCount > 0 ? (
                <div className="pt-4">
                  <Button
                    onClick={() => setShowAllSources(true)}
                    size="sm"
                    type="button"
                    variant="secondary"
                  >
                    Show {hiddenSourceCount} more sources
                  </Button>
                </div>
              ) : showAllSources && visibleSources.length > 8 ? (
                <div className="pt-4">
                  <Button
                    onClick={() => setShowAllSources(false)}
                    size="sm"
                    type="button"
                    variant="secondary"
                  >
                    Show fewer sources
                  </Button>
                </div>
              ) : null}
              {visibleSources.length === 0 ? (
                <p className="py-4 text-sm text-muted-foreground">
                  No sources match the current filters.
                </p>
              ) : null}
            </div>
          )}
        </DomainPanel>

        <aside className="self-start space-y-4">
          <SourceDetailPanel source={selectedSource} />
          <ClaimsPanel citedClaims={citedClaims} unsupportedClaims={unsupportedClaims} />
          <details className="rounded-lg border border-border bg-card p-5">
            <summary className="cursor-pointer list-none">
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-base font-semibold">Search source chunks</h2>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Search stored source text when you need to inspect retrieval details.
              </p>
            </summary>
          <label className="mt-4 block border-t border-border pt-4">
              <span className="text-sm font-medium">Search query</span>
              <textarea
                className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                onChange={(event) => setRetrievalQuery(event.target.value)}
                value={retrievalQuery}
              />
            </label>
            <label className="mt-3 block">
              <span className="text-sm font-medium">Mode</span>
              <select
                className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                onChange={(event) => setRetrievalMode(event.target.value as RetrievalMode)}
                value={retrievalMode}
              >
                <option value="hybrid">Hybrid</option>
                <option value="semantic">Semantic</option>
                <option value="keyword">Keyword</option>
              </select>
            </label>
            <Button
              className="mt-4 w-full"
              disabled={retrievalMutation.isPending || retrievalQuery.trim().length === 0}
              onClick={() => retrievalMutation.mutate()}
              type="button"
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              {retrievalMutation.isPending ? "Searching sources..." : "Search sources"}
            </Button>

            {retrievalMutation.data ? (
              <div className="mt-5 divide-y divide-border">
                {retrievalMutation.data.results.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No matching chunks.</p>
                ) : (
                  retrievalMutation.data.results.map((result) => (
                    <details key={result.chunk_id} className="py-3 first:pt-0">
                      <summary className="cursor-pointer list-none">
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-medium text-foreground">
                            {result.title ?? "Untitled"}
                          </span>
                          <span>{result.source_type}</span>
                          <span>score {result.score.toFixed(2)}</span>
                        </div>
                      </summary>
                      <p className="mt-2 border-t border-border pt-2 text-sm leading-6 text-muted-foreground">
                        {truncate(result.text, 440)}
                      </p>
                    </details>
                  ))
                )}
              </div>
            ) : null}
          </details>
        </aside>
      </div>
    </section>
  );
}

function EvidenceFindingsPanel({
  citedClaims,
  health,
  onAddEvidence,
  sourceCount,
  unsupportedClaims,
}: {
  citedClaims: Claim[];
  health: NonNullable<Awaited<ReturnType<typeof getProjectOverview>>>["evidence_health"] | undefined;
  onAddEvidence: () => void;
  sourceCount: number;
  unsupportedClaims: string[];
}) {
  const supportedClaims = citedClaims.slice(0, 4);
  const weakClaims = unsupportedClaims.slice(0, 3);
  const summarySourceCount = health?.source_count ?? sourceCount;
  const supportedCount = health?.cited_claim_count ?? citedClaims.length;
  const openCount = health?.unsupported_claim_count ?? unsupportedClaims.length;
  const hasEvidence = summarySourceCount > 0 || supportedCount > 0 || openCount > 0;

  return (
    <DomainPanel>
      <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">Supported findings</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Start with what the sources support. Open source details only when you need the
            underlying receipt.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          <span className="rounded-md bg-muted px-2 py-1">{summarySourceCount} sources</span>
          <span className="rounded-md bg-muted px-2 py-1">{supportedCount} supported</span>
          <span className="rounded-md bg-muted px-2 py-1">{openCount} open</span>
        </div>
      </div>

      {!hasEvidence ? (
        <div className="mt-4 border-t border-dashed border-border pt-4">
          <h4 className="text-sm font-semibold">No supported findings yet.</h4>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Add sources or plan an evidence review so recommendations can point back to concrete
            evidence.
          </p>
          <Button className="mt-3" onClick={onAddEvidence} size="sm" type="button" variant="secondary">
            <LinkIcon className="h-4 w-4" aria-hidden="true" />
            Add source
          </Button>
        </div>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="min-w-0">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold text-muted-foreground">
                Supported findings
              </h4>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                top {supportedClaims.length}
              </span>
            </div>
            <div className="mt-3 divide-y divide-border">
              {supportedClaims.length === 0 ? (
                <p className="py-3 text-sm text-muted-foreground">No supported findings recorded yet.</p>
              ) : (
                supportedClaims.map((claim) => (
                  <div className="py-3" key={claim.id}>
                    <p className="text-xs font-medium text-muted-foreground">
                      Finding
                    </p>
                    <p className="mt-1 text-sm font-semibold leading-6 text-foreground">
                      {findingHeadline(claim.text)}
                    </p>
                    <p className="mt-2 text-xs font-medium text-muted-foreground">
                      Evidence
                    </p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{claim.text}</p>
                    <p className="mt-2 text-xs font-medium text-muted-foreground">
                      Implication
                    </p>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {findingImplication(claim.text)}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span className="rounded-md bg-muted px-2 py-1">
                        {claim.support_level}
                      </span>
                      <span>
                        {claim.evidence_links.length} citation
                        {claim.evidence_links.length === 1 ? "" : "s"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <aside className="border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
            <h4 className="text-sm font-semibold">Evidence health</h4>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <HealthMetric label="Sources" value={String(health?.source_count ?? sourceCount)} />
              <HealthMetric label="Competitors" value={String(health?.competitor_count ?? 0)} />
              <HealthMetric label="Supported" value={String(health?.cited_claim_count ?? citedClaims.length)} />
              <HealthMetric label="Open" value={String(health?.unsupported_claim_count ?? unsupportedClaims.length)} />
            </dl>
            <div className="mt-4 border-t border-border pt-4">
            <h5 className="text-xs font-medium text-muted-foreground">
                Weakest area
              </h5>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {health?.weakest_evidence_area ?? "Not enough evidence to identify a weak area."}
              </p>
            </div>
            <div className="mt-4 border-t border-border pt-4">
              <h5 className="text-sm font-semibold">Open questions / evidence gaps</h5>
              <div className="mt-3 divide-y divide-border">
                {weakClaims.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No open questions recorded.</p>
                ) : (
                  weakClaims.map((claim) => (
                    <div className="py-3 first:pt-0" key={claim}>
                      <p className="text-xs font-medium text-muted-foreground">
                        Open question
                      </p>
                      <p className="mt-1 text-sm font-semibold leading-6 text-foreground">
                        {claim}
                      </p>
                      <p className="mt-2 text-xs font-medium text-muted-foreground">
                        Why it matters
                      </p>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">
                        This is a decision risk until evidence proves or weakens it.
                      </p>
                      <p className="mt-2 text-xs font-medium text-muted-foreground">
                        Recommended evidence
                      </p>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">
                        Run customer interviews, pricing tests, or source discovery targeted at this question.
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </aside>
        </div>
      )}
    </DomainPanel>
  );
}

function findingHeadline(text: string) {
  const sentence = text.split(/[.!?]/).find((part) => part.trim().length > 0)?.trim();
  return sentence && sentence.length <= 90 ? sentence : truncate(sentence ?? text, 90);
}

function findingImplication(text: string) {
  const lower = text.toLowerCase();
  if (lower.includes("pay") || lower.includes("pricing") || lower.includes("willingness")) {
    return "Treat willingness to pay as the next proof target before building more product.";
  }
  if (lower.includes("competitor") || lower.includes("substitute") || lower.includes("alternative")) {
    return "Position against the existing workaround, not only direct product competitors.";
  }
  if (lower.includes("trust") || lower.includes("rationale")) {
    return "The product must show why the recommendation is credible, not just generate an answer.";
  }
  return "Use this finding to narrow the next validation question and avoid broad build scope.";
}

function HealthMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-semibold">{value}</dd>
    </div>
  );
}

function SourceDetailPanel({ source }: { source: EvidenceSource | null }) {
  return (
    <DomainPanel>
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-primary" aria-hidden="true" />
        <h2 className="text-base font-semibold">Source Detail</h2>
      </div>
      {!source ? (
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Select a source to inspect its summary, provenance, status, and preview. Raw text
          stays hidden until you ask for details.
        </p>
      ) : (
        <div className="mt-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
              {source.source_type}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
              {source.ingestion_status}
            </span>
            {source.classification ? (
              <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                {source.classification}
              </span>
            ) : null}
          </div>
          <h3 className="mt-3 text-sm font-semibold">{source.title ?? "Untitled source"}</h3>
          {source.url ? (
            <a
              className="mt-2 block break-all text-xs text-primary hover:underline"
              href={source.url}
              rel="noreferrer"
              target="_blank"
            >
              {source.url}
            </a>
          ) : null}
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {source.summary ?? source.text_preview ?? "No summary available."}
          </p>
          <details className="mt-3 border-t border-border pt-3">
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
              Show source preview
            </summary>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {source.text_preview ?? "No preview available."}
            </p>
          </details>
        </div>
      )}
    </DomainPanel>
  );
}

function ClaimsPanel({
  citedClaims,
  unsupportedClaims,
}: {
  citedClaims: Claim[];
  unsupportedClaims: string[];
}) {
  return (
    <DomainPanel>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Findings and Open Questions</h2>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {citedClaims.length} supported
        </span>
      </div>
      <details className="mt-4 border-t border-border pt-3" open={citedClaims.length > 0}>
        <summary className="cursor-pointer text-sm font-medium">Supported Findings</summary>
        <div className="mt-3 max-h-72 space-y-3 overflow-auto border-t border-border pt-3">
          {citedClaims.length === 0 ? (
            <p className="text-sm text-muted-foreground">No supported findings recorded yet.</p>
          ) : (
            citedClaims.slice(0, 8).map((claim) => (
              <div key={claim.id} className="border-b border-border pb-3 last:border-b-0">
                <p className="text-sm leading-6 text-muted-foreground">{claim.text}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {claim.evidence_links.length} citation
                  {claim.evidence_links.length === 1 ? "" : "s"}
                </p>
              </div>
            ))
          )}
        </div>
      </details>
      <details className="mt-3 border-t border-border pt-3">
        <summary className="cursor-pointer text-sm font-medium">Open Questions</summary>
        <div className="mt-3 max-h-72 space-y-2 overflow-auto border-t border-border pt-3">
          {unsupportedClaims.length === 0 ? (
            <p className="text-sm text-muted-foreground">No open questions recorded.</p>
          ) : (
            unsupportedClaims.slice(0, 8).map((claim) => (
              <p className="text-sm leading-6 text-muted-foreground" key={claim}>
                {claim}
              </p>
            ))
          )}
        </div>
      </details>
    </DomainPanel>
  );
}

function SourceRow({
  source,
  onDelete,
  onReprocess,
  onSelect,
  deletePending,
  reprocessPending,
  selected,
}: {
  source: EvidenceSource;
  onDelete: () => void;
  onReprocess: () => void;
  onSelect: () => void;
  deletePending: boolean;
  reprocessPending: boolean;
  selected: boolean;
}) {
  return (
    <details className={selected ? "bg-success-muted px-3 py-4" : "py-4"}>
      <summary className="cursor-pointer list-none">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="line-clamp-2 text-sm font-semibold">{source.title ?? "Untitled source"}</h3>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {source.source_type}
            </span>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {source.ingestion_status}
            </span>
            {source.classification ? (
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {source.classification}
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {source.chunk_count} {source.chunk_count === 1 ? "chunk" : "chunks"}
          </p>
        </div>
        <button
          className="shrink-0 text-xs font-medium text-primary hover:underline"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onSelect();
          }}
          type="button"
        >
          Open details
        </button>
      </div>
      </summary>
      <div className="mt-4 border-t border-border pt-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h4 className="text-xs font-medium text-muted-foreground">
              Source Details
            </h4>
            {source.url ? (
              <a
                className="mt-2 block truncate text-sm text-primary hover:underline"
                href={source.url}
                rel="noreferrer"
                target="_blank"
              >
                {source.url}
              </a>
            ) : null}
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {source.text_preview ?? source.summary ?? "No preview available."}
            </p>
            {source.ingestion_error ? (
              <p className="mt-2 text-sm text-danger-foreground">{source.ingestion_error}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-2">
          <Button
            disabled={reprocessPending}
            onClick={onReprocess}
            size="sm"
            type="button"
            variant="secondary"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Reprocess
          </Button>
          <Button
            disabled={deletePending}
            onClick={onDelete}
            size="sm"
            type="button"
            variant="secondary"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Delete
          </Button>
          </div>
        </div>
      </div>
    </details>
  );
}

function truncate(value: string, maxLength: number) {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

function stringsFromUnknown(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

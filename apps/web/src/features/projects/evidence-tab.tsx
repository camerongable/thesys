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
import {
  addEvidenceNote,
  addEvidenceUrl,
  deleteEvidenceSource,
  EvidenceSource,
  getProjectOverview,
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

  const sourcesQuery = useQuery({
    queryKey: ["projects", projectId, "evidence"],
    queryFn: () => listEvidenceSources(projectId),
  });
  const overviewQuery = useQuery({
    queryKey: ["projects", projectId, "overview", "evidence-health"],
    queryFn: () => getProjectOverview(projectId),
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
      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Evidence
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-normal">
              What sources support the analysis?
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Evidence keeps the product from becoming generic AI advice. Use this page to
              inspect sources and cited claims without reading raw chunks by default.
            </p>
          </div>
          <Button
            onClick={openAddEvidence}
            type="button"
          >
            <LinkIcon className="h-4 w-4" aria-hidden="true" />
            Add Evidence
          </Button>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Metric label="Sources" value={health?.source_count ?? sources.length} />
          <Metric label="Competitors" value={health?.competitor_count ?? 0} />
          <Metric label="Cited claims" value={health?.cited_claim_count ?? 0} />
          <Metric label="Unsupported claims" value={health?.unsupported_claim_count ?? 0} />
          <Metric label="Weakest area" value={health?.weakest_evidence_area ?? "Unknown"} />
        </div>
      </div>

      <details id="add-evidence-panel" className="rounded-lg border border-border bg-white p-5">
        <summary className="cursor-pointer text-sm font-semibold">
          Add evidence manually
        </summary>
      <div className="mt-5 grid gap-4 border-t border-border pt-5 lg:grid-cols-3">
        <div className="self-start rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <LinkIcon className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Add URL</h2>
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
            <span className="text-sm font-medium">Title</span>
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
            {urlMutation.isPending ? "Adding..." : "Add URL"}
          </Button>
        </div>

        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <Type className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Add Note</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">Title</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setNoteTitle(event.target.value)}
              value={noteTitle}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-sm font-medium">Text</span>
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
            {noteMutation.isPending ? "Adding..." : "Add Note"}
          </Button>
        </div>

        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <FileUp className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Upload File</h2>
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
            {fileMutation.isPending ? "Uploading..." : "Upload"}
          </Button>
        </div>
      </div>
      </details>

      {error ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {(error as Error).message}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="self-start rounded-lg border border-border bg-white p-5">
          <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Sources</h2>
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
            <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {(sourcesQuery.error as Error).message}
            </div>
          ) : sources.length === 0 ? (
            <div className="mt-4 rounded-md border border-dashed border-border p-4">
              <h3 className="text-sm font-semibold">No evidence yet.</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Evidence keeps this from becoming generic AI advice. Run a research sprint
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
                Add Evidence
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
                  reprocessPending={reprocessMutation.isPending}
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
        </div>

        <div className="self-start rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Retrieve</h2>
          </div>
          <label className="mt-4 block">
            <span className="text-sm font-medium">Query</span>
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
            {retrievalMutation.isPending ? "Retrieving..." : "Retrieve"}
          </Button>

          {retrievalMutation.data ? (
            <div className="mt-5 space-y-3">
              {retrievalMutation.data.results.length === 0 ? (
                <p className="text-sm text-muted-foreground">No matching chunks.</p>
              ) : (
                retrievalMutation.data.results.map((result) => (
                  <details key={result.chunk_id} className="rounded-md border border-border p-3">
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
        </div>
      </div>
    </section>
  );
}

function SourceRow({
  source,
  onDelete,
  onReprocess,
  deletePending,
  reprocessPending,
}: {
  source: EvidenceSource;
  onDelete: () => void;
  onReprocess: () => void;
  deletePending: boolean;
  reprocessPending: boolean;
}) {
  return (
    <details className="py-4">
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
        <span className="shrink-0 text-xs font-medium text-primary">Show details</span>
      </div>
      </summary>
      <div className="mt-4 rounded-md bg-muted p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h4 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
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
              <p className="mt-2 text-sm text-red-700">{source.ingestion_error}</p>
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

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md bg-muted px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
    </div>
  );
}

function truncate(value: string, maxLength: number) {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

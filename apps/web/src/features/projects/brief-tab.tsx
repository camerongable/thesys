"use client";

import { AlertTriangle, FileText, RefreshCw, ShieldCheck } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Artifact,
  generateOpportunityBrief,
  listArtifacts,
  OpportunityBriefGenerateResult,
} from "@/lib/api";

type BriefTabProps = {
  projectId: string;
};

export function BriefTab({ projectId }: BriefTabProps) {
  const queryClient = useQueryClient();
  const artifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts", "opportunity_brief"],
    queryFn: () => listArtifacts(projectId, "opportunity_brief"),
  });

  const generateMutation = useMutation({
    mutationFn: () => generateOpportunityBrief(projectId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "artifacts", "opportunity_brief"],
      });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
    },
  });

  const artifacts = artifactsQuery.data ?? [];
  const current = generateMutation.data?.artifact ?? artifacts[0] ?? null;
  const currentVersion = generateMutation.data?.version ?? current?.current_version ?? null;
  const claims = generateMutation.data?.claims ?? currentVersion?.claims ?? [];
  const unsupportedClaims = unsupportedFromResult(generateMutation.data, current);
  const error = artifactsQuery.error ?? generateMutation.error ?? null;

  return (
    <section className="mt-6 space-y-6">
      <div className="flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold">Opportunity Brief</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Source-grounded brief, cited claims, unsupported claims, and version history.
          </p>
        </div>
        <Button
          disabled={generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
          type="button"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          {generateMutation.isPending
            ? "Generating..."
            : currentVersion
              ? "Regenerate"
              : "Generate Brief"}
        </Button>
      </div>

      {error ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {(error as Error).message}
        </div>
      ) : null}

      {artifactsQuery.isLoading ? (
        <div className="text-sm text-muted-foreground">Loading brief...</div>
      ) : !currentVersion ? (
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">No brief generated yet.</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Add evidence first for a stronger cited brief, then generate the first version.
          </p>
        </div>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <article className="rounded-lg border border-border bg-white p-5">
            <div className="flex flex-wrap items-center gap-2 border-b border-border pb-4">
              <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">{current?.title ?? "Opportunity Brief"}</h3>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                Version {currentVersion.version}
              </span>
            </div>
            <div className="mt-5 whitespace-pre-wrap text-sm leading-7 text-foreground">
              {currentVersion.markdown_content}
            </div>
          </article>

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
                        {claim.evidence_links.length > 0 ? (
                          <span className="text-muted-foreground">
                            {claim.evidence_links.length} citation
                            {claim.evidence_links.length === 1 ? "" : "s"}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        {claim.text}
                      </p>
                      {claim.evidence_links.length > 0 ? (
                        <div className="mt-3 space-y-2 border-t border-border pt-3">
                          {claim.evidence_links.map((link) => (
                            <p
                              className="text-xs leading-5 text-muted-foreground"
                              key={link.id}
                            >
                              {link.quote
                                ? truncate(link.quote, 220)
                                : `Source ${link.evidence_source_id}`}
                            </p>
                          ))}
                        </div>
                      ) : null}
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
                    <p key={claim} className="text-sm leading-6 text-muted-foreground">
                      {claim}
                    </p>
                  ))
                )}
              </div>
            </div>

            {current && current.versions.length > 0 ? (
              <div className="rounded-lg border border-border bg-white p-5">
                <h3 className="text-sm font-semibold">Version History</h3>
                <div className="mt-4 space-y-2">
                  {current.versions.map((version) => (
                    <div
                      className="flex items-center justify-between text-sm text-muted-foreground"
                      key={version.id}
                    >
                      <span>Version {version.version}</span>
                      <span>{new Date(version.created_at).toLocaleDateString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </aside>
        </div>
      )}
    </section>
  );
}

function unsupportedFromResult(
  result: OpportunityBriefGenerateResult | undefined,
  artifact: Artifact | null,
) {
  if (result) {
    return result.unsupported_claims;
  }
  const unsupported = artifact?.current_version?.structured_content.unsupported_claims;
  return Array.isArray(unsupported) ? unsupported.filter((item) => typeof item === "string") : [];
}

function truncate(value: string, maxLength: number) {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

"use client";

import { AlertTriangle, FileText, RefreshCw, ShieldCheck } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import {
  Artifact,
  generateOpportunityBrief,
  listProjectWorkflows,
  listArtifacts,
  OpportunityBriefGenerateResult,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

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
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "workflows"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
    },
  });
  const activeWorkflowQuery = useQuery({
    queryKey: ["projects", projectId, "workflows", "opportunity_brief", "active"],
    queryFn: () => listProjectWorkflows(projectId, 5),
    enabled: generateMutation.isPending,
    refetchInterval: generateMutation.isPending ? 1000 : false,
  });

  const artifacts = artifactsQuery.data ?? [];
  const current = generateMutation.data?.artifact ?? artifacts[0] ?? null;
  const currentVersion = generateMutation.data?.version ?? current?.current_version ?? null;
  const claims = generateMutation.data?.claims ?? currentVersion?.claims ?? [];
  const unsupportedClaims = unsupportedFromResult(generateMutation.data, current);
  const activeBriefRun = generateMutation.isPending
    ? activeWorkflowQuery.data?.find(
        (run) =>
          run.workflow_type === "opportunity_brief" &&
          (run.status === "queued" || run.status === "running"),
      )
    : null;
  const error = artifactsQuery.error ?? generateMutation.error ?? null;

  return (
    <section className="mt-6 space-y-6">
      <DomainHeader
        action={
          <Button
            disabled={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
            type="button"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {generateMutation.isPending
              ? "Generating brief..."
              : currentVersion
                ? "Regenerate brief"
                : "Generate brief"}
          </Button>
        }
        description="Keep the generated thesis tied to cited claims, unsupported claims, and version history so the brief stays useful as decision evidence."
        icon={<FileText className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="What is the current cited thesis?"
        signals={[
          { label: "Version", value: currentVersion ? currentVersion.version : "None" },
          { label: "Cited claims", tone: claims.length > 0 ? "success" : "neutral", value: claims.length },
          { label: "Open questions", tone: unsupportedClaims.length > 0 ? "warning" : "neutral", value: unsupportedClaims.length },
          { label: "History", value: current?.versions.length ?? 0 },
        ]}
        title="Opportunity Brief"
      />

      {error ? (
        <DomainError message={(error as Error).message} />
      ) : null}

      <details className="rounded-lg border border-border bg-card p-5" open={generateMutation.isPending}>
        <summary className="cursor-pointer text-sm font-semibold">View brief trace</summary>
        <div className="mt-4 border-t border-border pt-4">
          <WorkflowTrace
            pending={generateMutation.isPending}
            pendingSteps={[
              "load_project_state",
              "retrieve_existing_evidence",
              "generate_structured_brief",
              "citation_audit",
              "write_artifact_version",
            ]}
            runId={generateMutation.data?.ai_run_id ?? activeBriefRun?.id ?? null}
          />
        </div>
      </details>

      {artifactsQuery.isLoading ? (
        <div className="text-sm text-muted-foreground">Loading brief...</div>
      ) : !currentVersion ? (
        <DomainPanel>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">No opportunity brief yet.</h3>
          </div>
          <div className="mt-3 grid gap-2 text-sm leading-6 text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">Missing:</span> a cited research
              brief for the current thesis.
            </p>
            <p>
              <span className="font-medium text-foreground">Why it matters:</span> the brief
              turns project state and evidence into risks, assumptions, validation plan, and
              recommendation.
            </p>
            <p>
              <span className="font-medium text-foreground">Next:</span> add evidence if the idea
              is still thin, then generate the first brief.
            </p>
          </div>
          <Button
            className="mt-4"
            disabled={generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
            size="sm"
            type="button"
            variant="secondary"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {generateMutation.isPending ? "Generating brief..." : "Generate brief"}
          </Button>
        </DomainPanel>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <article className="rounded-lg border border-border bg-card p-5">
            <div className="flex flex-wrap items-center gap-2 border-b border-border pb-4">
              <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">{current?.title ?? "Opportunity Brief"}</h3>
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                Version {currentVersion.version}
              </span>
            </div>
            <MarkdownContent markdown={currentVersion.markdown_content} />
          </article>

          <aside className="space-y-5">
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Cited claims</h3>
              </div>
              <div className="mt-4 space-y-3">
                {claims.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No cited claims recorded.</p>
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
                      <MarkdownContent
                        className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground"
                        markdown={claim.text}
                      />
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

            <div className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Unsupported claims</h3>
              </div>
              <div className="mt-4 space-y-2">
                {unsupportedClaims.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No unsupported claims recorded.</p>
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

            {current && current.versions.length > 0 ? (
              <div className="rounded-lg border border-border bg-card p-5">
                <h3 className="text-sm font-semibold">Version history</h3>
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

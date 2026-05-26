"use client";

import { Beaker, CheckCircle2, FileText, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Experiment,
  ExperimentOutcome,
  generateValidationPlan,
  listArtifacts,
  listAssumptions,
  listExperiments,
  logExperimentResult,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

type ExperimentsTabProps = {
  projectId: string;
};

export function ExperimentsTab({ projectId }: ExperimentsTabProps) {
  const queryClient = useQueryClient();
  const experimentsQuery = useQuery({
    queryKey: ["projects", projectId, "experiments"],
    queryFn: () => listExperiments(projectId),
  });
  const assumptionsQuery = useQuery({
    queryKey: ["projects", projectId, "assumptions"],
    queryFn: () => listAssumptions(projectId),
  });
  const artifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts", "validation_plan"],
    queryFn: () => listArtifacts(projectId, "validation_plan"),
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "experiments"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assumptions"] });
    await queryClient.invalidateQueries({
      queryKey: ["projects", projectId, "artifacts", "validation_plan"],
    });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "workflows"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
  };

  const generateMutation = useMutation({
    mutationFn: () => generateValidationPlan(projectId, { max_plans: 3 }),
    onSuccess: invalidate,
  });

  const experiments = generateMutation.data?.experiments ?? experimentsQuery.data ?? [];
  const assumptions = assumptionsQuery.data ?? [];
  const validationPlanArtifact =
    generateMutation.data?.artifact ?? artifactsQuery.data?.[0] ?? null;
  const validationPlanVersion = validationPlanArtifact?.current_version ?? null;
  const assumptionById = new Map(assumptions.map((assumption) => [assumption.id, assumption]));
  const error =
    experimentsQuery.error ??
    assumptionsQuery.error ??
    artifactsQuery.error ??
    generateMutation.error ??
    null;

  return (
    <section className="mt-6 space-y-6">
      <div className="rounded-lg border border-border bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Validation
            </p>
            <h2 className="mt-2 text-xl font-semibold tracking-normal">
              What should I test next?
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
              Turn the riskiest assumption into a concrete test with success criteria,
              failure criteria, assets, result logging, and interpretation.
            </p>
          </div>
          <Button
            className="w-full justify-center whitespace-nowrap sm:w-60"
            disabled={generateMutation.isPending || assumptions.length === 0}
            onClick={() => generateMutation.mutate()}
            type="button"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {generateMutation.isPending ? "Generating..." : "Create Validation Plan"}
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {(error as Error).message}
        </div>
      ) : null}

      <WorkflowTrace
        pending={generateMutation.isPending}
        pendingSteps={["generate_validation_plan", "write_artifact_version", "write_experiments"]}
        runId={generateMutation.data?.ai_run_id ?? null}
      />

      {experimentsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading experiments...</p>
      ) : experiments.length === 0 ? (
        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center gap-2">
            <Beaker className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">No validation experiments yet.</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Experiments help you reduce uncertainty before building. Start by testing the
            riskiest assumption with a clear method, success criteria, and failure
            threshold.
          </p>
          <Button
            className="mt-4 whitespace-nowrap"
            disabled={generateMutation.isPending || assumptions.length === 0}
            onClick={() => generateMutation.mutate()}
            size="sm"
            type="button"
            variant="secondary"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {assumptions.length === 0
              ? "Review Assumptions First"
              : generateMutation.isPending
                ? "Creating..."
                : "Create Validation Plan"}
          </Button>
        </div>
      ) : (
        <>
        <RecommendedValidationPlan
          artifactTitle={validationPlanArtifact?.title ?? "Recommended Validation Plan"}
          experiments={experiments}
        />
        <div
          className={
            validationPlanVersion
              ? "grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]"
              : "grid gap-5"
          }
        >
          <div className="grid gap-5">
            {experiments.map((experiment) => (
              <ExperimentCard
                assumptionText={
                  experiment.assumption_id
                    ? assumptionById.get(experiment.assumption_id)?.text ?? null
                    : null
                }
                experiment={experiment}
                key={experiment.id}
                onSaved={invalidate}
                projectId={projectId}
              />
            ))}
          </div>

          {validationPlanVersion ? (
            <aside className="rounded-lg border border-border bg-white p-5">
              <div className="flex items-center gap-2 border-b border-border pb-4">
                <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">
                  {validationPlanArtifact?.title ?? "Validation Plan"}
                </h3>
                <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                  Version {validationPlanVersion.version}
                </span>
              </div>
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium">
                  Show full validation plan
                </summary>
              <MarkdownContent
                className="mt-4 space-y-4 text-sm leading-6 text-foreground"
                markdown={validationPlanVersion.markdown_content}
              />
              </details>
            </aside>
          ) : null}
        </div>
        </>
      )}
    </section>
  );
}

function RecommendedValidationPlan({
  artifactTitle,
  experiments,
}: {
  artifactTitle: string;
  experiments: Experiment[];
}) {
  const recommended = experiments[0];
  if (!recommended) {
    return null;
  }
  return (
    <div className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
            Recommended Validation Plan
          </p>
          <h3 className="mt-2 text-lg font-semibold">{recommended.name}</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {artifactTitle}. Start with this test before building more product surface area.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {recommended.status}
        </span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Block title="Test Type" value={recommended.method ?? "Manual validation"} />
        <Block title="Success Criteria" value={recommended.success_criteria} />
        <Block title="Failure Criteria" value={recommended.failure_threshold} />
      </div>
      <ValidationAssetGrid experiment={recommended} />
    </div>
  );
}

function ValidationAssetGrid({ experiment }: { experiment: Experiment }) {
  const assets = [
    {
      title: "Interview Script",
      value: experiment.plan,
    },
    {
      title: "Screener Questions",
      value: experiment.plan
        ? `Use the target respondent profile from the plan.\n\n${experiment.plan}`
        : null,
    },
    {
      title: "Survey Questions",
      value: experiment.success_criteria
        ? `Questions should test the same success signal:\n\n${experiment.success_criteria}`
        : null,
    },
    {
      title: "Outreach Message",
      value: experiment.plan
        ? `I'm researching ${experiment.name.toLowerCase()} and looking for quick feedback from people who match this workflow. Would you be open to a short conversation?`
        : null,
    },
    {
      title: "Results Rubric",
      value: [
        experiment.success_criteria ? `Success: ${experiment.success_criteria}` : null,
        experiment.failure_threshold ? `Failure: ${experiment.failure_threshold}` : null,
      ]
        .filter(Boolean)
        .join("\n\n"),
    },
  ];

  return (
    <div className="mt-5 border-t border-border pt-5">
      <div className="flex items-center justify-between gap-3">
        <h4 className="text-sm font-semibold">Generated Assets</h4>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          Copyable
        </span>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {assets.map((asset) => (
          <details className="rounded-md border border-border p-3" key={asset.title}>
            <summary className="cursor-pointer text-sm font-medium">{asset.title}</summary>
            <div className="mt-3 border-t border-border pt-3">
              <Block title={asset.title} value={asset.value || "Not generated yet"} />
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function ExperimentCard({
  assumptionText,
  experiment,
  onSaved,
  projectId,
}: {
  assumptionText: string | null;
  experiment: Experiment;
  onSaved: () => Promise<void>;
  projectId: string;
}) {
  return (
    <article className="rounded-lg border border-border bg-white p-5">
      <div className="flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{experiment.name}</h3>
            <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {experiment.status}
            </span>
            {experiment.method ? (
              <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {formatLabel(experiment.method)}
              </span>
            ) : null}
          </div>
          {assumptionText ? (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{assumptionText}</p>
          ) : null}
        </div>
        <span className="text-xs text-muted-foreground">
          {experiment.results.length} result{experiment.results.length === 1 ? "" : "s"}
        </span>
      </div>

      <details className="mt-4 rounded-md bg-muted/50 p-3">
        <summary className="cursor-pointer text-sm font-medium">
          Show test plan and log results
        </summary>
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div>
            <Block title="Plan" value={experiment.plan} />
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Block title="Success Criteria" value={experiment.success_criteria} />
              <Block title="Failure Threshold" value={experiment.failure_threshold} />
            </div>
            {experiment.results.length > 0 ? (
              <div className="mt-4 space-y-3">
                <h4 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                  Results
                </h4>
                {experiment.results.map((result) => (
                  <div key={result.id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        {result.outcome}
                      </span>
                      {result.confidence_delta ? (
                        <span className="text-muted-foreground">
                          delta {result.confidence_delta}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {result.result_summary}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <ResultForm experiment={experiment} onSaved={onSaved} projectId={projectId} />
        </div>
      </details>
    </article>
  );
}

function ResultForm({
  experiment,
  onSaved,
  projectId,
}: {
  experiment: Experiment;
  onSaved: () => Promise<void>;
  projectId: string;
}) {
  const [summary, setSummary] = useState("");
  const [outcome, setOutcome] = useState<ExperimentOutcome>("positive");
  const [rawNotes, setRawNotes] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      logExperimentResult(projectId, experiment.id, {
        result_summary: summary,
        outcome,
        raw_notes: rawNotes.trim().length > 0 ? rawNotes : undefined,
      }),
    onSuccess: async () => {
      setSummary("");
      setRawNotes("");
      await onSaved();
    },
  });

  return (
    <form
      className="rounded-md border border-border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
        <h4 className="text-sm font-semibold">Log Result</h4>
      </div>
      {mutation.error ? (
        <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {(mutation.error as Error).message}
        </div>
      ) : null}
      <label className="mt-4 block">
        <span className="text-sm font-medium">Outcome</span>
        <select
          className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setOutcome(event.target.value as ExperimentOutcome)}
          value={outcome}
        >
          {["positive", "negative", "mixed", "inconclusive"].map((item) => (
            <option key={item} value={item}>
              {formatLabel(item)}
            </option>
          ))}
        </select>
      </label>
      <label className="mt-3 block">
        <span className="text-sm font-medium">Summary</span>
        <textarea
          className="mt-2 min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setSummary(event.target.value)}
          value={summary}
        />
      </label>
      <label className="mt-3 block">
        <span className="text-sm font-medium">Raw Notes</span>
        <textarea
          className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setRawNotes(event.target.value)}
          value={rawNotes}
        />
      </label>
      <Button
        className="mt-4"
        disabled={mutation.isPending || summary.trim().length === 0}
        type="submit"
      >
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        {mutation.isPending ? "Saving..." : "Save Result"}
      </Button>
    </form>
  );
}

function Block({ title, value }: { title: string; value: string | null }) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  async function handleCopy() {
    if (!value) {
      return;
    }
    try {
      await copyText(value);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    window.setTimeout(() => setCopyState("idle"), 1600);
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
          {title}
        </h4>
        {value ? (
          <button
            className="text-xs font-medium text-primary hover:underline"
            onClick={() => void handleCopy()}
            type="button"
          >
            {copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : "Copy"}
          </button>
        ) : null}
      </div>
      <MarkdownContent
        className="mt-1 space-y-2 text-sm leading-6 text-muted-foreground"
        markdown={value ?? "Not recorded"}
      />
    </div>
  );
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall back for embedded browsers that expose the Clipboard API but deny writes.
    }
  }

  try {
    copyWithClipboardEvent(value);
    return;
  } catch {
    // Fall back to selecting a temporary textarea.
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, value.length);

  try {
    const copied = document.execCommand("copy");
    if (!copied) {
      throw new Error("Copy command failed");
    }
  } finally {
    document.body.removeChild(textarea);
  }
}

function copyWithClipboardEvent(value: string) {
  let handled = false;
  const onCopy = (event: ClipboardEvent) => {
    event.clipboardData?.setData("text/plain", value);
    event.preventDefault();
    handled = true;
  };

  document.addEventListener("copy", onCopy);
  try {
    const copied = document.execCommand("copy");
    if (!copied && !handled) {
      throw new Error("Copy event failed");
    }
  } finally {
    document.removeEventListener("copy", onCopy);
  }
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

"use client";

import { Beaker, CheckCircle2, FileText, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import { assumptionBeliefText } from "@/features/projects/assumption-copy";
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
  const hasExperiments = experiments.length > 0;
  const hasLoggedResults = experiments.some((experiment) => experiment.results.length > 0);
  const resultCount = experiments.reduce(
    (count, experiment) => count + experiment.results.length,
    0,
  );
  const primaryActionLabel = validationPrimaryActionLabel(hasExperiments, hasLoggedResults);
  const error =
    experimentsQuery.error ??
    assumptionsQuery.error ??
    artifactsQuery.error ??
    generateMutation.error ??
    null;

  function runPrimaryAction() {
    if (!hasExperiments) {
      generateMutation.mutate();
      return;
    }
    if (hasLoggedResults) {
      if (typeof window !== "undefined") {
        window.location.hash = "decisions";
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      }
      return;
    }
    document.getElementById("log-results-panel")?.scrollIntoView({ behavior: "smooth" });
  }

  return (
    <section className="mt-6 space-y-6">
      <DomainHeader
        action={
          <Button
            className="w-full justify-center whitespace-nowrap sm:w-60"
            disabled={generateMutation.isPending || (!hasExperiments && assumptions.length === 0)}
            onClick={runPrimaryAction}
            type="button"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {generateMutation.isPending ? "Creating test plan..." : primaryActionLabel}
          </Button>
        }
        description="Convert the top decision blocker into a test with success criteria, failure criteria, assets, result logging, and interpretation."
        icon={<Beaker className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="What should we test before deciding?"
        signals={[
          { label: "Experiments", value: experiments.length },
          { label: "Assumptions", value: assumptions.length },
          { label: "Logged results", tone: resultCount > 0 ? "success" : "warning", value: resultCount },
          {
            label: "Next move",
            tone: hasLoggedResults ? "success" : hasExperiments ? "warning" : "neutral",
            value: primaryActionLabel,
          },
        ]}
        title="Validation"
      />

      {error ? (
        <DomainError message={(error as Error).message} />
      ) : null}

      {generateMutation.isPending || generateMutation.data?.ai_run_id ? (
        <details className="rounded-lg border border-border bg-card p-5" open={generateMutation.isPending}>
          <summary className="cursor-pointer text-sm font-semibold">View validation trace</summary>
          <div className="mt-4 border-t border-border pt-4">
            <WorkflowTrace
              pending={generateMutation.isPending}
              pendingSteps={["generate_validation_plan", "write_artifact_version", "write_experiments"]}
              runId={generateMutation.data?.ai_run_id ?? null}
            />
          </div>
        </details>
      ) : null}

      {experimentsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading validation tests...</p>
      ) : experiments.length === 0 ? (
        <DomainPanel>
          <div className="flex items-center gap-2">
            <Beaker className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">No validation tests yet.</h3>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Experiments help you reduce uncertainty before building. Start by testing the
            top decision blocker with a clear method, success criteria, and failure
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
              ? "Rank blockers first"
              : generateMutation.isPending
                ? "Creating test plan..."
                : "Create test plan"}
          </Button>
        </DomainPanel>
      ) : (
        <>
        <RecommendedValidationPlan
          artifactTitle={validationPlanArtifact?.title ?? "Recommended validation plan"}
          experiments={experiments}
          hasLoggedResults={hasLoggedResults}
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
                    ? assumptionBeliefText(assumptionById.get(experiment.assumption_id)?.text ?? "") || null
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
            <aside className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-center gap-2 border-b border-border pb-4">
                <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">
                  {validationPlanArtifact?.title ?? "Validation plan"}
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
  hasLoggedResults,
}: {
  artifactTitle: string;
  experiments: Experiment[];
  hasLoggedResults: boolean;
}) {
  const recommended = experiments[0];
  if (!recommended) {
    return null;
  }
  return (
    <DomainPanel>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            Next test
          </p>
          <h3 className="mt-2 text-lg font-semibold">{recommended.name}</h3>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {artifactTitle}. Start with this test before building more product surface area.
          </p>
        </div>
        <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          {hasLoggedResults ? "results logged" : recommended.status}
        </span>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Block title="Goal" value={recommended.name} />
        <Block title="Run" value={recommended.plan} />
        <Block title="Success" value={recommended.success_criteria} />
        <Block title="Failure" value={recommended.failure_threshold} />
      </div>
      <div className="mt-4 border-t border-border pt-3">
        <Block
          title="Next after results"
          value="Update confidence and review whether the evidence supports continuing research, pivoting, pausing, killing, or proceeding narrowly."
        />
      </div>
      <ValidationAssetGrid experiment={recommended} />
    </DomainPanel>
  );
}

function ValidationAssetGrid({ experiment }: { experiment: Experiment }) {
  const assets = [
    {
      title: "Interview script",
      value: experiment.plan,
    },
    {
      title: "Screener questions",
      value: "1. Have you recently tried to solve this problem?\n2. What did you use instead?\n3. How painful was the workaround?\n4. Did you spend money or serious time on it?",
    },
    {
      title: "Survey questions",
      value: experiment.success_criteria
        ? `Questions should test the same success signal:\n\n${experiment.success_criteria}`
        : null,
    },
    {
      title: "Outreach message",
      value: experiment.plan
        ? `I'm researching ${experiment.name.toLowerCase()} and looking for quick feedback from people who recently faced this situation. Would you be open to a short conversation?`
        : null,
    },
    {
      title: "Landing page copy",
      value: `Validate demand for ${experiment.name.toLowerCase()} before building. Ask visitors to describe their current workaround and whether they would try a dedicated solution.`,
    },
    {
      title: "Results rubric",
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
        <h4 className="text-sm font-semibold">Test assets</h4>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          Ready to copy
        </span>
      </div>
      <div className="mt-3 grid gap-x-6 gap-y-3 md:grid-cols-2">
        {assets.map((asset, index) => (
          <details className="border-t border-border py-3 first:border-t-0 first:pt-0" key={asset.title} open={index === 0}>
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
    <DomainPanel>
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

      <div className="mt-4 grid gap-4 2xl:grid-cols-[minmax(24rem,1fr)_360px]">
        <div className="min-w-0 space-y-4">
          <div>
            <Block title="Step-by-step test plan" value={experiment.plan} />
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <Block title="Success criteria" value={experiment.success_criteria} />
              <Block title="Failure criteria" value={experiment.failure_threshold} />
            </div>
          </div>
          <ResultInterpretation experiment={experiment} />
          <details className="border-t border-border pt-3">
            <summary className="cursor-pointer text-sm font-medium">
              Show logged results
            </summary>
            <div className="mt-3 divide-y divide-border border-t border-border pt-3">
              {experiment.results.length === 0 ? (
                <p className="text-sm text-muted-foreground">No results logged yet.</p>
              ) : (
                experiment.results.map((result) => (
                  <div key={result.id} className="py-3 first:pt-0">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-md bg-muted px-2 py-1 text-muted-foreground">
                        {formatLabel(result.outcome)}
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
                ))
              )}
            </div>
          </details>
        </div>
        <ResultForm experiment={experiment} onSaved={onSaved} projectId={projectId} />
      </div>
    </DomainPanel>
  );
}

function ResultInterpretation({ experiment }: { experiment: Experiment }) {
  const latestResult = [...experiment.results].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )[0];

  if (!latestResult) {
    return (
      <div className="border-t border-border pt-3">
        <h4 className="text-xs font-medium text-muted-foreground">
          Result interpretation
        </h4>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          No result has been logged. Run the test, then record the outcome before making a
          proceed or pivot decision.
        </p>
      </div>
    );
  }

  const interpretation = resultInterpretation(latestResult.outcome);
  return (
    <div className="border-t border-border pt-3">
      <h4 className="text-xs font-medium text-muted-foreground">
        Result interpretation
      </h4>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {interpretation}
      </p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Latest signal: {latestResult.result_summary}
      </p>
    </div>
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
  const [evidenceStrength, setEvidenceStrength] = useState("medium");
  const [confidenceChange, setConfidenceChange] = useState("no_change");
  const [recommendationChange, setRecommendationChange] = useState("no_change");
  const mutation = useMutation({
    mutationFn: () =>
      logExperimentResult(projectId, experiment.id, {
        result_summary: summary,
        outcome,
        raw_notes: resultNotes({
          confidenceChange,
          evidenceStrength,
          rawNotes,
          recommendationChange,
        }),
      }),
    onSuccess: async () => {
      setSummary("");
      setRawNotes("");
      setEvidenceStrength("medium");
      setConfidenceChange("no_change");
      setRecommendationChange("no_change");
      await onSaved();
    },
  });

  return (
    <form
      className="border-t border-border pt-4 2xl:border-l 2xl:border-t-0 2xl:pl-4 2xl:pt-0"
      id={experiment.results.length === 0 ? "log-results-panel" : undefined}
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
        <h4 className="text-sm font-semibold">Log test result</h4>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        The validation loop is not complete until real-world results are logged.
      </p>
      {mutation.error ? (
        <DomainError message={(mutation.error as Error).message} />
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
        <span className="text-sm font-medium">What happened?</span>
        <textarea
          className="mt-2 min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setSummary(event.target.value)}
          value={summary}
        />
      </label>
      <label className="mt-3 block">
        <span className="text-sm font-medium">Evidence strength</span>
        <select
          className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setEvidenceStrength(event.target.value)}
          value={evidenceStrength}
        >
          {["weak", "medium", "strong"].map((item) => (
            <option key={item} value={item}>
              {formatLabel(item)}
            </option>
          ))}
        </select>
      </label>
      <label className="mt-3 block">
        <span className="text-sm font-medium">Should confidence change?</span>
        <select
          className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setConfidenceChange(event.target.value)}
          value={confidenceChange}
        >
          <option value="increase">Increase confidence</option>
          <option value="no_change">No change yet</option>
          <option value="decrease">Decrease confidence</option>
        </select>
      </label>
      <label className="mt-3 block">
        <span className="text-sm font-medium">Should the recommendation change?</span>
        <select
          className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setRecommendationChange(event.target.value)}
          value={recommendationChange}
        >
          <option value="no_change">No change yet</option>
          <option value="revisit">Revisit recommendation</option>
          <option value="proceed">Consider proceeding</option>
          <option value="pivot">Consider pivoting</option>
          <option value="pause">Consider pausing</option>
        </select>
      </label>
      <label className="mt-3 block">
        <span className="text-sm font-medium">Interview notes / raw evidence</span>
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
        {mutation.isPending ? "Logging result..." : "Log result"}
      </Button>
    </form>
  );
}

function resultInterpretation(outcome: ExperimentOutcome) {
  if (outcome === "positive") {
    return "This strengthens the tested belief. Review whether the result meets the decision threshold before changing the verdict.";
  }
  if (outcome === "negative") {
    return "This weakens the tested belief. Consider pivoting, narrowing the wedge, or pausing before building more.";
  }
  if (outcome === "mixed") {
    return "This is a partial signal. Run a tighter follow-up test before treating the belief as validated.";
  }
  return "This is not strong enough proof yet. Clarify the respondent profile or test design and run another validation pass.";
}

function validationPrimaryActionLabel(hasExperiments: boolean, hasLoggedResults: boolean) {
  if (!hasExperiments) {
    return "Create test plan";
  }
  if (hasLoggedResults) {
    return "Review decision";
  }
  return "Log results";
}

function resultNotes({
  confidenceChange,
  evidenceStrength,
  rawNotes,
  recommendationChange,
}: {
  confidenceChange: string;
  evidenceStrength: string;
  rawNotes: string;
  recommendationChange: string;
}) {
  const parts = [
    rawNotes.trim(),
    `Evidence strength: ${formatLabel(evidenceStrength)}`,
    `Confidence change: ${formatLabel(confidenceChange)}`,
    `Recommendation change: ${formatLabel(recommendationChange)}`,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join("\n\n") : undefined;
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
    <div className="min-w-0">
      <div className="flex items-start justify-between gap-3">
        <h4 className="min-w-0 text-xs font-medium text-muted-foreground">
          {title}
        </h4>
        {value ? (
          <button
            className="shrink-0 text-xs font-medium text-primary hover:underline"
            onClick={() => void handleCopy()}
            type="button"
          >
            {copyState === "copied" ? "Copied" : copyState === "failed" ? "Copy failed" : "Copy"}
          </button>
        ) : null}
      </div>
      <MarkdownContent
        className="mt-1 min-w-0 space-y-2 break-words text-sm leading-6 text-muted-foreground"
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

"use client";

import { AlertTriangle, ChevronDown, Link2, Plus, ScrollText, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  assumptionBeliefText,
  clarifyDecisionNarrative,
  decisionBlockerText,
} from "@/features/projects/assumption-copy";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import {
  Assumption,
  createDecision,
  DecisionType,
  Experiment,
  getProjectOverview,
  listArtifacts,
  listAssumptions,
  listDecisions,
  listEvidenceSources,
  listExperiments,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";

type DecisionsTabProps = {
  activeAnchor?: string | null;
  onOpenValidation?: () => void;
  projectId: string;
};

const decisionTypes: DecisionType[] = [
  "build",
  "pivot",
  "pause",
  "kill",
  "change_icp",
  "change_positioning",
  "run_experiment",
  "other",
];

export function DecisionsTab({ activeAnchor, onOpenValidation, projectId }: DecisionsTabProps) {
  const queryClient = useQueryClient();
  const [decisionType, setDecisionType] = useState<DecisionType>("run_experiment");
  const [title, setTitle] = useState("");
  const [rationale, setRationale] = useState("");
  const [expectedOutcome, setExpectedOutcome] = useState("");
  const [reviewDate, setReviewDate] = useState("");
  const [linkedAssumptions, setLinkedAssumptions] = useState<string[]>([]);
  const [linkedEvidence, setLinkedEvidence] = useState<string[]>([]);
  const [linkedArtifacts, setLinkedArtifacts] = useState<string[]>([]);
  const [linkedExperiments, setLinkedExperiments] = useState<string[]>([]);
  const [recordStepActive, setRecordStepActive] = useState(false);
  const [overrideWithoutValidation, setOverrideWithoutValidation] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");

  const decisionsQuery = useQuery({
    queryKey: ["projects", projectId, "decisions"],
    queryFn: () => listDecisions(projectId),
  });
  const assumptionsQuery = useQuery({
    queryKey: ["projects", projectId, "assumptions"],
    queryFn: () => listAssumptions(projectId),
  });
  const evidenceQuery = useQuery({
    queryKey: ["projects", projectId, "evidence"],
    queryFn: () => listEvidenceSources(projectId),
  });
  const artifactsQuery = useQuery({
    queryKey: ["projects", projectId, "artifacts"],
    queryFn: () => listArtifacts(projectId),
  });
  const experimentsQuery = useQuery({
    queryKey: ["projects", projectId, "experiments"],
    queryFn: () => listExperiments(projectId),
  });
  const overviewQuery = useQuery({
    queryKey: ["projects", projectId, "overview", "decision-recommendation"],
    queryFn: () => getProjectOverview(projectId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createDecision(projectId, {
        decision_type: decisionType,
        title,
        rationale: emptyToUndefined(
          withOverrideRationale(rationale, overrideReason, validationGuardActive && overrideReady),
        ),
        expected_outcome: emptyToUndefined(expectedOutcome),
        review_date: emptyToUndefined(reviewDate),
        linked_assumption_ids: linkedAssumptions,
        linked_evidence_source_ids: linkedEvidence,
        linked_artifact_ids: linkedArtifacts,
        linked_experiment_ids: linkedExperiments,
    }),
    onSuccess: async () => {
      resetDecisionDraft();
      setRecordStepActive(false);
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "decisions"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
    },
  });

  const decisions = decisionsQuery.data ?? [];
  const assumptions = assumptionsQuery.data ?? [];
  const evidence = evidenceQuery.data ?? [];
  const artifacts = artifactsQuery.data ?? [];
  const experiments = experimentsQuery.data ?? [];
  const hasLoggedResults = experiments.some((experiment) => experiment.results.length > 0);
  const resultCount = experiments.reduce(
    (count, experiment) => count + experiment.results.length,
    0,
  );
  const decisionGradeReady = evidence.length > 0 && assumptions.length > 0 && hasLoggedResults;
  const suggestedDecision = buildDecisionSuggestion({
    assumptions,
    evidenceCount: evidence.length,
    experiments,
    overview: overviewQuery.data,
  });
  const alternateOutcomes: {
    disabled?: boolean;
    label: string;
    reason?: string;
    type: DecisionType;
  }[] = [
    {
      disabled: !hasLoggedResults,
      label: "Proceed narrowly",
      reason: "Log validation results before recording a proceed decision.",
      type: "build",
    },
    { label: "Pivot", type: "pivot" },
    { label: "Pause", type: "pause" },
    { label: "Kill", type: "kill" },
    { label: "Continue research", type: "run_experiment" },
  ];
  const error =
    decisionsQuery.error ??
    assumptionsQuery.error ??
    evidenceQuery.error ??
    artifactsQuery.error ??
    experimentsQuery.error ??
    overviewQuery.error ??
    createMutation.error ??
    null;
  const draftLinkCount =
    linkedAssumptions.length +
    linkedEvidence.length +
    linkedArtifacts.length +
    linkedExperiments.length;
  const validationGuardActive = !decisionGradeReady;
  const overrideReady =
    overrideWithoutValidation && overrideReason.trim().length >= 20;
  const canSubmitDecision =
    title.trim().length > 0 && (!validationGuardActive || overrideReady);

  useEffect(() => {
    if (activeAnchor === "record-decision-panel" && decisionGradeReady) {
      setRecordStepActive(true);
      window.setTimeout(() => document.getElementById("decision-title")?.focus(), 0);
    }
  }, [activeAnchor, decisionGradeReady]);

  function openDecisionForm() {
    setRecordStepActive(true);
    window.setTimeout(() => document.getElementById("decision-title")?.focus(), 0);
  }

  function resetDecisionDraft() {
    setTitle("");
    setRationale("");
    setExpectedOutcome("");
    setReviewDate("");
    setLinkedAssumptions([]);
    setLinkedEvidence([]);
    setLinkedArtifacts([]);
    setLinkedExperiments([]);
    setOverrideWithoutValidation(false);
    setOverrideReason("");
  }

  function cancelDecisionDraft() {
    resetDecisionDraft();
    setRecordStepActive(false);
  }

  function applyDecisionSuggestion(type: DecisionType, label: string) {
    const suggestion = buildDecisionSuggestion({
      assumptions,
      decisionType: type,
      evidenceCount: evidence.length,
      experiments,
      label,
      overview: overviewQuery.data,
    });
    setDecisionType(type);
    setTitle(suggestion.title);
    setRationale(suggestion.rationale);
    setExpectedOutcome(suggestion.expectedOutcome);
    setLinkedAssumptions(suggestion.linkedAssumptionId ? [suggestion.linkedAssumptionId] : []);
    setLinkedEvidence([]);
    setLinkedArtifacts([]);
    setLinkedExperiments(suggestion.linkedExperimentIds);
    openDecisionForm();
  }

  return (
    <section className="space-y-6">
      <DomainHeader
        action={
          validationGuardActive && onOpenValidation ? (
            <Button onClick={onOpenValidation} type="button">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
              Log validation result
            </Button>
          ) : (
            <Button onClick={openDecisionForm} type="button">
              <ScrollText className="h-4 w-4" aria-hidden="true" />
              Prepare record
            </Button>
          )
        }
        description={
          validationGuardActive
            ? "Record is guarded until validation evidence exists. Use an override only when you need to preserve an explicit exception."
            : "Draft the durable decision record from the current recommendation and linked evidence."
        }
        icon={<ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />}
        question={validationGuardActive ? "Complete validation before recording" : "Prepare the decision record"}
        title="Decisions"
      />

      <DomainPanel>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-[72ch]">
            <div className="flex items-center gap-2">
              <ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-base font-semibold">Decision ritual</h3>
            </div>
            <p className="mt-3 text-lg font-semibold leading-7 text-foreground">
              {suggestedDecision.title}
            </p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {suggestedDecision.rationale}
            </p>
          </div>
          <div className="w-full shrink-0 lg:w-64">
            {validationGuardActive && onOpenValidation ? (
              <Button className="w-full" onClick={onOpenValidation} type="button">
                <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                Log validation result
              </Button>
            ) : (
              <Button
                className="w-full"
                onClick={() =>
                  applyDecisionSuggestion(suggestedDecision.type, suggestedDecision.actionLabel)
                }
                type="button"
              >
                <ScrollText className="h-4 w-4" aria-hidden="true" />
                Prepare recommended record
              </Button>
            )}
            {validationGuardActive ? (
              <Button
                className="mt-2 w-full"
                onClick={() =>
                  applyDecisionSuggestion(suggestedDecision.type, suggestedDecision.actionLabel)
                }
                type="button"
                variant="secondary"
              >
                <ScrollText className="h-4 w-4" aria-hidden="true" />
                Prepare override record
              </Button>
            ) : null}
            {suggestedDecision.linkedAssumptionId || suggestedDecision.linkedExperimentIds.length > 0 ? (
              <p className="mt-2 text-xs leading-5 text-muted-foreground">
                Pre-fills the record and links the most relevant blocker or validation test.
              </p>
            ) : null}
          </div>
        </div>

        {suggestedDecision.missingEvidence.length > 0 ? (
          <div className="mt-5 rounded-md border border-warning-border bg-warning-muted/50 px-4 py-4 sm:px-5">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-foreground" aria-hidden="true" />
              <div className="min-w-0 max-w-[72ch]">
                <h4 className="text-sm font-semibold text-warning-foreground">
                  Evidence warning
                </h4>
                <ul className="mt-2 space-y-1 text-sm leading-6 text-warning-foreground">
                  {suggestedDecision.missingEvidence.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-5 border-t border-border pt-3 text-sm leading-6 text-muted-foreground">
            No major missing evidence is flagged. Review the rationale before recording the decision.
          </p>
        )}

        {!validationGuardActive ? (
          <details className="mt-4 border-t border-border pt-3">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-md py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:min-h-10">
              <span>Choose a different outcome</span>
              <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
            </summary>
            <div className="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
              {alternateOutcomes.map((outcome) => (
                <Button
                  disabled={outcome.disabled}
                  key={outcome.type}
                  onClick={() => applyDecisionSuggestion(outcome.type, outcome.label)}
                  title={outcome.reason}
                  type="button"
                  variant="secondary"
                >
                  {outcome.label}
                </Button>
              ))}
            </div>
          </details>
        ) : null}
      </DomainPanel>

      {recordStepActive ? (
        <DomainPanel id="record-decision-panel">
          <div className="flex flex-col gap-4 border-b border-border pb-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Plus className="h-4 w-4 text-primary" aria-hidden="true" />
                <span>Step 2</span>
              </div>
              <h2 className="mt-1 text-base font-semibold">Review and record the decision</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Edit the draft, then expand evidence links only if the record needs more traceability.
              </p>
            </div>
            <Button onClick={cancelDecisionDraft} type="button" variant="ghost">
              <X className="h-4 w-4" aria-hidden="true" />
              Cancel draft
            </Button>
          </div>

          <form
            className="mt-5"
            onSubmit={(event) => {
              event.preventDefault();
              if (canSubmitDecision) {
                createMutation.mutate();
              }
            }}
          >
            {validationGuardActive ? (
              <div className="mb-5 rounded-md border border-warning-border bg-warning-muted p-4">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-foreground" aria-hidden="true" />
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-warning-foreground">
                      Validation guardrail
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-warning-foreground">
                      Record is locked by default because {resultCount === 0 ? "no validation results are logged" : "the blocker is not ready for a durable decision"}.
                      Continue only if you need to preserve an exception.
                    </p>
                    {suggestedDecision.missingEvidence.length > 0 ? (
                      <ul className="mt-2 space-y-1 text-sm leading-6 text-warning-foreground">
                        {suggestedDecision.missingEvidence.slice(0, 3).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : null}
                    <label className="mt-3 flex min-h-11 cursor-pointer items-start gap-3 rounded-md bg-card/70 px-3 py-2 text-sm text-warning-foreground">
                      <input
                        checked={overrideWithoutValidation}
                        className="mt-1 h-4 w-4 shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                        onChange={(event) => setOverrideWithoutValidation(event.target.checked)}
                        type="checkbox"
                      />
                      <span>
                        Record without validation evidence
                      </span>
                    </label>
                    {overrideWithoutValidation ? (
                      <label className="mt-3 block">
                        <span className="text-sm font-medium text-warning-foreground">
                          Override rationale
                        </span>
                        <textarea
                          className={`${fieldClassName} min-h-24 border-warning-border bg-card text-foreground`}
                          onChange={(event) => setOverrideReason(event.target.value)}
                          placeholder="Explain why this decision must be recorded before validation results exist."
                          value={overrideReason}
                        />
                        <span className="mt-1 block text-xs leading-5 text-warning-foreground">
                          {overrideReady
                            ? "Override rationale is ready."
                            : "Write at least 20 characters to unlock recording."}
                        </span>
                      </label>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="space-y-4">
                <label className="block">
                  <span className="text-sm font-medium">Decision title</span>
                  <input
                    id="decision-title"
                    className={fieldClassName}
                    onChange={(event) => setTitle(event.target.value)}
                    value={title}
                  />
                </label>

                <label className="block">
                  <span className="text-sm font-medium">Rationale</span>
                  <textarea
                    className={`${fieldClassName} min-h-28`}
                    onChange={(event) => setRationale(event.target.value)}
                    value={rationale}
                  />
                </label>

                <label className="block">
                  <span className="text-sm font-medium">Expected outcome</span>
                  <textarea
                    className={`${fieldClassName} min-h-24`}
                    onChange={(event) => setExpectedOutcome(event.target.value)}
                    value={expectedOutcome}
                  />
                </label>
              </div>

              <div className="space-y-4">
                <label className="block">
                  <span className="text-sm font-medium">Decision type</span>
                  <select
                    className={fieldClassName}
                    onChange={(event) => setDecisionType(event.target.value as DecisionType)}
                    value={decisionType}
                  >
                    {decisionTypes.map((item) => (
                      <option key={item} value={item}>
                        {decisionLabel(item)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="text-sm font-medium">Review date</span>
                  <input
                    className={fieldClassName}
                    onChange={(event) => setReviewDate(event.target.value)}
                    type="date"
                    value={reviewDate}
                  />
                </label>

                <div className="rounded-md border border-border bg-surface p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className="text-sm font-semibold">Evidence links</h3>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {draftLinkCount > 0
                          ? `${draftLinkCount} selected for traceability`
                          : "No links selected yet"}
                      </p>
                    </div>
                    <Link2 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  </div>
                  <div className="mt-3 space-y-2">
                    <LinkPicker
                      items={assumptions}
                      label="Blockers"
                      onChange={setLinkedAssumptions}
                      selected={linkedAssumptions}
                      titleFor={(item) => assumptionBeliefText(item.text)}
                    />
                    <LinkPicker
                      items={evidence}
                      label="Evidence"
                      onChange={setLinkedEvidence}
                      selected={linkedEvidence}
                      titleFor={(item) => item.title ?? item.url ?? item.id}
                    />
                    <LinkPicker
                      items={artifacts}
                      label="Briefs, memos, or plans"
                      onChange={setLinkedArtifacts}
                      selected={linkedArtifacts}
                      titleFor={(item) => item.title}
                    />
                    <LinkPicker
                      items={experiments}
                      label="Validation tests"
                      onChange={setLinkedExperiments}
                      selected={linkedExperiments}
                      titleFor={(item) => item.name}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-xs leading-5 text-muted-foreground">
                Recording preserves the decision, rationale, expected outcome, and selected links.
              </p>
              <Button
                disabled={createMutation.isPending || !canSubmitDecision}
                type="submit"
              >
                <ScrollText className="h-4 w-4" aria-hidden="true" />
                {createMutation.isPending
                  ? "Recording decision..."
                  : validationGuardActive
                    ? "Record with override"
                    : "Record decision"}
              </Button>
            </div>
          </form>
        </DomainPanel>
      ) : null}

      <DomainPanel className="self-start">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Decision record</h2>
          </div>
          <span className="text-sm text-muted-foreground">{decisions.length} total</span>
        </div>

        {error ? (
          <div className="mt-4">
            <DomainError message={(error as Error).message} />
          </div>
        ) : null}

        {decisionsQuery.isLoading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading decisions...</p>
        ) : decisions.length === 0 ? (
          <div className="mt-4 rounded-md border border-dashed border-border p-4">
            <h3 className="text-sm font-semibold">No decisions recorded yet.</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Decisions capture what you chose, why you chose it, what evidence supported
              it, and when to revisit it.
            </p>
            <Button
              className="mt-3"
              onClick={openDecisionForm}
              type="button"
              variant="secondary"
            >
              <ScrollText className="h-4 w-4" aria-hidden="true" />
              {validationGuardActive ? "Prepare override record" : "Record decision"}
            </Button>
          </div>
        ) : (
          <div className="mt-4 divide-y divide-border">
            {decisions.map((decision) => (
              <details key={decision.id} className="py-4 first:pt-0">
                <summary className="cursor-pointer list-none rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold">{decision.title}</h3>
                        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                          {decisionLabel(decision.decision_type)}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">
                        {new Date(decision.created_at).toLocaleDateString()}
                        {decision.review_date ? ` · review ${decision.review_date}` : ""}
                      </p>
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                      <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
                      {decision.links.length}
                    </span>
                  </div>
                </summary>
                {decision.rationale ? (
                  <MarkdownContent
                    className="mt-3 border-t border-border pt-3 text-sm leading-6 text-muted-foreground"
                    markdown={decision.rationale}
                  />
                ) : null}
                {decision.expected_outcome ? (
                  <div className="mt-3 border-t border-border pt-3">
                    <MarkdownContent
                      className="space-y-2 text-sm leading-6 text-muted-foreground"
                      markdown={decision.expected_outcome}
                    />
                  </div>
                ) : null}
                {decision.links.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {decision.links.map((link) => (
                      <span
                        className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                        key={link.id}
                      >
                        {link.linked_type}
                      </span>
                    ))}
                  </div>
                ) : null}
              </details>
            ))}
          </div>
        )}
      </DomainPanel>
    </section>
  );
}

function LinkPicker<T extends { id: string }>({
  items,
  label,
  onChange,
  selected,
  titleFor,
}: {
  items: T[];
  label: string;
  onChange: (value: string[]) => void;
  selected: string[];
  titleFor: (item: T) => string;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <details className="rounded-md border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
        <span className="font-medium">{label}</span>
        <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
          {selected.length} of {items.length}
          <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      </summary>
      <fieldset className="border-t border-border p-2">
        <legend className="sr-only">{label}</legend>
        <div className="max-h-36 space-y-2 overflow-auto">
          {items.map((item) => (
            <label className="flex items-start gap-2 text-sm text-muted-foreground" key={item.id}>
              <input
                checked={selected.includes(item.id)}
                className="mt-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                onChange={() => onChange(toggle(selected, item.id))}
                type="checkbox"
              />
              <span className="line-clamp-2">{titleFor(item)}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </details>
  );
}

const fieldClassName =
  "mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-focus";

type DecisionSuggestion = {
  actionLabel: string;
  expectedOutcome: string;
  linkedAssumptionId: string | null;
  linkedExperimentIds: string[];
  missingEvidence: string[];
  rationale: string;
  title: string;
  type: DecisionType;
};

function buildDecisionSuggestion({
  assumptions,
  decisionType,
  evidenceCount,
  experiments,
  label,
  overview,
}: {
  assumptions: Assumption[];
  decisionType?: DecisionType;
  evidenceCount: number;
  experiments: Experiment[];
  label?: string;
  overview: Awaited<ReturnType<typeof getProjectOverview>> | undefined;
}): DecisionSuggestion {
  const hasExperiments = experiments.length > 0;
  const hasLoggedResults = experiments.some((experiment) => experiment.results.length > 0);
  const riskiestAssumption = [...assumptions].sort(compareDecisionAssumptions)[0] ?? null;
  const unresolvedHighRisk = riskiestAssumption
    ? riskiestAssumption.status !== "validated"
    : false;
  const type = decisionType ?? "run_experiment";
  const actionLabel = label ?? decisionLabel(type);
  const currentRecommendation = clarifyDecisionNarrative(
    overview?.current_recommendation.recommendation ?? "Continue research. Do not build yet.",
  );
  const currentRationale = clarifyDecisionNarrative(
    overview?.current_recommendation.rationale ??
      "The project needs stronger proof before a build decision is justified.",
  );
  const explicitRecommendedDecision =
    currentRecommendation.match(/^Recommended decision:\s*(.+)$/i)?.[1] ?? null;
  const missingEvidence = [
    evidenceCount === 0 ? "Add or gather source-backed evidence for the core claim." : null,
    assumptions.length === 0 ? "Identify and rank the decision blockers." : null,
    !hasExperiments ? "Create a validation plan for the top decision blocker." : null,
    !hasLoggedResults ? "Log at least one real validation result." : null,
    unresolvedHighRisk && riskiestAssumption
      ? decisionBlockerText(riskiestAssumption)
      : null,
  ].filter((item): item is string => Boolean(item));

  if (type === "build") {
    return {
      actionLabel,
      expectedOutcome: hasLoggedResults
        ? "Move into a narrow build pass only if the logged validation result supports the decision blocker."
        : "This should trigger a review after validation results are logged, because proceed evidence is currently missing.",
      linkedAssumptionId: riskiestAssumption?.id ?? null,
      linkedExperimentIds: experiments.slice(0, 1).map((experiment) => experiment.id),
      missingEvidence,
      rationale: hasLoggedResults
        ? `Proceed only with a narrow scope. Current recommendation: ${currentRecommendation}`
        : `Proceed is premature. ${currentRationale} Log validation evidence before committing build effort.`,
      title: hasLoggedResults ? "Proceed with narrow scope" : "Proceed with validation warning",
      type,
    };
  }

  if (type === "pivot") {
    return {
      actionLabel,
      expectedOutcome:
        "Use the evidence trail to narrow the wedge, change the target customer, or reposition the idea before more build work.",
      linkedAssumptionId: riskiestAssumption?.id ?? null,
      linkedExperimentIds: experiments.slice(0, 1).map((experiment) => experiment.id),
      missingEvidence,
      rationale: `A pivot is justified only if the current decision blocker is weak or invalidated. Current recommendation: ${currentRecommendation}`,
      title: "Pivot based on validation signal",
      type,
    };
  }

  if (type === "pause" || type === "kill") {
    return {
      actionLabel,
      expectedOutcome:
        type === "kill"
          ? "Stop active work and preserve the evidence trail for future reference."
          : "Pause build work until a stronger validation signal is available.",
      linkedAssumptionId: riskiestAssumption?.id ?? null,
      linkedExperimentIds: experiments.slice(0, 1).map((experiment) => experiment.id),
      missingEvidence,
      rationale: `Use this only when the missing evidence is material enough to stop momentum. Current recommendation: ${currentRecommendation}`,
      title: type === "kill" ? "Kill the idea" : "Pause until evidence improves",
      type,
    };
  }

  return {
    actionLabel: label ?? "Continue research",
    expectedOutcome:
      "Run or complete the next validation test, update confidence in the decision blocker, and revisit the decision after results are logged.",
    linkedAssumptionId: riskiestAssumption?.id ?? null,
    linkedExperimentIds: experiments
      .filter((experiment) => experiment.results.length === 0)
      .slice(0, 1)
      .map((experiment) => experiment.id),
    missingEvidence,
    rationale: `${currentRationale} The next decision should wait until the validation loop has real evidence.`,
    title: explicitRecommendedDecision
      ? sentenceCase(explicitRecommendedDecision)
      : hasLoggedResults
        ? "Continue research unless the result supports a narrow proceed decision"
        : "Continue research. Do not proceed yet",
    type: "run_experiment",
  };
}

function sentenceCase(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function compareDecisionAssumptions(a: Assumption, b: Assumption) {
  const score = (assumption: Assumption) =>
    (assumption.kill_risk ? 100 : 0) +
    importanceScore(assumption.importance) +
    uncertaintyScore(assumption.uncertainty);
  return score(b) - score(a);
}

function importanceScore(value: Assumption["importance"]) {
  return { critical: 40, high: 30, medium: 15, low: 5 }[value];
}

function uncertaintyScore(value: Assumption["uncertainty"]) {
  return { high: 25, medium: 12, low: 3 }[value];
}

function toggle(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function emptyToUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function withOverrideRationale(
  rationale: string,
  overrideReason: string,
  shouldIncludeOverride: boolean,
) {
  if (!shouldIncludeOverride) {
    return rationale;
  }
  const base = rationale.trim();
  const override = `Validation override: ${overrideReason.trim()}`;
  return base.length > 0 ? `${base}\n\n${override}` : override;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function decisionLabel(value: DecisionType) {
  const labels: Record<DecisionType, string> = {
    build: "Proceed",
    pivot: "Pivot",
    pause: "Pause",
    kill: "Kill",
    change_icp: "Change ICP",
    change_positioning: "Change positioning",
    run_experiment: "Continue research",
    other: "Other",
  };
  return labels[value] ?? formatLabel(value);
}

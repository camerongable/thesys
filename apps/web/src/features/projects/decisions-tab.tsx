"use client";

import { Link2, Plus, ScrollText } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  createDecision,
  DecisionType,
  listArtifacts,
  listAssumptions,
  listDecisions,
  listEvidenceSources,
  listExperiments,
} from "@/lib/api";

type DecisionsTabProps = {
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

export function DecisionsTab({ projectId }: DecisionsTabProps) {
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

  const createMutation = useMutation({
    mutationFn: () =>
      createDecision(projectId, {
        decision_type: decisionType,
        title,
        rationale: emptyToUndefined(rationale),
        expected_outcome: emptyToUndefined(expectedOutcome),
        review_date: emptyToUndefined(reviewDate),
        linked_assumption_ids: linkedAssumptions,
        linked_evidence_source_ids: linkedEvidence,
        linked_artifact_ids: linkedArtifacts,
        linked_experiment_ids: linkedExperiments,
      }),
    onSuccess: async () => {
      setTitle("");
      setRationale("");
      setExpectedOutcome("");
      setReviewDate("");
      setLinkedAssumptions([]);
      setLinkedEvidence([]);
      setLinkedArtifacts([]);
      setLinkedExperiments([]);
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "decisions"] });
    },
  });

  const decisions = decisionsQuery.data ?? [];
  const assumptions = assumptionsQuery.data ?? [];
  const evidence = evidenceQuery.data ?? [];
  const artifacts = artifactsQuery.data ?? [];
  const experiments = experimentsQuery.data ?? [];
  const error =
    decisionsQuery.error ??
    assumptionsQuery.error ??
    evidenceQuery.error ??
    artifactsQuery.error ??
    experimentsQuery.error ??
    createMutation.error ??
    null;

  return (
    <section className="mt-6 space-y-6">
      <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <form
          className="rounded-lg border border-border bg-white p-5"
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate();
          }}
        >
          <div className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Record Decision</h2>
          </div>

          <label className="mt-4 block">
            <span className="text-sm font-medium">Type</span>
            <select
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setDecisionType(event.target.value as DecisionType)}
              value={decisionType}
            >
              {decisionTypes.map((item) => (
                <option key={item} value={item}>
                  {formatLabel(item)}
                </option>
              ))}
            </select>
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Title</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setTitle(event.target.value)}
              value={title}
            />
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Rationale</span>
            <textarea
              className="mt-2 min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setRationale(event.target.value)}
              value={rationale}
            />
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Expected Outcome</span>
            <textarea
              className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setExpectedOutcome(event.target.value)}
              value={expectedOutcome}
            />
          </label>

          <label className="mt-3 block">
            <span className="text-sm font-medium">Review Date</span>
            <input
              className="mt-2 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              onChange={(event) => setReviewDate(event.target.value)}
              type="date"
              value={reviewDate}
            />
          </label>

          <div className="mt-5 space-y-4">
            <LinkPicker
              items={assumptions}
              label="Link assumptions"
              onChange={setLinkedAssumptions}
              selected={linkedAssumptions}
              titleFor={(item) => item.text}
            />
            <LinkPicker
              items={evidence}
              label="Link evidence"
              onChange={setLinkedEvidence}
              selected={linkedEvidence}
              titleFor={(item) => item.title ?? item.url ?? item.id}
            />
            <LinkPicker
              items={artifacts}
              label="Link artifacts"
              onChange={setLinkedArtifacts}
              selected={linkedArtifacts}
              titleFor={(item) => item.title}
            />
            <LinkPicker
              items={experiments}
              label="Link experiments"
              onChange={setLinkedExperiments}
              selected={linkedExperiments}
              titleFor={(item) => item.name}
            />
          </div>

          <Button
            className="mt-5"
            disabled={createMutation.isPending || title.trim().length === 0}
            type="submit"
          >
            <ScrollText className="h-4 w-4" aria-hidden="true" />
            {createMutation.isPending ? "Recording..." : "Record"}
          </Button>
        </form>

        <div className="rounded-lg border border-border bg-white p-5">
          <div className="flex items-center justify-between border-b border-border pb-4">
            <div className="flex items-center gap-2">
              <ScrollText className="h-4 w-4 text-primary" aria-hidden="true" />
              <h2 className="text-base font-semibold">Decision Ledger</h2>
            </div>
            <span className="text-sm text-muted-foreground">{decisions.length} total</span>
          </div>

          {error ? (
            <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {(error as Error).message}
            </div>
          ) : null}

          {decisionsQuery.isLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading decisions...</p>
          ) : decisions.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">No decisions recorded yet.</p>
          ) : (
            <div className="mt-4 space-y-4">
              {decisions.map((decision) => (
                <article key={decision.id} className="rounded-md border border-border p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold">{decision.title}</h3>
                        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                          {formatLabel(decision.decision_type)}
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
                  {decision.rationale ? (
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {decision.rationale}
                    </p>
                  ) : null}
                  {decision.expected_outcome ? (
                    <p className="mt-3 border-t border-border pt-3 text-sm leading-6 text-muted-foreground">
                      {decision.expected_outcome}
                    </p>
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
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
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
    <fieldset>
      <legend className="text-sm font-medium">{label}</legend>
      <div className="mt-2 max-h-32 space-y-2 overflow-auto rounded-md border border-border p-2">
        {items.map((item) => (
          <label className="flex items-start gap-2 text-sm text-muted-foreground" key={item.id}>
            <input
              checked={selected.includes(item.id)}
              className="mt-1"
              onChange={() => onChange(toggle(selected, item.id))}
              type="checkbox"
            />
            <span className="line-clamp-2">{titleFor(item)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function toggle(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function emptyToUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

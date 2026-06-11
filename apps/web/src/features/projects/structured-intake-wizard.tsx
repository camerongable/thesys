"use client";

import { Check, CircleHelp, FileCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  analyzeProjectIntake,
  answerProjectIntake,
  ClarifyingAnswer,
  finalizeProjectIntake,
  Project,
  StructuredProjectIntake,
} from "@/lib/api";
import { MarkdownContent } from "@/features/projects/markdown-content";
import { WorkflowTrace } from "@/features/projects/workflow-trace";

type StructuredIntakeWizardProps = {
  onFinalized?: () => Promise<string | null> | string | null;
  project: Project;
  sectionId?: string;
};

export function StructuredIntakeWizard({
  onFinalized,
  project,
  sectionId = "structured-intake",
}: StructuredIntakeWizardProps) {
  const queryClient = useQueryClient();
  const [rawIdea, setRawIdea] = useState(
    project.short_description ?? project.current_thesis?.thesis_text ?? "",
  );
  const [intake, setIntake] = useState<StructuredProjectIntake | null>(null);
  const [answers, setAnswers] = useState<ClarifyingAnswer[]>([]);
  const [appliedAnswers, setAppliedAnswers] = useState<ClarifyingAnswer[]>([]);
  const [finalizedMessage, setFinalizedMessage] = useState<string | null>(null);
  const filledAnswers = answers.filter((answer) => answer.answer.trim().length > 0);

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeProjectIntake(project.id, { raw_idea: rawIdea }),
    onSuccess: (result) => {
      setIntake(result.intake);
      setAnswers(result.intake.clarifying_questions.map((question) => ({ question, answer: "" })));
      setAppliedAnswers([]);
      setFinalizedMessage(null);
    },
  });

  const answerMutation = useMutation({
    mutationFn: () =>
      answerProjectIntake(project.id, {
        raw_idea: rawIdea,
        initial_intake: intake ?? undefined,
        answers: mergeAnswers(appliedAnswers, filledAnswers),
      }),
    onSuccess: (result) => {
      setIntake(result.intake);
      setAppliedAnswers((current) => mergeAnswers(current, filledAnswers));
      setAnswers(result.intake.clarifying_questions.map((question) => ({ question, answer: "" })));
      setFinalizedMessage(null);
    },
  });

  const finalizeMutation = useMutation({
    mutationFn: () =>
      finalizeProjectIntake(project.id, {
        structured_intake: intake as StructuredProjectIntake,
        raw_idea: rawIdea,
        answers: mergeAnswers(appliedAnswers, filledAnswers),
      }),
    onSuccess: async (result) => {
      queryClient.setQueryData(["projects", project.id], result.project);
      await queryClient.invalidateQueries({
        queryKey: ["projects", project.id],
        refetchType: "active",
      });
      await queryClient.invalidateQueries({ queryKey: ["projects", project.id, "overview"] });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", project.id, "workflows"] });
      await queryClient.invalidateQueries({ queryKey: ["projects", project.id, "evals", "mvp"] });
      const nextActionLabel = (await onFinalized?.()) ?? null;
      setAppliedAnswers([]);
      setFinalizedMessage(
        nextActionLabel
          ? `Project context saved. Next step is now ${nextActionLabel}.`
          : "Project context saved.",
      );
    },
  });

  const pending = analyzeMutation.isPending || answerMutation.isPending || finalizeMutation.isPending;
  const error =
    analyzeMutation.error ?? answerMutation.error ?? finalizeMutation.error ?? null;

  function updateAnswer(index: number, answer: string) {
    setAnswers((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, answer } : item)),
    );
  }

  return (
    <section id={sectionId} className="mt-6 rounded-lg border border-border bg-card p-5">
      <div className="flex flex-col gap-4 border-b border-border pb-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
            <h2 className="text-base font-semibold">Project context</h2>
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Rough idea, target segments, problem hypotheses, and unresolved questions.
          </p>
        </div>
        {project.customer_segments.length > 0 || project.problems.length > 0 ? (
          <span className="inline-flex w-fit items-center gap-2 rounded-md bg-success-muted px-2 py-1 text-xs font-medium text-success-foreground">
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            Structured
          </span>
        ) : null}
      </div>

      <label className="mt-5 block">
        <span className="text-sm font-medium">Rough idea</span>
        <textarea
          id="structured-intake-raw-idea"
          className="mt-2 min-h-32 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          maxLength={10000}
          onChange={(event) => setRawIdea(event.target.value)}
          value={rawIdea}
        />
      </label>

      <div className="mt-4 flex flex-wrap gap-3">
        <Button
          disabled={pending || rawIdea.trim().length === 0}
          onClick={() => analyzeMutation.mutate()}
          type="button"
        >
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          {analyzeMutation.isPending ? "Structuring..." : "Structure context"}
        </Button>
        <Button
          disabled={pending || !intake || filledAnswers.length === 0}
          onClick={() => answerMutation.mutate()}
          type="button"
          variant="secondary"
        >
          <CircleHelp className="h-4 w-4" aria-hidden="true" />
          {answerMutation.isPending
            ? "Applying answers..."
            : `Apply ${filledAnswers.length === 1 ? "answer" : "answers"} to draft`}
        </Button>
        <Button
          disabled={pending || !intake}
          onClick={() => finalizeMutation.mutate()}
          type="button"
          variant="secondary"
        >
          <FileCheck className="h-4 w-4" aria-hidden="true" />
          {finalizeMutation.isPending ? "Saving..." : "Save project context"}
        </Button>
      </div>

      {error ? (
        <div
          className="mt-4 break-words rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground"
          role="alert"
        >
          {(error as Error).message}
        </div>
      ) : null}

      <div className="mt-4">
        <WorkflowTrace
          pending={pending}
          pendingSteps={["analyze_idea", "generate_clarifying_questions"]}
          runId={
            analyzeMutation.data?.ai_run_id ??
            answerMutation.data?.ai_run_id ??
            finalizeMutation.data?.ai_run_id ??
            null
          }
        />
      </div>

      {appliedAnswers.length > 0 ? (
        <div className="mt-4 rounded-md border border-success-border bg-success-muted px-3 py-2 text-sm text-success-foreground">
          Applied {appliedAnswers.length}{" "}
          {appliedAnswers.length === 1 ? "clarifying answer" : "clarifying answers"} to the draft.
          Save project context to update the project and next step.
        </div>
      ) : null}

      {intake ? (
        <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold">{intake.project_name}</h3>
            <MarkdownContent
              className="mt-2 space-y-2 text-sm leading-6 text-muted-foreground"
              markdown={intake.one_sentence_summary}
            />
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <ListBlock label="Target users" values={intake.target_users} />
              <ListBlock label="Problem hypotheses" values={intake.problem_hypotheses} />
              <ListBlock label="Suspected competitors" values={intake.suspected_competitors} />
              <ListBlock label="Key uncertainties" values={intake.key_uncertainties} />
            </div>
            <div className="mt-4 rounded-md bg-muted px-3 py-2 text-sm">
              <span className="font-medium">Proposed solution:</span>
              <MarkdownContent
                className="mt-1 space-y-2 text-sm leading-6 text-muted-foreground"
                markdown={intake.proposed_solution}
              />
            </div>
          </div>

          <div className="border-t border-border pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
            <h3 className="text-sm font-semibold">Clarifying questions</h3>
            <div className="mt-3 space-y-3">
              {answers.length === 0 ? (
                <p className="text-sm text-muted-foreground">No open questions.</p>
              ) : (
                answers.map((item, index) => (
                  <label className="block" key={`${item.question}-${index}`}>
                    <span className="text-sm text-muted-foreground">{item.question}</span>
                    <textarea
                      className="mt-2 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
                      maxLength={5000}
                      onChange={(event) => updateAnswer(index, event.target.value)}
                      value={item.answer}
                    />
                  </label>
                ))
              )}
            </div>
          </div>
        </div>
      ) : null}

      {finalizedMessage ? (
        <div className="mt-4 rounded-md border border-success-border bg-success-muted px-3 py-2 text-sm text-success-foreground">
          {finalizedMessage}
        </div>
      ) : null}
    </section>
  );
}

function mergeAnswers(existing: ClarifyingAnswer[], incoming: ClarifyingAnswer[]) {
  const byQuestion = new Map<string, ClarifyingAnswer>();

  for (const answer of [...existing, ...incoming]) {
    const question = answer.question.trim();
    const value = answer.answer.trim();
    if (question.length > 0 && value.length > 0) {
      byQuestion.set(question.toLowerCase(), { question, answer: value });
    }
  }

  return [...byQuestion.values()];
}

function ListBlock({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-normal text-muted-foreground">
        {label}
      </h4>
      {values.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">Unknown</p>
      ) : (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {values.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

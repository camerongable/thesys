"use client";

import { ArrowLeft, CheckCircle2, CircleAlert, FileSearch, GitBranch, Save } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { AiModeIndicator } from "@/features/ai/ai-mode-indicator";
import { DomainError } from "@/features/projects/decision-room";
import {
  ClarifyingAnswer,
  ConversationalInvestigationPreview,
  createProject,
  finalizeProjectIntake,
  InvestigationMode,
  InvestigationModeOption,
  previewInvestigation,
} from "@/lib/api";

const RAW_IDEA_MAX_LENGTH = 10000;
type CreateLandingTarget = "current" | "research" | "wedge";

export function NewProjectForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [rawIdea, setRawIdea] = useState("");
  const [answers, setAnswers] = useState<ClarifyingAnswer[]>([]);
  const [preview, setPreview] = useState<ConversationalInvestigationPreview | null>(null);
  const [selectedMode, setSelectedMode] = useState<InvestigationMode>("evidence_review");
  const [submitted, setSubmitted] = useState(false);
  const trimmedRawIdea = rawIdea.trim();
  const rawIdeaError =
    (submitted || rawIdea.length > 0) && trimmedRawIdea.length === 0
      ? "Paste at least one visible sentence about the idea."
      : null;
  const rawIdeaDescriptionId = rawIdeaError ? "raw-idea-limit raw-idea-error" : "raw-idea-limit";
  const guidance = useMemo(() => investigationGuidance(rawIdea, preview), [rawIdea, preview]);
  const readyCount = guidance.filter((item) => item.complete).length;

  const previewMutation = useMutation({
    mutationFn: previewInvestigation,
    onSuccess: (result) => {
      setPreview(result);
      setSelectedMode(result.recommended_mode.mode);
      if (result.clarifying_questions.length > 0) {
        setAnswers((current) =>
          result.clarifying_questions.map((question) => ({
            question,
            answer: current.find((item) => item.question === question)?.answer ?? "",
          })),
        );
      }
    },
  });

  const createMutation = useMutation({
    mutationFn: async (target: CreateLandingTarget) => {
      if (!preview) {
        throw new Error("Shape the idea before creating the investigation.");
      }
      const project = await createProject({
        name: preview.structured_intake.project_name,
        short_description: preview.structured_intake.one_sentence_summary,
        initial_thesis: preview.structured_intake.one_sentence_summary,
      });
      await finalizeProjectIntake(project.id, {
        structured_intake: preview.structured_intake,
        raw_idea: preview.raw_idea,
        answers: filledAnswers(answers),
      });
      return { project, target };
    },
    onSuccess: async ({ project, target }) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}${landingHash(target)}`);
    },
  });

  const pending = previewMutation.isPending || createMutation.isPending;
  const canPreview = trimmedRawIdea.length > 0 && !rawIdeaError && !pending;
  const canCreate = Boolean(preview?.ready_to_create) && !pending;

  function useSampleIdea() {
    previewMutation.reset();
    createMutation.reset();
    setSubmitted(false);
    setPreview(null);
    setAnswers([]);
    setRawIdea(
      "Independent online fitness coaches manage weekly client check-ins across spreadsheets, DMs, and coaching notes. They lose time spotting clients who need intervention before they churn. I want an AI workflow that turns check-ins into at-risk client triage and coaching follow-up drafts. The riskiest question is whether coaches would pay for this or keep using manual tracking.",
    );
  }

  function shapeIdea(options?: { continueWithAssumptions?: boolean }) {
    setSubmitted(true);
    if (!canPreview && trimmedRawIdea.length === 0) {
      return;
    }
    previewMutation.mutate({
      raw_idea: trimmedRawIdea,
      answers: filledAnswers(answers),
      continue_with_assumptions: options?.continueWithAssumptions ?? false,
      mode_preference: selectedMode,
    });
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (preview?.ready_to_create) {
      createMutation.mutate("current");
      return;
    }
    shapeIdea();
  }

  const error = previewMutation.error ?? createMutation.error;

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Link
            className="-ml-2 inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            href="/projects"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Projects
          </Link>
          <div className="flex w-full min-w-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            <ThemeToggle />
            <div className="min-w-0 flex-1 sm:flex-none">
              <AiModeIndicator />
            </div>
          </div>
        </div>

        <section className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0">
            <header className="border-b border-border pb-5">
              <p className="text-sm text-muted-foreground">New investigation</p>
              <h1 className="mt-2 max-w-[68ch] text-2xl font-semibold tracking-normal sm:text-3xl">
                Paste the messy version. Thesys will shape it.
              </h1>
              <p className="mt-3 max-w-[68ch] text-sm leading-6 text-muted-foreground">
                Start with rough notes. Thesys will ask only for missing context, draft a
                first testable thesis, and recommend the first investigation path.
              </p>
              <div className="mt-4 grid grid-cols-2 gap-2 sm:hidden">
                <Button onClick={useSampleIdea} type="button" variant="secondary">
                  Use sample
                </Button>
                <Button disabled={!canPreview && !canCreate} form="new-project-form" type="submit">
                  {preview?.ready_to_create ? "Create" : "Shape"}
                </Button>
              </div>
            </header>

            <form
              className="mt-6 space-y-5 rounded-lg border border-border bg-card p-5"
              id="new-project-form"
              onSubmit={onSubmit}
            >
              <label className="block">
                <span className="text-sm font-medium">Rough idea</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  Include the user, problem, current workaround, desired solution, or what would
                  prove the idea is worth another week. Missing parts are fine.
                </span>
                <textarea
                  aria-describedby={rawIdeaDescriptionId}
                  aria-invalid={Boolean(rawIdeaError)}
                  className="mt-2 min-h-48 w-full rounded-md border border-border bg-input px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-focus"
                  dir="auto"
                  maxLength={RAW_IDEA_MAX_LENGTH}
                  onChange={(event) => {
                    if (previewMutation.isError) previewMutation.reset();
                    if (createMutation.isError) createMutation.reset();
                    setPreview(null);
                    setAnswers([]);
                    setRawIdea(event.target.value);
                  }}
                  placeholder="Example: I want to build an AI assistant for independent fitness coaches. They manage check-ins in spreadsheets and DMs, and I think the painful moment is finding clients who need intervention..."
                  required
                  value={rawIdea}
                />
                <FieldLimit current={rawIdea.length} id="raw-idea-limit" max={RAW_IDEA_MAX_LENGTH} />
                {rawIdeaError ? (
                  <p
                    className="mt-1 text-xs font-medium text-danger-foreground"
                    id="raw-idea-error"
                    role="alert"
                  >
                    {rawIdeaError}
                  </p>
                ) : null}
              </label>

              <div className="border-t border-border pt-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-sm font-semibold">Context check</h2>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {readyCount === 0
                        ? "Paste the rough idea and Thesys will find what is missing."
                        : `${readyCount}/4 signals are visible enough for a first thesis draft.`}
                    </p>
                  </div>
                  <button
                    className="inline-flex min-h-11 w-fit items-center justify-center rounded-md border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus:ring-focus sm:min-h-9 sm:py-1.5"
                    onClick={useSampleIdea}
                    type="button"
                  >
                    Use sample idea
                  </button>
                </div>
                <div className="mt-3 divide-y divide-border">
                  {guidance.map((item) => (
                    <div className="flex items-start gap-2 py-2" key={item.label}>
                      {item.complete ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success-foreground" aria-hidden="true" />
                      ) : (
                        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning-foreground" aria-hidden="true" />
                      )}
                      <div className="min-w-0">
                        <div className="text-xs font-medium text-foreground">{item.label}</div>
                        <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{item.hint}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {preview?.clarifying_questions.length ? (
                <section className="border-t border-border pt-4" aria-labelledby="clarifying-title">
                  <h2 id="clarifying-title" className="text-sm font-semibold">
                    A few missing pieces
                  </h2>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    Answer what you know, or continue with assumptions and keep these as open
                    questions.
                  </p>
                  <div className="mt-3 space-y-3">
                    {answers.map((answer, index) => (
                      <QuestionInput
                        answer={answer}
                        index={index}
                        key={answer.question}
                        onChange={(value) => {
                          setAnswers((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, answer: value } : item,
                            ),
                          );
                        }}
                      />
                    ))}
                  </div>
                  <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                    <Button
                      disabled={pending || filledAnswers(answers).length === 0}
                      onClick={() => shapeIdea()}
                      type="button"
                      variant="secondary"
                    >
                      Answer questions
                    </Button>
                    <Button
                      disabled={pending}
                      onClick={() => shapeIdea({ continueWithAssumptions: true })}
                      type="button"
                      variant="secondary"
                    >
                      Continue with assumptions
                    </Button>
                  </div>
                </section>
              ) : null}

              {preview ? (
                <section className="border-t border-border pt-4" aria-labelledby="thesis-title">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    First testable thesis
                  </p>
                  <h2 id="thesis-title" className="mt-1 text-lg font-semibold">
                    {preview.structured_intake.project_name}
                  </h2>
                  <div className="mt-4 grid gap-3">
                    <DraftRow label="Target user" value={preview.thesis_draft.target_user} />
                    <DraftRow label="Problem" value={preview.thesis_draft.problem} />
                    <DraftRow label="Current workaround" value={preview.thesis_draft.current_workaround} />
                    <DraftRow label="Possible wedge" value={preview.thesis_draft.possible_wedge} />
                    <DraftRow label="Biggest unknown" value={preview.thesis_draft.biggest_unknown} />
                    <DraftRow label="First proof" value={preview.thesis_draft.proof_needed} />
                  </div>
                  {preview.assumptions_made.length > 0 ? (
                    <div className="mt-4 rounded-md border border-warning-border bg-warning-muted p-3">
                      <h3 className="text-sm font-semibold text-warning-foreground">
                        Continuing with assumptions
                      </h3>
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-warning-foreground">
                        {preview.assumptions_made.map((assumption) => (
                          <li key={assumption}>{assumption}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </section>
              ) : null}

              {preview ? (
                <fieldset className="border-t border-border pt-4">
                  <legend className="text-sm font-medium">Recommended investigation path</legend>
                  <div className="mt-3 rounded-md border border-primary/30 bg-primary/10 p-3">
                    <div className="text-sm font-semibold">{preview.recommended_mode.label}</div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {preview.recommended_mode.description}
                    </p>
                    {preview.recommended_mode.why_recommended ? (
                      <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        Why: {preview.recommended_mode.why_recommended}
                      </p>
                    ) : null}
                  </div>
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
                      Compare investigation paths
                    </summary>
                    <div className="mt-3 grid gap-3 lg:grid-cols-3">
                      {preview.modes.map((mode) => (
                        <ModeOption
                          active={selectedMode === mode.mode}
                          key={mode.mode}
                          mode={mode}
                          recommended={preview.recommended_mode.mode === mode.mode}
                          onClick={() => setSelectedMode(mode.mode)}
                        />
                      ))}
                    </div>
                  </details>
                </fieldset>
              ) : null}

              {error ? (
                <DomainError
                  action={
                    <Button
                      className="w-fit border-danger-border text-danger-foreground hover:bg-danger-muted"
                      disabled={pending}
                      onClick={() => (preview ? createMutation.mutate("current") : shapeIdea())}
                      size="sm"
                      type="button"
                      variant="secondary"
                    >
                      Retry
                    </Button>
                  }
                  message={(error as Error).message}
                />
              ) : null}

              <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-muted-foreground">
                  {preview?.ready_to_create
                    ? "Choose where to start. The project opens on a focused Current Step unless you pick a deeper path."
                    : preview?.next_action_description ??
                      "Thesys will draft the thesis before anything is saved to project memory."}
                </p>
                <div className="flex flex-col gap-2 sm:flex-row">
                  {!preview?.ready_to_create ? (
                    <Button disabled={!canPreview} type="submit" variant={preview ? "secondary" : "default"}>
                      <FileSearch className="h-4 w-4" aria-hidden="true" />
                      {previewMutation.isPending ? "Shaping idea..." : preview ? "Refresh thesis" : "Shape idea"}
                    </Button>
                  ) : (
                    <>
                      <Button disabled={!canCreate} onClick={() => createMutation.mutate("current")} type="button">
                        <Save className="h-4 w-4" aria-hidden="true" />
                        {createMutation.isPending ? "Creating..." : "Continue to Current Step"}
                      </Button>
                      <Button
                        disabled={!canCreate}
                        onClick={() => createMutation.mutate("research")}
                        type="button"
                        variant="secondary"
                      >
                        <FileSearch className="h-4 w-4" aria-hidden="true" />
                        Run research
                      </Button>
                      <Button
                        disabled={!canCreate}
                        onClick={() => createMutation.mutate("wedge")}
                        type="button"
                        variant="secondary"
                      >
                        <GitBranch className="h-4 w-4" aria-hidden="true" />
                        Compare wedges
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </form>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-5 lg:self-start">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2">
                <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">How this starts</h2>
              </div>
              <div className="mt-4 space-y-4">
                <ProcessStep title="Shape the idea" text="Turn messy notes into a first testable thesis." />
                <ProcessStep title="Clarify only gaps" text="Answer 2-4 useful questions, or skip and keep assumptions visible." />
                <ProcessStep title="Pick a path" text="Choose quick orientation, evidence review, or validation sprint." />
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-4">
              <h2 className="text-sm font-semibold">You do not need all the answers.</h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Unknowns are part of the workflow. Continue with assumptions when the idea is
                still early; Thesys will keep those assumptions visible in the project.
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function QuestionInput({
  answer,
  index,
  onChange,
}: {
  answer: ClarifyingAnswer;
  index: number;
  onChange: (value: string) => void;
}) {
  const id = `clarifying-answer-${index}`;
  return (
    <label className="block" htmlFor={id}>
      <span className="text-sm font-medium">{answer.question}</span>
      <textarea
        className="mt-2 min-h-20 w-full rounded-md border border-border bg-input px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-focus"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Answer briefly, or leave blank and continue with assumptions."
        value={answer.answer}
      />
    </label>
  );
}

function DraftRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <p className="mt-1 text-sm leading-6 text-foreground">{value}</p>
    </div>
  );
}

function ModeOption({
  active,
  mode,
  onClick,
  recommended,
}: {
  active: boolean;
  mode: InvestigationModeOption;
  onClick: () => void;
  recommended: boolean;
}) {
  return (
    <button
      aria-pressed={active}
      className={[
        "rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
        active
          ? "border-primary bg-primary/10 text-foreground"
          : "border-border bg-card text-foreground hover:bg-muted",
      ].join(" ")}
      onClick={onClick}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium">{mode.label}</div>
          {recommended ? (
            <div className="mt-1 text-xs font-medium text-primary">Recommended</div>
          ) : null}
        </div>
        {active ? <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" /> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{mode.description}</p>
    </button>
  );
}

function investigationGuidance(
  rawIdea: string,
  preview: ConversationalInvestigationPreview | null,
) {
  const combined = `${rawIdea} ${preview?.thesis_draft.problem ?? ""} ${preview?.thesis_draft.current_workaround ?? ""} ${preview?.thesis_draft.biggest_unknown ?? ""}`.toLowerCase();
  return [
    {
      complete:
        /\b(coach|founder|manager|owner|team|buyer|user|customer|operator|creator|developer)\b/.test(
          combined,
        ) || Boolean(preview?.thesis_draft.target_user),
      hint: "Name the first user or buying context.",
      label: "Target user",
    },
    {
      complete: /\b(problem|pain|hard|manual|slow|frustrat|churn|struggle|workaround|lose time)\b/.test(combined),
      hint: "Describe the moment that hurts.",
      label: "Problem signal",
    },
    {
      complete: /\b(spreadsheet|email|dm|manual|crm|workaround|current|today|alternative|messages)\b/.test(combined),
      hint: "Include what they use today.",
      label: "Current workaround",
    },
    {
      complete: /\b(pay|willing|validate|test|pilot|interview|competitor|proof|risk|uncertain|unknown)\b/.test(combined),
      hint: "State what would change your mind.",
      label: "Riskiest proof",
    },
  ];
}

function filledAnswers(answers: ClarifyingAnswer[]) {
  return answers
    .map((answer) => ({ ...answer, answer: answer.answer.trim() }))
    .filter((answer) => answer.answer.length > 0);
}

function landingHash(target: CreateLandingTarget) {
  if (target === "research") {
    return "#research";
  }
  if (target === "wedge") {
    return "#wedge";
  }
  return "#current-step";
}

function FieldLimit({
  current,
  id,
  max,
}: {
  current: number;
  id: string;
  max: number;
}) {
  return (
    <p
      aria-live="polite"
      className="mt-1 text-xs leading-5 text-muted-foreground"
      id={id}
    >
      {formatNumber(current)} of {formatNumber(max)} characters
    </p>
  );
}

function ProcessStep({ text, title }: { text: string; title: string }) {
  return (
    <div className="flex gap-3">
      <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" aria-hidden="true" />
      <div className="min-w-0">
        <div className="text-sm font-medium">{title}</div>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">{text}</p>
      </div>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat(undefined).format(value);
}

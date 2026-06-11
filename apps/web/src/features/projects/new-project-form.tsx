"use client";

import { ArrowLeft, CheckCircle2, CircleAlert, FileSearch, Save } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { AiModeIndicator } from "@/features/ai/ai-mode-indicator";
import { DomainError } from "@/features/projects/decision-room";
import { createProject } from "@/lib/api";

type ScanType = "quick" | "deep";

const PROJECT_NAME_MAX_LENGTH = 255;
const SHORT_DESCRIPTION_MAX_LENGTH = 5000;
const INITIAL_THESIS_MAX_LENGTH = 10000;

export function NewProjectForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [initialThesis, setInitialThesis] = useState("");
  const [scanType, setScanType] = useState<ScanType>("deep");
  const [submitted, setSubmitted] = useState(false);
  const guidance = investigationGuidance(shortDescription, initialThesis);
  const readyCount = guidance.filter((item) => item.complete).length;
  const trimmedName = name.trim();
  const trimmedShortDescription = shortDescription.trim();
  const trimmedInitialThesis = initialThesis.trim();
  const nameError =
    (submitted || name.length > 0) && trimmedName.length === 0
      ? "Use at least one visible character."
      : null;
  const nameDescriptionId = nameError ? "idea-name-limit idea-name-error" : "idea-name-limit";

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}${scanType === "deep" ? "#research" : ""}`);
    },
  });
  const canCreate = trimmedName.length > 0 && !nameError && !mutation.isPending;

  function useSampleStructure() {
    mutation.reset();
    setSubmitted(false);
    setShortDescription(
      "Independent online fitness coaches manage client check-ins in spreadsheets, DMs, and memory. The painful moment is spotting which clients need intervention before they churn.",
    );
    setInitialThesis(
      "The riskiest uncertainty is willingness to pay for automated client triage. Validate with paid pilot interviews and compare against current spreadsheet and CRM workarounds.",
    );
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (mutation.isPending || trimmedName.length === 0) {
      return;
    }
    createInvestigation();
  }

  function createInvestigation() {
    mutation.mutate({
      name: trimmedName,
      short_description: trimmedShortDescription || undefined,
      initial_thesis: trimmedInitialThesis || undefined,
    });
  }

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
                Start with a rough idea.
              </h1>
              <p className="mt-3 max-w-[68ch] text-sm leading-6 text-muted-foreground">
                Capture the customer, problem, current workaround, and riskiest unknown.
                Thesys will turn that into a decision room and name the first validation step.
              </p>
              <div className="mt-4 grid grid-cols-2 gap-2 sm:hidden">
                <Button onClick={useSampleStructure} type="button" variant="secondary">
                  Use sample
                </Button>
                <Button
                  disabled={!canCreate}
                  form="new-project-form"
                  type="submit"
                >
                  Create
                </Button>
              </div>
            </header>

            <form
              className="mt-6 rounded-lg border border-border bg-card p-5"
              id="new-project-form"
              onSubmit={onSubmit}
            >
              <label className="block">
                <span className="text-sm font-medium">Idea name</span>
                <input
                  aria-describedby={nameDescriptionId}
                  aria-invalid={Boolean(nameError)}
                  className="mt-2 h-11 w-full rounded-md border border-border bg-input px-3 text-sm outline-none focus:ring-2 focus:ring-focus"
                  dir="auto"
                  maxLength={PROJECT_NAME_MAX_LENGTH}
                  onChange={(event) => {
                    if (mutation.isError) {
                      mutation.reset();
                    }
                    setName(event.target.value);
                  }}
                  placeholder="AI assistant for independent fitness coaches"
                  required
                  value={name}
                />
                <FieldLimit
                  current={name.length}
                  id="idea-name-limit"
                  max={PROJECT_NAME_MAX_LENGTH}
                />
                {nameError ? (
                  <p
                    className="mt-1 text-xs font-medium text-danger-foreground"
                    id="idea-name-error"
                    role="alert"
                  >
                    {nameError}
                  </p>
                ) : null}
              </label>

              <label className="mt-5 block">
                <span className="text-sm font-medium">Customer, problem, and current workaround</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  Include who has the problem, what they do today, and where that workflow hurts.
                </span>
                <textarea
                  aria-describedby="short-description-limit"
                  className="mt-2 min-h-28 w-full rounded-md border border-border bg-input px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-focus"
                  dir="auto"
                  maxLength={SHORT_DESCRIPTION_MAX_LENGTH}
                  onChange={(event) => {
                    if (mutation.isError) {
                      mutation.reset();
                    }
                    setShortDescription(event.target.value);
                  }}
                  placeholder="Independent online fitness coaches manage client check-ins in spreadsheets and DMs, then lose time finding who needs attention."
                  value={shortDescription}
                />
                <FieldLimit
                  current={shortDescription.length}
                  id="short-description-limit"
                  max={SHORT_DESCRIPTION_MAX_LENGTH}
                />
              </label>

              <label className="mt-5 block">
                <span className="text-sm font-medium">Riskiest uncertainty and proof needed</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  Name what would change your mind: willingness to pay, switching behavior, a competitor gap, or a validation test.
                </span>
                <textarea
                  aria-describedby="initial-thesis-limit"
                  className="mt-2 min-h-32 w-full rounded-md border border-border bg-input px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-focus"
                  dir="auto"
                  maxLength={INITIAL_THESIS_MAX_LENGTH}
                  onChange={(event) => {
                    if (mutation.isError) {
                      mutation.reset();
                    }
                    setInitialThesis(event.target.value);
                  }}
                  placeholder="Will coaches pay for automated client triage, or is the current manual workflow acceptable? Validate with five paid pilot interviews."
                  value={initialThesis}
                />
                <FieldLimit
                  current={initialThesis.length}
                  id="initial-thesis-limit"
                  max={INITIAL_THESIS_MAX_LENGTH}
                />
              </label>

              <div className="mt-5 border-t border-border pt-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-sm font-semibold">Input guide</h2>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {readyCount === 0
                        ? "Add detail to improve the first recommendation."
                        : `${readyCount}/4 signals are specific enough for a useful first recommendation.`}
                    </p>
                  </div>
                  <button
                    className="inline-flex min-h-11 w-fit items-center justify-center rounded-md border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:min-h-9 sm:py-1.5"
                    onClick={useSampleStructure}
                    type="button"
                  >
                    Use sample structure
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

              <fieldset className="mt-5">
                <legend className="text-sm font-medium">Investigation depth</legend>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <ScanTypeOption
                    active={scanType === "quick"}
                    description="Create the project room and structure the idea before deeper research."
                    label="Quick orientation"
                    onClick={() => setScanType("quick")}
                  />
                  <ScanTypeOption
                    active={scanType === "deep"}
                    description="Open the evidence lane after creation so you can approve a plan and gather sources."
                    label="Evidence review"
                    onClick={() => setScanType("deep")}
                  />
                </div>
              </fieldset>

              {mutation.isError ? (
                <div className="mt-4">
                  <DomainError
                    action={
                      <Button
                        className="w-fit border-danger-border text-danger-foreground hover:bg-danger-muted"
                        disabled={!canCreate}
                        onClick={createInvestigation}
                        size="sm"
                        type="button"
                        variant="secondary"
                      >
                        Retry create
                      </Button>
                    }
                    message={(mutation.error as Error).message}
                  />
                </div>
              ) : null}

              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-muted-foreground">
                  You can review the structured thesis before it is saved to project memory.
                </p>
                <Button disabled={!canCreate} type="submit">
                  <Save className="h-4 w-4" aria-hidden="true" />
                  {mutation.isPending ? "Creating investigation..." : "Create investigation"}
                </Button>
              </div>
            </form>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-5 lg:self-start">
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="flex items-center gap-2">
                <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
                <h2 className="text-sm font-semibold">What happens next</h2>
              </div>
              <div className="mt-4 space-y-4">
                <ProcessStep title="Structure the idea" text="Extract target users, problem hypotheses, solution shape, and open questions." />
                <ProcessStep title="Check evidence gaps" text="Identify missing sources, unsupported claims, and competitor gaps." />
                <ProcessStep title="Choose the next step" text="Recommend whether to research, test, pause, pivot, kill, or proceed narrowly." />
              </div>
            </div>

            <div className="rounded-lg border border-border bg-card p-4">
              <h2 className="text-sm font-semibold">Good input is specific.</h2>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Skip polish. Name the customer, the current workaround, the pain signal,
                and what would prove the idea is worth another week.
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function investigationGuidance(customerProblem: string, uncertainty: string) {
  const combined = `${customerProblem} ${uncertainty}`.toLowerCase();
  return [
    {
      complete: customerProblem.trim().length >= 20,
      hint: "Name the user or buying context.",
      label: "Target customer",
    },
    {
      complete: /\b(problem|pain|hard|manual|slow|frustrat|churn|struggle|workaround)\b/.test(combined),
      hint: "Describe the moment that hurts.",
      label: "Problem signal",
    },
    {
      complete: /\b(spreadsheet|email|dm|manual|crm|workaround|current|today|alternative)\b/.test(combined),
      hint: "Include what they use today.",
      label: "Current workaround",
    },
    {
      complete: /\b(pay|willing|validate|test|pilot|interview|competitor|proof|risk|uncertain)\b/.test(combined),
      hint: "State what would change your mind.",
      label: "Riskiest proof",
    },
  ];
}

function ScanTypeOption({
  active,
  description,
  label,
  onClick,
}: {
  active: boolean;
  description: string;
  label: string;
  onClick: () => void;
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
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium">{label}</div>
        {active ? <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" /> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
    </button>
  );
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

"use client";

import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { AiModeIndicator } from "@/features/ai/ai-mode-indicator";
import { createProject } from "@/lib/api";

type ScanType = "quick" | "deep";

export function NewProjectForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [initialThesis, setInitialThesis] = useState("");
  const [scanType, setScanType] = useState<ScanType>("deep");

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}${scanType === "deep" ? "#research" : ""}`);
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mutation.mutate({
      name,
      short_description: shortDescription || undefined,
      initial_thesis: initialThesis || undefined,
    });
  }

  return (
    <main className="min-h-screen px-5 py-6 md:px-8">
      <div className="mx-auto max-w-3xl">
        <Link
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
          href="/projects"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Projects
        </Link>

        <header className="mt-6 flex flex-col gap-3 border-b border-border pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Local workspace</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-normal">
              Investigate a New Idea
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Start with a rough idea. The app will help turn it into a research plan,
              strategic verdict, and first validation action.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <ThemeToggle />
            <AiModeIndicator />
          </div>
        </header>

        <form className="mt-6 rounded-lg border border-border bg-white p-5" onSubmit={onSubmit}>
          <label className="block">
            <span className="text-sm font-medium">What idea are you considering?</span>
            <input
              className="mt-2 h-11 w-full rounded-md border border-border px-3 text-sm outline-none focus:ring-2 focus:ring-primary"
              maxLength={255}
              onChange={(event) => setName(event.target.value)}
              placeholder="AI assistant for independent fitness coaches"
              required
              value={name}
            />
          </label>

          <label className="mt-5 block">
            <span className="text-sm font-medium">Who do you think it is for?</span>
            <textarea
              className="mt-2 min-h-28 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              maxLength={5000}
              onChange={(event) => setShortDescription(event.target.value)}
              placeholder="Optional. Example: independent online fitness coaches who manage client check-ins manually."
              value={shortDescription}
            />
          </label>

          <label className="mt-5 block">
            <span className="text-sm font-medium">What do you want to learn?</span>
            <textarea
              className="mt-2 min-h-32 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              maxLength={10000}
              onChange={(event) => setInitialThesis(event.target.value)}
              placeholder="Optional. Example: Is this worth building? Who are the real competitors? What should I validate first? Would users pay?"
              value={initialThesis}
            />
          </label>

          <div className="mt-5">
            <div className="text-sm font-medium">Choose the investigation depth</div>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <ScanTypeOption
                active={scanType === "quick"}
                description="Get oriented quickly, then decide whether to run deeper research."
                label="Quick Scan"
                onClick={() => setScanType("quick")}
              />
              <ScanTypeOption
                active={scanType === "deep"}
                description="Review a research plan, discover sources and competitors, and generate a cited memo."
                label="Deep Research Sprint"
                onClick={() => setScanType("deep")}
              />
            </div>
          </div>

          {mutation.isError ? (
            <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {(mutation.error as Error).message}
            </div>
          ) : null}

          <div className="mt-6 flex justify-end">
            <Button disabled={mutation.isPending} type="submit">
              <Save className="h-4 w-4" aria-hidden="true" />
              {mutation.isPending ? "Starting..." : "Start Investigation"}
            </Button>
          </div>
        </form>
      </div>
    </main>
  );
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
      className={
        active
          ? "rounded-lg border border-primary bg-muted p-4 text-left"
          : "rounded-lg border border-border bg-white p-4 text-left hover:bg-muted"
      }
      onClick={onClick}
      type="button"
    >
      <div className="font-medium">{label}</div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
    </button>
  );
}

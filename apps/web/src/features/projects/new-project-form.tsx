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

export function NewProjectForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [initialThesis, setInitialThesis] = useState("");

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(`/projects/${project.id}`);
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
            <h1 className="mt-1 text-2xl font-semibold tracking-normal">New Project</h1>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <ThemeToggle />
            <AiModeIndicator />
          </div>
        </header>

        <form className="mt-6 rounded-lg border border-border bg-white p-5" onSubmit={onSubmit}>
          <label className="block">
            <span className="text-sm font-medium">Name</span>
            <input
              className="mt-2 h-11 w-full rounded-md border border-border px-3 text-sm outline-none focus:ring-2 focus:ring-primary"
              maxLength={255}
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
          </label>

          <label className="mt-5 block">
            <span className="text-sm font-medium">Description</span>
            <textarea
              className="mt-2 min-h-28 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              maxLength={5000}
              onChange={(event) => setShortDescription(event.target.value)}
              value={shortDescription}
            />
          </label>

          <label className="mt-5 block">
            <span className="text-sm font-medium">Initial Thesis</span>
            <textarea
              className="mt-2 min-h-32 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              maxLength={10000}
              onChange={(event) => setInitialThesis(event.target.value)}
              value={initialThesis}
            />
          </label>

          {mutation.isError ? (
            <div className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {(mutation.error as Error).message}
            </div>
          ) : null}

          <div className="mt-6 flex justify-end">
            <Button disabled={mutation.isPending} type="submit">
              <Save className="h-4 w-4" aria-hidden="true" />
              {mutation.isPending ? "Saving..." : "Save Project"}
            </Button>
          </div>
        </form>
      </div>
    </main>
  );
}

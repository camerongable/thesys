"use client";

import { Beaker, CheckCircle2, ClipboardCheck, FileText, PlayCircle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { DomainError, DomainHeader, DomainPanel } from "@/features/projects/decision-room";
import { assumptionBeliefText } from "@/features/projects/assumption-copy";
import {
  Experiment,
  ExperimentOutcome,
  generateValidationPlan,
  getCurrentValidationMission,
  interpretValidationMission,
  listArtifacts,
  listAssumptions,
  listExperiments,
  listValidationMissions,
  logExperimentResult,
  startValidationMission,
  ValidationMission,
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
  const missionsQuery = useQuery({
    queryKey: ["projects", projectId, "validation-missions"],
    queryFn: () => listValidationMissions(projectId),
  });
  const currentMissionQuery = useQuery({
    queryKey: ["projects", projectId, "validation-missions", "current"],
    queryFn: () => getCurrentValidationMission(projectId),
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
    await queryClient.invalidateQueries({
      queryKey: ["projects", projectId, "validation-missions"],
    });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assumptions"] });
    await queryClient.invalidateQueries({
      queryKey: ["projects", projectId, "artifacts", "validation_plan"],
    });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "overview"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "approvals"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "workflows"] });
    await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "evals", "mvp"] });
  };

  const generateMutation = useMutation({
    mutationFn: () => generateValidationPlan(projectId, { max_plans: 3 }),
    onSuccess: invalidate,
  });
  const startMissionMutation = useMutation({
    mutationFn: (missionId: string) => startValidationMission(projectId, missionId),
    onSuccess: invalidate,
  });
  const interpretMissionMutation = useMutation({
    mutationFn: ({ missionId, rawNotes }: { missionId: string; rawNotes?: string }) =>
      interpretValidationMission(projectId, missionId, {
        include_logged_results: true,
        raw_notes: rawNotes?.trim() || undefined,
      }),
    onSuccess: invalidate,
  });

  const experiments = generateMutation.data?.experiments ?? experimentsQuery.data ?? [];
  const missions = generateMutation.data?.missions ?? missionsQuery.data ?? [];
  const currentMission =
    interpretMissionMutation.data?.mission ??
    generateMutation.data?.missions?.[0] ?? currentMissionQuery.data ?? missions[0] ?? null;
  const assumptions = assumptionsQuery.data ?? [];
  const validationPlanArtifact =
    generateMutation.data?.artifact ?? artifactsQuery.data?.[0] ?? null;
  const validationPlanVersion = validationPlanArtifact?.current_version ?? null;
  const assumptionById = new Map(assumptions.map((assumption) => [assumption.id, assumption]));
  const hasExperiments = experiments.length > 0;
  const hasLoggedResults = experiments.some((experiment) => experiment.results.length > 0);
  const currentExperiment = currentMission?.experiment_id
    ? experiments.find((experiment) => experiment.id === currentMission.experiment_id) ?? null
    : experiments[0] ?? null;
  const resultCount = experiments.reduce(
    (count, experiment) => count + experiment.results.length,
    0,
  );
  const primaryActionLabel = validationPrimaryActionLabel(currentMission);
  const primaryActionPending =
    generateMutation.isPending ||
    startMissionMutation.isPending ||
    interpretMissionMutation.isPending;
  const error =
    experimentsQuery.error ??
    assumptionsQuery.error ??
    artifactsQuery.error ??
    missionsQuery.error ??
    currentMissionQuery.error ??
    generateMutation.error ??
    interpretMissionMutation.error ??
    null;

  function runPrimaryAction() {
    if (!currentMission) {
      generateMutation.mutate();
      return;
    }
    if (currentMission.status === "planned") {
      startMissionMutation.mutate(currentMission.id);
      return;
    }
    if (currentMission.status === "results_logged") {
      document.getElementById("interpret-results-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
      return;
    }
    if (currentMission.status === "interpreted" || currentMission.status === "closed") {
      if (typeof window !== "undefined") {
        window.location.hash = "decisions";
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      }
      return;
    }
    document.getElementById("log-results-panel")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  return (
    <section className="mt-6 space-y-6">
      <DomainHeader
        action={
          <Button
            className="w-full justify-center whitespace-nowrap sm:w-60"
            disabled={primaryActionPending || (!currentMission && assumptions.length === 0)}
            onClick={runPrimaryAction}
            type="button"
          >
            {currentMission?.status === "planned" ? (
              <PlayCircle className="h-4 w-4" aria-hidden="true" />
            ) : (
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            )}
            {primaryActionPending ? "Updating mission..." : primaryActionLabel}
          </Button>
        }
        description="Turn the top decision blocker into one guided proof with steps, assets, result logging, and interpretation."
        icon={<Beaker className="h-4 w-4 text-primary" aria-hidden="true" />}
        question="What proof should we run before deciding?"
        signals={[
          { label: "Missions", value: missions.length },
          { label: "Assumptions", value: assumptions.length },
          { label: "Logged results", tone: resultCount > 0 ? "success" : "warning", value: resultCount },
          {
            label: "Next move",
            tone: currentMission?.status === "interpreted" ? "success" : currentMission ? "warning" : "neutral",
            value: primaryActionLabel,
          },
        ]}
        title="Validation Mission"
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
              pendingSteps={[
                "generate_validation_plan",
                "write_artifact_version",
                "write_experiments",
                "write_validation_missions",
              ]}
              runId={generateMutation.data?.ai_run_id ?? null}
            />
          </div>
        </details>
      ) : null}

      {experimentsQuery.isLoading || missionsQuery.isLoading || currentMissionQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading validation mission...</p>
      ) : !currentMission ? (
        <DomainPanel>
          <div className="flex items-center gap-2">
            <Beaker className="h-4 w-4 text-primary" aria-hidden="true" />
            <h3 className="text-sm font-semibold">No validation mission yet.</h3>
          </div>
          <div className="mt-3 grid gap-2 text-sm leading-6 text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">Missing:</span> the proof that will
              unblock the next decision.
            </p>
            <p>
              <span className="font-medium text-foreground">Why it matters:</span> a mission
              turns the top blocker into exact steps, assets, success criteria, result logging,
              and interpretation.
            </p>
            <p>
              <span className="font-medium text-foreground">Next:</span>{" "}
              {assumptions.length === 0
                ? "rank blockers first."
                : "create the validation mission."}
            </p>
          </div>
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
                ? "Creating mission..."
                : "Create validation mission"}
          </Button>
        </DomainPanel>
      ) : (
        <>
          <ValidationMissionPanel
            mission={currentMission}
            onInterpret={(rawNotes) =>
              interpretMissionMutation.mutate({
                missionId: currentMission.id,
                rawNotes,
              })
            }
            onPrimaryAction={runPrimaryAction}
            interpretationPending={interpretMissionMutation.isPending}
            pending={primaryActionPending}
          />

          <div
            className={
              validationPlanVersion
                ? "grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]"
                : "grid gap-5"
            }
          >
            <div className="grid gap-5">
              {currentExperiment ? (
                <ExperimentCard
                  assumptionText={
                    currentExperiment.assumption_id
                      ? assumptionBeliefText(
                          assumptionById.get(currentExperiment.assumption_id)?.text ?? "",
                        ) || null
                      : null
                  }
                  experiment={currentExperiment}
                  key={currentExperiment.id}
                  onSaved={invalidate}
                  projectId={projectId}
                />
              ) : null}

              {experiments.length > 1 ? (
                <details className="rounded-lg border border-border bg-card p-5">
                  <summary className="cursor-pointer text-sm font-semibold">
                    Show other validation tests
                  </summary>
                  <div className="mt-4 grid gap-5 border-t border-border pt-4">
                    {experiments
                      .filter((experiment) => experiment.id !== currentExperiment?.id)
                      .map((experiment) => (
                        <ExperimentCard
                          assumptionText={
                            experiment.assumption_id
                              ? assumptionBeliefText(
                                  assumptionById.get(experiment.assumption_id)?.text ?? "",
                                ) || null
                              : null
                          }
                          experiment={experiment}
                          key={experiment.id}
                          onSaved={invalidate}
                          projectId={projectId}
                        />
                      ))}
                  </div>
                </details>
              ) : null}
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

function ValidationMissionPanel({
  interpretationPending,
  mission,
  onInterpret,
  onPrimaryAction,
  pending,
}: {
  interpretationPending: boolean;
  mission: ValidationMission;
  onInterpret: (rawNotes: string) => void;
  onPrimaryAction: () => void;
  pending: boolean;
}) {
  const completedSteps =
    mission.status === "planned" ? 0 : mission.status === "running" ? 1 : mission.steps.length;
  const progressLabel =
    mission.status === "interpreted"
      ? "Results interpreted"
      : mission.status === "results_logged"
        ? "Results logged"
        : mission.status === "running"
          ? "Mission running"
          : "Mission planned";

  return (
    <DomainPanel>
      <div id="validation-mission" className="scroll-mt-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-medium text-muted-foreground">Active test</p>
            <h3 className="mt-2 text-lg font-semibold">{mission.mission_title}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {mission.why_it_matters}
            </p>
          </div>
          <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            {progressLabel}
          </span>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <Block title="Target user" value={mission.target_user} />
          <Block title="Test type" value={formatLabel(mission.test_type)} />
          <Block title="Progress" value={`${completedSteps}/${mission.steps.length} steps`} />
        </div>

        <div className="mt-5 rounded-md border border-border bg-background p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h4 className="text-sm font-semibold">Mission steps</h4>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                Run these steps before changing the decision recommendation.
              </p>
            </div>
            <Button
              className="w-full whitespace-nowrap sm:w-fit"
              disabled={pending}
              onClick={onPrimaryAction}
              size="sm"
              type="button"
            >
              {mission.status === "planned" ? (
                <PlayCircle className="h-4 w-4" aria-hidden="true" />
              ) : (
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              )}
              {pending ? "Updating mission..." : validationPrimaryActionLabel(mission)}
            </Button>
          </div>
          <ol className="mt-4 space-y-3">
            {mission.steps.map((step, index) => {
              const complete = index < completedSteps;
              return (
                <li className="flex gap-3" key={`${mission.id}:step:${index}`}>
                  <span
                    className={[
                      "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
                      complete
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border text-muted-foreground",
                    ].join(" ")}
                  >
                    {complete ? (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <span className="text-sm leading-6 text-muted-foreground">{step}</span>
                </li>
              );
            })}
          </ol>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Block title="Success criteria" value={mission.success_criteria} />
          <Block title="Failure criteria" value={mission.failure_criteria} />
        </div>

        <MissionAssetGrid assets={mission.assets} />

        <div className="mt-5 border-t border-border pt-4">
          <ResultInterpretationSummary mission={mission} />
        </div>

        <InterpretResultsForm
          disabled={interpretationPending}
          mission={mission}
          onInterpret={onInterpret}
        />
      </div>
    </DomainPanel>
  );
}

function MissionAssetGrid({ assets }: { assets: ValidationMission["assets"] }) {
  return (
    <div className="mt-5 border-t border-border pt-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-primary" aria-hidden="true" />
          <h4 className="text-sm font-semibold">Mission assets</h4>
        </div>
        <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
          Ready to use
        </span>
      </div>
      <div className="mt-3 grid gap-x-6 gap-y-3 md:grid-cols-2">
        {assets.map((asset, index) => (
          <details
            className="border-t border-border py-3 first:border-t-0 first:pt-0"
            key={`${asset.type}:${asset.title}`}
            open={index === 0}
          >
            <summary className="cursor-pointer text-sm font-medium">{asset.title}</summary>
            <div className="mt-3 border-t border-border pt-3">
              <Block title={asset.title} value={asset.content} />
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function ResultInterpretationSummary({ mission }: { mission: ValidationMission }) {
  const interpretation = mission.latest_interpretation;
  if (interpretation) {
    return (
      <>
        <h4 className="text-xs font-medium text-muted-foreground">Result interpretation</h4>
        <div className="mt-3 rounded-md border border-border bg-background p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold">{interpretation.signal_summary}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {interpretation.confidence_rationale}
              </p>
            </div>
            <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
              {formatLabel(interpretation.decision_recommendation)}
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <Block title="Pain" value={formatLabel(interpretation.pain_severity)} />
            <Block title="Urgency" value={formatLabel(interpretation.urgency)} />
            <Block
              title="Willingness to pay"
              value={formatLabel(interpretation.willingness_to_pay)}
            />
            <Block title="Switching" value={formatLabel(interpretation.switching_signal)} />
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Block
              title="What strengthened"
              value={markdownBullets(interpretation.what_strengthened)}
            />
            <Block title="What weakened" value={markdownBullets(interpretation.what_weakened)} />
            <Block title="Current workaround" value={interpretation.current_workaround} />
            <Block title="Recommended next action" value={interpretation.recommended_next_action} />
          </div>
          {interpretation.approval_request_id ? (
            <p className="mt-4 rounded-md bg-warning-muted px-3 py-2 text-xs leading-5 text-warning-foreground">
              Confidence and decision-trail updates are pending human approval in the
              Overview governance panel.
            </p>
          ) : null}
        </div>
      </>
    );
  }
  if (mission.result_count > 0 || mission.status === "results_logged") {
    return (
      <>
        <h4 className="text-xs font-medium text-muted-foreground">Result interpretation</h4>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Results are logged. Interpret them against the mission criteria, then review the
          decision recommendation.
        </p>
      </>
    );
  }
  return (
    <>
      <h4 className="text-xs font-medium text-muted-foreground">Result interpretation</h4>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        No results have been logged. Run the mission, capture real notes, then compare the
        signal against the success and failure criteria.
      </p>
    </>
  );
}

function InterpretResultsForm({
  disabled,
  mission,
  onInterpret,
}: {
  disabled: boolean;
  mission: ValidationMission;
  onInterpret: (rawNotes: string) => void;
}) {
  const [rawNotes, setRawNotes] = useState("");
  const canUseLoggedResults = mission.result_count > 0;
  const canSubmit = rawNotes.trim().length > 0 || canUseLoggedResults;

  return (
    <form
      className="mt-5 rounded-md border border-border bg-background p-4"
      id="interpret-results-panel"
      onSubmit={(event) => {
        event.preventDefault();
        onInterpret(rawNotes);
      }}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-sm font-semibold">Interpret validation notes</h4>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Paste interview notes, survey responses, landing page metrics, objections, or
            pricing reactions. Thesys will extract signal and propose confidence updates for
            approval.
          </p>
        </div>
        {canUseLoggedResults ? (
          <span className="w-fit rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
            Logged results included
          </span>
        ) : null}
      </div>
      <label className="mt-4 block">
        <span className="text-sm font-medium">Raw notes or metrics</span>
        <textarea
          className="mt-2 min-h-28 w-full rounded-md border border-border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
          onChange={(event) => setRawNotes(event.target.value)}
          placeholder="Example: 5 coaches interviewed. 4 described missed check-ins as painful. 2 asked for a pilot. 1 said they would pay $49/mo. Main objection: setup time."
          value={rawNotes}
        />
      </label>
      <Button className="mt-4" disabled={disabled || !canSubmit} type="submit">
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        {disabled ? "Interpreting..." : "Interpret results"}
      </Button>
    </form>
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

function validationPrimaryActionLabel(mission: ValidationMission | null) {
  if (!mission) {
    return "Create validation mission";
  }
  if (mission.status === "planned") {
    return "Start mission";
  }
  if (mission.status === "results_logged") {
    return "Interpret results";
  }
  if (mission.status === "interpreted" || mission.status === "closed") {
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

function markdownBullets(values: string[]) {
  return values.length > 0 ? values.map((value) => `- ${value}`).join("\n") : "Not found";
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

"use client";

import {
  ArrowRight,
  Bell,
  Compass,
  HelpCircle,
  MessageSquare,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  askProjectGuide,
  dismissProjectNudge,
  executeGuideAction,
  getGuideRecommendation,
  getProjectNudges,
  GuideAction,
  GuideChatResponse,
  ProjectNudge,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function GuidePanel({
  className,
  onAction,
  projectId,
}: {
  className?: string;
  onAction: (action: GuideAction) => void;
  projectId: string;
}) {
  const [message, setMessage] = useState("");
  const [chatResponse, setChatResponse] = useState<GuideChatResponse | null>(null);
  const queryClient = useQueryClient();
  const guideQuery = useQuery({
    queryKey: ["projects", projectId, "guide", "recommendation"],
    queryFn: () => getGuideRecommendation(projectId),
  });
  const nudgesQuery = useQuery({
    queryKey: ["projects", projectId, "nudges"],
    queryFn: () => getProjectNudges(projectId),
  });
  const actionMutation = useMutation({
    mutationFn: (action: GuideAction) => executeGuideAction(projectId, action.id),
    onSuccess: (action) => onAction(action),
  });
  const dismissNudgeMutation = useMutation({
    mutationFn: (nudgeId: string) => dismissProjectNudge(projectId, nudgeId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects", projectId, "nudges"] });
    },
  });
  const chatMutation = useMutation({
    mutationFn: (question: string) => askProjectGuide(projectId, question),
    onSuccess: (response) => setChatResponse(response),
  });

  function submitMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = message.trim();
    if (!question) {
      return;
    }
    chatMutation.mutate(question);
    setMessage("");
  }

  function askSuggestedQuestion(question: string) {
    setMessage("");
    chatMutation.mutate(question);
  }

  return (
    <aside
      aria-label="Thesys Guide"
      className={cn(
        "min-w-0 rounded-lg border border-border bg-card p-4 lg:sticky lg:top-5 lg:self-start",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-primary/10 p-2 text-primary">
          <Compass className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">Guide</p>
          <h2 className="text-base font-semibold">What matters now</h2>
        </div>
      </div>

      {guideQuery.isLoading ? (
        <GuidePanelSkeleton />
      ) : guideQuery.isError ? (
        <div className="mt-4 rounded-md border border-danger-border bg-danger-muted p-3">
          <p className="text-sm font-medium text-danger-foreground">Guide unavailable</p>
          <p className="mt-1 text-xs leading-5 text-danger-foreground">
            {(guideQuery.error as Error).message}
          </p>
          <Button
            className="mt-3 w-full border-danger-border text-danger-foreground hover:bg-danger-muted"
            onClick={() => void guideQuery.refetch()}
            size="sm"
            type="button"
            variant="secondary"
          >
            Retry guide
          </Button>
        </div>
      ) : guideQuery.data ? (
        <div className="mt-4 space-y-4">
          <section>
            <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
              Current focus
            </p>
            <p className="mt-1 text-sm font-medium leading-6">{guideQuery.data.current_focus}</p>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {guideQuery.data.why_this_matters}
            </p>
          </section>

          {nudgesQuery.data && nudgesQuery.data.length > 0 ? (
            <section>
              <div className="flex items-center gap-2">
                <Bell className="h-4 w-4 text-primary" aria-hidden="true" />
                <h3 className="text-sm font-semibold">Nudges</h3>
              </div>
              <div className="mt-2 grid gap-2">
                {nudgesQuery.data.slice(0, 2).map((nudge) => (
                  <GuideNudgeCard
                    disabled={dismissNudgeMutation.isPending}
                    key={nudge.id}
                    nudge={nudge}
                    onAction={() => onAction(nudge.action)}
                    onDismiss={() => dismissNudgeMutation.mutate(nudge.id)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <section className="rounded-md border border-border bg-background p-3">
            <p className="text-xs font-medium text-muted-foreground">Recommended next move</p>
            <button
              className="mt-2 flex w-full cursor-pointer items-start justify-between gap-3 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              disabled={actionMutation.isPending}
              onClick={() => actionMutation.mutate(guideQuery.data.recommended_action)}
              type="button"
            >
              <span className="min-w-0">
                <span className="block text-sm font-semibold">
                  {guideQuery.data.recommended_action.label}
                </span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                  {guideQuery.data.recommended_action.description}
                </span>
              </span>
              <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            </button>
          </section>

          {guideQuery.data.secondary_actions.length > 0 ? (
            <section>
              <p className="text-xs font-medium text-muted-foreground">Actions</p>
              <div className="mt-2 grid gap-2">
                {guideQuery.data.secondary_actions.map((action) => (
                  <GuideActionButton
                    action={action}
                    disabled={actionMutation.isPending}
                    key={action.id}
                    onClick={() => actionMutation.mutate(action)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          <section>
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" aria-hidden="true" />
              <h3 className="text-sm font-semibold">Ask Thesys</h3>
            </div>
            <form className="mt-2 flex gap-2" onSubmit={submitMessage}>
              <input
                className="min-h-11 min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-focus"
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Ask what to do next..."
                value={message}
              />
              <Button
                aria-label="Ask guide"
                disabled={chatMutation.isPending || !message.trim()}
                size="icon"
                type="submit"
              >
                <Send className="h-4 w-4" aria-hidden="true" />
              </Button>
            </form>

            <div className="mt-2 flex flex-wrap gap-2">
              {guideQuery.data.suggested_questions.slice(0, 3).map((question) => (
                <button
                  className="rounded-md border border-border px-2 py-1 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  disabled={chatMutation.isPending}
                  key={question}
                  onClick={() => askSuggestedQuestion(question)}
                  type="button"
                >
                  {question}
                </button>
              ))}
            </div>
          </section>

          {chatMutation.isPending ? (
            <div className="rounded-md border border-border bg-background p-3">
              <p className="text-sm text-muted-foreground">Thinking through this project...</p>
            </div>
          ) : chatResponse ? (
            <section className="rounded-md border border-border bg-background p-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" aria-hidden="true" />
                <p className="text-xs font-medium text-muted-foreground">Guide answer</p>
              </div>
              <p className="mt-2 text-sm leading-6">{chatResponse.answer}</p>
              {chatResponse.action_cards.length > 0 ? (
                <div className="mt-3 grid gap-2">
                  {chatResponse.action_cards.slice(0, 3).map((action) => (
                    <GuideActionButton
                      action={action}
                      disabled={actionMutation.isPending}
                      key={action.id}
                      onClick={() => actionMutation.mutate(action)}
                    />
                  ))}
                </div>
              ) : null}
              {chatResponse.related_entities.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {chatResponse.related_entities.map((entity) => (
                    <span
                      className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
                      key={`${entity.type}:${entity.id}`}
                    >
                      {entity.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}

function GuideNudgeCard({
  disabled,
  nudge,
  onAction,
  onDismiss,
}: {
  disabled: boolean;
  nudge: ProjectNudge;
  onAction: () => void;
  onDismiss: () => void;
}) {
  return (
    <section className={cn("rounded-md border p-3", nudgeToneClass(nudge.severity))}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{nudge.title}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{nudge.message}</p>
        </div>
        <button
          aria-label={`Dismiss ${nudge.title}`}
          className="rounded-md p-1 text-muted-foreground hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          disabled={disabled}
          onClick={onDismiss}
          type="button"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
        {nudge.why_it_matters}
      </p>
      <Button
        className="mt-3 min-h-10 w-full"
        onClick={onAction}
        size="sm"
        type="button"
        variant={nudge.severity === "action_required" ? "default" : "secondary"}
      >
        {nudge.action.label}
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Button>
    </section>
  );
}

function GuideActionButton({
  action,
  disabled,
  onClick,
}: {
  action: GuideAction;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className="flex min-h-11 w-full cursor-pointer items-start justify-between gap-3 rounded-md border border-border px-3 py-2 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-not-allowed disabled:opacity-60"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">{action.label}</span>
        <span className="mt-0.5 line-clamp-2 block text-xs leading-5 text-muted-foreground">
          {action.why_it_matters}
        </span>
      </span>
      {action.type === "explain" ? (
        <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      ) : (
        <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
      )}
    </button>
  );
}

function nudgeToneClass(severity: ProjectNudge["severity"]) {
  if (severity === "action_required") {
    return "border-warning-border bg-warning-muted";
  }
  if (severity === "warning") {
    return "border-warning-border bg-background";
  }
  return "border-border bg-background";
}

function GuidePanelSkeleton() {
  return (
    <div className="mt-4 animate-pulse space-y-4 motion-reduce:animate-none">
      <div>
        <div className="h-3 w-24 rounded bg-muted" />
        <div className="mt-2 h-5 w-full rounded bg-muted" />
        <div className="mt-2 h-4 w-5/6 rounded bg-muted" />
      </div>
      <div className="h-24 rounded-md bg-muted" />
      <div className="space-y-2">
        <div className="h-11 rounded-md bg-muted" />
        <div className="h-11 rounded-md bg-muted" />
      </div>
    </div>
  );
}

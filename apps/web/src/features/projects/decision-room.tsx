import { ReactNode } from "react";

type DomainSignalTone = "neutral" | "success" | "warning" | "danger";

type DomainSignal = {
  label: string;
  tone?: DomainSignalTone;
  value: ReactNode;
};

type DomainHeaderProps = {
  action?: ReactNode;
  description: string;
  icon?: ReactNode;
  signals?: DomainSignal[];
  title: string;
  question: string;
};

export function DomainHeader({
  action,
  description,
  icon,
  question,
  signals = [],
  title,
}: DomainHeaderProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            {icon}
            <span>{title}</span>
          </div>
          <h2 className="mt-2 text-xl font-semibold tracking-normal text-foreground">
            {question}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        {action ? <div className="hidden shrink-0 lg:block">{action}</div> : null}
      </div>
      {signals.length > 0 ? (
        <dl className="mt-5 grid gap-x-5 gap-y-3 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
          {signals.map((signal) => (
            <SignalMetric
              key={signal.label}
              label={signal.label}
              tone={signal.tone}
              value={signal.value}
            />
          ))}
        </dl>
      ) : null}
    </div>
  );
}

export function SignalMetric({
  label,
  tone = "neutral",
  value,
}: {
  label: string;
  tone?: DomainSignalTone;
  value: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 min-w-0 line-clamp-2 text-sm font-semibold leading-5 text-foreground">
        {value}
      </dd>
      {tone !== "neutral" ? <span className={signalToneClass(tone)} aria-hidden="true" /> : null}
    </div>
  );
}

export function DomainPanel({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <div className={["rounded-lg border border-border bg-card p-5", className].join(" ")} id={id}>
      {children}
    </div>
  );
}

export function DomainError({
  action,
  message,
}: {
  action?: ReactNode;
  message: string;
}) {
  return (
    <div
      className="rounded-md border border-danger-border bg-danger-muted px-3 py-2 text-sm text-danger-foreground"
      role="alert"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="min-w-0 break-words">{message}</p>
        <div className="shrink-0">
          {action ?? (
            <button
              className="w-fit rounded-md border border-danger-border bg-card px-2 py-1 text-xs font-medium text-danger-foreground hover:bg-danger-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              onClick={() => window.location.reload()}
              type="button"
            >
              Retry page
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function signalToneClass(tone: DomainSignalTone) {
  if (tone === "success") {
    return "mt-2 block h-0.5 w-12 rounded-full bg-success";
  }
  if (tone === "warning") {
    return "mt-2 block h-0.5 w-12 rounded-full bg-warning";
  }
  if (tone === "danger") {
    return "mt-2 block h-0.5 w-12 rounded-full bg-danger";
  }
  return "mt-2 block h-0.5 w-12 rounded-full bg-muted-foreground";
}

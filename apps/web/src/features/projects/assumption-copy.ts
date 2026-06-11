import { Assumption } from "@/lib/api";

type AssumptionCopyInput = Pick<
  Assumption,
  "confidence_score" | "evidence_links" | "recommended_test" | "text"
>;

export function assumptionBeliefText(text: string) {
  const trimmed = text.trim();
  const lower = trimmed.toLowerCase();

  if (
    lower.includes("willingness-to-pay") &&
    lower.includes("strong enough to justify building")
  ) {
    return "Target users will pay enough to make this worth building.";
  }

  if (lower.includes("signal is strong enough to justify building")) {
    return trimmed
      .replace(/^the\s+/i, "")
      .replace(
        /\s+signal\s+is\s+strong enough\s+to justify building\.?$/i,
        " signal will meet the decision threshold.",
      );
  }

  return trimmed;
}

export function decisionBlockerText(assumption: AssumptionCopyInput) {
  return `Decision blocker: validate whether ${lowercaseFirst(
    assumptionBeliefText(assumption.text),
  )}`;
}

export function nextProofText(assumption: AssumptionCopyInput) {
  if (assumption.recommended_test?.trim()) {
    return `Next proof: ${assumption.recommended_test.trim()}`;
  }
  return "Next proof: run a narrow validation test and log the result before changing the verdict.";
}

export function evidenceReadinessText(assumption: AssumptionCopyInput) {
  if (assumption.evidence_links.length === 0) {
    return "Needs evidence";
  }
  if (Number(assumption.confidence_score ?? 0) >= 0.7) {
    return "Evidence exists, verify threshold";
  }
  return "Partial evidence";
}

export function clarifyDecisionNarrative(text: string) {
  const clarified = text
    .replace(/\bthe highest-risk assumption\b/gi, "the decision blocker")
    .replace(/\bthe highest risk assumption\b/gi, "the decision blocker")
    .replace(/\bthe riskiest assumption\b/gi, "the decision blocker")
    .replace(/\bhighest-risk assumption\b/gi, "decision blocker")
    .replace(/\bhighest risk assumption\b/gi, "decision blocker")
    .replace(/\briskiest assumption\b/gi, "decision blocker")
    .replace(
      /for:\s*The willingness-to-pay signal is strong enough to justify building\.?/gi,
      "for this blocker: target users will pay enough to make this worth building.",
    )
    .replace(
      /The willingness-to-pay signal is strong enough to justify building\.?/gi,
      "Target users will pay enough to make this worth building.",
    )
    .replace(
      /the willingness-to-pay signal is strong enough to justify building\.?/gi,
      "target users will pay enough to make this worth building.",
    )
    .replace(
      /([A-Za-z][A-Za-z -]*?) signal is strong enough to justify building\.?/g,
      "$1 signal will meet the decision threshold.",
    );

  return clarified
    .replace(/worth building\.\.+/gi, "worth building.")
    .replace(/decision threshold\.\.+/gi, "decision threshold.");
}

function lowercaseFirst(value: string) {
  return value.charAt(0).toLowerCase() + value.slice(1);
}

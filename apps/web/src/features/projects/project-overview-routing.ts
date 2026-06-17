export const projectTabs = [
  "Current Step",
  "Shape",
  "Research",
  "Test",
  "Decide",
  "History",
] as const;

export type ProjectTab = (typeof projectTabs)[number];
export type RecordSurface = "decision" | "history";

export type ProjectNavigationItem = {
  anchor: string | null;
  detail: string;
  key: string;
  label: ProjectTab;
};

export const projectNavigationItems: ProjectNavigationItem[] = [
  {
    anchor: null,
    detail: "The one thing to do next",
    key: "current-step",
    label: "Current Step",
  },
  {
    anchor: "thesis-canvas",
    detail: "Thesis and wedge",
    key: "shape",
    label: "Shape",
  },
  {
    anchor: null,
    detail: "Evidence summary",
    key: "research",
    label: "Research",
  },
  {
    anchor: null,
    detail: "Active test",
    key: "test",
    label: "Test",
  },
  {
    anchor: "record-decision-panel",
    detail: "Record the call",
    key: "decide",
    label: "Decide",
  },
  {
    anchor: "history",
    detail: "Receipts and changes",
    key: "history",
    label: "History",
  },
];

export function tabHash(tab: ProjectTab) {
  return tab.toLowerCase().replace(/\s+/g, "-");
}

export function recordSurfaceForTab(tab: ProjectTab): RecordSurface | null {
  if (tab === "Decide") {
    return "decision";
  }
  if (tab === "History") {
    return "history";
  }
  return null;
}

export function tabFromHash(hash: string): ProjectTab | null {
  const normalized = hash.replace("#", "").toLowerCase();
  const aliases: Record<string, ProjectTab> = {
    assumption: "Test",
    assumptions: "Test",
    brief: "Research",
    competitor: "Research",
    competitors: "Research",
    "current-step": "Current Step",
    current: "Current Step",
    decision: "Current Step",
    decisions: "Decide",
    decide: "Decide",
    evidence: "Research",
    experiment: "Test",
    experiments: "Test",
    guide: "Current Step",
    history: "History",
    inspect: "Research",
    intelligence: "Research",
    market: "Research",
    overview: "Current Step",
    record: "Decide",
    research: "Research",
    shape: "Shape",
    test: "Test",
    thesis: "Shape",
    validation: "Test",
    wedge: "Shape",
    wedges: "Shape",
  };
  return aliases[normalized] ?? null;
}

export function tabFromAnchor(anchor: string | null): ProjectTab | null {
  if (!anchor) {
    return null;
  }
  if (
    anchor.includes("thesis") ||
    anchor.includes("evolution") ||
    anchor.includes("wedge")
  ) {
    return "Shape";
  }
  if (
    anchor.includes("research") ||
    anchor.includes("evidence") ||
    anchor.includes("source") ||
    anchor.includes("competitor") ||
    anchor.includes("brief")
  ) {
    return "Research";
  }
  if (
    anchor.includes("experiment") ||
    anchor.includes("validation") ||
    anchor.includes("result") ||
    anchor.includes("assumption") ||
    anchor.includes("blocker")
  ) {
    return "Test";
  }
  if (anchor.includes("history")) {
    return "History";
  }
  if (anchor.includes("decision-record") || anchor.includes("record-decision")) {
    return "Decide";
  }
  return null;
}

export function tabForActionType(actionType: string): ProjectTab {
  if (
    actionType.includes("thesis") ||
    actionType.includes("wedge") ||
    actionType.includes("evolution")
  ) {
    return "Shape";
  }
  if (
    actionType.includes("brief") ||
    actionType.includes("research") ||
    actionType.includes("competitor") ||
    actionType.includes("evidence") ||
    actionType.includes("source")
  ) {
    return "Research";
  }
  if (
    actionType.includes("assumption") ||
    actionType.includes("experiment") ||
    actionType.includes("validation") ||
    actionType.includes("result")
  ) {
    return "Test";
  }
  if (actionType.includes("history")) {
    return "History";
  }
  if (actionType.includes("decision") || actionType.includes("record")) {
    return "Decide";
  }
  return "Current Step";
}

export function tabForGuideAction(action: {
  id: string;
  type: string;
}): ProjectTab {
  if (
    action.type === "update_thesis" ||
    action.type === "compare_wedges" ||
    action.id.includes("thesis") ||
    action.id.includes("evolution") ||
    action.id.includes("wedge")
  ) {
    return "Shape";
  }
  if (action.id.includes("evidence")) {
    return "Research";
  }
  if (action.type === "log_result" || action.id.includes("validation")) {
    return "Test";
  }
  if (action.type === "record_decision") {
    return "Decide";
  }
  return tabForActionType(action.id);
}

export function hashShouldRemainAnchor(anchor: string | null) {
  return anchor === "history";
}

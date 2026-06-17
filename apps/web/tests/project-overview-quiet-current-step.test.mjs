import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const sourcePath = fileURLToPath(
  new URL("../src/features/projects/project-overview.tsx", import.meta.url),
);
const source = readFileSync(sourcePath, "utf8");
const currentStepPanelSource = source.slice(
  source.indexOf("function CurrentStepPanel"),
  source.indexOf("function IdeaStorySection"),
);

test("Current Step does not mount the default workspace chrome", () => {
  assert.match(
    source,
    /activeTab !== "Current Step" \? \(\s*<MobileProjectMenu/s,
  );
  assert.match(
    source,
    /activeTab !== "Current Step" \? \(\s*<MobileWorkspaceAction/s,
  );
  assert.match(
    source,
    /activeTab !== "Current Step" \? \(\s*<ProjectMap/s,
  );
  assert.match(
    source,
    /activeTab === "Current Step"\s*\?\s*"mt-5 grid gap-5 lg:grid-cols-1"/s,
  );
  assert.doesNotMatch(source, /<ProjectStatusBar\s+overview=\{overview\}\s*\/>/);
  assert.doesNotMatch(source, /<MobileDecisionSpine\s/);
});

test("Current Step keeps details behind inspect controls", () => {
  assert.match(currentStepPanelSource, /id="quiet-current-step-inspect"/);
  assert.match(currentStepPanelSource, /Inspect details/);
  assert.match(currentStepPanelSource, /<OverviewNudges[\s\S]*<DecisionContextDrawer/);
  assert.match(currentStepPanelSource, /Show test plan/);
  assert.match(currentStepPanelSource, /Show evidence/);
  assert.match(currentStepPanelSource, /Compare wedges/);
  assert.doesNotMatch(
    currentStepPanelSource,
    /onOpenWorkspace\("Current Step", "project-guide"\)/,
  );
  assert.match(source, /<GuideActionDrawer/);
});

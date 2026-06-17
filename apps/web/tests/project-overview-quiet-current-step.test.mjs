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
  source.indexOf("function ProjectInspectDrawer"),
);
const ideaStorySectionSource = source.slice(
  source.indexOf("function IdeaStorySection"),
  source.indexOf("function IdeaGrowthDetails"),
);

test("Current Step does not mount the default workspace chrome", () => {
  assert.doesNotMatch(source, /<MobileProjectMenu\s/);
  assert.doesNotMatch(source, /function MobileProjectMenu/);
  assert.doesNotMatch(source, /<ProjectMap\s/);
  assert.doesNotMatch(source, /function ProjectMap/);
  assert.doesNotMatch(source, /Guided mode/);
  assert.match(
    source,
    /className="mt-5 grid gap-5 lg:grid-cols-1"/,
  );
  assert.doesNotMatch(source, /<ProjectStatusBar\s+overview=\{overview\}\s*\/>/);
  assert.doesNotMatch(source, /<MobileDecisionSpine\s/);
});

test("Current Step keeps details behind inspect controls", () => {
  assert.doesNotMatch(currentStepPanelSource, /id="quiet-current-step-inspect"/);
  assert.doesNotMatch(currentStepPanelSource, /<OverviewNudges/);
  assert.doesNotMatch(currentStepPanelSource, /<DecisionContextDrawer/);
  assert.doesNotMatch(ideaStorySectionSource, /Inspect idea growth/);
  assert.doesNotMatch(ideaStorySectionSource, /Inspect story/);
  assert.match(currentStepPanelSource, /onOpenInspect/);
  assert.match(currentStepPanelSource, /Inspect details/);
  assert.doesNotMatch(
    currentStepPanelSource,
    /onOpenWorkspace\("Current Step", "project-guide"\)/,
  );
  assert.match(source, /<GuideActionDrawer/);
});

test("Inspect drawer preserves advanced project details behind one surface", () => {
  assert.match(source, /function ProjectInspectDrawer/);
  assert.match(source, /id="project-inspect-drawer"/);
  assert.match(source, /h-full w-full flex-col[^"]*sm:w-\[min\(34rem,calc\(100vw-2rem\)\)\]/);
  for (const label of [
    "Status",
    "Evidence summary",
    "Assumptions behind the decision",
    "Test path",
    "Research details",
    "Decision history",
    "Project context",
  ]) {
    assert.match(source, new RegExp(label));
  }
  assert.match(source, /onOpenWorkspace\("Research", "evidence"\)/);
  assert.match(source, /onOpenWorkspace\("Test", "validation-mission"\)/);
  assert.match(source, /onOpenWorkspace\("Shape", "wedge-explorer"\)/);
  assert.match(source, /onOpenWorkspace\("History", "history"\)/);
  assert.match(source, /function IdeaGrowthDetails/);
  assert.match(source, /Inspect idea growth/);
});

test("compact Explore control replaces full guided navigation", () => {
  assert.match(source, /<ProjectExploreControl activeTab=\{activeTab\} onOpen=\{openNavigationItem\} \/>/);
  assert.match(source, /function ProjectExploreControl/);
  assert.match(source, /Explore project sections/);
  assert.match(source, /h-full w-full flex-col[^"]*sm:w-\[min\(24rem,calc\(100vw-2rem\)\)\]/);
  assert.match(source, /projectNavigationItems\.map/);
});

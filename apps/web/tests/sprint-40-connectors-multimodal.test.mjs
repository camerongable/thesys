import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const evidenceTabSource = readSource("../src/features/projects/evidence-tab.tsx");
const projectOverviewSource = readSource("../src/features/projects/project-overview.tsx");
const apiSource = readSource("../src/lib/api.ts");
const currentStepPanelSource = projectOverviewSource.slice(
  projectOverviewSource.indexOf("function CurrentStepPanel"),
  projectOverviewSource.indexOf("function ProjectInspectDrawer"),
);

test("Sprint 40 evidence upload accepts image extensions and MIME types", () => {
  assert.match(
    evidenceTabSource,
    /accept="[^"]*\.png[^"]*\.jpg[^"]*\.jpeg[^"]*\.webp[^"]*image\/png[^"]*image\/jpeg[^"]*image\/webp/,
  );
  assert.match(evidenceTabSource, /PDF, image, text, or Markdown/);
  assert.match(apiSource, /metadata: Record<string, unknown>;/);
});

test("Sprint 40 source review renders compact search provenance", () => {
  assert.match(projectOverviewSource, /source\.search_provider/);
  assert.match(projectOverviewSource, /rank \{source\.search_result_rank\}/);
  assert.match(projectOverviewSource, /Show search provenance/);
  assert.match(projectOverviewSource, /formatDateTime\(source\.retrieved_at\)/);
});

test("Sprint 40 evidence detail keeps extraction metadata behind preview controls", () => {
  assert.match(evidenceTabSource, /function SourceMetadataDetails/);
  assert.match(evidenceTabSource, /Show provenance and extraction details/);
  assert.match(evidenceTabSource, /extraction_provider/);
  assert.match(evidenceTabSource, /search_provider/);
  assert.doesNotMatch(currentStepPanelSource, /extraction_provider/);
  assert.doesNotMatch(currentStepPanelSource, /search_provider/);
});

function readSource(relativePath) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

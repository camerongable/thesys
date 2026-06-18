import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const projectListSource = readSource("../src/features/projects/project-list.tsx");
const newProjectFormSource = readSource("../src/features/projects/new-project-form.tsx");

test("Sprint 35 launcher keeps filters collapsed and removes competing launcher cards", () => {
  assert.match(projectListSource, /id="project-filter-panel"/);
  assert.match(projectListSource, />\s*Filter\s*</);
  assert.match(projectListSource, /mt-3 hidden gap-2 group-open:grid/);
  assert.match(projectListSource, /Show test projects/);
  assert.equal(projectListSource.match(/Show test projects/g)?.length, 1);
  assert.doesNotMatch(projectListSource, /<aside\b/);
  assert.doesNotMatch(projectListSource, /Start an investigation/);
  assert.doesNotMatch(projectListSource, /min-\[1200px\]:contents/);
  assert.match(projectListSource, /Load guided demo/);
  assert.match(projectListSource, /Start investigation/);
});

test("Sprint 35 new investigation is single-column with Current Step as the primary landing", () => {
  assert.doesNotMatch(newProjectFormSource, /<aside\b/);
  assert.doesNotMatch(newProjectFormSource, /How this starts/);
  assert.doesNotMatch(newProjectFormSource, /ProcessStep/);
  assert.match(newProjectFormSource, /First testable thesis/);
  assert.match(newProjectFormSource, /Possible wedge/);
  assert.match(newProjectFormSource, /Biggest unknown/);
  assert.match(newProjectFormSource, /Recommended investigation path/);
  assert.match(newProjectFormSource, /Continue to Current Step/);
  assert.match(newProjectFormSource, /Run research/);
  assert.match(newProjectFormSource, /Compare wedges/);
  assert.match(newProjectFormSource, /sm:flex-row sm:flex-wrap sm:items-center/);
  assert.match(newProjectFormSource, /w-full whitespace-nowrap sm:w-auto/);
  assert.match(newProjectFormSource, /return "#current-step"/);
});

function readSource(relativePath) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

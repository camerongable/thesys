import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const projectListSource = readSource("../src/features/projects/project-list.tsx");
const newProjectFormSource = readSource("../src/features/projects/new-project-form.tsx");
const projectOverviewSource = readSource("../src/features/projects/project-overview.tsx");
const supportSurfaceSource = [
  readSource("../src/features/projects/assumptions-tab.tsx"),
  readSource("../src/features/projects/brief-tab.tsx"),
  readSource("../src/features/projects/competitors-tab.tsx"),
  readSource("../src/features/projects/decisions-tab.tsx"),
  readSource("../src/features/projects/evidence-tab.tsx"),
  readSource("../src/features/projects/experiments-tab.tsx"),
  readSource("../src/features/projects/thesis-tab.tsx"),
].join("\n");

test("Sprint 36 keeps default launcher and intake surfaces quiet", () => {
  assert.match(projectListSource, /<div className="border-y border-border">/);
  assert.match(newProjectFormSource, /className="mt-6 space-y-5 border-y border-border py-5"/);
  assert.match(newProjectFormSource, /Continue to Current Step/);
  assert.doesNotMatch(projectListSource, /<aside\b/);
  assert.doesNotMatch(newProjectFormSource, /<aside\b/);
  assert.doesNotMatch(newProjectFormSource, /Continue with assumptions/);
  assert.doesNotMatch(newProjectFormSource, /className="mt-6 space-y-5 rounded-lg border border-border bg-card p-5"/);
});

test("Sprint 36 avoids stale broad card/navigation skeletons", () => {
  assert.doesNotMatch(projectOverviewSource, /lg:grid-cols-\[270px_minmax\(0,1fr\)\]/);
  assert.match(projectOverviewSource, /className="mt-5 border-y border-border py-5"/);
  assert.match(projectOverviewSource, /className="border-y border-border py-5"/);
  assert.match(projectOverviewSource, /id="project-inspect-drawer"/);
  assert.match(projectOverviewSource, /Explore project sections/);
});

test("Sprint 36 empty states explain missing item, importance, and next step", () => {
  for (const source of [
    projectListSource,
    projectOverviewSource,
    supportSurfaceSource,
  ]) {
    assert.match(source, />Missing:</);
    assert.match(source, />Why it matters:</);
    assert.match(source, />Next:</);
  }
  assert.match(supportSurfaceSource, /No validation mission yet\./);
  assert.match(supportSurfaceSource, /No opportunity brief yet\./);
  assert.match(supportSurfaceSource, /No sources yet\./);
  assert.match(projectOverviewSource, /No evidence review planned yet\./);
  assert.match(projectOverviewSource, /Review queue clear/);
});

function readSource(relativePath) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

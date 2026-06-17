import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const sourcePath = fileURLToPath(
  new URL("../src/features/projects/project-list-utils.ts", import.meta.url),
);
const source = readFileSync(sourcePath, "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
});

const moduleScope = { exports: {} };
new Function("exports", "require", "module", outputText)(
  moduleScope.exports,
  require,
  moduleScope,
);

const listUtils = moduleScope.exports;

test("homepage hides disposable QA and browser projects by default", () => {
  const rows = [
    { project: { name: "AI Assistant for Independent Fitness Coaches" } },
    { project: { name: "Sprint 32 smoke project" } },
    { project: { name: "Browser test project" } },
    { project: { name: "Sprint 24 Browser QA 1781575206366" } },
    { project: { name: "[QA] Sprint 22 Final Browser Smoke" } },
    { project: { name: "Sprint 16 Governance Browser Check" } },
    {
      project: {
        name: "AI endpoint audit 2026-05-24T22:10:06.270Z",
        short_description: "Disposable local audit project for AI endpoint verification.",
      },
    },
    { project: { name: "[Demo] Fitness Coach Intelligence OS" } },
    { project: { name: "Plant parenthood" } },
  ];

  assert.equal(listUtils.isDisposableProject(rows[0].project), false);
  assert.equal(listUtils.isDisposableProject(rows[1].project), true);
  assert.equal(listUtils.isDisposableProject(rows[2].project), true);
  assert.equal(listUtils.isDisposableProject(rows[3].project), true);
  assert.equal(listUtils.isDisposableProject(rows[4].project), true);
  assert.equal(listUtils.isDisposableProject(rows[5].project), true);
  assert.equal(listUtils.isDisposableProject(rows[6].project), true);
  assert.equal(listUtils.isDisposableProject(rows[7].project), true);
  assert.equal(listUtils.isDisposableProject({ name: "[QA] Sprint 22 Wedge Explorer" }), true);
  assert.equal(
    listUtils.isDisposableProject({ name: "Sprint 15 Browser Smoke 2026-06-12T06-19-37-644Z" }),
    true,
  );
  assert.equal(listUtils.isDisposableProject({ name: "AI endpoint audit 2026-05-24T22:10:06.270Z" }), true);

  assert.deepEqual(
    listUtils.filterHomepageProjects(rows, false).map((row) => row.project.name),
    ["AI Assistant for Independent Fitness Coaches", "Plant parenthood"],
  );
  assert.deepEqual(
    listUtils.filterHomepageProjects(rows, true).map((row) => row.project.name),
    rows.map((row) => row.project.name),
  );
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const sourcePath = fileURLToPath(
  new URL("../src/features/projects/project-overview-routing.ts", import.meta.url),
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

const routing = moduleScope.exports;

test("guided navigation starts with Current Step and excludes Guide", () => {
  assert.deepEqual(routing.projectTabs, [
    "Current Step",
    "Shape",
    "Research",
    "Test",
    "Decide",
    "History",
  ]);
  assert.equal(routing.projectNavigationItems[0].label, "Current Step");
  assert.equal(
    routing.projectNavigationItems.some((item) => item.label === "Guide"),
    false,
  );
});

test("legacy hashes and deep links route into guided or inspect modes", () => {
  assert.equal(routing.tabHash("Current Step"), "current-step");
  assert.equal(routing.tabFromHash("#guide"), "Current Step");
  assert.equal(routing.tabFromHash("#decision"), "Current Step");
  assert.equal(routing.tabFromHash("#decide"), "Decide");
  assert.equal(routing.tabFromAnchor("research-sprint"), "Research");
  assert.equal(routing.tabFromAnchor("validation-mission"), "Test");
  assert.equal(routing.tabFromAnchor("record-decision-panel"), "Decide");
  assert.equal(routing.tabFromAnchor("history"), "History");
});

test("decision record and history render as separate record surfaces", () => {
  assert.equal(routing.recordSurfaceForTab("Decide"), "decision");
  assert.equal(routing.recordSurfaceForTab("History"), "history");
  assert.equal(routing.recordSurfaceForTab("Research"), null);
});

test("actions route to the right guided destination", () => {
  assert.equal(routing.tabForActionType("compare_wedges"), "Shape");
  assert.equal(routing.tabForActionType("review_evidence"), "Research");
  assert.equal(routing.tabForActionType("log_validation_result"), "Test");
  assert.equal(routing.tabForActionType("record_decision"), "Decide");
  assert.equal(routing.tabForActionType("show_history"), "History");
  assert.equal(routing.tabForActionType("unknown_action"), "Current Step");
});

test("guide actions route without making Guide a workspace", () => {
  assert.equal(
    routing.tabForGuideAction({ id: "compare_wedges", type: "compare_wedges" }),
    "Shape",
  );
  assert.equal(
    routing.tabForGuideAction({ id: "show_evidence", type: "navigate" }),
    "Research",
  );
  assert.equal(
    routing.tabForGuideAction({ id: "log_validation_result", type: "log_result" }),
    "Test",
  );
  assert.equal(
    routing.tabForGuideAction({ id: "record_decision", type: "record_decision" }),
    "Decide",
  );
});

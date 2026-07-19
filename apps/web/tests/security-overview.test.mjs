import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const apiPath = fileURLToPath(new URL("../src/lib/api.ts", import.meta.url));
const overviewPath = fileURLToPath(
  new URL("../src/features/projects/security-overview.tsx", import.meta.url),
);
const projectOverviewPath = fileURLToPath(
  new URL("../src/features/projects/project-overview.tsx", import.meta.url),
);
const apiSource = readFileSync(apiPath, "utf8");
const overviewSource = readFileSync(overviewPath, "utf8");
const projectOverviewSource = readFileSync(projectOverviewPath, "utf8");

test("security overview client uses the redacted project endpoint", () => {
  assert.match(apiSource, /export type SecurityOverview = \{/);
  assert.match(apiSource, /getProjectSecurityOverview\(projectId: string\)/);
  assert.match(apiSource, /`\/api\/projects\/\$\{projectId\}\/security-overview`/);
});

test("security overview prioritizes security signals without raw event content", () => {
  for (const label of [
    "High-priority events",
    "Blocked prompt attacks",
    "Denied tools",
    "PII redactions",
    "Memory quarantines",
    "Anomalous retrieval",
    "Pending high-risk approvals",
    "Open budget alerts",
    "Active workflows",
    "Active kill switches",
    "Containment",
    "MCP servers",
  ]) {
    assert.match(overviewSource, new RegExp(label));
  }
  assert.match(overviewSource, /getProjectSecurityOverview\(projectId\)/);
  assert.match(overviewSource, /Loading security overview/);
  assert.match(overviewSource, /DomainError/);
  assert.doesNotMatch(overviewSource, /event\.summary|event\.attributes|prompt_text/);
});

test("project header exposes the security overview through an icon control", () => {
  assert.match(projectOverviewSource, /href=\{`\/projects\/\$\{projectId\}\/security`\}/);
  assert.match(projectOverviewSource, /aria-label="Open security overview"/);
  assert.match(projectOverviewSource, /title="Security overview"/);
});

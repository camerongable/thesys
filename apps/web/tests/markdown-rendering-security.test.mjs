import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const renderer = readSource("../src/features/projects/markdown-content.tsx");
const safeUrlPolicy = readSource("../src/lib/safe-external-url.ts");
const safeExternalLink = readSource("../src/components/safe-external-link.tsx");
const safeExternalUrl = loadSafeExternalUrl(safeUrlPolicy);

test("Markdown rendering applies the shared external URL policy", () => {
  assert.match(renderer, /safeExternalUrl\(link\[3\]\)/);
  assert.match(renderer, /rel="noopener noreferrer"/);
  assert.equal(safeExternalUrl("https://example.com/report"), "https://example.com/report");
  for (const unsafeUrl of [
    "http://example.com/report",
    "javascript:alert(1)",
    "data:text/html,unsafe",
    "file:///etc/passwd",
    "mailto:security@example.com",
    "https://",
  ]) {
    assert.equal(safeExternalUrl(unsafeUrl), null);
  }
});

test("Markdown images are rendered as inert alt text", () => {
  assert.match(renderer, /text\.split\(\/\(!\?\\\[/);
  assert.match(renderer, /if \(!destination \|\| link\[1\] === "!"\)/);
  assert.match(renderer, /return link\[2\];/);
});

test("project metadata and citations use the safe external anchor wrapper", () => {
  assert.match(safeExternalLink, /safeExternalUrl\(href\)/);
  assert.match(safeExternalLink, /rel="noopener noreferrer"/);
  assert.match(safeExternalLink, /return <span className=\{props\.className\}>/);

  for (const [path, expectedCount] of [
    ["../src/features/projects/guide-panel.tsx", 1],
    ["../src/features/projects/workflow-trace.tsx", 1],
    ["../src/features/projects/evidence-tab.tsx", 2],
    ["../src/features/projects/competitors-tab.tsx", 2],
    ["../src/features/projects/project-overview.tsx", 8],
  ]) {
    const source = readSource(path);
    assert.equal((source.match(/<SafeExternalLink/g) ?? []).length, expectedCount, path);
    assert.doesNotMatch(
      source,
      /<a[\s\S]{0,240}href=\{(?:source|citation|candidate|competitor|run|version|sprintHistory)\./,
      path,
    );
  }
});

function readSource(relativePath) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf8");
}

function loadSafeExternalUrl(source) {
  const executable = source.replace(
    "export function safeExternalUrl(value: string | null | undefined): string | null {",
    "function safeExternalUrl(value) {",
  );
  return new Function(`${executable}\nreturn safeExternalUrl;`)();
}

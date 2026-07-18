import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const renderer = readSource("../src/features/projects/markdown-content.tsx");
const safeUrlPolicy = readSource("../src/lib/safe-external-url.ts");
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

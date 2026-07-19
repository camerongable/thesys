import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REDTEAM_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const API_DIRECTORY = resolve(REDTEAM_DIRECTORY, "../../apps/api");

export default class ThesysGuardrailProvider {
  constructor(options = {}) {
    this.uvBin = options.config?.uvBin || process.env.THESYS_UV_BIN || "uv";
    this.apiDirectory = options.config?.apiDirectory || API_DIRECTORY;
  }

  id() {
    return "thesys-deterministic-guardrail";
  }

  async callApi(prompt, context) {
    const result = spawnSync(
      this.uvBin,
      ["run", "python", "scripts/redteam_promptfoo_target.py"],
      {
        cwd: this.apiDirectory,
        encoding: "utf8",
        env: process.env,
        input: JSON.stringify({
          prompt,
          channel: context.vars?.channel || "user_input",
        }),
      },
    );
    if (result.error || result.status !== 0) {
      return { error: "The deterministic red-team target did not complete." };
    }
    return { output: result.stdout.trim() };
  }
}

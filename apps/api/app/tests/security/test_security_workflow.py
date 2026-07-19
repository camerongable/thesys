import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "security.yml"


def test_security_workflow_declares_pull_request_and_nightly_cadence() -> None:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text())

    assert workflow[True] == {
        "pull_request": None,
        "workflow_dispatch": None,
        "schedule": [{"cron": "17 3 * * *"}],
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["nightly-security"]["if"] == (
        "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
    )


def test_security_workflow_covers_required_pull_request_gates() -> None:
    content = WORKFLOW_PATH.read_text()

    for command in (
        "uv sync --project apps/api --locked --all-extras",
        "uv run --project apps/api ruff check app",
        "uv run --project apps/api pytest app/tests/security",
        "pnpm install --frozen-lockfile",
        "pnpm --filter thesys-web test",
        "pnpm --filter thesys-web typecheck",
        "pnpm audit --audit-level=high",
        "bandit==1.8.6",
        "pip-audit==2.9.0",
        "uv export --project apps/api --locked --no-dev",
        "semgrep==1.130.0",
        "pnpm security:redteam:fast",
        "gitleaks/gitleaks-action@dcedce43c6f43de0b836d1fe38946645c9c638dc",
        "google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@9a498708959aeaef5ef730655706c5a1df1edbc2",
        "anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610",
    ):
        assert command in content


def test_promptfoo_fast_command_uses_an_exact_cli_version() -> None:
    package_json = (REPO_ROOT / "package.json").read_text()

    assert "pnpm dlx promptfoo@0.121.15 eval" in package_json


def test_release_workflow_requires_signed_scanned_provenance_backed_images() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release-security.yml").read_text()

    for contract in (
        'tags:\n      - "v*"',
        "docker/build-push-action@10e90e3645eae34f1e60eeb005ba3a3d33f178e8",
        "provenance: mode=max",
        "sbom: true",
        "sigstore/cosign-installer@f713795cb21599bc4e5c4b58cbad1da852d7eeb9",
        "cosign sign --yes",
        "cosign verify",
        "aquasecurity/trivy-action@a9c7b0f06e461e9d4b4d1711f154ee024b8d7ab8",
        "format: json",
        "scripts/prepare_release_evidence.py",
        "scripts/generate_security_report.py",
        "if: always()",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ):
        assert contract in workflow


def test_nightly_workflow_runs_full_adversarial_and_deployment_scans() -> None:
    workflow = WORKFLOW_PATH.read_text()

    for contract in (
        "pnpm security:redteam:full",
        "garak==0.15.1",
        "--target_type rest",
        "--probes promptinject,encoding",
        "docker build --file apps/api/Dockerfile",
        "docker build --file apps/web/Dockerfile",
        "aquasecurity/trivy-action@a9c7b0f06e461e9d4b4d1711f154ee024b8d7ab8",
        "scan-type: config",
        "scan-ref: infra/k8s/base",
    ):
        assert contract in workflow


def test_security_workflows_pin_actions_and_dependabot_updates_them() -> None:
    for workflow_path in (
        WORKFLOW_PATH,
        REPO_ROOT / ".github" / "workflows" / "release-security.yml",
    ):
        references = re.findall(
            r"^\s*(?:- )?uses:\s+([^\s#]+)", workflow_path.read_text(), re.M
        )
        for reference in references:
            assert re.search(r"@[a-f0-9]{40}$", reference), reference

    dependabot = yaml.safe_load((REPO_ROOT / ".github" / "dependabot.yml").read_text())
    assert dependabot["version"] == 2
    assert {
        (entry["package-ecosystem"], entry["directory"])
        for entry in dependabot["updates"]
    } == {("github-actions", "/"), ("pip", "/apps/api"), ("npm", "/")}

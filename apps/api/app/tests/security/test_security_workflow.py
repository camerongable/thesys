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
        "gitleaks/gitleaks-action@v2",
        "google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@v2.3.8",
        "anchore/sbom-action@v0",
    ):
        assert command in content


def test_promptfoo_fast_command_uses_an_exact_cli_version() -> None:
    package_json = (REPO_ROOT / "package.json").read_text()

    assert "pnpm dlx promptfoo@0.121.15 eval" in package_json


def test_release_workflow_requires_signed_scanned_provenance_backed_images() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "release-security.yml").read_text()

    for contract in (
        'tags:\n      - "v*"',
        "docker/build-push-action@v6",
        "provenance: mode=max",
        "sbom: true",
        "sigstore/cosign-installer@v3",
        "cosign sign --yes",
        "cosign verify",
        "aquasecurity/trivy-action@0.31.0",
        "format: json",
        "scripts/prepare_release_evidence.py",
        "scripts/generate_security_report.py",
        "if: always()",
        "actions/upload-artifact@v4",
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
        "aquasecurity/trivy-action@0.36.0",
        "scan-type: config",
        "scan-ref: infra/k8s/base",
    ):
        assert contract in workflow

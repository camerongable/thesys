import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
SCRIPT = REPO_ROOT / "scripts" / "write_garak_rest_config.py"


def test_garak_config_requires_https_and_keeps_authorization_out_of_source(tmp_path: Path) -> None:
    output = tmp_path / "garak.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--target-uri",
            "https://scanner.example/thesys",
            "--authorization",
            "Bearer runtime-token",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    config = json.loads(output.read_text())
    generator = config["rest"]["RestGenerator"]
    assert generator["uri"] == "https://scanner.example/thesys"
    assert generator["headers"] == {"Authorization": "Bearer runtime-token"}
    assert generator["req_template_json_object"] == {"prompt": "$INPUT"}
    assert generator["response_json_field"] == "text"


def test_garak_config_rejects_non_https_targets(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--target-uri",
            "http://scanner.example/thesys",
            "--output",
            str(tmp_path / "garak.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "must use HTTPS" in result.stderr

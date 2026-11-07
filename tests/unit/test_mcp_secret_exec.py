"""Tests du wrapper de secrets pour les serveurs MCP Antigravity."""
from pathlib import Path
import subprocess
import sys


def _script_path() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "mcp_secret_exec.py"


def test_wrapper_loads_secrets_and_expands_arguments(tmp_path: Path) -> None:
    env_file = tmp_path / "secrets.env"
    env_file.write_text(
        "SECRET_VALUE=super-secret\n"
        "export OTHER_VALUE=ok\n",
        encoding="utf-8",
    )
    env_file.chmod(0o600)

    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--env-file",
            str(env_file),
            "--",
            sys.executable,
            "-c",
            (
                "import os, sys\n"
                "assert os.environ['SECRET_VALUE'] == 'super-secret'\n"
                "assert os.environ['OTHER_VALUE'] == 'ok'\n"
                "print(sys.argv[1])\n"
            ),
            "${SECRET_VALUE}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "super-secret"


def test_wrapper_rejects_missing_secret_file(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(_script_path()),
            "--env-file",
            str(tmp_path / "absent.env"),
            "--",
            sys.executable,
            "-c",
            "print('jamais exécuté')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "introuvable" in result.stderr

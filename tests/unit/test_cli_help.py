"""Tests de l'aide CLI du script bin/kimi-proxy."""
from pathlib import Path
import subprocess


def test_cli_help_defaults_to_loopback_host() -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "bin" / "kimi-proxy"

    result = subprocess.run(
        ["bash", str(script), "help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "127.0.0.1" in result.stdout
    assert "0.0.0.0" not in result.stdout

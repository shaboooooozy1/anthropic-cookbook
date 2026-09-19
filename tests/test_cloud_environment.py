"""Regression checks for Cloud Agent commands, without downloads or API calls."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="Cloud Agent setup requires Bash")


def run_bash(command: str, *args: str) -> subprocess.CompletedProcess:
    # Only fixed repository commands and local test doubles are run here.
    return subprocess.run(  # noqa: S603
        [BASH, "-c", command, "cloud-environment-test", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_config_and_shell_syntax():
    config = json.loads((ROOT / ".cursor/environment.json").read_text())
    assert config["install"] == "bash .cursor/install.sh"
    assert config["ports"] == [{"name": "jupyter", "port": 8888}]
    assert (ROOT / ".cursor/install.sh").stat().st_mode & 0o111
    assert run_bash("bash -n .cursor/install.sh").returncode == 0
    assert run_bash('bash -n -c "$1"', config["terminals"][0]["command"]).returncode == 0


@pytest.mark.parametrize("failure", ["none", "sync", "run"])
def test_install_uses_lock_and_propagates_failures(failure):
    result = run_bash(
        r"""
        uv() {
          printf 'CALL %s\n' "$*" >&2
          if [ "$1" = "$failure" ]; then return 42; fi
          case "$*" in
            '--version') echo 'uv test' ;;
            'sync --locked --all-extras') ;;
            'run --locked python --version') echo 'Python test' ;;
            *) return 99 ;;
          esac
        }
        curl() { echo 'Unexpected download' >&2; return 99; }
        failure=$1
        source .cursor/install.sh
        """,
        failure,
    )
    assert result.returncode == (0 if failure == "none" else 42)
    assert "CALL sync --locked --all-extras" in result.stderr
    assert "Unexpected download" not in result.stderr
    assert ("Dependencies synced." in result.stdout) == (failure == "none")


def test_bootstrap_download_failure_stops_install():
    result = run_bash(
        r"""
        command() { return 1; }
        curl() { return 22; }
        sh() { return 0; }
        uv() { echo 'Unexpected uv call' >&2; return 99; }
        source .cursor/install.sh
        """
    )
    assert result.returncode == 22
    assert "Unexpected uv call" not in result.stderr


@pytest.mark.parametrize("exit_code", [0, 42])
def test_terminal_uses_lock_and_propagates_failures(exit_code):
    config = json.loads((ROOT / ".cursor/environment.json").read_text())
    command = config["terminals"][0]["command"]
    result = run_bash(
        f'uv() {{ printf "%s\\n" "$*"; return "$exit_code"; }}\nexit_code={exit_code}\n{command}'
    )
    assert result.returncode == exit_code
    assert result.stdout.startswith("run --locked jupyter lab ")
    assert "--port 8888" in result.stdout

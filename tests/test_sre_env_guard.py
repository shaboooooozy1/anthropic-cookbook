"""Tests for the DB_POOL_SIZE guard in the site-reliability agent's MCP server.

The guard decides what ``edit_config_file`` may write to ``config/api-server.env`` and
whether ``run_shell_command`` may deploy with that file on disk. Each case below is a
file Docker Compose resolves differently from a line-by-line reading of it, so a guard
that reads line by line let it through at some point.

Nothing here needs Docker, the network or an API key: the demo stack is generated into
a temp directory and the docker call is stubbed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("httpx")  # imported by sre_mcp_server.py

SRE_DIR = Path(__file__).resolve().parents[1] / "claude_agent_sdk" / "site_reliability_agent"
BASH = shutil.which("bash")

POOL = "DB_POOL_SIZE=20"
TIMEOUT = "DB_POOL_TIMEOUT=2"
UP = "docker-compose -f config/docker-compose.yml up -d api-server"


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    """The real generated demo files, with the server loaded from beside them."""
    root = tmp_path_factory.mktemp("sre")
    for name in ("infra_setup.py", "sre_mcp_server.py"):
        shutil.copy(SRE_DIR / name, root / name)
    # Fixed repository script, run in a temp directory.
    subprocess.run([sys.executable, "infra_setup.py"], cwd=root, check=True, capture_output=True)  # noqa: S603
    spec = importlib.util.spec_from_file_location(
        "sre_mcp_server_guard", root / "sre_mcp_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, root


@pytest.fixture
def sre(stack, monkeypatch):
    module, root = stack
    env_file = root / "config" / "api-server.env"
    template = env_file.read_bytes()
    launched: list[list[str]] = []

    class Process:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def fake_exec(*args, **kwargs):
        launched.append(list(args))
        return Process()

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", fake_exec)
    yield SimpleNamespace(
        module=module, root=root, env_file=env_file, template=template.decode(), launched=launched
    )
    env_file.write_bytes(template)


def deploys(sre, command: str = UP) -> bool:
    before = len(sre.launched)
    asyncio.run(sre.module.run_shell_command(command))
    return len(sre.launched) > before


def edit(sre, old: str, new: str, path: str = "config/api-server.env") -> bool:
    result = asyncio.run(sre.module.edit_config_file(path, old, new))
    return not result.get("isError", False)


# What compose would hand the container is unsafe, or cannot be known from the file.
UNSAFE_FILES = {
    "below range": lambda t: t.replace(POOL, "DB_POOL_SIZE=1"),
    "above range": lambda t: t.replace(POOL, "DB_POOL_SIZE=500"),
    "not an integer": lambda t: t.replace(POOL, "DB_POOL_SIZE=abc"),
    "empty value": lambda t: t.replace(POOL, "DB_POOL_SIZE="),
    "quoted value": lambda t: t.replace(POOL, 'DB_POOL_SIZE="20"'),
    "trailing comment": lambda t: t.replace(POOL, "DB_POOL_SIZE=20 # ok"),
    "second assignment": lambda t: t + "DB_POOL_SIZE=1\n",
    "export form": lambda t: t.replace(POOL, "export DB_POOL_SIZE=1"),
    "colon form": lambda t: t.replace(POOL, "DB_POOL_SIZE: 1"),
    "no-break space before the key": lambda t: t + "\u00a0DB_POOL_SIZE=1\n",
    "byte order mark before the key": lambda t: t + "\ufeffDB_POOL_SIZE=1\n",
    "vertical tab in the value": lambda t: t.replace(POOL, "DB_POOL_SIZE=50\x0b0"),
    "line separator in the value": lambda t: t.replace(POOL, "DB_POOL_SIZE=50\u20280"),
    "carriage return before the key": lambda t: t + "\rDB_POOL_SIZE=1\n",
    "carriage return in the value": lambda t: t.replace(POOL, "DB_POOL_SIZE=50\r0"),
    "carriage return in a comment": lambda t: t + "# note\rDB_POOL_SIZE=1\n",
    "statement after a double-quoted value": lambda t: t.replace(
        TIMEOUT, 'DB_POOL_TIMEOUT="2" DB_POOL_SIZE=1'
    ),
    "statement after a single-quoted value": lambda t: t.replace(
        TIMEOUT, "DB_POOL_TIMEOUT='2' DB_POOL_SIZE=1"
    ),
    "statement after a multi-line quoted value": lambda t: t.replace(
        TIMEOUT, 'DB_POOL_TIMEOUT="2\n" DB_POOL_SIZE=1'
    ),
    "quoted value swallowing the real line": lambda t: t.replace(
        POOL, f'X="\n{POOL}\n" DB_POOL_SIZE=1'
    ),
    "quoted value on another key": lambda t: t.replace("DB_HOST=postgres", 'DB_HOST="postgres"'),
    "key with no value": lambda t: t + "DB_POOL_SIZE\n",
    "exported key with no value": lambda t: t + "export DB_POOL_SIZE\n",
}

SAFE_FILES = {
    "generated template": lambda t: t,
    "lower bound": lambda t: t.replace(POOL, "DB_POOL_SIZE=5"),
    "upper bound": lambda t: t.replace(POOL, "DB_POOL_SIZE=100"),
    "CRLF line endings": lambda t: t.replace("\n", "\r\n"),
    "non-ASCII and quotes in a comment": lambda t: '# pool \u2014 keep at "20", don\'t lower\n' + t,
    "similar key with no value": lambda t: t + "DB_POOL_SIZE_MAX\n",
}


def test_generated_template_is_what_the_cases_assume(sre):
    assert sre.template.count(POOL) == 1
    assert sre.template.count(TIMEOUT) == 1
    assert "DB_HOST=postgres" in sre.template
    assert sre.template.isascii() and "\r" not in sre.template


@pytest.mark.parametrize("case", UNSAFE_FILES)
def test_unsafe_file_blocks_deploy(sre, case):
    sre.env_file.write_bytes(UNSAFE_FILES[case](sre.template).encode())
    assert not deploys(sre)


@pytest.mark.parametrize("case", SAFE_FILES)
def test_safe_file_deploys(sre, case):
    sre.env_file.write_bytes(SAFE_FILES[case](sre.template).encode())
    assert deploys(sre)


@pytest.mark.parametrize("subcommand", ["ps", "down", "logs --tail 20 api-server"])
def test_commands_that_start_nothing_are_not_gated(sre, subcommand):
    sre.env_file.write_bytes(sre.template.replace(POOL, "DB_POOL_SIZE=1").encode())
    assert deploys(sre, f"docker-compose -f config/docker-compose.yml {subcommand}")


@pytest.mark.parametrize("service", ["", "prometheus", "grafana", "traffic-generator"])
def test_deploy_is_gated_whatever_service_is_named(sre, service):
    sre.env_file.write_bytes(sre.template.replace(POOL, "DB_POOL_SIZE=1").encode())
    assert not deploys(sre, f"docker-compose -f config/docker-compose.yml up -d {service}".strip())


REFUSED_EDITS = {
    "out of range by number only": ("20", "500"),
    "not an integer": (POOL, "DB_POOL_SIZE=abc"),
    "second assignment": (TIMEOUT, f"{TIMEOUT}\nDB_POOL_SIZE=1"),
    "no-break space before a second assignment": (TIMEOUT, f"{TIMEOUT}\n\u00a0DB_POOL_SIZE=1"),
    "carriage return before a second assignment": (TIMEOUT, f"{TIMEOUT}\n\rDB_POOL_SIZE=1"),
    "carriage return joining a second assignment": (TIMEOUT, f"{TIMEOUT}\rDB_POOL_SIZE=1"),
    "carriage return inside a comment": (TIMEOUT, f"{TIMEOUT}\n# note\rDB_POOL_SIZE=1"),
    "carriage return in the value": (POOL, "DB_POOL_SIZE=50\r0"),
    "statement after a double-quoted value": (TIMEOUT, 'DB_POOL_TIMEOUT="2" DB_POOL_SIZE=1'),
    "statement after a single-quoted value": (TIMEOUT, "DB_POOL_TIMEOUT='2' DB_POOL_SIZE=1"),
    "opening a multi-line quoted value": (TIMEOUT, 'DB_POOL_TIMEOUT="2'),
    "quoting another value": ("DB_HOST=postgres", 'DB_HOST="postgres"'),
    "key with no value": (POOL, "DB_POOL_SIZE"),
}


@pytest.mark.parametrize("case", REFUSED_EDITS)
def test_edit_that_makes_the_file_unsafe_is_refused(sre, case):
    old, new = REFUSED_EDITS[case]
    before = sre.env_file.read_bytes()
    assert not edit(sre, old, new)
    assert sre.env_file.read_bytes() == before


def test_in_range_edit_is_written_and_deploys(sre):
    assert edit(sre, POOL, "DB_POOL_SIZE=50")
    assert sre.env_file.read_bytes() == sre.template.replace(POOL, "DB_POOL_SIZE=50").encode()
    assert deploys(sre)


def test_incident_can_be_remediated_but_not_made_worse(sre):
    incident = sre.template.replace(POOL, "DB_POOL_SIZE=1")
    sre.env_file.write_bytes(incident.encode())
    assert not edit(sre, "DB_POOL_SIZE=1", "DB_POOL_SIZE=0")
    # An unrelated edit is not blamed for the standing value, and does not unblock a deploy.
    assert edit(sre, "DB_HOST=postgres", "DB_HOST=postgres2")
    assert not deploys(sre)
    assert edit(sre, "DB_POOL_SIZE=1", POOL)
    assert deploys(sre)


def test_edit_changes_no_byte_outside_the_replacement(sre):
    crlf = sre.template.replace("\n", "\r\n")
    sre.env_file.write_bytes(crlf.encode())
    assert edit(sre, POOL, "DB_POOL_SIZE=50")
    assert sre.env_file.read_bytes() == crlf.replace(POOL, "DB_POOL_SIZE=50").encode()


def test_edit_does_not_turn_a_carriage_return_into_a_line_break(sre):
    # Put there out of band: compose reads the second line as one comment, while text-mode
    # I/O would rewrite it as a comment followed by a real DB_POOL_SIZE=1 line.
    standing = sre.template + "# note\rDB_POOL_SIZE=1\n"
    sre.env_file.write_bytes(standing.encode())
    assert edit(sre, "DB_HOST=postgres", "DB_HOST=postgres2")
    assert (
        sre.env_file.read_bytes()
        == standing.replace("DB_HOST=postgres", "DB_HOST=postgres2").encode()
    )
    assert not deploys(sre)


@pytest.mark.parametrize(
    "path",
    [
        "config/docker-compose.yml",
        "config/./docker-compose.yml",
        "config/../config/docker-compose.yml",
    ],
)
def test_compose_file_is_not_editable(sre, path):
    compose = sre.root / "config" / "docker-compose.yml"
    before = compose.read_bytes()
    assert not edit(sre, "postgres:15-alpine", "attacker/image", path=path)
    assert compose.read_bytes() == before


def run_hook(sre, name: str, tool_input: dict) -> int:
    # Fixed generated script, fed a test payload on stdin.
    return subprocess.run(  # noqa: S603
        [BASH, str(sre.root / "hooks" / name)],
        input=json.dumps({"tool_input": tool_input}),
        cwd=sre.root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).returncode


needs_bash = pytest.mark.skipif(BASH is None, reason="the generated hooks are Bash scripts")


@needs_bash
@pytest.mark.parametrize(
    ("new_value", "exit_code"),
    [
        ("DB_POOL_SIZE=20", 0),
        ("DB_POOL_SIZE=500", 2),
        ("\rDB_POOL_SIZE=1", 2),
        ('DB_POOL_TIMEOUT="2" DB_POOL_SIZE=1', 2),
        ('# keep at "20"', 0),
    ],
)
def test_pool_size_hook(sre, new_value, exit_code):
    assert run_hook(sre, "validate_pool_size.sh", {"new_value": new_value}) == exit_code


@needs_bash
@pytest.mark.parametrize(
    "case",
    [
        "below range",
        "second assignment",
        "carriage return before the key",
        "carriage return in the value",
        "statement after a double-quoted value",
        "key with no value",
    ],
)
def test_deploy_hook_denies_unsafe_file(sre, case):
    sre.env_file.write_bytes(UNSAFE_FILES[case](sre.template).encode())
    assert run_hook(sre, "validate_config_before_deploy.sh", {"command": UP}) == 2


@needs_bash
@pytest.mark.parametrize("case", SAFE_FILES)
def test_deploy_hook_allows_safe_file(sre, case):
    sre.env_file.write_bytes(SAFE_FILES[case](sre.template).encode())
    assert run_hook(sre, "validate_config_before_deploy.sh", {"command": UP}) == 0

import asyncio
import json
import subprocess

import pytest

from pyrite64_mcp.server import create_server


def test_cli_arguments_and_failure_reporting(tmp_path, monkeypatch):
    (tmp_path / "project.p64proj").write_text('{"name":"Build test"}')
    executable = tmp_path / "pyrite64.exe"
    executable.write_bytes(b"placeholder")
    seen = []
    def run(args, **kwargs):
        seen.append((args, kwargs))
        return subprocess.CompletedProcess(args, 1, "toolchain build output", "specific error")
    monkeypatch.setattr("pyrite64_mcp.server.subprocess.run", run)
    async def exercise():
        server = create_server(tmp_path, str(executable))
        result = await server.call_tool("build_project", {"command": "clean", "timeout_seconds": 42})
        # FastMCP returns the structured Python value when called directly.
        if isinstance(result, tuple):
            value = result[1]
        elif isinstance(result, dict):
            value = result
        else:
            value = json.loads(result[0].text)
        assert value["success"] is False
        assert value["returncode"] == 1
        assert value["stderr"] == "specific error"
    asyncio.run(exercise())
    args, options = seen[0]
    assert args == [str(executable.resolve()), "--cli", "--cmd", "clean", str((tmp_path / "project.p64proj").resolve())]
    assert options["shell"] is False
    assert options["cwd"] == executable.parent
    assert options["timeout"] == 42


def test_cli_timeout_releases_build_lock(tmp_path, monkeypatch):
    (tmp_path / "project.p64proj").write_text('{"name":"Build test"}')
    executable = tmp_path / "pyrite64.exe"
    executable.write_bytes(b"placeholder")
    def run(args, **kwargs):
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])
    monkeypatch.setattr("pyrite64_mcp.server.subprocess.run", run)
    async def exercise():
        server = create_server(tmp_path, str(executable))
        for _ in range(2):
            with pytest.raises(Exception, match="exceeded timeout"):
                await server.call_tool("build_project", {"timeout_seconds": 1})
    asyncio.run(exercise())

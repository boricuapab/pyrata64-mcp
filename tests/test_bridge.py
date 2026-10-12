import asyncio
import importlib.util
import json
import time
from pathlib import Path

import pytest

from pyrite64_mcp.bridge import Bridge


def test_bridge_response_and_error(tmp_path):
    async def run(ok):
        async def editor():
            for _ in range(100):
                requests = list(tmp_path.glob("*.request.json"))
                if requests:
                    request = json.loads(requests[0].read_text())
                    assert request["action"] == "status"
                    assert request["expires"] > time.time()
                    response = {"id": request["id"], "ok": ok, "result": {"connected": True}, "error": "Different project"}
                    (tmp_path / f'{request["id"]}.response.json').write_text(json.dumps(response))
                    return
                await asyncio.sleep(0.01)
        task = asyncio.create_task(editor())
        try:
            if ok:
                assert await Bridge(tmp_path).call("status") == {"connected": True}
            else:
                with pytest.raises(RuntimeError, match="Different project"):
                    await Bridge(tmp_path).call("status")
        finally:
            await task
        assert not list(tmp_path.glob("*.json"))
    asyncio.run(run(True))
    asyncio.run(run(False))


def test_bridge_timeout_cleans_pending_request(tmp_path):
    async def run():
        with pytest.raises(TimeoutError):
            await Bridge(tmp_path).call("get_scene", timeout=0.1)
        assert not list(tmp_path.glob("*.json"))
    asyncio.run(run())


def test_installer_preserves_source_and_is_idempotent(tmp_path):
    path = Path(__file__).parents[1] / "scripts" / "install_bridge.py"
    spec = importlib.util.spec_from_file_location("install_bridge", path)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    (tmp_path / "src").mkdir()
    main = tmp_path / "src" / "main.cpp"
    original = '// existing code\n      auto frameStart = SDL_GetTicksNS();\n'
    main.write_text(original)
    installer.install(tmp_path)
    assert main.with_suffix(".cpp.mcp-backup").read_text() == original
    assert main.read_text().count("Pyrite64MCP::poll();") == 1
    assert installer.install(tmp_path) == "Already installed"


def test_installer_rejects_changed_layout(tmp_path):
    path = Path(__file__).parents[1] / "scripts" / "install_bridge.py"
    spec = importlib.util.spec_from_file_location("install_bridge", path)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.cpp").write_text("Different editor version")
    with pytest.raises(ValueError, match="layout"):
        installer.install(tmp_path)

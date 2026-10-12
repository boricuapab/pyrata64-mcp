"""Real MCP initialization, tool calls, resources and both transports."""
import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


ROOT = Path(__file__).resolve().parents[1]


def env():
    return {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def payload(result):
    assert not result.isError, result.content
    if result.structuredContent:
        return result.structuredContent
    return json.loads(result.content[0].text)


async def exercise(session, project):
    initialized = await session.initialize()
    assert initialized.serverInfo.name == "Pyrite64"
    tools = await session.list_tools()
    assert {"get_status", "build_project", "search_knowledge", "create_object"} <= {tool.name for tool in tools.tools}
    status = payload(await session.call_tool("get_status"))
    assert status["port"] == 8974
    assert status["knowledge"]["counts"]["website"] > 150
    assert (await session.list_resources()).resources
    resource = await session.read_resource("pyrite64://reference/components")
    assert len(json.loads(resource.contents[0].text)["components"]) == 14
    assert (await session.list_prompts()).prompts
    assert (await session.get_prompt("pyrite64_workflow", {"task": "Add a camera"})).messages
    assert not (await session.call_tool("search_knowledge", {"query": "character body"})).isError
    payload(await session.call_tool("create_scene", {"scene_id": 1, "name": "Protocol test"}))
    created = payload(await session.call_tool("create_object", {"scene_id": 1, "name": "Player"}))
    uid = created["object"]["uuid"]
    payload(await session.call_tool("update_object", {"scene_id": 1, "object_uuid": uid, "changes": {"pos": [1, 2, 3]}}))
    scene = payload(await session.call_tool("get_scene", {"scene_id": 1}))
    assert scene["scene"]["graph"]["children"][0]["pos"] == [1, 2, 3]
    root_uid = scene["scene"]["graph"]["uuid"]
    created_child = payload(await session.call_tool("create_object", {"scene_id": 1, "name": "Child"}))
    child_uid = created_child["object"]["uuid"]
    payload(await session.call_tool("reparent_object", {"scene_id": 1, "object_uuid": child_uid, "parent_uuid": uid}))
    cycle = await session.call_tool("reparent_object", {"scene_id": 1, "object_uuid": uid, "parent_uuid": child_uid})
    assert cycle.isError
    scene = payload(await session.call_tool("get_scene", {"scene_id": 1}))
    document = scene["scene"]
    component_uuid = 18446744073709551601
    document["graph"]["children"][0]["components"].append({"id": 0, "uuid": component_uuid,
                       "name": "Code", "enabled": True, "data": {"script": 0, "args": {"preserve": "yes", "update": "before"}}})
    payload(await session.call_tool("write_project_file", {"path": "data/scenes/1/scene.json", "content": json.dumps(document), "expected_sha256": scene["sha256"]}))
    payload(await session.call_tool("update_component", {"scene_id": 1, "object_uuid": uid, "component_uuid": str(component_uuid), "data_changes": {"args": {"update": "after"}}, "enabled": False}))
    updated = payload(await session.call_tool("get_object", {"scene_id": 1, "object_uuid": uid}))
    assert updated["components"][0]["data"]["args"] == {"preserve": "yes", "update": "after"}
    assert updated["components"][0]["uuid"] == component_uuid
    assert updated["components"][0]["enabled"] is False
    payload(await session.call_tool("remove_component", {"scene_id": 1, "object_uuid": uid, "component_uuid": str(component_uuid)}))
    assert (project / ".pyrite64-mcp/backups").exists()
    rejected = await session.call_tool("read_project_file", {"path": "../secret.txt"})
    assert rejected.isError
    unsupported = await session.call_tool("add_component", {"scene_id": 1, "object_uuid": uid, "component_id": 3})
    assert unsupported.isError
    payload(await session.call_tool("delete_object", {"scene_id": 1, "object_uuid": uid}))
    scene = payload(await session.call_tool("get_scene", {"scene_id": 1}))
    assert scene["scene"]["graph"]["children"] == []


def test_stdio(tmp_path):
    (tmp_path / "project.p64proj").write_text('{"name":"Protocol test"}')
    async def run():
        params = StdioServerParameters(command=sys.executable,
                    args=["-m", "pyrite64_mcp.server", "--transport", "stdio", "--project", str(tmp_path)], env=env())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await exercise(session, tmp_path)
    asyncio.run(run())


def test_streamable_http_on_8974(tmp_path):
    (tmp_path / "project.p64proj").write_text('{"name":"Protocol test"}')
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", 8974))
        except OSError as exc:
            pytest.skip(f"Port 8974 unavailable: {exc}")
    log = (tmp_path / "server.log").open("w")
    process = subprocess.Popen([sys.executable, "-m", "pyrite64_mcp.server", "--project", str(tmp_path)],
                               env=env(), stdout=log, stderr=log)
    async def run():
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError((tmp_path / "server.log").read_text())
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", 8974)
                writer.close()
                await writer.wait_closed()
                break
            except OSError:
                await asyncio.sleep(0.1)
        async with streamable_http_client("http://127.0.0.1:8974/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await exercise(session, tmp_path)
    try:
        asyncio.run(run())
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()

"""Exercise the compiled bridge against an isolated open test project (never a real game)."""
import argparse
import asyncio
import copy
import json
from pathlib import Path

from pyrite64_mcp.bridge import Bridge
from pyrite64_mcp.project import new_object, validate_scene


async def run(project, directory):
    bridge = Bridge(directory)
    async def call(action, **args):
        return await bridge.call(action, {"project_path": str(Path(project).resolve()), **args})
    status = await call("status")
    scene_id = status["scene_id"]
    original = (await call("get_scene", scene_id=scene_id))["scene"]
    changed = copy.deepcopy(original)
    obj = new_object("MCP smoke test", changed["graph"])
    changed["graph"]["children"].append(obj)
    validate_scene(changed)
    await call("replace_scene", scene_id=scene_id, scene=changed, expected=original)
    current = (await call("get_scene", scene_id=scene_id))["scene"]
    actual = next(node for node in current["graph"]["children"] if node["uuid"] == obj["uuid"])
    assert actual["rot"] == [0, 0, 0, 1], actual["rot"]
    assert current["graph"]["rot"] == original["graph"]["rot"]
    # A stale editor revision must never replace an unsaved user edit.
    try:
        await call("replace_scene", scene_id=scene_id, scene=original, expected=original)
    except RuntimeError as exc:
        assert "changed" in str(exc)
    else:
        raise AssertionError("Stale transaction was not rejected")
    for component_id in range(14):
        await call("add_component", scene_id=scene_id, object_uuid=obj["uuid"], component_id=component_id)
    current = (await call("get_scene", scene_id=scene_id))["scene"]
    actual = next(node for node in current["graph"]["children"] if node["uuid"] == obj["uuid"])
    assert len(actual["components"]) == 14
    await call("select_object", object_uuid=obj["uuid"])
    assert (await call("status"))["selected_object"] == obj["uuid"]
    await call("save_project")
    saved = json.loads((Path(project) / "data/scenes" / str(scene_id) / "scene.json").read_text())
    assert len(saved["graph"]["children"][0]["components"]) == 14
    await call("replace_scene", scene_id=scene_id, scene=original, expected=current)
    await call("save_project")
    print(json.dumps({"native_bridge": "passed", "component_defaults_tested": 14,
                      "checks": ["connectivity", "scene create/read", "quaternion preservation", "stale revision rejection", "native component initialization", "selection", "save", "restore"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("bridge_directory")
    args = parser.parse_args()
    asyncio.run(run(args.project, args.bridge_directory))

import copy
import hashlib
import json

import pytest

from pyrite64_mcp.knowledge import DATA, Knowledge
from pyrite64_mcp.project import Project, new_object, validate_scene


@pytest.fixture
def project(tmp_path):
    (tmp_path / "project.p64proj").write_text('{"name":"Test"}', encoding="utf-8")
    return Project(tmp_path)


def test_scene_roundtrip_and_backups(project):
    project.create_scene(1, "Test scene")
    scene, revision = project.read_scene(1)
    old = project.scene_path(1).read_bytes()
    obj = new_object("Camera", scene["graph"])
    scene["graph"]["children"].append(obj)
    assert obj["rot"] == [0, 0, 0, 1]
    assert validate_scene(scene)["objects"] == 1
    result = project.write(project.scene_path(1), json.dumps(scene), revision)
    assert (project.root / result["backup"]).read_bytes() == old
    assert project.read_scene(1)[0]["graph"]["children"][0] == obj
    with pytest.raises(ValueError, match="changed"):
        project.write(project.scene_path(1), "{}", revision)
    with pytest.raises(ValueError, match="already exists"):
        project.create_scene(1, "Overwrite")


@pytest.mark.parametrize("path", ["../outside.txt", "C:/outside.txt", "file.txt:secret", ".git/config", ".pyrite64-mcp/backups/x", ".env"])
def test_path_confinement(project, path):
    with pytest.raises(ValueError):
        project.path(path)


def test_symlink_confinement(project, tmp_path):
    link = project.root / "linked"
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not allow creating symlinks")
    with pytest.raises(ValueError, match="escapes"):
        project.path("linked/file.txt")


def test_scene_validation_rejects_duplicates_and_nonfinite(project):
    project.create_scene(1, "Test")
    scene, _ = project.read_scene(1)
    obj = new_object("A", scene["graph"])
    scene["graph"]["children"] = [obj, copy.deepcopy(obj)]
    with pytest.raises(ValueError, match="unique"):
        validate_scene(scene)
    scene["graph"]["children"] = [obj]
    obj["pos"] = [float("nan"), 0, 0]
    with pytest.raises(ValueError, match="finite"):
        validate_scene(scene)


def test_windows_crlf_revision(project):
    project.create_scene(1, "Windows")
    path = project.scene_path(1)
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    scene, revision = project.read_scene(1)
    project.write(path, json.dumps(scene), revision)


def test_component_limit_and_rigidbody_constraint(project):
    project.create_scene(1, "Test")
    scene, _ = project.read_scene(1)
    obj = new_object("A", scene["graph"])
    scene["graph"]["children"] = [obj]
    obj["components"] = [{"id": 11, "uuid": i+1, "data": {}, "name": "Rigid-Body"} for i in range(2)]
    with pytest.raises(ValueError, match="only one"):
        validate_scene(scene)
    obj["components"] = [{"id": 0, "uuid": i+1, "data": {}, "name": "Code"} for i in range(256)]
    with pytest.raises(ValueError, match="255"):
        validate_scene(scene)


def test_knowledge_coverage_and_pagination():
    kb = Knowledge()
    assert kb.snapshot["metadata"]["website_failures"] == []
    assert kb.snapshot["metadata"]["counts"]["website"] > 150
    for query in ["character body move slide", "node graph custom", "HDR bloom", "materials color combiner", "ROM metadata", "CLI build"]:
        assert kb.search(query)
    result = kb.search("charBody", "source")[0]
    assert kb.read(result["id"], 1, 5)["text"]
    assert all(x["kind"] == "docs" for x in kb.search("camera", "docs"))
    assert len(json.loads((DATA / "components.json").read_text())["components"]) == 14

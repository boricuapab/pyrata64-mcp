"""Source-compatible scene editing, project confinement, backups and validation."""
import hashlib
import json
import math
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def walk(node):
    yield node
    for child in node.get("children", []):
        yield from walk(child)


def validate_scene(scene):
    if not isinstance(scene, dict) or not isinstance(scene.get("conf"), dict) or not isinstance(scene.get("graph"), dict):
        raise ValueError("Scene requires conf and graph objects")
    if scene.get("version") != 2:
        raise ValueError("Only source-reference scene format version 2 is supported")
    seen = set()
    component_count = 0
    for node in walk(scene["graph"]):
        uid = node.get("uuid")
        if type(uid) is not int or not 0 < uid <= 0xffffffff or uid in seen:
            raise ValueError("Object UUIDs must be unique nonzero uint32 integers")
        seen.add(uid)
        if not isinstance(node.get("name"), str):
            raise ValueError("Object name must be a string")
        for field, size in (("pos", 3), ("rot", 4), ("scale", 3)):
            value = node.get(field)
            if not isinstance(value, list) or len(value) != size or any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
                raise ValueError(f"{field} must contain {size} finite numbers; rot is [x,y,z,w]")
        if not isinstance(node.get("children", []), list) or not isinstance(node.get("components", []), list):
            raise ValueError("children/components must be arrays")
        components = node.get("components", [])
        component_ids = set()
        if len(components) > 255:
            raise ValueError("Pyrite64 allows at most 255 components per object")
        if sum(c.get("id") == 11 for c in components) > 1:
            raise ValueError("An object can have only one Rigid-Body component")
        for comp in components:
            uid = comp.get("uuid")
            if type(comp.get("id")) is not int or comp["id"] not in range(14):
                raise ValueError("Unknown component ID (reference supports 0..13)")
            if type(uid) is not int or not 0 < uid <= 0xffffffffffffffff or uid in component_ids:
                raise ValueError("Component UUIDs must be unique nonzero uint64 integers")
            component_ids.add(uid)
            component_count += 1
            if not isinstance(comp.get("data"), dict) or not isinstance(comp.get("name"), str):
                raise ValueError("Component requires data object and name string")
    json.dumps(scene, allow_nan=False)
    return {"objects": len(seen)-1, "components": component_count}


def new_object(name, existing):
    used = {n["uuid"] for n in walk(existing)}
    uid = secrets.randbelow(0xffffffff) + 1
    while uid in used:
        uid = secrets.randbelow(0xffffffff) + 1
    return {"name": name, "uuid": uid, "pos": [0, 0, 0], "rot": [0, 0, 0, 1],
            "scale": [1, 1, 1], "visMask": 1, "enabled": True, "selectable": True,
            "proportionalScale": False, "uuidPrefab": 0, "propOverrides": {},
            "children": [], "components": []}


def find_object(scene, object_uuid):
    for node in walk(scene["graph"]):
        if node["uuid"] == object_uuid:
            return node
    raise ValueError(f"Object {object_uuid} does not exist")


class Project:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        candidates = list(self.root.glob("*.p64proj"))
        if len(candidates) != 1:
            raise ValueError("Project directory must contain exactly one .p64proj file")
        self.config = self.path(candidates[0].name)

    def path(self, relative):
        value = Path(relative)
        if value.is_absolute() or value.drive or ".." in value.parts or ":" in str(value):
            raise ValueError("Use a project-relative path without traversal or alternate streams")
        target = (self.root / value).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Path escapes project (possibly through a symlink)")
        if any(part.lower() in {".git", ".pyrite64-mcp", ".aws", ".codex", ".env", ".ssh"} for part in value.parts):
            raise ValueError("Protected project path")
        return target

    def scene_path(self, scene_id):
        if type(scene_id) is not int or scene_id < 1:
            raise ValueError("scene_id must be a positive integer")
        return self.path(f"data/scenes/{scene_id}/scene.json")

    def read_scene(self, scene_id):
        data = self.scene_path(scene_id).read_bytes()
        return json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest()

    def write(self, path, content, expected_sha256=None, create=False):
        # Resolve again immediately before writing, including the backup destination.
        path = self.path(path.relative_to(self.root))
        if path.exists():
            previous = path.read_bytes()
            current = hashlib.sha256(previous).hexdigest()
            if expected_sha256 is None or current != expected_sha256:
                raise ValueError("File changed or no expected_sha256 supplied; read it again before editing")
            backup_dir = self.root / ".pyrite64-mcp" / "backups"
            if not backup_dir.resolve().is_relative_to(self.root):
                raise ValueError("Backup directory escapes project")
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_dir / f"{stamp}-{secrets.token_hex(4)}-{path.name}"
            backup.write_bytes(previous)
        elif not create:
            raise FileNotFoundError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".mcp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {"path": str(path.relative_to(self.root)), "sha256": digest(content), "backup": str(backup.relative_to(self.root)) if path.exists() and 'backup' in locals() else None}

    def scenes(self):
        directory = self.path("data/scenes")
        results = []
        if directory.exists():
            for item in sorted(directory.iterdir()):
                if item.name.isdecimal() and (item / "scene.json").exists():
                    scene, sha = self.read_scene(int(item.name))
                    results.append({"id": int(item.name), "name": scene["conf"].get("name"), "sha256": sha,
                                    "objects": sum(1 for _ in walk(scene["graph"]))-1})
        return results

    def create_scene(self, scene_id, name):
        path = self.scene_path(scene_id)
        if path.parent.exists():
            raise ValueError("Scene ID already exists")
        scene = json.loads((DATA / "scene-template.json").read_text(encoding="utf-8"))
        scene["conf"]["name"] = name
        validate_scene(scene)
        return self.write(path, json.dumps(scene, indent=2, allow_nan=False) + "\n", create=True)

"""Atomic local mailbox transport to the optional C++ main-thread bridge."""
import asyncio
import json
import os
import time
import uuid
from pathlib import Path


class Bridge:
    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()

    async def call(self, action, args=None, timeout=10):
        self.directory.mkdir(parents=True, exist_ok=True)
        request_id = uuid.uuid4().hex
        request = self.directory / f"{request_id}.request.json"
        response = self.directory / f"{request_id}.response.json"
        temporary = request.with_suffix(".tmp")
        temporary.write_text(json.dumps({"id": request_id, "action": action, "args": args or {},
                                         "expires": time.time() + timeout}), encoding="utf-8")
        os.replace(temporary, request)
        try:
            until = time.monotonic() + timeout
            while time.monotonic() < until:
                if response.exists():
                    result = json.loads(response.read_text(encoding="utf-8"))
                    if result.get("id") != request_id:
                        raise RuntimeError("Editor response ID mismatch")
                    if not result.get("ok"):
                        raise RuntimeError(result.get("error", "Editor bridge failed"))
                    return result["result"]
                await asyncio.sleep(0.05)
            raise TimeoutError("Pyrite64 bridge did not respond. Install the bridge, set PYRITE64_MCP_BRIDGE_DIR in both processes, and open a project. A timed-out edit may have executed; inspect state before retrying.")
        finally:
            request.unlink(missing_ok=True)
            response.unlink(missing_ok=True)
            temporary.unlink(missing_ok=True)

import asyncio
import hashlib
import json
import threading
import subprocess

import pytest
from pyrite64_mcp.server import create_server


def value(result):
    if isinstance(result, tuple): return result[1]
    if isinstance(result, dict): return result
    return json.loads(result[0].text)


@pytest.fixture
def game(tmp_path):
    (tmp_path/'project.p64proj').write_text('{"romName":"game"}')
    source = tmp_path/'src/user/player.cpp'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'// original\r\n')
    return tmp_path, source


def test_live_source_edits_preserve_scene_and_connection(game, monkeypatch):
    root, source = game
    actions = []
    async def call(self, action, args=None, **kw):
        actions.append(action)
        assert action == 'status', 'Source editing must not save/reload the scene or assets'
        return {'scene_id': 1}
    monkeypatch.setattr('pyrite64_mcp.server.Bridge.call', call)
    server = create_server(root, mode='live')
    async def exercise():
        original = source.read_bytes()
        result = value(await server.call_tool('write_project_file', {'path':'src/user/player.cpp', 'content':'// changed\n', 'expected_sha256':hashlib.sha256(original).hexdigest()}))
        assert source.read_text() == '// changed\n'
        assert (root/result['backup']).read_bytes() == original
        assert result['scene_reloaded'] is False and result['rebuild_required'] is True
        second = value(await server.call_tool('write_project_file', {'path':'src/user/player.cpp', 'content':'// second edit\n', 'expected_sha256':result['sha256']}))
        assert second['mode'] == 'live'
        created = value(await server.call_tool('write_project_file', {'path':'src/user/helper.h', 'content':'#pragma once\n'}))
        assert created['backup'] is None
    asyncio.run(exercise())
    assert actions == ['status', 'status', 'status']


@pytest.mark.parametrize('path', ['data/scenes/1/scene.json', 'src/p64/main.cpp', 'engine/game.cpp', 'assets/test.prefab', 'nodes/custom.js', 'project.p64proj'])
def test_live_rejects_files_that_can_conflict_with_editor_state(game, path):
    root, _ = game
    with pytest.raises(Exception, match='Live file writes support'):
        asyncio.run(create_server(root, mode='live').call_tool('write_project_file', {'path':path, 'content':'{}'}))


def test_disconnected_editor_does_not_write_and_lock_recovers(game, monkeypatch):
    root, source = game
    async def disconnected(*a, **kw): raise TimeoutError('Editor disconnected')
    monkeypatch.setattr('pyrite64_mcp.server.Bridge.call', disconnected)
    server = create_server(root, mode='live')
    async def exercise():
        for _ in range(2):
            with pytest.raises(Exception, match='Editor disconnected'):
                await server.call_tool('write_project_file', {'path':'src/user/new.cpp', 'content':'// test'})
            assert not (root/'src/user/new.cpp').exists()
    asyncio.run(exercise())


def test_live_stale_hash_does_not_overwrite(game, monkeypatch):
    root, source = game
    async def connected(*a, **kw): return {'scene_id':1}
    monkeypatch.setattr('pyrite64_mcp.server.Bridge.call', connected)
    with pytest.raises(Exception, match='changed'):
        asyncio.run(create_server(root, mode='live').call_tool('write_project_file', {'path':'src/user/player.cpp', 'content':'overwrite', 'expected_sha256':'stale'}))
    assert source.read_bytes() == b'// original\r\n'


def test_source_edit_is_blocked_during_mcp_build(game, monkeypatch):
    root, source = game
    editor = root/'pyrite64.exe'
    editor.write_bytes(b'placeholder')
    started, release = threading.Event(), threading.Event()
    async def connected(*a, **kw): return {'saved':True}
    def build(args, **kw):
        started.set()
        assert release.wait(5)
        return subprocess.CompletedProcess(args, 0, '', '')
    monkeypatch.setattr('pyrite64_mcp.server.Bridge.call', connected)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', build)
    server = create_server(root, str(editor), mode='live')
    async def exercise():
        task = asyncio.create_task(server.call_tool('build_project', {}))
        try:
            for _ in range(100):
                if started.is_set(): break
                await asyncio.sleep(.01)
            assert started.is_set()
            with pytest.raises(Exception, match='A build is running'):
                await server.call_tool('write_project_file', {'path':'src/user/new.cpp', 'content':'// blocked'})
            assert not (root/'src/user/new.cpp').exists()
        finally:
            release.set()
            await task
    asyncio.run(exercise())

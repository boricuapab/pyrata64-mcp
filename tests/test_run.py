import asyncio
import json
import subprocess
from types import SimpleNamespace
import pytest
from pyrite64_mcp.server import create_server


def value(result):
    if isinstance(result, tuple): return result[1]
    if isinstance(result, dict): return result
    return json.loads(result[0].text)


@pytest.fixture
def game(tmp_path):
    emulator = tmp_path / 'Ares Emulator' / 'ares.exe'
    emulator.parent.mkdir()
    emulator.write_bytes(b'fake executable')
    editor = tmp_path / 'pyrite64.exe'
    editor.write_bytes(b'fake executable')
    (tmp_path / 'project.p64proj').write_text(json.dumps({'romName': 'my game', 'pathEmu': str(emulator)}))
    return tmp_path, editor, emulator


@pytest.mark.parametrize('operation', ['build_and_run', 'build_project'])
def test_successful_build_launches_ares(game, monkeypatch, operation):
    root, editor, emulator = game
    calls = []
    def build(args, **kwargs):
        (root / 'my game.z64').write_bytes(b'fresh N64 ROM')
        return subprocess.CompletedProcess(args, 0, 'build complete', '')
    def launch(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(pid=123, wait=lambda: 0)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', build)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.Popen', launch)
    args = {'run': True} if operation == 'build_project' else {}
    result = value(asyncio.run(create_server(root, str(editor)).call_tool(operation, args)))
    assert result['success'] and result['emulator_launched']
    command, options = calls[0]
    assert command == [str(emulator), '--system', 'Nintendo 64', '--no-file-prompt', str(root / 'my game.z64')]
    assert options['shell'] is False and options['cwd'] == emulator.parent
    assert options['stdout'] == options['stderr'] == subprocess.DEVNULL


@pytest.mark.parametrize('case', ['failed', 'missing', 'stale', 'empty'])
def test_bad_build_never_launches(game, monkeypatch, case):
    root, editor, _ = game
    if case in {'stale', 'empty'}:
        (root / 'my game.z64').write_bytes(b'old game' if case == 'stale' else b'')
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', lambda args, **kw: subprocess.CompletedProcess(args, 1 if case == 'failed' else 0, '', ''))
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.Popen', lambda *a, **kw: pytest.fail('Ares must not launch'))
    result = value(asyncio.run(create_server(root, str(editor)).call_tool('build_and_run', {})))
    assert result['emulator_launched'] is False
    assert result['success'] is (case != 'failed')
    if case != 'failed': assert result['launch_error']


def test_missing_ares_releases_lock(game, monkeypatch):
    root, editor, _ = game
    server = create_server(root, str(editor), ares_executable=str(root / 'missing-ares.exe'))
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', lambda *a, **kw: pytest.fail('Unexpected build'))
    async def exercise():
        for _ in range(2):
            with pytest.raises(Exception, match='Ares was not found'):
                await server.call_tool('build_and_run', {})
    asyncio.run(exercise())


def test_launch_failure_preserves_build_result(game, monkeypatch):
    root, editor, _ = game
    def build(args, **kwargs):
        (root / 'my game.z64').write_bytes(b'ROM')
        return subprocess.CompletedProcess(args, 0, 'Built successfully', '')
    def launch(*args, **kwargs): raise OSError('Could not start emulator')
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', build)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.Popen', launch)
    result = value(asyncio.run(create_server(root, str(editor)).call_tool('build_and_run', {})))
    assert result['success'] and not result['emulator_launched']
    assert result['launch_error'] == 'Could not start emulator'


def test_live_save_precedes_config_read(game, monkeypatch):
    root, editor, emulator = game
    actions = []
    async def bridge_call(self, action, args=None, **kwargs):
        actions.append(action)
        (root / 'project.p64proj').write_text(json.dumps({'romName': 'saved name', 'pathEmu': str(emulator)}))
        return {'saved': True}
    def build(args, **kwargs):
        assert actions == ['save_project']
        (root / 'saved name.z64').write_bytes(b'fresh ROM')
        return subprocess.CompletedProcess(args, 0, '', '')
    monkeypatch.setattr('pyrite64_mcp.server.Bridge.call', bridge_call)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', build)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.Popen', lambda *a, **kw: SimpleNamespace(pid=123, wait=lambda: 0))
    result = value(asyncio.run(create_server(root, str(editor), mode='live').call_tool('build_and_run', {})))
    assert result['rom_path'] == str(root / 'saved name.z64')


def test_clean_cannot_run_game(game):
    root, editor, _ = game
    with pytest.raises(Exception, match='requires command=build'):
        asyncio.run(create_server(root, str(editor)).call_tool('build_project', {'command': 'clean', 'run': True}))


@pytest.mark.parametrize('selection', ['path', 'server', 'tool'])
def test_ares_selection_precedence(game, monkeypatch, selection):
    root, editor, emulator = game
    (root / 'project.p64proj').write_text(json.dumps({'romName': 'my game', 'pathEmu': 'gopher64'}))
    calls = []
    def build(args, **kwargs):
        (root / 'my game.z64').write_bytes(b'ROM')
        return subprocess.CompletedProcess(args, 0, '', '')
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.run', build)
    monkeypatch.setattr('pyrite64_mcp.server.shutil.which', lambda name: str(emulator) if selection == 'path' and name == 'ares' else None)
    monkeypatch.setattr('pyrite64_mcp.server.subprocess.Popen', lambda args, **kw: (calls.append(args) or SimpleNamespace(pid=1, wait=lambda: 0)))
    configured = str(emulator) if selection == 'server' else str(root / 'bad.exe') if selection == 'tool' else None
    arguments = {'ares_path': str(emulator)} if selection == 'tool' else {}
    result = value(asyncio.run(create_server(root, str(editor), ares_executable=configured).call_tool('build_and_run', arguments)))
    assert result['emulator_launched']
    assert calls[0][0] == str(emulator)

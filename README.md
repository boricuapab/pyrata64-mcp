# Pyrite64 MCP

Control Pyrite64 projects from **Codex or Claude** through Model Context Protocol.
The default server is **`http://127.0.0.1:8974/mcp`** (Streamable HTTP).
Stdio is also supported for clients such as Claude Desktop.

Inspired by [Blender's MCP server](https://www.blender.org/lab/mcp-server/),
this integration combines grounded documentation retrieval with project inspection,
scene editing, asset workflows and real build commands. Pyrite64 is a C++ editor,
so live control uses an optional main-thread C++ bridge rather than a Python add-on.

## Included knowledge

The server ships with an offline, searchable snapshot of:

| Reference | Indexed files/pages |
| --- | ---: |
| Published [Pyrite64 documentation](https://hailtododongo.github.io/pyrite64/), including generated runtime API pages | 197 |
| Documentation source and generator files from [pyrite64mia](https://github.com/boricuapab/pyrite64mia) | 64 |
| First-party editor/runtime source, examples, tests, scripts, graphs, shaders and build settings | 721 |

Source commit: `1794ffad169f453bfc992021c18d7e6756609a70`.
Snapshot date: October 12, 2026. No failed documentation-page fetches.
The machine-readable inventory is `src/pyrite64_mcp/data/manifest.json`.
Search results retain source URLs and commit references; full files can be read
in pages with line numbers. Neither an API key nor internet access is needed at
runtime. The assistant retrieves knowledge as needed; this does not train a model
or guarantee it will automatically remember every page. Third-party dependencies,
images, videos and binaries are excluded from the index.

## Install

### Easy Windows launcher

Double-click **`run-win-pyrite64mcp.cmd`**, or run:

```powershell
.\run-win-pyrite64mcp.ps1
```

Choose live editor control, offline project editing, or documentation-only mode.
Paste or drag your game folder (or `.p64proj` file) and editor executable into
the prompts. The launcher remembers your locations in the Git-ignored
`.pyrite64-mcp/launcher.json`. It works from any working directory, defaults to
port **8974**, checks Python/dependencies and reports an occupied port clearly.
Live mode can launch the rebuilt editor with the shared bridge directory.

For first-time dependency setup, explicitly run:

```powershell
.\run-win-pyrite64mcp.ps1 -Setup
```

This requires Python 3.11+ and installs the MCP SDK into the repository's `.venv`.
It does not download Python or rebuild the editor. The double-click wrapper uses
an execution-policy override for its own process only, without changing system
policy. For unattended documentation search, use `-Mode docs -NonInteractive`.
Use `-Port` to change the endpoint or `-ValidateOnly` to check setup without
starting a server. Delete `.pyrite64-mcp/launcher.json` to reset remembered choices.

### Manual installation

Requires Python 3.11 or newer. For builds, install Pyrite64 and its N64 toolchain.
From the repository directory on Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

On Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

The Windows launchers also work directly from `src` after installing the MCP SDK:

```powershell
.\.venv\Scripts\python.exe -m pip install "mcp>=1.26,<2"
```

## Start on port 8974

**Offline mode:** close the project in the editor before editing its files.
Pass the game project directory, containing exactly one `.p64proj` file.

```powershell
.\scripts\start-server.ps1 `
  -ProjectDirectory "C:\path\to\game" `
  -Executable "C:\path\to\pyrite64mia\pyrite64.exe"
```

The server remains running in that terminal. Use Ctrl+C to stop it. To search
documentation alone, omit `-ProjectDirectory` and `-Executable`.

Installed-package equivalent (all platforms):

```sh
pyrite64-mcp --project /path/to/game --executable /path/to/pyrite64 --port 8974
```

The HTTP server binds to loopback and uses SDK Host/Origin protections. It is a
local, trusted-client integration, with no remote authentication service. Keep it
on your own machine. Stdio has no listening port; `--port 8974` applies to HTTP.

## Connect Codex

Start the HTTP server first, then register it:

```sh
codex mcp add pyrite64 --url http://127.0.0.1:8974/mcp
```

Or add the contents of `examples/codex-http.toml` to your Codex configuration:

```toml
[mcp_servers.pyrite64]
url = "http://127.0.0.1:8974/mcp"
tool_timeout_sec = 1800
```

Restart/reload the client if necessary, and inspect the server with `/mcp`.
See [official Codex MCP instructions](https://developers.openai.com/codex/mcp).

## Connect Claude

For **Claude Code**:

```sh
claude mcp add --transport http pyrite64 http://127.0.0.1:8974/mcp
```

Use `/mcp` to check the connection. A project configuration example is in
`examples/claude-code-http.json`; place the appropriate `mcpServers` object in
your `.mcp.json` if you prefer file configuration.
See [official Claude Code MCP instructions](https://code.claude.com/docs/en/mcp).

For **Claude Desktop**, use `examples/claude-desktop-stdio.json` in the client's
MCP configuration. Replace the example repository/game paths with your absolute
paths. The client starts the stdio server itself. Choose `--mode offline` if you
are using the standard editor without the bridge. The example uses live mode.
Do not run the server manually in stdio mode and expect the client to attach to it.

## Live editor bridge

### Start inside Pyrite64

In the updated [pyrite64mia editor](https://github.com/boricuapab/pyrite64mia),
open a game and choose **MCP > Start Server**. On first use, browse to this
companion repository, then click **Save and Start**. Its `.venv` must already be
set up. The editor uses the open game automatically and defaults to port 8974.
Repository/port choices stay in local editor preferences.

The menu provides start/stop controls, status, a server log, and copyable client
commands. Server processes stop on project close/change or editor exit. Each
editor instance uses its own bridge directory. If the port is occupied, inspect
the log and stop the old launcher or choose a different port in Server Settings.

### Launch externally

Install the bridge in your own Pyrite64 source checkout. Installation changes
only `src/main.cpp` and adds `src/pyrite64_mcp_bridge.h`; the original main file
is preserved as `src/main.cpp.mcp-backup`:

```powershell
.\.venv\Scripts\python.exe .\scripts\install_bridge.py C:\path\to\pyrite64mia
```

Rebuild using your existing Pyrite64 build environment. For a configured Windows
CMake/Ninja tree, adapt these placeholder paths to your installation:

```powershell
$env:PATH = 'C:\path\to\ucrt64\bin;' + $env:PATH
cmake --build C:\path\to\pyrite64mia\build --target pyrite64 --parallel 4
```

See [Pyrite64's build documentation](https://hailtododongo.github.io/pyrite64/docs/dev/build.html)
for other installations. The bridge header requires no new linked library or
separate CMake target. The installer is idempotent and stops on unexpected source
layouts. To update an installed bridge, copy the newer header and rebuild. To
uninstall, remove the include and `Pyrite64MCP::poll()` line from `main.cpp`, then
remove the header and rebuild. Preserve subsequent source edits rather than
blindly restoring the old backup.

Launch the rebuilt editor with your game, then start the MCP in another terminal:

```powershell
.\scripts\start-editor.ps1 `
  -Executable "C:\path\to\pyrite64mia\pyrite64.exe" `
  -ProjectFile "C:\path\to\game\project.p64proj"

.\scripts\start-server.ps1 `
  -Mode live `
  -ProjectDirectory "C:\path\to\game" `
  -Executable "C:\path\to\pyrite64mia\pyrite64.exe"
```

Both launchers use the repository's `.pyrite64-mcp/bridge` directory by default.
If launching the editor yourself, set `PYRITE64_MCP_BRIDGE_DIR` to the same absolute
directory passed to the server's `--bridge-dir`. Existing editor processes must
be restarted to inherit the variable and load the rebuilt executable.

The bridge polls an atomic JSON mailbox on the editor's main thread. This avoids
threading editor mutations through a network callback. It is disabled unless its
environment variable is set. Requests expire, carry unique IDs, and verify the
project path. Scene edits use compare-and-swap against editor memory, preserve
unknown JSON fields, and record native undo changes. The bridge rejects requests
while the editor is building/running. A timeout can occur after an edit executes;
inspect the scene before retrying.

Live edits stay in memory until `save_project`. Build calls save first.
The requested scene must already be open; changing scenes automatically could
save unsaved work, so this integration asks you to select scenes in the editor.

## Tools

| Area | Tools |
| --- | --- |
| Status | `get_status` |
| Manual and source | `search_knowledge`, `read_knowledge`, `list_knowledge`, `list_components` |
| Project and scenes | `get_project`, `list_scenes`, `get_scene`, `create_scene`, `set_scene_config` |
| Objects and hierarchy | `list_objects`, `get_object`, `create_object`, `update_object`, `delete_object`, `reparent_object` |
| Components | `add_component`, `update_component`, `remove_component` |
| Assets and scripts | `list_project_files`, `read_project_file`, `write_project_file`, `import_asset` |
| Native editor | `select_object`, `save_project`, `reload_assets` |
| N64 toolchain | `build_project` (`build`/`clean`, optional `run=true`), `build_and_run` (build and launch Ares) |

Resources expose the knowledge manifest and native component registry; the
`pyrite64_workflow` prompt guides grounded game-development tasks.

Native components supported by the reference fork are Code, Model (Static),
Light, Camera, Collision-Mesh, Collider, Audio (2D), Constraint, Culling, Node
Graph, Model (Animated), Rigid-Body, Character-Body and Surface. In live mode,
`add_component` invokes their actual native initializers, avoiding guessed defaults.
`update_component` recursively merges documented native component data.

Object transforms use meters and `[x,y,z,w]` quaternions. Component/asset UUIDs
are uint64 values; pass component UUID tool arguments as decimal strings to
avoid client-side floating-point precision loss. Object UUIDs are uint32.

**Offline editing:** existing-file writes require the hash returned by a fresh
read, save original bytes in `.pyrite64-mcp/backups/`, and replace files atomically.
New files can be written without a hash. Paths are confined to the configured
project, with traversal, alternate streams, protected paths and escaping links
rejected. Assets import without overwriting existing files. Close the project in
the editor while using offline writes, to avoid its unsaved state overwriting them.

**Current boundaries:** creating scenes, importing assets and writing arbitrary
project text require offline mode. Native component initialization, selection,
asset reload and explicit editor save require live mode. Prefab overrides should
be authored in the editor; direct object/component edits reject prefab instances.
This version does not provide viewport screenshots, arbitrary code execution
inside the editor, or typed tools for every
material/graph/prefab UI operation. Source-grounded `.conf`, `.p64graph`, `.prefab`
and C++ file tools cover those offline workflows. An actual ROM build requires a
working Pyrite64 toolchain; an MCP connection alone does not establish that.

## Example requests

### Build and launch Ares

Ask the assistant **"Build and run my game in Ares."** It calls `build_and_run`:
live mode saves the current project, builds using the Pyrite64 CLI, checks for a
fresh nonempty `<romName>.z64` in the game folder, then launches Ares with the
Nintendo 64 system selected. `build_project(run=true)` provides the same option.
The tool returns promptly after launching the GUI; it does not wait for the game
to close. Build failure, missing/stale ROMs and emulator launch failures are
reported separately. A successful process launch does not verify gameplay.

Set the project's **emulator path** to the Ares executable in Pyrite64 settings.
The tool also supports Ares on `PATH`, a server-level `--ares` option or
`PYRITE64_ARES` environment variable, and an `ares_path` override for an individual
`build_and_run` call. The Windows launchers accept `-AresExecutable` as well.
No installation paths are hardcoded. Restart the MCP server after updating it
so the client discovers the new tool.

When using the editor-managed server on Windows, Ares belongs to that server's
process tree and closes when you stop the server or close the editor/project.
The CLI arguments follow the [official Ares command-line documentation](https://github.com/ares-emulator/ares/blob/master/README.md).

### Other tasks

- "Search the docs for character bodies, then explain move-and-slide with API references."
- "Inspect scene 1 and list the cameras, lights and collision components."
- "In the open scene, create a Player object and add a native Character-Body component."
- "Read the HDR and bloom documentation before changing the render pipeline."
- "Read my script, make this change with a backup, and build the project."

## Refresh the knowledge snapshot

Clone or update the reference fork yourself, then run:

```powershell
.\.venv\Scripts\python.exe scripts/sync_knowledge.py C:\path\to\pyrite64mia
```

This explicitly crawls all reachable HTML documentation pages under the official
site, including API reference pages, and rebuilds the source index. Source is
pinned to the checkout's current HEAD; commit your relevant source changes before
syncing so the provenance URL matches them. Failed fetches are reported in the
manifest and cause a nonzero exit. `--no-website` is available for an intentional
source-only snapshot. `--reuse-website` reindexes source while retaining the
previously fetched website pages and their original snapshot date. No background
refresh takes place during MCP sessions.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q -rs
```

Tests exercise real MCP initialization, tools, resources and prompts over stdio
and Streamable HTTP on 8974, scene/object round trips, backups, Windows newline
hashes, invalid scene rejection, path confinement, knowledge coverage, bridge
timeouts and installer behavior. A symlink test skips when Windows disallows
creating symbolic links. CI runs on Windows and Linux with Python 3.11 and 3.12.

For the compiled native bridge, `scripts/smoke_live.py` checks connectivity,
rotation preservation, stale-revision rejection, all 14 native component
initializers, selection and saving. Run it only against an isolated test project:
it creates objects/components temporarily and saves the project.

## Troubleshooting

- **Bridge timeout:** restart the rebuilt editor with the bridge variable set;
  check that both processes use the same directory and the same game project.
- **Different scene/project:** open the requested scene/project in Pyrite64.
- **Port already in use:** stop the existing server or change `--port` and the client URL together.
- **Build fails:** inspect the returned CLI output and verify the toolchain in Pyrite64.
  The MCP runs the executable from its installation directory so it can find `data/` and `n64/`.
- **File changed:** read it again and use the new SHA-256; the server deliberately rejects stale writes.
- **Claude Desktop cannot find the module:** replace all example paths and verify `PYTHONPATH` points to this repository's `src` directory.

MIT licensed; see `LICENSE` and `NOTICE.md` for upstream documentation/source attribution.

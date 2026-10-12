# Validation — October 12, 2026

- Python 3.12 on Windows; MCP Python SDK 1.30.0.
- Automated tests: **19 passed, 1 skipped**. The skipped symlink test could
  not create a symbolic link under the Windows test account.
- Real MCP client initialization, tool calls, prompts and resources passed
  over **stdio** and **Streamable HTTP on 127.0.0.1:8974**.
- Offline checks cover hierarchy edits/cycle rejection, component data merges,
  exact uint64 UUIDs, backups, stale-file rejection, Windows CRLF hashes,
  invalid scene rejection, project-path confinement and knowledge retrieval.
- CLI adapter tests verify build/clean arguments, installation working
  directory, failure output, timeout handling and build-lock release. They
  mock the toolchain process; they do not establish that a ROM builds.
- The C++ bridge was installed in a local Pyrite64 source checkout and compiled
  successfully with its existing CMake/Ninja UCRT64 toolchain.
- A real rebuilt editor opened an isolated temporary project and passed live
  connectivity, scene transactions, quaternion preservation, stale-revision
  rejection, **all 14 native component initializers**, object selection,
  project saving and restoration. Existing game projects were not used.
- Knowledge snapshot: **197 published pages, 64 documentation/generator
  files, 721 first-party source/reference files**, with zero website fetch failures.
- Python source compilation and Git whitespace checks passed.

CI is configured for Linux and Windows with Python 3.11 and 3.12. Its outcome
is separate from these local checks. No game ROM, emulator or N64 hardware
test is claimed. The local run used the source-tree launcher; a clean wheel
installation was not tested in this environment.

## In-app MCP controls

The editor MCP dropdown was rebuilt successfully. An isolated native harness
linked against the editor's build objects exercised the same controller used
by the menu, with a real Streamable HTTP MCP client. Startup, readiness, live
bridge connection, scene retrieval, stop/restart, project-close cleanup and
occupied-port failure reporting passed. No game projects were used for these
checks. The controller uses a separate bridge directory for each editor process.

The companion regression run passed 18 tests; the Windows symlink check and the
fixed-port HTTP test skipped. Port 8974 was occupied by an existing server, so
the native integration test used a free local port instead. The existing server
was not stopped. Validation compilation used the MSYS2 compiler's runtime DLL
directory on `PATH` after correcting the test command's environment.

## Build and run

The build-and-run tests use controlled build/emulator process substitutes to
verify exact shell-free Ares arguments, paths containing spaces, live-save
ordering, build failure handling, missing/empty/stale ROM rejection, launch
failure reporting and lock cleanup. They do not claim a real ROM build or an
actual Ares gameplay session. The MCP tools are exposed over the same standard
transports; restarting an existing server is required to load the new tool.

## Live game source updates

41 regression tests passed; the fixed-port HTTP and Windows symlink checks
skipped for the previously stated environment limitations. Tests cover repeated
live writes, byte-preserving backups, stale revisions, disconnected editors,
unsafe file classes and edits blocked during an MCP build.

A real MCP client connected to the native controller's isolated open project,
created and edited a C++ source file over the same connection, and verified that
the scene JSON was unchanged afterward. No editor rebuild or scene reload is
required for this companion-server feature. Source changes affect the compiled
game after its next build; they do not patch an already running ROM.

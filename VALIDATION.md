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

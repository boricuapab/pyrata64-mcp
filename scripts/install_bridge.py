"""Install the header bridge into a local Pyrite64 source tree, without building it."""
import argparse
import shutil
from pathlib import Path


def install(root):
    root = Path(root).resolve()
    main = root / "src" / "main.cpp"
    text = main.read_text(encoding="utf-8")
    anchor = "      auto frameStart = SDL_GetTicksNS();"
    include = '#include "pyrite64_mcp_bridge.h"'
    call = "      Pyrite64MCP::poll();"
    if include in text and call in text:
        return "Already installed"
    if include in text or call in text or text.count(anchor) != 1:
        raise ValueError("Source layout changed or installation is partial; inspect src/main.cpp manually")
    header = Path(__file__).resolve().parents[1] / "bridge" / "pyrite64_mcp_bridge.h"
    if (root / "src" / header.name).exists():
        raise ValueError("Bridge header already exists; inspect before overwriting")
    backup = main.with_suffix(".cpp.mcp-backup")
    if backup.exists():
        raise ValueError("Existing bridge installation backup; inspect before proceeding")
    shutil.copy2(main, backup)
    shutil.copy2(header, root / "src" / header.name)
    main.write_text(include + "\n" + text.replace(anchor, anchor + "\n" + call), encoding="utf-8")
    return f"Installed in {root}; rebuild Pyrite64 per its build documentation. Backup: {backup}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_tree")
    print(install(parser.parse_args().source_tree))

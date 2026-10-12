"""Rebuild offline knowledge from a pinned source checkout and the official docs website."""
import argparse
import gzip
import json
import re
import subprocess
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://hailtododongo.github.io/pyrite64/"
REPO = "https://github.com/boricuapab/pyrite64mia"
OUTPUT = Path(__file__).resolve().parents[1] / "src" / "pyrite64_mcp" / "data"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.parts = []
        self.title = []
        self.in_title = False
        self.depth = 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "title":
            self.in_title = True
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"main", "article"} or attrs.get("role") == "main":
            self.depth += 1
        if self.depth and tag in {"p", "div", "li", "pre", "h1", "h2", "h3", "br", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip-1)
        if tag in {"main", "article"}:
            self.depth = max(0, self.depth-1)
        if self.depth and tag in {"p", "li", "pre", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.depth and not self.skip:
            self.parts.append(data)


def sync(source, website=True, reuse_website=False):
    source = Path(source).resolve()
    # Trust only this explicitly selected checkout for the read-only revision lookup.
    commit = subprocess.check_output(["git", "-c", f"safe.directory={source.as_posix()}", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    entries = []
    for directory in ("docs", "src", "n64/engine", "n64/examples", "n64/tests", "data/scripts", "data/nodes", "data/build", "data/shader", "data/themes", "scripts", "tools"):
        for path in sorted((source / directory).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".rst", ".h", ".hpp", ".cpp", ".c", ".js", ".p64graph", ".p64proj", ".conf", ".json", ".py", ".sh", ".bat", ".ps1", ".ts", ".cmake", ".glsl", ".vert", ".frag", ".comp"}:
                continue
            if path.stat().st_size > 2*1024*1024:
                continue
            relative = path.relative_to(source).as_posix()
            kind = "docs" if relative.startswith("docs/") else "source"
            entries.append({"id": relative, "title": relative, "kind": kind,
                            "url": f"{REPO}/blob/{commit}/{relative}", "text": path.read_text(encoding="utf-8", errors="replace")})
    for name in ("README.md", "Readme.md", "CMakeLists.txt", "CMakePresets.json"):
        path = source / name
        if path.exists() and not any(e["id"].lower() == name.lower() for e in entries):
            entries.append({"id": name, "title": name, "kind": "source", "url": f"{REPO}/blob/{commit}/{name}", "text": path.read_text(encoding="utf-8")})
    failures = []
    visited = set()
    website_snapshot_utc = None
    if reuse_website:
        with gzip.open(OUTPUT / "knowledge.json.gz", "rt", encoding="utf-8") as stream:
            previous = json.load(stream)
        entries.extend(e for e in previous["entries"] if e["kind"] == "website")
        failures = previous["metadata"]["website_failures"]
        website_snapshot_utc = previous["metadata"].get("website_snapshot_utc") or previous["metadata"]["snapshot_utc"]
    elif website:
        queue = deque([BASE])
        while queue:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            try:
                request = Request(url, headers={"User-Agent": "Pyrite64-MCP-docs-snapshot/0.1"})
                with urlopen(request, timeout=30) as response:
                    if not response.url.startswith(BASE):
                        raise ValueError("Unexpected redirect outside docs site")
                    html = response.read(8*1024*1024).decode("utf-8")
                page = Page()
                page.feed(html)
                content = re.sub(r"\n\s*\n+", "\n\n", "".join(page.parts)).strip()
                if content:
                    entries.append({"id": "website/" + url.removeprefix(BASE), "title": "".join(page.title),
                                    "kind": "website", "url": url, "text": content})
                for href in page.links:
                    linked = urldefrag(urljoin(url, href))[0]
                    parsed = urlparse(linked)
                    if linked.startswith(BASE) and not parsed.query and (parsed.path.endswith(".html") or parsed.path.endswith("/")) and not parsed.path.endswith(("search.html", "genindex.html")) and linked not in visited:
                        queue.append(linked)
            except Exception as exc:
                failures.append({"url": url, "error": str(exc)})
            if len(visited) > 2000:
                raise RuntimeError("Unexpected docs crawl size; inspect links")
    counts = {kind: sum(e["kind"] == kind for e in entries) for kind in ("docs", "source", "website")}
    metadata = {"source_repository": REPO, "source_commit": commit, "docs_site": BASE,
                "snapshot_utc": datetime.now(timezone.utc).isoformat(), "counts": counts,
                "website_attempted": website, "website_failures": failures,
                "website_snapshot_utc": website_snapshot_utc or (datetime.now(timezone.utc).isoformat() if website else None),
                "scope": "All repo Markdown/RST docs, first-party editor/runtime source, examples, tests, built-in nodes/scripts, build configuration, tool scripts, shaders and themes; all reachable documentation HTML pages. Excludes vendored third-party APIs, media and binaries."}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT / "knowledge.json.gz", "wt", encoding="utf-8") as stream:
        json.dump({"metadata": metadata, "entries": entries}, stream, ensure_ascii=False)
    (OUTPUT / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    scene = json.loads((source / "n64/examples/empty/data/scenes/1/scene.json").read_text())
    # Preserve the reference scene's root and native render/physics defaults.
    scene["graph"]["children"] = []
    scene["graph"]["components"] = []
    (OUTPUT / "scene-template.json").write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    table = (source / "src/project/component/components.h").read_text(encoding="utf-8")
    matches = re.findall(r'\.id = (\d+),.*?\.name = "([^"]+)".*?\.docSlug = "([^"]+)"', table, re.S)
    (OUTPUT / "components.json").write_text(json.dumps({"source_commit": commit, "components": [{"id": int(i), "name": name, "documentation": BASE + "docs" + slug + ".html"} for i, name, slug in matches]}, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "UPSTREAM-LICENSE.txt").write_text((source / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    if failures:
        raise SystemExit("Snapshot saved with incomplete website crawl; inspect manifest and rerun")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_checkout")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--no-website", action="store_true")
    group.add_argument("--reuse-website", action="store_true", help="Reindex source while retaining the already fetched website snapshot")
    args = parser.parse_args()
    sync(args.source_checkout, not args.no_website, args.reuse_website)

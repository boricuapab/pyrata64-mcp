"""Offline documentation/source retrieval with provenance and bounded responses."""
import gzip
import json
import math
import re
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"


class Knowledge:
    def __init__(self):
        with gzip.open(DATA / "knowledge.json.gz", "rt", encoding="utf-8") as stream:
            self.snapshot = json.load(stream)
        self.entries = {entry["id"]: entry for entry in self.snapshot["entries"]}
        self.tokens = {key: Counter(self.tokenize(e["title"] + " " + e["text"]))
                       for key, e in self.entries.items()}
        self.df = Counter(word for words in self.tokens.values() for word in words)

    @staticmethod
    def tokenize(text):
        return re.findall(r"[a-z0-9_]+", text.lower())

    def search(self, query, kind="all", limit=8):
        if kind not in {"all", "docs", "source", "website"}:
            raise ValueError("kind must be all, docs, source or website")
        words = set(self.tokenize(query))
        if not words:
            return []
        ranked = []
        for key, entry in self.entries.items():
            if kind != "all" and entry["kind"] != kind:
                continue
            counts = self.tokens[key]
            length = sum(counts.values())
            score = sum(math.log(1 + len(self.entries) / (1 + self.df[word])) *
                        counts[word] / (counts[word] + 1.2 * (0.25 + 0.75 * length / 500))
                        for word in words if counts[word])
            score += sum(2 for word in words if word in self.tokenize(entry["title"]))
            if score:
                lines = entry["text"].splitlines()
                best = max(range(len(lines)), key=lambda i: sum(w in lines[i].lower() for w in words)) if lines else 0
                ranked.append((score, {"id": key, "title": entry["title"], "kind": entry["kind"],
                                       "url": entry["url"], "line": best + 1,
                                       "excerpt": "\n".join(lines[max(0, best-3):best+12])[:2200]}))
        return [item for _, item in sorted(ranked, key=lambda x: x[0], reverse=True)[:max(1, min(limit, 30))]]

    def read(self, entry_id, start_line=1, line_count=120):
        entry = self.entries[entry_id]
        lines = entry["text"].splitlines()
        start = max(1, start_line)
        end = min(len(lines), start - 1 + max(1, min(line_count, 250)))
        return {"id": entry_id, "url": entry["url"], "total_lines": len(lines),
                "text": "\n".join(f"{i+1}: {lines[i]}" for i in range(start-1, end))}

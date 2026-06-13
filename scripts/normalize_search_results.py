#!/usr/bin/env python3
"""Normalize search results from Hermes/native tools or provider JSON into raw-search JSONL.

This script intentionally does not call a search provider. It accepts records
from any source and standardizes common fields used by the lead workflow.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def pick(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def normalize(row: dict, default_query: str = "", default_lane: str = "organic") -> dict:
    query = pick(row, "query", "source_query") or default_query
    lane = pick(row, "source_lane", "lane") or default_lane
    link = pick(row, "link", "url", "href", "website")
    title = pick(row, "title", "name")
    snippet = pick(row, "snippet", "description", "summary", "content")
    mode = pick(row, "mode") or ("maps" if row.get("maps_data") else "search")
    return {
        "mode": mode,
        "query": query,
        "source_query": query,
        "source_lane": lane,
        "title": title,
        "link": link,
        "snippet": snippet,
        "position": row.get("position", row.get("rank", 0)),
        "source": pick(row, "source", "provider") or "hermes_native",
        "maps_data": row.get("maps_data", {}),
        "raw": row,
    }


def iter_input(path: str):
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return
    if stripped.startswith("["):
        data = json.loads(stripped)
        for row in data:
            if isinstance(row, dict):
                yield row
        return
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if isinstance(data.get("results"), list):
            for row in data["results"]:
                if isinstance(row, dict):
                    yield row
        else:
            yield data
        return
    for line in text.splitlines():
        if line.strip():
            yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON, JSON array, JSONL, or '-' for stdin.")
    parser.add_argument("--query", default="")
    parser.add_argument("--lane", default="organic")
    args = parser.parse_args()

    for row in iter_input(args.input):
        print(json.dumps(normalize(row, args.query, args.lane), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

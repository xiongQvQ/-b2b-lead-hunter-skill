#!/usr/bin/env python3
"""Read a URL through Jina Reader and emit markdown or JSON."""

from __future__ import annotations

import argparse
import json
import os
import time

import requests


def jina_url(url: str) -> str:
    return f"https://r.jina.ai/{url}"


def read_jina(url: str, timeout: int = 60, retries: int = 3, delay: float = 1.0) -> str:
    target = jina_url(url)
    headers = {"Accept": "text/markdown"}
    api_key = os.environ.get("JINA_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    for attempt in range(retries):
        try:
            resp = requests.get(target, headers=headers, timeout=timeout)
            if resp.status_code == 429:
                wait = delay * (2 ** attempt)
                print(f"Jina 429 rate-limited, retry {attempt+1}/{retries} in {wait:.0f}s...", file=__import__("sys").stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.ConnectionError:
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))
                continue
            raise
    # Final attempt already made above; if we get here it was a 429 loop
    resp.raise_for_status()
    return resp.text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-chars", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3, help="Max retries for 429/connection errors.")
    parser.add_argument("--delay", type=float, default=1.0, help="Base delay (s) for exponential backoff.")
    parser.add_argument("--output", "-o", default="", help="Write UTF-8 content to a file instead of stdout.")
    args = parser.parse_args()

    content = read_jina(args.url, timeout=args.timeout, retries=args.retries, delay=args.delay)
    if args.max_chars > 0:
        content = content[: args.max_chars]

    if args.json:
        output = json.dumps({"url": args.url, "content": content, "content_length": len(content)}, ensure_ascii=False, indent=2) + "\n"
    else:
        output = content

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(output)
    else:
        print(output, end="" if output.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

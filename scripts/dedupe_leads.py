#!/usr/bin/env python3
"""Deduplicate JSONL leads by website domain, email, or company/address key."""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import urlparse


def domain(url: str) -> str:
    netloc = urlparse(url or "").netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.split(":", 1)[0]


def emails_key(item: dict) -> str:
    emails = []
    for obj in item.get("emails", []) or []:
        if isinstance(obj, dict) and obj.get("email"):
            emails.append(str(obj["email"]).lower())
        elif isinstance(obj, str):
            emails.append(obj.lower())
    return "|".join(sorted(set(emails)))


def company_key(item: dict) -> str:
    name = re.sub(r"\W+", "", str(item.get("company_name", "")).lower())
    address = re.sub(r"\W+", "", str(item.get("address", "")).lower())
    return f"{name}|{address}" if name else ""


def identity(item: dict) -> str:
    d = domain(str(item.get("website", "")))
    if d:
        return f"domain:{d}"
    e = emails_key(item)
    if e:
        return f"email:{e}"
    c = company_key(item)
    if c:
        return f"company:{c}"
    return ""


def merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for key, value in b.items():
        if value in ("", None, [], {}):
            continue
        if key not in out or out[key] in ("", None, [], {}):
            out[key] = value
        elif isinstance(out[key], list) and isinstance(value, list):
            seen = {json.dumps(x, sort_keys=True, ensure_ascii=False) for x in out[key]}
            for x in value:
                marker = json.dumps(x, sort_keys=True, ensure_ascii=False)
                if marker not in seen:
                    out[key].append(x)
                    seen.add(marker)
        elif isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = {**value, **out[key]}
    for key in ("source_queries", "source_urls", "evidence", "emails", "phones", "decision_makers"):
        if key in out and isinstance(out[key], list):
            out[key] = unique_list(out[key])
    return out


def unique_list(values: list) -> list:
    seen: set[str] = set()
    out = []
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            out.append(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl")
    args = parser.parse_args()

    seen: dict[str, dict] = {}
    passthrough = []
    with open(args.jsonl, "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            item = json.loads(line)
            key = identity(item)
            if not key:
                passthrough.append(item)
            elif key in seen:
                seen[key] = merge(seen[key], item)
            else:
                seen[key] = item

    for item in list(seen.values()) + passthrough:
        print(json.dumps(item, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Search Google Maps through Serper and emit normalized place JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

import requests

SERPER_MAPS_URL = "https://google.serper.dev/maps"


def fetch_maps(payload: dict[str, Any], api_key: str, timeout: int = 40, retries: int = 3, delay: float = 1.0) -> dict[str, Any]:
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    for attempt in range(retries):
        resp = requests.post(SERPER_MAPS_URL, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            wait = delay * (2 ** attempt)
            print(f"Serper 429 rate-limited, retry {attempt+1}/{retries} in {wait:.0f}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return resp.json()


def normalize_maps(data: dict[str, Any], query: str, lane: str = "maps") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    places = data.get("places") or data.get("data", {}).get("places", []) or []
    for item in places:
        rows.append(
            {
                "mode": "maps",
                "query": query,
                "source_query": query,
                "source_lane": lane,
                "title": item.get("title", ""),
                "link": item.get("website", ""),
                "snippet": " | ".join(
                    str(v)
                    for v in [
                        item.get("type", ""),
                        item.get("address", ""),
                        item.get("phoneNumber", ""),
                    ]
                    if v
                ),
                "position": item.get("position", 0),
                "source": "serper_maps",
                "maps_data": {
                    "address": item.get("address", ""),
                    "phone_number": item.get("phoneNumber", ""),
                    "rating": item.get("rating", 0),
                    "rating_count": item.get("ratingCount", 0),
                    "type": item.get("type", ""),
                    "types": item.get("types", []),
                    "latitude": item.get("latitude", 0),
                    "longitude": item.get("longitude", 0),
                    "cid": item.get("cid", ""),
                    "place_id": item.get("placeId", ""),
                },
                "raw": item,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", "-q", required=True)
    parser.add_argument("--num", type=int, default=10)
    parser.add_argument("--gl", default="")
    parser.add_argument("--hl", default="")
    parser.add_argument("--ll", default="", help="Maps latitude/longitude hint accepted by Serper.")
    parser.add_argument("--lane", default="maps")
    parser.add_argument("--retries", type=int, default=3, help="Max retries for 429/connection errors.")
    parser.add_argument("--delay", type=float, default=1.0, help="Base delay (s) for exponential backoff.")
    parser.add_argument("--jsonl", action="store_true", help="Emit one normalized result per line.")
    args = parser.parse_args()

    api_key = os.environ.get("SERPER_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("SERPER_API_KEY is required for Serper Maps.")

    payload: dict[str, Any] = {"q": args.query, "num": args.num}
    if args.gl:
        payload["gl"] = args.gl
    if args.hl:
        payload["hl"] = args.hl
    if args.ll:
        payload["ll"] = args.ll

    data = fetch_maps(payload, api_key, retries=args.retries, delay=args.delay)
    rows = normalize_maps(data, args.query, args.lane)

    if args.jsonl:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(json.dumps({"query": args.query, "mode": "maps", "count": len(rows), "results": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

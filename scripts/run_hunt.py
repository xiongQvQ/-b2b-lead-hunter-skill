#!/usr/bin/env python3
"""Lightweight B2B lead hunt orchestrator.

This script is glue only. It creates run files, calls deterministic helpers,
and writes JSONL/CSV artifacts. Hermes still owns organic/web search strategy,
fit scoring, ambiguous decisions, and run-report writing. Only Maps queries are
optionally executed through the Serper Maps adapter.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def normalized_domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]


def candidate_key(row: dict) -> str:
    link = str(row.get("link", "") or "").strip().lower()
    if link:
        domain = normalized_domain(link)
        if domain:
            return f"domain:{domain}"
        return f"url:{link}"
    maps = row.get("maps_data") or {}
    place_id = str(maps.get("place_id") or maps.get("cid") or "").strip().lower()
    if place_id:
        return f"place:{place_id}"
    title = str(row.get("title", "")).strip().lower()
    address = str(maps.get("address", "")).strip().lower()
    return f"name:{title}|{address}" if title or address else ""


def load_queries(path: Path) -> list[dict]:
    """Load queries from JSONL or CSV.

    JSONL rows can contain: query, mode, gl, hl, num, lane.
    CSV needs at least a query column.
    """
    queries: list[dict] = []
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("query"):
                    queries.append(dict(row))
        return queries

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if line.lstrip().startswith("{"):
                queries.append(json.loads(line))
            else:
                queries.append({"query": line.strip()})
    return queries


def run_json(command: list[str]) -> dict:
    proc = subprocess.run(command, check=True, text=True, capture_output=True)
    return json.loads(proc.stdout)


def run_text(command: list[str]) -> str:
    proc = subprocess.run(command, check=True, text=True, encoding="utf-8", errors="replace", capture_output=True)
    return proc.stdout


def append_candidates_from_rows(rows: list[dict], seen: set[str]) -> list[dict]:
    candidates: list[dict] = []
    for row in rows:
        key = candidate_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "company_name": row.get("title", ""),
                "website": row.get("link", ""),
                "source_queries": [row.get("source_query") or row.get("query", "")],
                "source_urls": [row.get("link", "")] if row.get("link") else [],
                "source_lane": row.get("source_lane", ""),
                "search_snippet": row.get("snippet", ""),
                "maps_data": row.get("maps_data", {}),
                "raw": row,
            }
        )
    return candidates


def build_candidates_from_raw(out_dir: Path) -> None:
    raw_path = out_dir / "raw-search.jsonl"
    candidates_path = out_dir / "candidates.jsonl"
    seen: set[str] = set()
    candidates = append_candidates_from_rows(read_jsonl(raw_path), seen)
    append_jsonl(candidates_path, candidates)
    write_json(
        out_dir / "pilot-stats.json",
        {
            "raw_result_count": len(read_jsonl(raw_path)),
            "candidate_count": len(candidates),
            "search_execution": "hermes_native_or_preprovided_raw",
        },
    )


def pilot(brief_path: Path, queries_path: Path, out_dir: Path, *, maps_only: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    brief = read_json(brief_path)
    write_json(out_dir / "brief.json", brief)

    queries = load_queries(queries_path)
    write_json(out_dir / "pilot-config.json", {"queries": queries})

    raw_path = out_dir / "raw-search.jsonl"
    candidates_path = out_dir / "candidates.jsonl"
    seen: set[str] = set()
    candidates: list[dict] = []

    for query in queries:
        q = str(query.get("query", "")).strip()
        if not q:
            continue
        mode = str(query.get("mode", "search") or "search")
        if mode != "maps":
            if maps_only:
                continue
            raise SystemExit(
                "run_hunt.py no longer executes organic search. "
                "Use Hermes native search, normalize results to raw-search.jsonl, then run --build-candidates/--enrich."
            )
        num = str(query.get("num", brief.get("results_per_query", 10)))
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "serper_maps.py"),
            "--query",
            q,
            "--num",
            num,
            "--lane",
            str(query.get("lane", "maps")),
        ]
        for arg in ("gl", "hl"):
            if query.get(arg):
                cmd.extend([f"--{arg}", str(query[arg])])
        data = run_json(cmd)
        rows = data.get("results", [])
        append_jsonl(raw_path, rows)
        candidates.extend(append_candidates_from_rows(rows, seen))
        time.sleep(1)

    append_jsonl(candidates_path, candidates)
    write_json(
        out_dir / "pilot-stats.json",
        {
            "query_count": len(queries),
            "raw_result_count": sum(1 for _ in raw_path.open("r", encoding="utf-8")) if raw_path.exists() else 0,
            "candidate_count": len(candidates),
            "search_execution": "serper_maps_only",
        },
    )


def likely_subpages(base_url: str) -> list[str]:
    if not base_url:
        return []
    base = base_url.rstrip("/")
    return [
        base,
        f"{base}/contact",
        f"{base}/kontakt",
        f"{base}/impressum",
    ]


def enrich(out_dir: Path, max_companies: int = 30) -> None:
    candidates = read_jsonl(out_dir / "candidates.jsonl")[:max_companies]
    enriched_path = out_dir / "enriched.jsonl"

    # Skip companies already enriched (checkpoint/resume)
    done_domains: set[str] = set()
    if enriched_path.exists():
        for row in read_jsonl(enriched_path):
            d = normalized_domain(str(row.get("website", "")))
            if d:
                done_domains.add(d)

    for cand in candidates:
        website = str(cand.get("website", "") or "")
        if normalized_domain(website) in done_domains:
            continue
        pages = likely_subpages(website)[:4]
        page_records = []
        all_emails = []
        all_phones = []
        social: dict = {}
        contact_pages = []
        company_domain = normalized_domain(website)

        for page in pages:
            try:
                content = run_text([sys.executable, str(SCRIPT_DIR / "read_jina.py"), page, "--max-chars", "8000"])
            except subprocess.CalledProcessError as exc:
                page_records.append({"url": page, "error": exc.stderr.strip() or str(exc)})
                continue
            time.sleep(0.5)
            contact = run_json(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "extract_contacts.py"),
                    "-",
                    "--source-url",
                    page,
                    "--company-domain",
                    company_domain,
                ],
                input_text=content,
            )
            all_emails.extend(contact.get("emails", []))
            all_phones.extend(contact.get("phones", []))
            social.update(contact.get("social", {}))
            contact_pages.extend(contact.get("contact_pages", []))
            page_records.append({"url": page, "content_length": len(content)})

        row = {
            **cand,
            "emails": unique_dicts(all_emails),
            "phones": sorted(set(all_phones)),
            "social": social,
            "contact_pages": sorted(set(contact_pages)),
            "pages_read": page_records,
            "rule_contactability_score": rule_contactability(all_emails, all_phones, social, contact_pages),
            "needs_review": True,
        }
        append_jsonl(enriched_path, [row])


def run_json(command: list[str], input_text: str | None = None) -> dict:
    proc = subprocess.run(command, input=input_text, check=True, text=True, encoding="utf-8", errors="replace", capture_output=True)
    return json.loads(proc.stdout)


def unique_dicts(values: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            out.append(value)
    return out


def rule_contactability(emails: list, phones: list, social: dict, contact_pages: list) -> float:
    score = 0.0
    if emails:
        score += 0.55
        if any(isinstance(e, dict) and e.get("type") == "person" for e in emails):
            score += 0.15
    if phones:
        score += 0.15
    if contact_pages:
        score += 0.1
    if social:
        score += 0.1
    return round(min(score, 1.0), 2)


def export(out_dir: Path, source: str = "leads.jsonl") -> None:
    source_path = out_dir / source
    strict_path = out_dir / "leads.csv"
    all_path = out_dir / "leads_all.csv"
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "export_leads.py"), str(source_path), "--view", "strict", "--output", str(strict_path)],
        check=True,
    )
    subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "export_leads.py"), str(source_path), "--view", "all", "--output", str(all_path)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", nargs="?", help="brief.json for --pilot")
    parser.add_argument("--out", required=True)
    parser.add_argument("--queries", help="JSONL/CSV query list for --pilot")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--build-candidates", action="store_true", help="Build candidates from existing raw-search.jsonl.")
    parser.add_argument("--enrich", action="store_true")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--export-source", default="leads.jsonl")
    parser.add_argument("--max-companies", type=int, default=30)
    args = parser.parse_args()

    out_dir = Path(args.out)
    if args.pilot:
        if not args.brief or not args.queries:
            raise SystemExit("--pilot requires brief and --queries")
        pilot(Path(args.brief), Path(args.queries), out_dir)
    if args.build_candidates:
        build_candidates_from_raw(out_dir)
    if args.enrich:
        enrich(out_dir, max_companies=args.max_companies)
    if args.export:
        export(out_dir, source=args.export_source)
    if not any([args.pilot, args.build_candidates, args.enrich, args.export]):
        raise SystemExit("Choose at least one: --pilot, --build-candidates, --enrich, --export")
    return 0


if __name__ == "__main__":
    sys.exit(main())

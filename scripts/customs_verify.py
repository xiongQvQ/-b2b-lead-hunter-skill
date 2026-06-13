#!/usr/bin/env python3
"""Structure public customs/trade evidence from search result JSON/JSONL.

This helper does not call paid customs databases. Feed it normalized search
results from Panjiva, ImportGenius, ImportYeti, UK trade sources, or web search
snippets; it extracts conservative import signals for lead scoring.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from contracts import ContractError, validate_customs_verification

PLATFORMS = {
    "panjiva.com": "panjiva",
    "importgenius.com": "importgenius",
    "importyeti.com": "importyeti",
    "uktradeinfo.com": "uktradeinfo",
}
ASIA_TERMS = {
    "china",
    "hong kong",
    "taiwan",
    "vietnam",
    "thailand",
    "malaysia",
    "indonesia",
    "india",
    "korea",
    "japan",
    "shenzhen",
    "ningbo",
    "qingdao",
    "xiamen",
    "shanghai",
    "guangzhou",
}


def read_rows(path: str) -> list[dict]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return [json.loads(line) for line in lines]
    if stripped.startswith("["):
        return [row for row in json.loads(stripped) if isinstance(row, dict)]
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if isinstance(data.get("results"), list):
            return [row for row in data["results"] if isinstance(row, dict)]
        return [data]
    return [json.loads(line) for line in lines]


def text_of(row: dict) -> str:
    parts = []
    for key in ("title", "snippet", "description", "summary", "content"):
        if row.get(key):
            parts.append(str(row[key]))
    raw = row.get("raw")
    if isinstance(raw, dict):
        for key in ("title", "snippet", "description", "content"):
            if raw.get(key):
                parts.append(str(raw[key]))
    return " ".join(parts)


def link_of(row: dict) -> str:
    for key in ("link", "url", "href"):
        if row.get(key):
            return str(row[key])
    raw = row.get("raw")
    if isinstance(raw, dict):
        for key in ("link", "url", "href"):
            if raw.get(key):
                return str(raw[key])
    return ""


def platform_for(url: str) -> str:
    low = url.lower()
    for domain, name in PLATFORMS.items():
        if domain in low:
            return name
    return "web"


def extract_count(text: str) -> int | None:
    patterns = [
        r"(\d{1,3}(?:,\d{3})*|\d+)\s+(?:shipments?|imports?|records?)",
        r"(?:shipments?|imports?|records?)\D{0,20}(\d{1,3}(?:,\d{3})*|\d+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def extract_latest_date(text: str) -> str:
    m = re.search(r"\b(20\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01]))\b", text)
    if m:
        return m.group(1).replace("/", "-").replace(".", "-")
    m = re.search(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2})\b", text, flags=re.I)
    return m.group(1) if m else ""


def extract_hs_codes(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in re.finditer(r"\bHS(?:\s+code)?[:\s#-]*(\d{2,10})\b", text, flags=re.I):
        code = m.group(1)
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out[:5]


def extract_suppliers(text: str) -> list[str]:
    out: list[str] = []
    for pattern in (
        r"supplier[s]?\s*[:\-]\s*([^.;|]{3,80})",
        r"from\s+([A-Z][A-Za-z0-9&.,'\-\s]{3,80})\s+(?:Ltd|Limited|Co\.?|Company|Inc|GmbH)",
    ):
        for m in re.finditer(pattern, text, flags=re.I):
            value = re.sub(r"\s+", " ", m.group(1)).strip(" ,;:-")
            if value and value not in out:
                out.append(value)
    return out[:5]


def confidence(record: dict) -> float:
    score = 0.0
    if record["platform"] in {"panjiva", "importgenius", "importyeti", "uktradeinfo"}:
        score += 0.35
    if record["shipment_count"] is not None:
        score += 0.25
    if record["asia_origin_terms"]:
        score += 0.2
    if record["hs_codes"]:
        score += 0.1
    if record["latest_shipment_date"]:
        score += 0.1
    return round(min(score, 1.0), 2)


def analyze(company: str, rows: list[dict]) -> dict:
    evidence = []
    for row in rows:
        url = link_of(row)
        text = text_of(row)
        low = text.lower()
        if company and company.lower() not in low:
            if not any(part.lower() in low for part in company.split() if len(part) >= 4):
                continue
        platform = platform_for(url)
        if platform == "web" and not any(term in low for term in ("shipment", "customs", "import", "supplier", "hs code")):
            continue
        asia_terms = sorted(term for term in ASIA_TERMS if term in low)
        record = {
            "source_url": url,
            "platform": platform,
            "title": str(row.get("title") or ""),
            "shipment_count": extract_count(text),
            "latest_shipment_date": extract_latest_date(text),
            "hs_codes": extract_hs_codes(text),
            "suppliers": extract_suppliers(text),
            "asia_origin_terms": asia_terms,
            "snippet": re.sub(r"\s+", " ", text).strip()[:500],
        }
        record["confidence"] = confidence(record)
        evidence.append(record)

    evidence.sort(key=lambda item: item["confidence"], reverse=True)
    confirmed_asia = any(item["asia_origin_terms"] and item["confidence"] >= 0.55 for item in evidence)
    confirmed_import = any(item["confidence"] >= 0.45 for item in evidence)
    return {
        "company_name": company,
        "confirmed_import_activity": confirmed_import,
        "confirmed_asia_import_signal": confirmed_asia,
        "fit_score_adjustment": 2 if confirmed_asia else 1 if confirmed_import else 0,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Search result JSON/JSONL, or '-' for stdin.")
    parser.add_argument("--company", required=True)
    parser.add_argument("--output", "-o", default="-")
    args = parser.parse_args()

    result = analyze(args.company, read_rows(args.input))
    validate_customs_verification(result)
    out = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output == "-":
        print(out, end="")
    else:
        Path(args.output).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

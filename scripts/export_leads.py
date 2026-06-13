#!/usr/bin/env python3
"""Export JSONL leads to strict or full CSV views."""

from __future__ import annotations

import argparse
import csv
import json
import sys


FIELDS = [
    "company_name",
    "website",
    "country",
    "business_type",
    "industry",
    "priority",
    "review_required",
    "fit_score",
    "contactability_score",
    "evidence_score",
    "emails",
    "phones",
    "decision_makers",
    "social",
    "source_urls",
    "source_quality",
    "official_site_found",
    "uncertainty_reason",
    "missing_evidence",
    "fit_reason_zh",
    "contact_source",
    "notes",
]


def has_contact_channel(item: dict) -> bool:
    emails = item.get("emails") or []
    phones = item.get("phones") or []
    social = item.get("social") or {}
    contact_pages = item.get("contact_pages") or []
    decision_makers = item.get("decision_makers") or []

    if any(isinstance(e, dict) and e.get("email") for e in emails):
        return True
    if any(isinstance(p, dict) and p.get("phone") for p in phones):
        return True
    if any(isinstance(p, str) and p.strip() for p in phones):
        return True
    if any(str(v).strip() for v in social.values()) if isinstance(social, dict) else bool(social):
        return True
    if any(str(v).strip() for v in contact_pages):
        return True
    for dm in decision_makers:
        if isinstance(dm, dict) and any(dm.get(k) for k in ("email", "linkedin", "source_url")):
            return True
    return False


def has_buyer_evidence(item: dict) -> bool:
    if item.get("evidence"):
        return True
    for key in ("description", "fit_reason_zh", "notes"):
        if str(item.get(key) or "").strip():
            return True
    return False


def strict_eligible(item: dict) -> tuple[bool, str]:
    source_urls = [u for u in item.get("source_urls", []) or [] if str(u).strip()]
    if not item.get("official_site_found"):
        return False, "official website not confirmed"
    if not source_urls:
        return False, "missing source URLs"
    if str(item.get("source_quality") or "").lower() in {"directory", "snippet"}:
        return False, "directory/snippet-only source quality"
    if not has_buyer_evidence(item):
        return False, "missing buyer-role evidence"
    if not has_contact_channel(item):
        return False, "missing usable contact channel"
    return True, ""


def compact(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl")
    parser.add_argument("--output", "-o", default="-")
    parser.add_argument(
        "--view",
        choices=["strict", "all"],
        default="strict",
        help="strict exports high/medium only; all exports high/medium/low.",
    )
    parser.add_argument(
        "--no-strict-gates",
        action="store_true",
        help="Legacy behavior: strict view filters priority only, without contact/evidence gates.",
    )
    args = parser.parse_args()

    out_fh = sys.stdout if args.output == "-" else open(args.output, "w", encoding="utf-8", newline="")
    try:
        writer = csv.DictWriter(out_fh, fieldnames=FIELDS)
        writer.writeheader()
        with open(args.jsonl, "r", encoding="utf-8") as in_fh:
            for line in in_fh:
                if not line.strip():
                    continue
                item = json.loads(line)
                priority = str(item.get("priority", "")).lower()
                if priority == "reject":
                    continue
                if args.view == "strict" and priority not in {"high", "medium"}:
                    continue
                if args.view == "strict" and not args.no_strict_gates:
                    ok, reason = strict_eligible(item)
                    if not ok:
                        print(
                            f"skip strict: {item.get('company_name', '')}: {reason}",
                            file=sys.stderr,
                        )
                        continue
                if args.view == "all" and priority not in {"high", "medium", "low"}:
                    continue
                writer.writerow({field: compact(item.get(field, "")) for field in FIELDS})
    finally:
        if out_fh is not sys.stdout:
            out_fh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

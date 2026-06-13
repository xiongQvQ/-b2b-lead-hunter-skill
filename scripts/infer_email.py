#!/usr/bin/env python3
"""
Email Format Inference — detect email naming patterns and infer addresses.

Two modes:
1. Detect: Given one or more known emails, detect the format pattern.
2. Infer: Given a name + domain (+ optional format), generate likely emails.

Usage:
    # Detect format from known emails
    python3 infer_email.py --detect john.doe@rutronik.com jane.smith@rutronik.com
    python3 infer_email.py --detect --input emails.jsonl

    # Infer emails for a person
    python3 infer_email.py --name "David Axford" --domain rutronik.com
    python3 infer_email.py --name "Georg Schukat" --domain schukat.com --format first.last

    # Batch infer from JSON input (e.g., LinkedIn search output)
    python3 infer_email.py --batch linkedin_results.json --domain rutronik.com

Common formats detected:
    first.last   → john.doe@company.com
    first_last   → john_doe@company.com
    first        → john@company.com
    flast        → jdoe@company.com
    f.last       → j.doe@company.com
    firstl       → johnd@company.com
    last         → doe@company.com
    first-last   → john-doe@company.com
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional


# Characters to strip/replace for clean email generation
CLEAN_RE = re.compile(r"[^a-z]", re.IGNORECASE)

# German special chars
UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
})

# Polish special chars
POLISH_MAP = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
})


def clean_name(name: str) -> tuple[str, str]:
    """Clean a full name and return (first, last) lowercase ASCII-safe."""
    name = name.translate(UMLAUT_MAP).translate(POLISH_MAP)
    name = CLEAN_RE.sub(" ", name)
    parts = [p.lower() for p in name.split() if p]

    if len(parts) < 2:
        return ("", "")

    first = parts[0]
    last = parts[-1]
    return (first, last)


def generate_formats(first: str, last: str, domain: str) -> dict[str, str]:
    """Generate all common email format variants."""
    fi = first[0] if first else ""
    li = last[0] if last else ""

    return {
        "first.last": f"{first}.{last}@{domain}",
        "first_last": f"{first}_{last}@{domain}",
        "first": f"{first}@{domain}",
        "flast": f"{fi}{last}@{domain}",
        "firstl": f"{first}{li}@{domain}",
        "f.last": f"{fi}.{last}@{domain}",
        "last": f"{last}@{domain}",
        "first-last": f"{first}-{last}@{domain}",
    }


def detect_format(emails: list[str]) -> Optional[str]:
    """Detect the email naming pattern from a list of known emails."""
    if not emails:
        return None

    # For each email, extract the local part and analyze its structure
    formats_seen = Counter()

    for email in emails:
        if "@" not in email:
            continue
        local = email.split("@")[0].lower()

        # Skip generic prefixes — they don't follow person naming patterns
        generic_prefixes = {"info", "sales", "vertrieb", "contact", "support", "office",
                           "hello", "admin", "export", "import", "enquiry", "inquiry",
                           "service", "team", "marketing", "einkauf", "post", "mail"}
        if local in generic_prefixes:
            continue

        # Count dots and underscores
        dots = local.count(".")
        underscores = local.count("_")
        hyphens = local.count("-")

        if underscores > 0:
            formats_seen["first_last"] += 1
        elif hyphens > 0:
            formats_seen["first-last"] += 1
        elif dots >= 2:
            # Could be f.m.last — but treat as first.last for now
            formats_seen["first.last"] += 1
        elif dots == 1:
            formats_seen["first.last"] += 1
        else:
            # No separators — could be flast, first, last
            if len(local) <= 2:
                formats_seen["first"] += 1
            else:
                formats_seen["flast"] += 1

    # Return the most common format
    if formats_seen:
        return formats_seen.most_common(1)[0][0]
    return None


def detect_batch(emails_data: list[dict]) -> Optional[str]:
    """Detect format from a list of {email, name} dicts (for higher accuracy)."""
    emails = [e.get("email", "") for e in emails_data if e.get("email")]
    return detect_format(emails)


def infer_single(
    name: str,
    domain: str,
    format_hint: Optional[str] = None,
) -> list[str]:
    """Infer emails for a single person."""
    first, last = clean_name(name)
    if not first or not last:
        return []

    all_formats = generate_formats(first, last, domain)

    if format_hint and format_hint in all_formats:
        return [all_formats[format_hint]]

    # Return top candidates in order of likelihood
    priority = ["first.last", "first_last", "flast", "first", "f.last"]
    return [all_formats[k] for k in priority if k in all_formats]


def infer_batch(
    people: list[dict],
    domain: str,
    format_hint: Optional[str] = None,
) -> list[dict]:
    """Batch infer emails for multiple people."""
    results = []
    for p in people:
        name = p.get("name", "")
        if not name:
            continue

        emails = infer_single(name, domain, format_hint)
        entry = {
            "name": name,
            "domain": domain,
            "inferred_emails": emails,
        }
        # Preserve original fields
        for k in ("title", "linkedin_url", "source"):
            if k in p:
                entry[k] = p[k]
        results.append(entry)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", help="Mode: detect or infer")

    # Detect mode
    detect_parser = sub.add_parser("detect", help="Detect email format from known emails")
    detect_parser.add_argument("emails", nargs="*", help="Known email addresses")
    detect_parser.add_argument("--input", "-i", help="JSON file with emails or {email, name} objects")

    # Infer mode
    infer_parser = sub.add_parser("infer", help="Infer email for a person")
    infer_parser.add_argument("--name", required=True, help="Full name")
    infer_parser.add_argument("--domain", required=True, help="Company domain")
    infer_parser.add_argument("--format", default=None, help="Known format hint")

    # Batch infer mode
    batch_parser = sub.add_parser("batch", help="Batch infer from JSON file")
    batch_parser.add_argument("input_file", help="JSON file with people [{name, title, ...}]")
    batch_parser.add_argument("--domain", required=True, help="Company domain")
    batch_parser.add_argument("--format", default=None, help="Known format hint")
    batch_parser.add_argument("--output", "-o", default=None, help="Output JSON file")

    args = parser.parse_args()

    if args.mode == "detect":
        emails = list(args.emails)
        if args.input:
            data = json.loads(Path(args.input).read_text())
            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    result = detect_batch(data)
                else:
                    emails.extend(str(x) for x in data)
            elif isinstance(data, str):
                emails.append(data)

        fmt = detect_format(emails)
        if fmt:
            print(json.dumps({"detected_format": fmt, "source_emails": emails}, indent=2))
        else:
            print(json.dumps({"detected_format": None, "error": "Could not detect format"}, indent=2))

    elif args.mode == "infer":
        emails = infer_single(args.name, args.domain, args.format)
        print(json.dumps({"name": args.name, "domain": args.domain, "inferred_emails": emails}, indent=2))

    elif args.mode == "batch":
        data = json.loads(Path(args.input_file).read_text())
        if isinstance(data, dict):
            people = data.get("decision_makers", data.get("people", [data]))
        else:
            people = data

        results = infer_batch(people, args.domain, args.format)

        if args.output:
            Path(args.output).write_text(json.dumps(results, ensure_ascii=False, indent=2))
            print(f"Saved {len(results)} inferences to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

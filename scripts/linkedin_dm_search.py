#!/usr/bin/env python3
"""
LinkedIn Decision-Maker Search via Tavily API.

Search for decision-makers (procurement, purchasing, sourcing, etc.) at a company
by querying LinkedIn profiles. Returns names, titles, profile URLs, and optionally
infers email addresses if an email format is known.

Usage:
    python3 linkedin_dm_search.py --company "Rutronik" --domain rutronik.com
    python3 linkedin_dm_search.py --company "Schukat" --domain schukat.com --region DE
    python3 linkedin_dm_search.py --company "TME" --domain tme.eu --email-format "first.last"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

TAVILY_URL = "https://api.tavily.com/search"
DEFAULT_API_KEY_ENV = "TAVILY_API_KEY"

# Role keywords to search for (by region)
ROLE_KEYWORDS = {
    "DE": ["Einkauf", "Einkäufer", "Vertrieb", "Geschäftsführer", "Produktmanager",
           "Purchasing Manager", "Procurement Manager", "Supply Chain", "Sourcing"],
    "PL": ["zakupy", "zaopatrzenie", "kierownik zakupów", "dyrektor", "product manager",
           "Purchasing Manager", "Procurement", "Supply Chain"],
    "AE": ["Purchasing Manager", "Procurement Manager", "Supply Chain", "Sourcing",
           "General Manager", "Import Manager", "Purchase", "Buyer"],
    "GLOBAL": ["Purchasing Manager", "Procurement Manager", "Supply Chain Manager",
               "Sourcing Manager", "Buyer", "Import Manager", "General Manager",
               "Product Manager", "Sales Director", "CEO", "Managing Director"],
}


def get_api_key() -> str:
    """Get Tavily API key from env var or local Hermes config."""
    key = os.environ.get(DEFAULT_API_KEY_ENV, "")
    if key:
        return key
    # Read from ~/.hermes/config if exists
    config_path = Path.home() / ".hermes" / "config"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            key = cfg.get("tavily_api_key", "")
        except Exception:
            pass
    return key


def tavily_search(api_key: str, query: str, max_results: int = 8) -> list[dict]:
    """Run a Tavily search and return results."""
    payload = json.dumps({
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }).encode("utf-8")

    req = urllib.request.Request(
        TAVILY_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode())
        return data.get("results", [])
    except Exception as e:
        print(f"  Tavily error: {e}", file=sys.stderr)
        return []


def extract_linkedin_profiles(results: list[dict], company_name: str) -> list[dict]:
    """Filter results to LinkedIn /in/ profiles matching the company."""
    profiles = []
    seen_urls = set()

    for r in results:
        url = r.get("url", "")
        if "linkedin.com/in/" not in url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = r.get("title", "")
        content = r.get("content", "")

        # Check company mention in title or snippet
        company_terms = company_name.lower().split()
        text = (title + " " + content).lower()
        if not any(term in text for term in company_terms):
            continue

        # Extract name from LinkedIn title
        # Format: "Name - Title | LinkedIn" or "Name – Title | LinkedIn"
        # Sometimes: "Name – Company Name | LinkedIn"
        name = title
        role = ""

        # Split on common separators
        for sep in [" - ", " – ", " | "]:
            if sep in name:
                parts = name.split(sep, 1)
                name = parts[0].strip()
                if not role:
                    role = parts[1].strip()
                break

        # Remove company name appended with " – " from name if it looks like one
        if " – " in name:
            name = name.split(" – ")[0].strip()

        # Clean role: remove "| LinkedIn" suffix
        role = role.split(" | ")[0].strip() if " | " in role else role

        profiles.append({
            "name": name,
            "title": role,
            "linkedin_url": url,
            "source": "tavily_linkedin",
        })

    return profiles


def search_decision_makers(
    api_key: str,
    company_name: str,
    domain: str,
    region: str = "GLOBAL",
    max_per_query: int = 6,
) -> list[dict]:
    """Search for decision-makers at a company on LinkedIn."""
    keywords = ROLE_KEYWORDS.get(region.upper(), ROLE_KEYWORDS["GLOBAL"])
    all_profiles = []
    seen_names = set()

    for kw in keywords[:6]:  # Limit to 6 role queries to avoid rate limits
        query = f'"{company_name}" {kw} site:linkedin.com/in'
        results = tavily_search(api_key, query, max_per_query)
        profiles = extract_linkedin_profiles(results, company_name)

        for p in profiles:
            if p["name"] not in seen_names:
                seen_names.add(p["name"])
                p["search_keyword"] = kw
                all_profiles.append(p)

        time.sleep(0.3)  # Rate limit

    return all_profiles


def infer_email(name: str, domain: str, format_hint: Optional[str] = None) -> list[str]:
    """Infer possible email addresses from a name and domain.

    If format_hint is provided (e.g., 'first.last', 'first_last', 'flast'),
    only return that format. Otherwise return all common formats.
    """
    # Split name into parts, handle middle names
    parts = name.strip().split()
    if len(parts) < 2:
        return []

    first = parts[0].lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    last = parts[-1].lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    first_initial = first[0]
    last_initial = last[0]

    # Clean names: remove non-alpha
    first = re.sub(r"[^a-z]", "", first)
    last = re.sub(r"[^a-z]", "", last)

    formats = {
        "first.last": f"{first}.{last}@{domain}",
        "first_last": f"{first}_{last}@{domain}",
        "first": f"{first}@{domain}",
        "flast": f"{first_initial}{last}@{domain}",
        "firstl": f"{first}{last_initial}@{domain}",
        "f.last": f"{first_initial}.{last}@{domain}",
        "last": f"{last}@{domain}",
        "first-last": f"{first}-{last}@{domain}",
    }

    if format_hint and format_hint in formats:
        return [formats[format_hint]]

    # Return all common formats
    return [formats[k] for k in ["first.last", "first_last", "flast", "first", "f.last"]]


def detect_email_format(known_emails: list[str]) -> Optional[str]:
    """Detect the email format from known email addresses and names."""
    if not known_emails:
        return None

    for email in known_emails:
        local = email.split("@")[0].lower()
        if "." in local and "_" not in local:
            return "first.last"
        if "_" in local:
            return "first_last"
        if len(local) >= 3:
            return "flast"  # Common default

    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True, help="Company name as it appears on LinkedIn")
    parser.add_argument("--domain", required=True, help="Company domain (for email inference)")
    parser.add_argument("--region", default="GLOBAL",
                        help="Region code: DE, PL, AE, GLOBAL (default: GLOBAL)")
    parser.add_argument("--email-format", default=None,
                        help="Known email format: first.last, first_last, flast, first, f.last, last")
    parser.add_argument("--max-results", type=int, default=6,
                        help="Max results per query (default: 6)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file (JSON). Default: stdout")
    parser.add_argument("--json", action="store_true", default=True,
                        help="Output as JSON (always on, kept for compat)")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        raise SystemExit(
            "Missing Tavily API key. Set TAVILY_API_KEY or ~/.hermes/config tavily_api_key; "
            "this script no longer ships with a fallback key."
        )

    print(f"  Searching LinkedIn for decision-makers at {args.company}...", file=sys.stderr)
    profiles = search_decision_makers(
        api_key, args.company, args.domain, args.region, args.max_results
    )

    # Try to detect email format from profile names + domain
    email_format = args.email_format
    if not email_format and profiles:
        # Search for known emails at this domain to detect format
        email_query = f'"@{args.domain}" email'
        email_results = tavily_search(api_key, email_query, 5)
        known_emails = set()
        for r in email_results:
            found = re.findall(rf"[\w.-]+@{re.escape(args.domain)}", r.get("content", ""))
            known_emails.update(found)
        email_format = detect_email_format(list(known_emails))

    # Add inferred emails
    for p in profiles:
        if email_format:
            p["inferred_emails"] = infer_email(p["name"], args.domain, email_format)
            p["email_format"] = email_format
        else:
            p["inferred_emails"] = infer_email(p["name"], args.domain)
            p["email_format"] = "unknown"

    output = {
        "company": args.company,
        "domain": args.domain,
        "region": args.region,
        "email_format_detected": email_format,
        "decision_makers": profiles,
        "total": len(profiles),
    }

    if args.output:
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"  Saved {len(profiles)} profiles to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())

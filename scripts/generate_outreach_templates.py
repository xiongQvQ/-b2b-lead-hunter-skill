#!/usr/bin/env python3
"""Generate regional outreach template clusters from leads and candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from contracts import ContractError, validate_outreach_candidate, validate_outreach_template, validate_sender_profile


ENGLISH_BUSINESS_COUNTRIES = {
    "australia",
    "canada",
    "hong kong",
    "ireland",
    "new zealand",
    "singapore",
    "united arab emirates",
    "uae",
    "united kingdom",
    "uk",
    "united states",
    "usa",
}
LOCAL_LANGUAGE_BY_COUNTRY = {
    "germany": "de",
    "austria": "de",
    "switzerland": "de",
    "france": "fr",
    "spain": "es",
    "italy": "it",
    "poland": "pl",
    "netherlands": "nl",
    "portugal": "pt",
    "brazil": "pt",
    "turkey": "tr",
    "japan": "ja",
    "south korea": "ko",
    "korea": "ko",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    out_fh = sys.stdout if path == "-" else open(path, "w", encoding="utf-8")
    try:
        for row in rows:
            out_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    finally:
        if out_fh is not sys.stdout:
            out_fh.close()


def load_template_library(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    rows: list[dict] = []
    if path.is_dir():
        children = sorted(path.glob("*.json")) + sorted(path.glob("*.jsonl"))
    else:
        children = [path]
    for child in children:
        if child.suffix == ".json":
            data = json.loads(child.read_text(encoding="utf-8"))
            rows.extend(data if isinstance(data, list) else [data])
        else:
            rows.extend(read_jsonl(child))
    templates: dict[str, dict] = {}
    for i, row in enumerate(rows, start=1):
        validate_outreach_template(row, f"template-library[{i}]")
        templates[str(row["cluster_key"])] = row
    return templates


def normalized_domain(url_or_domain: str) -> str:
    value = (url_or_domain or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    host = urlparse(value).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]


def normalized_company(name: str) -> str:
    return re.sub(r"\W+", "", (name or "").lower())


def short_hash(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def lead_id(lead: dict, domain: str) -> str:
    existing = str(lead.get("lead_id") or "").strip()
    if existing:
        return existing
    name = str(lead.get("company_name") or "")
    country = str(lead.get("country") or "")
    base = domain or normalized_company(name) or "lead"
    return f"{base}-{short_hash(name + '|' + country, 8)}"


def build_lead_index(leads: list[dict]) -> dict[str, dict]:
    out = {}
    for lead in leads:
        domain = normalized_domain(str(lead.get("website") or ""))
        out[lead_id(lead, domain)] = lead
    return out


def first(values: list[str] | None, fallback: str = "") -> str:
    for value in values or []:
        if str(value).strip():
            return str(value).strip()
    return fallback


def choose_language(country: str, forced_language: str | None = None) -> str:
    if forced_language:
        return forced_language
    country_lc = country.strip().lower()
    if country_lc in ENGLISH_BUSINESS_COUNTRIES:
        return "en"
    return LOCAL_LANGUAGE_BY_COUNTRY.get(country_lc, "en")


def buyer_role(lead: dict) -> str:
    roles = [str(v).strip().lower() for v in lead.get("business_type", []) or [] if str(v).strip()]
    for preferred in ("distributor", "importer", "wholesaler", "oem", "integrator", "installer", "end_user"):
        if preferred in roles:
            return preferred
    return first(roles, "buyer")


def cluster_key(country: str, language: str, role: str, product_angle: str) -> str:
    raw = "|".join([country.strip().lower(), language, role, product_angle.strip().lower()])
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def template_text(language: str) -> tuple[str, str, list[str]]:
    if language == "de":
        subject = "{product} fuer {country}"
        body = "\n\n".join(
            [
                "Guten Tag {greeting},",
                "ich habe {company_name} bei der Recherche nach passenden B2B-Partnern in {country} gefunden.",
                "{personalization_reason}",
                "Wir sind {sender_company} und liefern {product} fuer {application}.",
                "{cta}",
                "Mit freundlichen Gruessen\n{signature}",
                "{opt_out}",
            ]
        )
        notes = ["Formal German B2B tone.", "Keep claims factual and concise.", "Avoid exaggerated price or urgency language."]
        return subject, body, notes
    subject = "{product} cooperation for {country}"
    body = "\n\n".join(
        [
            "Hi {greeting},",
            "I found {company_name} while researching relevant B2B channel partners in {country}.",
            "{personalization_reason}",
            "We are {sender_company} and supply {product} for {application}.",
            "{cta}",
            "Best regards,\n{signature}",
            "{opt_out}",
        ]
    )
    notes = ["Neutral first-touch B2B tone.", "Ask for routing or relevance, not a hard sales call.", "Avoid unsupported certifications, stock, or pricing claims."]
    return subject, body, notes


def build_template(sender: dict, country: str, language: str, role: str, product_angle: str) -> dict:
    key = cluster_key(country, language, role, product_angle)
    subject, body, notes = template_text(language)
    row = {
        "template_id": "tpl-" + short_hash(key),
        "cluster_key": key,
        "country": country,
        "language": language,
        "buyer_role": role,
        "product_angle": product_angle,
        "subject_template": subject,
        "body_template": body,
        "required_variables": [
            "company_name",
            "country",
            "greeting",
            "sender_company",
            "product",
            "application",
            "personalization_reason",
            "cta",
            "signature",
            "opt_out",
        ],
        "tone_notes": notes,
        "claim_boundaries": list(sender.get("forbidden_claims") or []) + [
            "Do not claim prior relationship.",
            "Do not claim local stock, certification, or customer references unless explicitly in sender-profile.",
            "Do not use urgency or lowest-price claims.",
        ],
        "created_at": now_iso(),
    }
    validate_outreach_template(row)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leads", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--sender-profile", required=True, type=Path)
    parser.add_argument("--output", "-o", default="-")
    parser.add_argument("--language", help="Force one language for all clusters, e.g. en, de, fr.")
    parser.add_argument("--template-library", type=Path, help="Optional JSON/JSONL file or directory of human-maintained outreach templates.")
    args = parser.parse_args()

    sender = read_json(args.sender_profile)
    validate_sender_profile(sender, "sender-profile")
    leads = build_lead_index(read_jsonl(args.leads))
    candidates = read_jsonl(args.candidates)
    product_angle = first(sender.get("product_lines"), "B2B products")
    template_library = load_template_library(args.template_library)

    templates: dict[str, dict] = {}
    for i, candidate in enumerate(candidates, start=1):
        validate_outreach_candidate(candidate, f"outreach-candidates[{i}]")
        if not candidate.get("draft_allowed") or candidate.get("selected_channel") != "email":
            continue
        lead = leads.get(str(candidate.get("lead_id") or ""), {})
        country = str(candidate.get("country") or lead.get("country") or "global")
        language = choose_language(country, args.language)
        role = buyer_role(lead)
        key = cluster_key(country, language, role, product_angle)
        if key not in templates:
            templates[key] = template_library.get(key) or build_template(sender, country, language, role, product_angle)

    write_jsonl(args.output, list(templates.values()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

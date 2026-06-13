#!/usr/bin/env python3
"""Build decision-maker search plans and merge public employee contacts into leads.

The script is intentionally deterministic. Hermes still performs web search and
judges source quality. This helper turns lead records plus search result snippets
or manually collected people into structured decision-maker artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from contracts import ContractError, validate_decision_maker, validate_lead


ROLE_KEYWORDS = {
    "DE": ["Einkauf", "Einkaeufer", "Leiter Einkauf", "Einkaufsleiter", "Beschaffung", "Supply Chain", "Produktmanager", "Geschaeftsfuehrer"],
    "PL": ["zakupy", "kierownik zakupow", "zaopatrzenie", "dyrektor", "procurement", "supply chain"],
    "FR": ["achat", "acheteur", "responsable achats", "approvisionnement", "directeur", "chef produit"],
    "ES": ["compras", "responsable de compras", "aprovisionamiento", "director", "jefe de producto"],
    "IT": ["acquisti", "responsabile acquisti", "approvvigionamento", "direttore", "product manager"],
    "GLOBAL": ["purchasing manager", "procurement manager", "buyer", "sourcing manager", "supply chain", "product manager", "general manager", "managing director", "owner"],
}
COUNTRY_REGION = {
    "germany": "DE",
    "austria": "DE",
    "switzerland": "DE",
    "poland": "PL",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
}
GENERIC_LOCAL_PARTS = {"info", "sales", "contact", "support", "office", "hello", "admin", "export", "import", "service", "team", "marketing", "einkauf", "vertrieb"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path or not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    out = sys.stdout if path == "-" else open(path, "w", encoding="utf-8")
    try:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    finally:
        if out is not sys.stdout:
            out.close()


def normalized_domain(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    host = urlparse(text).netloc.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]


def short_hash(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def lead_id(lead: dict, domain: str) -> str:
    existing = str(lead.get("lead_id") or "").strip()
    if existing:
        return existing
    seed = str(lead.get("company_name") or "") + "|" + str(lead.get("country") or "")
    return f"{domain or 'lead'}-{short_hash(seed, 8)}"


def region_for(lead: dict) -> str:
    return COUNTRY_REGION.get(str(lead.get("country") or "").strip().lower(), "GLOBAL")


def role_category(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["einkauf", "purchas", "buyer", "acheteur", "compras", "acquisti", "zakup"]):
        return "purchasing"
    if any(x in t for x in ["procurement", "beschaffung", "approvisionnement", "aprovisionamiento", "zaopatrzenie"]):
        return "procurement"
    if any(x in t for x in ["sourcing", "supply chain"]):
        return "sourcing"
    if any(x in t for x in ["owner", "founder", "geschaeftsfuehrer", "geschäftsführer", "managing director", "general manager", "ceo", "director", "dyrektor"]):
        return "management"
    if any(x in t for x in ["product", "produkt", "chef produit"]):
        return "product"
    if any(x in t for x in ["technical", "engineer", "technik"]):
        return "technical"
    if any(x in t for x in ["sales", "vertrieb", "commercial"]):
        return "sales"
    return "unknown"


def seniority(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["ceo", "owner", "founder", "geschäftsführer", "geschaeftsfuehrer", "managing director", "general manager"]):
        return "executive"
    if any(x in t for x in ["director", "leiter", "head", "responsable", "dyrektor"]):
        return "director"
    if "manager" in t or "kierownik" in t:
        return "manager"
    return "unknown"


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else ""


def email_type(email: str, domain: str, explicit_type: str = "") -> str:
    if explicit_type in {"public", "inferred", "unknown", "none"}:
        return explicit_type
    if not email:
        return "none"
    local = email.split("@", 1)[0].lower()
    if local in GENERIC_LOCAL_PARTS:
        return "unknown"
    return "public" if email_domain(email) == domain else "unknown"


def query_plan_for_lead(lead: dict) -> list[dict]:
    domain = normalized_domain(str(lead.get("website") or ""))
    lid = lead_id(lead, domain)
    company = str(lead.get("company_name") or "")
    region = region_for(lead)
    keywords = ROLE_KEYWORDS.get(region, ROLE_KEYWORDS["GLOBAL"])[:8]
    rows = []
    for kw in keywords:
        rows.extend(
            [
                {"lead_id": lid, "company_name": company, "company_domain": domain, "stage": "role_profile", "source_hint": "linkedin", "query": f'"{company}" "{kw}" site:linkedin.com/in'},
                {"lead_id": lid, "company_name": company, "company_domain": domain, "stage": "role_profile", "source_hint": "xing", "query": f'"{company}" "{kw}" site:xing.com/profile'},
                {"lead_id": lid, "company_name": company, "company_domain": domain, "stage": "official_people", "source_hint": "official_site", "query": f'site:{domain} "{kw}" email OR contact OR Ansprechpartner'},
            ]
        )
    rows.extend(
        [
            {"lead_id": lid, "company_name": company, "company_domain": domain, "stage": "email_pattern", "source_hint": "web", "query": f'"@{domain}" "{company}" email'},
            {"lead_id": lid, "company_name": company, "company_domain": domain, "stage": "pdf_contacts", "source_hint": "pdf", "query": f'site:{domain} filetype:pdf contact OR catalog OR brochure OR team'},
            {"lead_id": lid, "company_name": company, "company_domain": domain, "stage": "supplier_pages", "source_hint": "directory", "query": f'"{company}" purchasing OR procurement OR buyer OR contact'},
        ]
    )
    return rows


def extract_people_from_result(row: dict, lead: dict) -> list[dict]:
    domain = normalized_domain(str(lead.get("website") or ""))
    lid = lead_id(lead, domain)
    company = str(lead.get("company_name") or "")
    title = str(row.get("title") or row.get("raw", {}).get("title") or "")
    snippet = str(row.get("snippet") or row.get("content") or row.get("raw", {}).get("snippet") or row.get("raw", {}).get("content") or "")
    url = str(row.get("link") or row.get("url") or row.get("raw", {}).get("url") or row.get("raw", {}).get("link") or "")
    query = str(row.get("query") or row.get("source_query") or "")
    text = " ".join([title, snippet])
    if not text.strip():
        return []
    source_type = "search_snippet"
    if "linkedin.com/in/" in url:
        source_type = "linkedin"
    elif "xing.com/profile" in url:
        source_type = "xing"
    elif domain and domain in normalized_domain(url):
        source_type = "official_site"
    elif url.lower().endswith(".pdf") or "filetype:pdf" in query:
        source_type = "pdf"
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    candidates: list[tuple[str, str]] = []
    if "linkedin.com/in/" in url or "xing.com/profile" in url:
        name = re.split(r"\s[-–|]\s", title, 1)[0].strip()
        role = title.replace(name, "").strip(" -–|")
        if name and len(name.split()) >= 2:
            candidates.append((name, role))
    for email in emails:
        local = email.split("@", 1)[0]
        parts = re.split(r"[._-]+", local)
        if len(parts) >= 2 and parts[0].lower() not in GENERIC_LOCAL_PARTS:
            name = " ".join(p.capitalize() for p in parts[:2])
            candidates.append((name, title or snippet[:80]))
    out = []
    seen = set()
    for name, role in candidates:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        person_email = ""
        for email in emails:
            local = email.split("@", 1)[0].lower()
            if all(part.lower() in local for part in name.split()[:2]):
                person_email = email.lower()
                break
        etype = email_type(person_email, domain)
        contactability = "email_public" if etype == "public" else "profile_only"
        record = {
            "decision_maker_id": "dm-" + short_hash("|".join([lid, name, url or query]), 12),
            "lead_id": lid,
            "company_name": company,
            "company_domain": domain,
            "name": name,
            "title": role or "",
            "role_category": role_category(role + " " + query + " " + snippet),
            "seniority": seniority(role + " " + snippet),
            "email": person_email,
            "email_type": etype,
            "email_confidence": 0.9 if etype == "public" else 0.0,
            "phone": "",
            "linkedin": url if "linkedin.com/in/" in url else "",
            "xing": url if "xing.com/profile" in url else "",
            "source_type": source_type,
            "source_url": url or "search_result",
            "source_query": query,
            "evidence_text": snippet[:500],
            "contactability": contactability,
            "send_allowed": etype == "public",
            "confidence": 0.75 if source_type in {"linkedin", "xing"} else 0.65,
            "created_at": now_iso(),
        }
        validate_decision_maker(record)
        out.append(record)
    return out


def load_manual_people(path: Path | None, leads_by_id: dict[str, dict]) -> list[dict]:
    rows = read_jsonl(path) if path else []
    out = []
    for row in rows:
        lead = leads_by_id.get(str(row.get("lead_id") or ""))
        if not lead:
            continue
        domain = normalized_domain(str(lead.get("website") or ""))
        lid = lead_id(lead, domain)
        email = str(row.get("email") or "").strip().lower()
        etype = email_type(email, domain, str(row.get("email_type") or ""))
        record = {
            "decision_maker_id": str(row.get("decision_maker_id") or "dm-" + short_hash("|".join([lid, str(row.get("name") or ""), email or str(row.get("source_url") or "")]), 12)),
            "lead_id": lid,
            "company_name": str(row.get("company_name") or lead.get("company_name") or ""),
            "company_domain": domain,
            "name": str(row.get("name") or ""),
            "title": str(row.get("title") or ""),
            "role_category": role_category(str(row.get("title") or "")),
            "seniority": seniority(str(row.get("title") or "")),
            "email": email,
            "email_type": etype,
            "email_confidence": float(row.get("email_confidence") or (0.9 if etype == "public" else 0.6 if etype == "inferred" else 0)),
            "phone": str(row.get("phone") or ""),
            "linkedin": str(row.get("linkedin") or ""),
            "xing": str(row.get("xing") or ""),
            "source_type": str(row.get("source_type") or "manual"),
            "source_url": str(row.get("source_url") or row.get("linkedin") or row.get("xing") or "manual"),
            "source_query": str(row.get("source_query") or ""),
            "evidence_text": str(row.get("evidence_text") or ""),
            "contactability": "email_public" if etype == "public" else "email_inferred" if etype == "inferred" else "profile_only",
            "send_allowed": etype == "public",
            "confidence": float(row.get("confidence") or 0.75),
            "created_at": str(row.get("created_at") or now_iso()),
        }
        validate_decision_maker(record)
        out.append(record)
    return out


def merge_into_leads(leads: list[dict], decision_makers: list[dict]) -> list[dict]:
    by_lead: dict[str, list[dict]] = {}
    for dm in decision_makers:
        by_lead.setdefault(str(dm["lead_id"]), []).append(dm)
    out = []
    for lead in leads:
        domain = normalized_domain(str(lead.get("website") or ""))
        lid = lead_id(lead, domain)
        merged = dict(lead)
        existing_dm = list(merged.get("decision_makers") or [])
        existing_keys = {(str(x.get("name") or "").lower(), str(x.get("email") or "").lower()) for x in existing_dm if isinstance(x, dict)}
        emails = list(merged.get("emails") or [])
        email_keys = {str(x.get("email") or "").lower() for x in emails if isinstance(x, dict)}
        for dm in by_lead.get(lid, []):
            key = (dm["name"].lower(), str(dm.get("email") or "").lower())
            if key not in existing_keys:
                existing_dm.append(dm)
                existing_keys.add(key)
            if dm.get("email") and dm["email"].lower() not in email_keys:
                emails.append(
                    {
                        "email": dm["email"].lower(),
                        "type": "person" if dm["email_type"] == "public" else "inferred",
                        "source_url": dm["source_url"],
                        "domain_relation": "same_domain" if email_domain(dm["email"]) == domain else "unknown",
                        "verification": "format_only",
                        "confidence": float(dm.get("email_confidence") or dm.get("confidence") or 0.6),
                    }
                )
                email_keys.add(dm["email"].lower())
        merged["decision_makers"] = existing_dm
        merged["emails"] = emails
        if any(dm.get("email_type") == "public" for dm in by_lead.get(lid, [])):
            merged["contactability_score"] = max(float(merged.get("contactability_score") or 0), 0.85)
        validate_lead(merged)
        out.append(merged)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leads", required=True, type=Path)
    parser.add_argument("--search-results", type=Path, help="Normalized search JSONL containing LinkedIn/Xing/person-contact snippets.")
    parser.add_argument("--manual-people", type=Path, help="JSONL manually collected people to normalize and merge.")
    parser.add_argument("--query-plan", help="Write decision-maker search query plan JSONL.")
    parser.add_argument("--decision-makers-output", help="Write decision-makers JSONL.")
    parser.add_argument("--enriched-leads-output", help="Write enriched leads JSONL.")
    args = parser.parse_args()

    leads = read_jsonl(args.leads)
    for i, lead in enumerate(leads, start=1):
        validate_lead(lead, f"leads[{i}]")
    leads_by_id = {lead_id(lead, normalized_domain(str(lead.get("website") or ""))): lead for lead in leads}

    if args.query_plan:
        plan = []
        for lead in leads:
            if str(lead.get("priority") or "").lower() in {"high", "medium"}:
                plan.extend(query_plan_for_lead(lead))
        write_jsonl(args.query_plan, plan)

    decision_makers: list[dict] = []
    if args.search_results:
        for result in read_jsonl(args.search_results):
            result_lid = str(result.get("lead_id") or "")
            possible = [leads_by_id[result_lid]] if result_lid in leads_by_id else list(leads_by_id.values())
            for lead in possible:
                company = str(lead.get("company_name") or "").lower()
                text = json.dumps(result, ensure_ascii=False).lower()
                if result_lid or company in text:
                    decision_makers.extend(extract_people_from_result(result, lead))
                    break
    decision_makers.extend(load_manual_people(args.manual_people, leads_by_id))

    unique = {}
    for dm in decision_makers:
        unique[(dm["lead_id"], dm["name"].lower(), str(dm.get("email") or "").lower(), str(dm.get("source_url") or ""))] = dm
    decision_makers = list(unique.values())
    for i, dm in enumerate(decision_makers, start=1):
        validate_decision_maker(dm, f"decision-makers[{i}]")

    if args.decision_makers_output:
        write_jsonl(args.decision_makers_output, decision_makers)
    if args.enriched_leads_output:
        write_jsonl(args.enriched_leads_output, merge_into_leads(leads, decision_makers))
    if not any([args.query_plan, args.decision_makers_output, args.enriched_leads_output]):
        write_jsonl("-", decision_makers)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

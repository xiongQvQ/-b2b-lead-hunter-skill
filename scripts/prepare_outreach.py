#!/usr/bin/env python3
"""Prepare outreach recipient candidates from qualified JSONL leads.

This script is deterministic glue. It selects the best first-touch channel
from already-qualified leads and records why a lead can draft, needs review,
or must be skipped. Hermes still owns email language, personalization, and
send/review/skip judgment for the final draft.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from contracts import ContractError, validate_outreach_candidate

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "yahoo.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
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


def normalized_domain(url_or_domain: str) -> str:
    value = (url_or_domain or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    host = urlparse(value).netloc.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]


def normalized_company(name: str) -> str:
    return re.sub(r"\W+", "", (name or "").lower())


def email_domain(email: str) -> str:
    if "@" not in (email or ""):
        return ""
    return email.rsplit("@", 1)[-1].lower().strip()


def short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lead_id(lead: dict, domain: str) -> str:
    existing = str(lead.get("lead_id") or "").strip()
    if existing:
        return existing
    name = str(lead.get("company_name") or "")
    country = str(lead.get("country") or "")
    base = domain or normalized_company(name) or "lead"
    return f"{base}-{short_hash(name + '|' + country)}"


def load_suppressions(path: Path | None) -> dict[str, set[str]]:
    out = {"email": set(), "domain": set(), "company": set()}
    if not path or not path.exists():
        return out
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            typ = str(row.get("type") or "").strip().lower()
            value = str(row.get("value") or "").strip().lower()
            if typ == "email" and value:
                out["email"].add(value)
            elif typ == "domain" and value:
                out["domain"].add(normalized_domain(value))
            elif typ == "company" and value:
                out["company"].add(normalized_company(value))
    return out


def load_sent_domains(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    sent: set[str] = set()
    for row in read_jsonl(path):
        event = str(row.get("event_type") or "")
        result = str(row.get("result") or "")
        domain = normalized_domain(str(row.get("company_domain") or ""))
        if event == "send_success" and result == "ok" and domain:
            sent.add(domain)
    return sent


def suppression_reason(lead: dict, email: str, domain: str, suppressions: dict[str, set[str]]) -> str:
    company = normalized_company(str(lead.get("company_name") or ""))
    email_lc = email.lower()
    email_dom = email_domain(email_lc)
    if email_lc and email_lc in suppressions["email"]:
        return "recipient email is suppressed"
    if email_dom and email_dom in suppressions["domain"]:
        return "recipient email domain is suppressed"
    if domain and domain in suppressions["domain"]:
        return "company domain is suppressed"
    if company and company in suppressions["company"]:
        return "company is suppressed"
    return ""


def email_score(email_obj: dict, company_domain: str) -> tuple[int, str]:
    email = str(email_obj.get("email") or "").strip().lower()
    typ = str(email_obj.get("type") or "generic").lower()
    relation = str(email_obj.get("domain_relation") or "unknown").lower()
    confidence = float(email_obj.get("confidence") or 0)
    dom = email_domain(email)

    if not email or typ == "inferred" or relation in {"free_mail", "third_party"} or dom in FREE_EMAIL_DOMAINS:
        return (-1, "high")

    score = 0
    risk = "medium"
    if typ == "person":
        score += 40
        risk = "low"
    elif typ == "generic":
        score += 25
    if relation == "same_domain":
        score += 30
    elif relation == "parent_domain":
        score += 15
    if company_domain and dom == company_domain:
        score += 20
    if confidence >= 0.8:
        score += 10
    elif confidence < 0.5:
        risk = "high"
    return (score, risk)


def best_email(lead: dict, company_domain: str) -> tuple[dict | None, str]:
    candidates = []
    for dm in lead.get("decision_makers", []) or []:
        if not isinstance(dm, dict):
            continue
        email = str(dm.get("email") or "").strip().lower()
        if not email:
            continue
        email_obj = {
            "email": email,
            "type": "person" if dm.get("email_type") == "public" else "inferred",
            "source_url": str(dm.get("source_url") or dm.get("linkedin") or dm.get("xing") or ""),
            "domain_relation": "same_domain" if email_domain(email) == company_domain else "unknown",
            "verification": "format_only",
            "confidence": float(dm.get("email_confidence") or dm.get("confidence") or 0.6),
        }
        score, risk = email_score(email_obj, company_domain)
        if score >= 0:
            candidates.append((score + 20, risk, email_obj))
    for obj in lead.get("emails", []) or []:
        if not isinstance(obj, dict):
            continue
        score, risk = email_score(obj, company_domain)
        if score >= 0:
            candidates.append((score, risk, obj))
    if not candidates:
        return None, "no usable same-domain or parent-domain business email"
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][2], candidates[0][1]


def build_candidate(lead: dict, suppressions: dict[str, set[str]], sent_domains: set[str]) -> dict:
    company_name = str(lead.get("company_name") or "")
    domain = normalized_domain(str(lead.get("website") or ""))
    lid = lead_id(lead, domain)
    priority = str(lead.get("priority") or "").lower()
    source_quality = str(lead.get("source_quality") or "").lower()
    source_urls = [u for u in lead.get("source_urls", []) or [] if u]
    official = bool(lead.get("official_site_found"))
    evidence = lead.get("evidence", []) or []
    buyer_evidence = bool(
        evidence
        or str(lead.get("fit_reason_zh") or "").strip()
        or str(lead.get("description") or "").strip()
        or str(lead.get("notes") or "").strip()
    )

    base = {
        "candidate_id": f"{lid}-outreach-{short_hash(company_name + '|' + domain)}",
        "lead_id": lid,
        "company_name": company_name,
        "company_domain": domain,
        "country": str(lead.get("country") or ""),
        "priority": priority or "low",
        "selected_channel": "skip",
        "selected_recipient_email": "",
        "recipient_type": "none",
        "domain_relation": "none",
        "recipient_rank": 0,
        "recipient_risk": "high",
        "draft_allowed": False,
        "auto_send_allowed": False,
        "selection_reason": "",
        "blocked_reason": "",
        "source_urls": source_urls,
        "created_at": now_iso(),
    }

    blocked = []
    if priority not in {"high", "medium"}:
        blocked.append("priority is not high or medium")
    if not official:
        blocked.append("official website not confirmed")
    if source_quality in {"directory", "snippet"}:
        blocked.append("source quality is directory/snippet only")
    if not source_urls:
        blocked.append("missing source URLs")
    if not buyer_evidence:
        blocked.append("missing buyer-role evidence")
    if domain and domain in sent_domains:
        blocked.append("company already has a successful first-touch send")

    selected, risk = best_email(lead, domain)
    if selected:
        email = str(selected.get("email") or "").strip().lower()
        base.update(
            {
                "selected_channel": "email",
                "selected_recipient_email": email,
                "recipient_type": str(selected.get("type") or "generic"),
                "domain_relation": str(selected.get("domain_relation") or "unknown"),
                "recipient_rank": 1,
                "recipient_risk": risk,
            }
        )
        suppressed = suppression_reason(lead, email, domain, suppressions)
        if suppressed:
            blocked.append(suppressed)
    elif official and domain:
        base.update(
            {
                "selected_channel": "contact_form",
                "recipient_risk": "medium",
                "selection_reason": "no usable email; official website may support contact-form outreach",
            }
        )
    else:
        blocked.append("no usable email or contact-form path")

    if blocked:
        base["selected_channel"] = "review_only" if selected and priority in {"high", "medium"} else base["selected_channel"]
        base["blocked_reason"] = "; ".join(dict.fromkeys(blocked))
        base["selection_reason"] = base["selection_reason"] or "not eligible for outreach drafting"
        return base

    if selected:
        typ = base["recipient_type"]
        relation = base["domain_relation"]
        base["draft_allowed"] = True
        base["auto_send_allowed"] = typ == "person" and relation in {"same_domain", "parent_domain"} and risk == "low"
        base["selection_reason"] = f"selected best public business email ({typ}, {relation})"
    else:
        base["draft_allowed"] = True
        base["auto_send_allowed"] = False
        base["selection_reason"] = "selected official contact-form channel for manual outreach"
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("leads_jsonl", type=Path)
    parser.add_argument("--output", "-o", default="-")
    parser.add_argument("--suppression-list", type=Path)
    parser.add_argument("--sent-log", type=Path)
    args = parser.parse_args()

    suppressions = load_suppressions(args.suppression_list)
    sent_domains = load_sent_domains(args.sent_log)
    rows = [build_candidate(lead, suppressions, sent_domains) for lead in read_jsonl(args.leads_jsonl)]
    for i, row in enumerate(rows, start=1):
        validate_outreach_candidate(row, f"outreach-candidates[{i}]")
    write_jsonl(args.output, rows)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

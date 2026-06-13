#!/usr/bin/env python3
"""Generate conservative first-touch outreach drafts from outreach candidates.

This script renders safe, source-backed draft records. It does not approve,
queue, or send email. Hermes can revise and localize the output before human
approval.
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

from contracts import (
    ContractError,
    validate_outreach_candidate,
    validate_outreach_draft,
    validate_outreach_template,
    validate_sender_profile,
)

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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def compact_text(value: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def first(values: list[str] | None, fallback: str = "") -> str:
    for value in values or []:
        if str(value).strip():
            return str(value).strip()
    return fallback


def localized_first(sender: dict, key: str, language: str, fallback_key: str, fallback: str) -> str:
    localized = sender.get(key) or {}
    if isinstance(localized, dict):
        value = first(localized.get(language) or [])
        if value:
            return value
    return first(sender.get(fallback_key), fallback)


def load_templates(path: Path | None) -> dict[str, dict]:
    if not path:
        return {}
    rows = read_jsonl(path)
    out: dict[str, dict] = {}
    for i, row in enumerate(rows, start=1):
        validate_outreach_template(row, f"outreach-templates[{i}]")
        out[str(row["cluster_key"])] = row
    return out


def choose_language(country: str, forced_language: str | None = None) -> tuple[str, str, str, str]:
    if forced_language:
        return forced_language, "high", f"Forced by --language={forced_language}.", "low"
    country_lc = (country or "").strip().lower()
    if country_lc in ENGLISH_BUSINESS_COUNTRIES:
        return "en", "high", "Country commonly supports English-language B2B outreach.", "low"
    if country_lc in LOCAL_LANGUAGE_BY_COUNTRY:
        language = LOCAL_LANGUAGE_BY_COUNTRY[country_lc]
        return language, "medium", f"Selected local-language template for {country}. Manual language review recommended.", "medium"
    return "en", "medium", "Defaulted to English because deterministic script cannot verify local-language quality.", "medium"


def buyer_role(lead: dict) -> str:
    roles = [str(v).strip().lower() for v in lead.get("business_type", []) or [] if str(v).strip()]
    for preferred in ("distributor", "importer", "wholesaler", "oem", "integrator", "installer", "end_user"):
        if preferred in roles:
            return preferred
    return first(roles, "buyer")


def cluster_key(country: str, language: str, role: str, product_angle: str) -> str:
    raw = "|".join([country.strip().lower(), language, role, product_angle.strip().lower()])
    return re.sub(r"[^a-z0-9]+", "-", raw).strip("-")


def build_lead_index(leads: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for lead in leads:
        domain = normalized_domain(str(lead.get("website") or ""))
        lid = lead_id(lead, domain)
        out[lid] = lead
    return out


def personalization_point(lead: dict, candidate: dict) -> dict:
    source_url = first(candidate.get("source_urls") or lead.get("source_urls") or [], str(lead.get("website") or ""))
    evidence = lead.get("evidence") or []
    if evidence and isinstance(evidence[0], dict):
        claim = compact_text(str(evidence[0].get("claim") or "public company information indicates relevant business fit"))
        source_url = str(evidence[0].get("source_url") or source_url)
    else:
        claim = compact_text(
            str(lead.get("fit_reason_zh") or lead.get("description") or "public company information indicates relevant business fit")
        )
    return {"claim": claim, "source_url": source_url}


def mostly_ascii(value: str) -> bool:
    if not value:
        return False
    ascii_count = sum(1 for ch in value if ord(ch) < 128)
    return ascii_count / max(1, len(value)) >= 0.85


def localized_personalization(point: dict, language: str) -> str:
    claim = str(point.get("claim") or "").strip()
    if language == "en" and claim and mostly_ascii(claim):
        return claim
    if language == "de":
        return "Ihre oeffentlichen Unternehmensinformationen zeigen einen relevanten Bezug zu dieser Produktkategorie."
    if language == "fr":
        return "Les informations publiques de votre entreprise indiquent un lien pertinent avec cette categorie de produits."
    if language == "es":
        return "La informacion publica de su empresa indica una relacion relevante con esta categoria de productos."
    if language == "pl":
        return "Publiczne informacje o Panstwa firmie wskazuja na zwiazek z ta kategoria produktow."
    return "Your public company information indicates a relevant fit with this product category."


def localized_country(country: str, language: str) -> str:
    value = (country or "").strip()
    key = value.lower()
    names = {
        "de": {
            "germany": "Deutschland",
            "austria": "Oesterreich",
            "switzerland": "der Schweiz",
        },
        "fr": {
            "germany": "Allemagne",
            "france": "France",
            "spain": "Espagne",
            "italy": "Italie",
        },
        "es": {
            "germany": "Alemania",
            "france": "Francia",
            "spain": "Espana",
            "italy": "Italia",
        },
        "pl": {
            "germany": "Niemczech",
            "poland": "Polsce",
            "france": "Francji",
            "spain": "Hiszpanii",
        },
    }
    return names.get(language, {}).get(key, value or "your market")


def localized_cta(language: str) -> str:
    if language == "de":
        return "Waeren Sie die richtige Ansprechperson, um zu pruefen, ob diese Kategorie fuer Sie relevant ist? Bei Interesse sende ich gern einen kurzen Katalog, technische Daten oder Angebotsdetails."
    if language == "fr":
        return "Seriez-vous la bonne personne pour verifier si cette categorie est pertinente ? Je peux envoyer un court catalogue, des specifications ou des details de devis si utile."
    if language == "es":
        return "Seria usted la persona adecuada para revisar si esta categoria es relevante? Puedo enviar un catalogo breve, especificaciones o detalles de cotizacion si resulta util."
    if language == "pl":
        return "Czy jest Pan/Pani wlasciwa osoba, aby sprawdzic, czy ta kategoria jest dla Panstwa istotna? W razie potrzeby moge przeslac krotki katalog, specyfikacje lub informacje ofertowe."
    return "Would you be the right person to check whether this category is relevant? I can send a short catalog, specs, or quotation details if useful."


def localized_opt_out(language: str) -> str:
    if language == "de":
        return "Falls dies nicht relevant ist, antworten Sie bitte mit \"stop\"; ich werde Sie dann nicht erneut kontaktieren."
    if language == "fr":
        return "Si ce n'est pas pertinent, repondez \"stop\" et je ne vous contacterai plus."
    if language == "es":
        return "Si esto no es relevante, responda \"stop\" y no volvere a contactarle."
    if language == "pl":
        return "Jesli to nie jest istotne, prosze odpowiedziec \"stop\"; nie bede kontaktowac sie ponownie."
    return "If this is not relevant, reply \"stop\" and I will not contact you again."


def localized_offer_angle(product: str, application: str, language: str) -> str:
    if language == "de":
        return f"{product} fuer {application}"
    if language == "fr":
        return f"{product} pour {application}"
    if language == "es":
        return f"{product} para {application}"
    if language == "pl":
        return f"{product} dla {application}"
    return f"{product} for {application}"


def recipient_greeting(candidate: dict) -> str:
    email = str(candidate.get("selected_recipient_email") or "")
    local = email.split("@", 1)[0].lower()
    if candidate.get("recipient_type") == "person":
        name = re.sub(r"[._-]+", " ", local).title()
        return name or "there"
    return "team"


def build_body(sender: dict, lead: dict, candidate: dict, product: str, point: dict) -> str:
    company = str(candidate.get("company_name") or lead.get("company_name") or "your company")
    country = str(candidate.get("country") or lead.get("country") or "your market")
    application = first(sender.get("target_applications"), "B2B distribution or project supply")
    signature = str(sender.get("signature") or "").strip()
    if not signature:
        signature = "\n".join(
            [
                str(sender.get("sender_name") or ""),
                str(sender.get("sender_title") or ""),
                str(sender.get("company_name") or ""),
                str(sender.get("reply_to") or sender.get("from_email") or ""),
            ]
        ).strip()

    return "\n\n".join(
        [
            f"Hi {recipient_greeting(candidate)},",
            f"I found {company} while researching potential B2B channel partners in {country}.",
            f"We are {sender.get('company_name')} and supply {product} for {application}. Based on your public company information, this may be relevant to your current product or customer work.",
            "Would you be the right person to check whether this category is relevant? I can send a short catalog, specs, or quotation details if useful.",
            f"Best regards,\n{signature}",
            "If this is not relevant, reply \"stop\" and I will not contact you again.",
        ]
    )


def render_template(template: dict, variables: dict[str, str]) -> tuple[str, str]:
    missing = [key for key in template["required_variables"] if not variables.get(key)]
    if missing:
        raise ContractError(f"template {template['template_id']}: missing variable(s): {', '.join(missing)}")
    subject = template["subject_template"].format(**variables)
    body = template["body_template"].format(**variables)
    return subject, body


def build_draft(
    sender: dict,
    lead: dict,
    candidate: dict,
    forced_language: str | None,
    templates: dict[str, dict],
    require_template: bool,
) -> dict | None:
    if not candidate.get("draft_allowed"):
        return None
    if candidate.get("selected_channel") != "email":
        return None
    recipient = str(candidate.get("selected_recipient_email") or "").strip().lower()
    if not recipient:
        return None

    canonical_product = first(sender.get("product_lines"), "B2B products")
    country = str(candidate.get("country") or lead.get("country") or "")
    language, language_confidence, language_reason, localization_risk = choose_language(country, forced_language)
    point = personalization_point(lead, candidate)
    role = buyer_role(lead)
    key = cluster_key(country or "global", language, role, canonical_product)
    template = templates.get(key)
    if require_template and not template:
        raise ContractError(f"outreach-draft {candidate.get('candidate_id')}: missing outreach template for cluster_key={key}")
    draft_version = 1
    draft_id = "draft-" + short_hash(
        "|".join(
            [
                str(candidate.get("lead_id") or ""),
                recipient,
                language,
                str(draft_version),
            ]
        )
    )

    source_urls = []
    for value in list(candidate.get("source_urls") or []) + list(lead.get("source_urls") or []):
        if value and value not in source_urls:
            source_urls.append(value)
    if point["source_url"] and point["source_url"] not in source_urls:
        source_urls.append(point["source_url"])

    product = localized_first(sender, "localized_product_lines", language, "product_lines", "B2B products")
    application = localized_first(sender, "localized_target_applications", language, "target_applications", "B2B distribution or project supply")
    signature = str(sender.get("signature") or "").strip()
    if not signature:
        signature = "\n".join(
            [
                str(sender.get("sender_name") or ""),
                str(sender.get("sender_title") or ""),
                str(sender.get("company_name") or ""),
                str(sender.get("reply_to") or sender.get("from_email") or ""),
            ]
        ).strip()
    cta = localized_cta(language)
    opt_out = localized_opt_out(language)
    variables = {
        "company_name": str(candidate.get("company_name") or lead.get("company_name") or "your company"),
        "country": localized_country(country, language),
        "greeting": recipient_greeting(candidate),
        "sender_company": str(sender.get("company_name") or ""),
        "product": product,
        "application": application,
        "personalization_reason": localized_personalization(point, language),
        "cta": cta,
        "signature": signature,
        "opt_out": opt_out,
    }
    if template:
        subject, body = render_template(template, variables)
        language = str(template["language"])
        language_reason = f"Rendered from outreach template {template['template_id']} for cluster {template['cluster_key']}."
    else:
        subject = f"{product} cooperation for {country or candidate.get('company_name')}"
        body = build_body(sender, lead, candidate, product, point)
    risk_flags = []
    if candidate.get("recipient_type") == "generic":
        risk_flags.append("generic recipient; manual review recommended")
    if language_confidence != "high":
        risk_flags.append("language confidence is not high")
    if not candidate.get("auto_send_allowed"):
        risk_flags.append("candidate is not marked auto_send_allowed")

    send_recommendation = "send" if not risk_flags and candidate.get("auto_send_allowed") else "review"

    return {
        "draft_id": draft_id,
        "draft_version": draft_version,
        "template_id": str(template.get("template_id") if template else ""),
        "template_cluster_key": str(template.get("cluster_key") if template else key),
        "lead_id": str(candidate.get("lead_id") or ""),
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "company_domain": str(candidate.get("company_domain") or ""),
        "company_name": str(candidate.get("company_name") or lead.get("company_name") or ""),
        "website": str(lead.get("website") or ""),
        "country": country,
        "region": str(lead.get("region") or ""),
        "recipient_email": recipient,
        "recipient_type": str(candidate.get("recipient_type") or "generic"),
        "recipient_name": "",
        "recipient_title": "",
        "language": language,
        "language_confidence": language_confidence,
        "language_reason": language_reason,
        "fallback_language": "en",
        "localization_risk": localization_risk,
        "subject": subject,
        "body_text": body,
        "personalization_points": [point],
        "source_urls": source_urls,
        "claims_made": [
            {
                "claim": f"{sender.get('company_name')} supplies {product}.",
                "claim_type": "about_sender",
                "support": "sender-profile.json",
                "risk": "low",
            },
            {
                "claim": point["claim"],
                "claim_type": "about_recipient",
                "support": "source_url",
                "source_url": point["source_url"],
                "risk": "medium" if language_confidence != "high" else "low",
            },
            {
                "claim": "The product category may be relevant to the recipient's current product or customer work.",
                "claim_type": "about_fit",
                "support": "lead qualification evidence",
                "source_url": point["source_url"],
                "risk": "medium",
            },
        ],
        "offer_angle": localized_offer_angle(product, application, language),
        "cta": cta,
        "opt_out_line": opt_out,
        "send_recommendation": send_recommendation,
        "risk_flags": risk_flags,
        "approval_status": "pending",
        "state": "review_pending",
        "review_notes": "Generated draft requires human review before approval or sending.",
        "created_at": now_iso(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leads", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--sender-profile", required=True, type=Path)
    parser.add_argument("--output", "-o", default="-")
    parser.add_argument("--language", help="Force a language code such as en, de, fr, es, pl.")
    parser.add_argument("--templates", type=Path, help="outreach-template-clusters.jsonl generated by generate_outreach_templates.py.")
    parser.add_argument("--require-template", action="store_true", help="Fail if an email-capable candidate has no matching template.")
    args = parser.parse_args()

    sender = read_json(args.sender_profile)
    validate_sender_profile(sender, "sender-profile")
    leads = build_lead_index(read_jsonl(args.leads))
    candidates = read_jsonl(args.candidates)
    templates = load_templates(args.templates)

    drafts: list[dict] = []
    for i, candidate in enumerate(candidates, start=1):
        validate_outreach_candidate(candidate, f"outreach-candidates[{i}]")
        lead = leads.get(str(candidate.get("lead_id") or ""), {})
        draft = build_draft(sender, lead, candidate, args.language, templates, args.require_template)
        if draft:
            validate_outreach_draft(draft, f"outreach-drafts[{len(drafts) + 1}]")
            drafts.append(draft)

    write_jsonl(args.output, drafts)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

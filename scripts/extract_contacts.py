#!/usr/bin/env python3
"""Extract public B2B contact signals from text or markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(
    r"""(?<!\d)(?<!\.)
    (?:
        \+\d{1,3}[\s.\-]
        |
        \(\d{2,4}\)[\s.\-]?
        |
        \d{2,4}[\s\-]\d
    )
    [\d\s.\-\(\)]{5,20}
    (?!\d)(?!\.)
    """,
    re.VERBOSE,
)
SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9\-_.%]+/?", re.I),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[a-zA-Z0-9.\-]+/?", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+/?", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_.]+/?", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|channel/|c/)[a-zA-Z0-9\-_.]+/?", re.I),
    "whatsapp": re.compile(r"https?://(?:wa\.me|api\.whatsapp\.com|chat\.whatsapp\.com)/[a-zA-Z0-9+]+/?", re.I),
}
SHARE_BLACKLIST = re.compile(r"(?:sharer|share|intent/tweet|dialog/share|plugins|embed|watch\?)", re.I)
CONTACT_KEYWORDS = {
    "contact", "contacts", "kontakt", "contacto", "contato", "contatti",
    "about", "about-us", "company", "team", "impressum", "imprint",
    "legal-notice", "ueber-uns", "uber-uns", "nosotros", "chi-siamo",
    "a-propos", "qui-sommes-nous", "azienda", "empresa", "over-ons",
    "o-nas", "contacter", "contattaci", "kontaktieren", "lianxi", "guanyu",
}
GENERIC_LOCAL_PARTS = {
    "info", "sales", "contact", "support", "office", "hello", "admin",
    "marketing", "service", "team", "enquiry", "enquiries", "inquiry",
    "inquiries", "export", "exports", "import", "imports", "customerservice",
}
FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "aol.com", "proton.me", "protonmail.com",
    "qq.com", "163.com", "126.com", "mail.ru", "yandex.ru", "gmx.de",
    "web.de", "orange.fr", "libero.it", "naver.com", "daum.net",
}
INVALID_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.net", "test.com", "localhost",
    "domain.com", "email.com", "yourdomain.com",
}
INVALID_EMAIL_LOCALS = {
    "example", "test", "demo", "noreply", "no-reply", "donotreply",
}


def normalize_phone_digits(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return digits[2:] if digits.startswith("00") else digits


def valid_phone(raw: str) -> bool:
    digits = normalize_phone_digits(raw)
    if not 7 <= len(digits) <= 15:
        return False
    if re.search(r"\d\.\d", raw):
        return False
    if len(set(digits)) == 1:
        return False
    if max(digits.count(d) for d in set(digits)) / len(digits) > 0.6:
        return False
    if re.match(r"^\d{4,6}(19|20)\d{2}$", digits):
        return False
    return True


def email_type(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    compact = re.sub(r"[\W_]+", "", local)
    return "generic" if local in GENERIC_LOCAL_PARTS or compact in GENERIC_LOCAL_PARTS else "person"


def normalized_domain(url_or_domain: str) -> str:
    value = (url_or_domain or "").strip().lower()
    if not value:
        return ""
    if "://" not in value and "/" not in value:
        host = value
    else:
        host = urlparse(value).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0]


def domain_relation(email: str, source_url: str, company_domain: str = "") -> str:
    email_domain = email.rsplit("@", 1)[-1].lower()
    if email_domain in FREE_MAIL_DOMAINS:
        return "free_mail"
    source_domain = normalized_domain(source_url)
    target_domain = normalized_domain(company_domain) or source_domain
    if not target_domain:
        return "unknown"
    if email_domain == target_domain:
        return "same_domain"
    if email_domain.endswith("." + target_domain) or target_domain.endswith("." + email_domain):
        return "parent_domain"
    return "third_party"


def valid_email(email: str) -> bool:
    if email.count("@") != 1:
        return False
    local, domain = email.lower().split("@", 1)
    if not local or not domain or "." not in domain:
        return False
    if domain in INVALID_EMAIL_DOMAINS:
        return False
    if local in INVALID_EMAIL_LOCALS:
        return False
    if local.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
        return False
    return True


def extract_emails(text: str, source_url: str, company_domain: str = "") -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for match in EMAIL_RE.findall(text):
        email = match.strip().lower()
        if email in seen or not valid_email(email):
            continue
        seen.add(email)
        kind = email_type(email)
        relation = domain_relation(email, source_url, company_domain)
        confidence = 0.9 if kind == "person" else 0.85
        if relation == "same_domain":
            confidence += 0.05
        elif relation in {"third_party", "free_mail"}:
            confidence -= 0.2
        rows.append(
            {
                "email": email,
                "type": kind,
                "source_url": source_url,
                "domain_relation": relation,
                "verification": "format_only",
                "confidence": round(max(0.1, min(confidence, 0.98)), 2),
            }
        )
    return rows


def extract_phones(text: str) -> list[str]:
    seen: set[str] = set()
    phones: list[str] = []
    for raw in PHONE_RE.findall(text):
        cleaned = re.sub(r"\s+", " ", raw).strip(" \t\r\n-.,;:")
        if not valid_phone(cleaned):
            continue
        key = normalize_phone_digits(cleaned)
        if key not in seen:
            seen.add(key)
            phones.append(cleaned)
    return phones[:10]


def extract_social(text: str) -> dict[str, str]:
    social: dict[str, str] = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        for url in pattern.findall(text):
            if not SHARE_BLACKLIST.search(url):
                social[platform] = url.rstrip("/")
                break
    return social


def discover_contact_pages(text: str, base_url: str) -> list[str]:
    if not base_url:
        return []
    links = []
    links.extend(re.findall(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", text, flags=re.I))
    links.extend(url for _, url in re.findall(r"\[([^\]]*)\]\(([^)]+)\)", text))
    seen: set[str] = set()
    out: list[str] = []
    for href in links:
        low = href.lower()
        if low.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        path = absolute.lower().split("?", 1)[0].strip("/")
        if any(token in path for token in CONTACT_KEYWORDS) and absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
        if len(out) >= 5:
            break
    return out


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Text/markdown file, or '-' for stdin.")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--company-domain", default="", help="Official company domain for email relation checks.")
    args = parser.parse_args()

    text = read_text(args.file)
    result = {
        "source_url": args.source_url,
        "emails": extract_emails(text, args.source_url, args.company_domain),
        "phones": extract_phones(text),
        "social": extract_social(text),
        "contact_pages": discover_contact_pages(text, args.source_url),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

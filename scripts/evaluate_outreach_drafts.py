#!/usr/bin/env python3
"""Evaluate outreach drafts before human approval.

This is a deterministic quality gate. It does not approve, send, or rewrite
emails. It scores language fit, personalization, claim risk, spam risk, and
reply likelihood so weak drafts stay out of approved-outreach.jsonl.
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

from contracts import ContractError, validate_outreach_draft, validate_outreach_evaluation


LOCAL_LANGUAGE_BY_COUNTRY = {
    "germany": "de",
    "austria": "de",
    "switzerland": "de",
    "france": "fr",
    "belgium": "fr",
    "spain": "es",
    "mexico": "es",
    "italy": "it",
    "poland": "pl",
    "czech republic": "cs",
    "czechia": "cs",
    "netherlands": "nl",
    "brazil": "pt",
    "portugal": "pt",
    "turkey": "tr",
    "japan": "ja",
    "south korea": "ko",
    "korea": "ko",
    "china": "zh",
    "taiwan": "zh",
}
ENGLISH_OK_COUNTRIES = {
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
SPAM_PHRASES = {
    "best price",
    "cheapest",
    "guaranteed",
    "risk-free",
    "limited time",
    "act now",
    "urgent",
    "free quote",
    "dear sir/madam",
    "to whom it may concern",
}
HIGH_RISK_CLAIM_TERMS = {
    "certified",
    "authorized",
    "exclusive",
    "local stock",
    "in stock",
    "factory direct lowest",
    "guarantee",
    "approved supplier",
    "existing customer",
}


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


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


def compact_body(body: str) -> str:
    return re.sub(r"\s+", " ", body or "").strip().lower()


def clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def body_hash(draft: dict) -> str:
    payload = "\n".join(
        [
            str(draft.get("recipient_email") or "").strip().lower(),
            str(draft.get("subject") or ""),
            str(draft.get("body_text") or ""),
            str(draft.get("opt_out_line") or ""),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def language_fit(draft: dict, review: list[str], block: list[str], actions: list[str]) -> float:
    language = str(draft.get("language") or "").lower()
    confidence = str(draft.get("language_confidence") or "").lower()
    country = str(draft.get("country") or "").strip().lower()
    expected = LOCAL_LANGUAGE_BY_COUNTRY.get(country)

    if confidence == "low":
        block.append("language_confidence is low")
        actions.append("Regenerate in English or local language after manual language review.")
        return 0.2
    if expected and language == expected:
        return 0.95 if confidence == "high" else 0.8
    if country in ENGLISH_OK_COUNTRIES and language == "en":
        return 0.95 if confidence == "high" else 0.75
    if expected and language == "en":
        review.append(f"English draft for {country}; local language {expected} may perform better.")
        actions.append(f"Consider regenerating with --language {expected} or manual local-language editing.")
        return 0.55 if confidence == "medium" else 0.65
    if confidence == "high":
        return 0.75
    review.append("language confidence is not high")
    actions.append("Review language choice before approval.")
    return 0.5


def personalization_strength(draft: dict, review: list[str], block: list[str], actions: list[str]) -> float:
    points = draft.get("personalization_points") or []
    source_urls = [url for url in draft.get("source_urls") or [] if str(url).strip()]
    body = compact_body(str(draft.get("body_text") or ""))
    score = 0.25
    if source_urls:
        score += 0.2
    if points:
        score += 0.2
    if len(points) >= 2:
        score += 0.1
    if str(draft.get("company_name") or "").lower() in body:
        score += 0.1
    if "public company information" in body:
        score -= 0.15
        review.append("Personalization is generic: body uses 'public company information'.")
        actions.append("Replace generic personalization with one concrete source-backed reason.")
    if not points or not source_urls:
        block.append("missing source-backed personalization")
        actions.append("Add at least one personalization point with source_url.")
    return clamp(score)


def claim_risk(draft: dict, review: list[str], block: list[str], actions: list[str]) -> float:
    claims = draft.get("claims_made") or []
    body = compact_body(str(draft.get("body_text") or ""))
    high_claims = [c for c in claims if isinstance(c, dict) and c.get("risk") == "high"]
    medium_claims = [c for c in claims if isinstance(c, dict) and c.get("risk") == "medium"]
    flagged_terms = sorted(term for term in HIGH_RISK_CLAIM_TERMS if term in body)
    if high_claims:
        block.append("claims_made contains high-risk claim")
        actions.append("Remove or source high-risk claims before approval.")
    if flagged_terms:
        review.append("Body contains risky claim terms: " + ", ".join(flagged_terms))
        actions.append("Verify or remove risky commercial/certification claims.")
    score = 1.0 - 0.35 * len(high_claims) - 0.12 * len(medium_claims) - 0.08 * len(flagged_terms)
    return clamp(score)


def spam_risk(draft: dict, review: list[str], block: list[str], actions: list[str]) -> float:
    subject = str(draft.get("subject") or "")
    body_text = str(draft.get("body_text") or "")
    body = compact_body(body_text)
    score = 1.0
    if len(subject) > 90:
        score -= 0.15
        review.append("Subject is long.")
        actions.append("Shorten subject below 90 characters.")
    if len(body_text) > 1300:
        score -= 0.2
        review.append("Body is long for first-touch outreach.")
        actions.append("Shorten first-touch email to a concise ask.")
    if body_text.count("http://") + body_text.count("https://") > 1:
        score -= 0.15
        review.append("Body contains multiple links.")
        actions.append("Use no links or one trusted catalog/company link.")
    if "!" in subject or body_text.count("!") > 1:
        score -= 0.15
        review.append("Too many exclamation marks.")
        actions.append("Use neutral B2B tone.")
    found = sorted(phrase for phrase in SPAM_PHRASES if phrase in body)
    if found:
        score -= 0.08 * len(found)
        review.append("Spam-like wording: " + ", ".join(found))
        actions.append("Remove urgency, cheapest-price, or generic mass-email phrasing.")
    if "stop" not in body and "unsubscribe" not in body and "not contact" not in body:
        block.append("missing clear opt-out language")
        actions.append("Add a clear opt-out sentence.")
        score -= 0.35
    return clamp(score)


def reply_likelihood(draft: dict, review: list[str], block: list[str], actions: list[str]) -> float:
    body = compact_body(str(draft.get("body_text") or ""))
    routing_phrases = (
        "would you be the right person",
        "are you the right person",
        "right person",
        "richtige ansprechperson",
        "bonne personne",
        "persona adecuada",
        "wlasciwa osoba",
    )
    score = 0.35
    if "?" in str(draft.get("body_text") or ""):
        score += 0.2
    if any(phrase in body for phrase in routing_phrases) or "relevant" in body:
        score += 0.15
    if "catalog" in body or "spec" in body or "quotation" in body:
        score += 0.1
    if draft.get("recipient_type") == "person":
        score += 0.1
    elif draft.get("recipient_type") == "generic":
        score -= 0.05
        review.append("Generic recipient lowers reply likelihood.")
        actions.append("Find a named buyer/procurement/product contact when possible.")
    if not any(phrase in body for phrase in routing_phrases):
        review.append("CTA does not clearly route to the right person.")
        actions.append("Use a low-friction routing CTA.")
    return clamp(score)


def decision(overall: float, scores: dict[str, float], block: list[str], review: list[str], actions: list[str]) -> str:
    if block:
        return "reject"
    if min(scores.values()) < 0.45:
        review.append("At least one quality dimension is below 0.45.")
        actions.append("Revise draft before approval.")
        return "review"
    if overall >= 0.72 and not review:
        return "pass"
    if overall >= 0.62:
        return "review"
    return "reject" if overall < 0.45 else "review"


def evaluate(draft: dict) -> dict:
    review: list[str] = []
    block: list[str] = []
    actions: list[str] = []
    scores = {
        "language_fit_score": language_fit(draft, review, block, actions),
        "personalization_score": personalization_strength(draft, review, block, actions),
        "claim_risk_score": claim_risk(draft, review, block, actions),
        "spam_risk_score": spam_risk(draft, review, block, actions),
        "reply_likelihood_score": reply_likelihood(draft, review, block, actions),
    }
    overall = clamp(
        scores["language_fit_score"] * 0.2
        + scores["personalization_score"] * 0.25
        + scores["claim_risk_score"] * 0.2
        + scores["spam_risk_score"] * 0.2
        + scores["reply_likelihood_score"] * 0.15
    )
    dedup_review = list(dict.fromkeys(review))
    dedup_block = list(dict.fromkeys(block))
    dedup_actions = list(dict.fromkeys(actions))
    verdict = decision(overall, scores, dedup_block, dedup_review, dedup_actions)
    seed = "|".join([str(draft.get("draft_id") or ""), str(draft.get("recipient_email") or ""), str(overall)])
    row = {
        "evaluation_id": "eval-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12],
        "draft_id": str(draft.get("draft_id") or ""),
        "lead_id": str(draft.get("lead_id") or ""),
        "company_name": str(draft.get("company_name") or ""),
        "recipient_email": str(draft.get("recipient_email") or "").strip().lower(),
        "language": str(draft.get("language") or ""),
        "evaluated_body_hash": body_hash(draft),
        **scores,
        "overall_score": overall,
        "decision": verdict,
        "blocking_reasons": dedup_block,
        "review_reasons": dedup_review,
        "recommended_actions": dedup_actions,
        "created_at": now_iso(),
    }
    validate_outreach_evaluation(row)
    return row


def write_review_csv(path: Path, drafts: list[dict], evaluations: list[dict]) -> None:
    eval_by_id = {row["draft_id"]: row for row in evaluations}
    with path.open("w", encoding="utf-8", newline="") as fh:
        fieldnames = [
            "decision",
            "overall_score",
            "draft_id",
            "company_name",
            "recipient_email",
            "language",
            "subject",
            "review_reasons",
            "blocking_reasons",
            "recommended_actions",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for draft in drafts:
            ev = eval_by_id.get(str(draft.get("draft_id") or ""))
            if not ev:
                continue
            writer.writerow(
                {
                    "decision": ev["decision"],
                    "overall_score": ev["overall_score"],
                    "draft_id": ev["draft_id"],
                    "company_name": ev["company_name"],
                    "recipient_email": ev["recipient_email"],
                    "language": ev["language"],
                    "subject": draft.get("subject", ""),
                    "review_reasons": " | ".join(ev["review_reasons"]),
                    "blocking_reasons": " | ".join(ev["blocking_reasons"]),
                    "recommended_actions": " | ".join(ev["recommended_actions"]),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drafts", required=True, type=Path)
    parser.add_argument("--output", "-o", default="-", help="Write outreach-evaluations JSONL.")
    parser.add_argument("--review-csv", type=Path, help="Optional human review CSV path.")
    parser.add_argument("--min-pass-score", type=float, default=0.72)
    args = parser.parse_args()

    drafts = read_jsonl(args.drafts)
    evaluations = []
    for i, draft in enumerate(drafts, start=1):
        validate_outreach_draft(draft, f"outreach-drafts[{i}]")
        ev = evaluate(draft)
        if ev["overall_score"] < args.min_pass_score and ev["decision"] == "pass":
            ev["decision"] = "review"
            ev["review_reasons"].append(f"overall_score below min-pass-score {args.min_pass_score}")
            validate_outreach_evaluation(ev, f"outreach-evaluations[{i}]")
        evaluations.append(ev)

    write_jsonl(args.output, evaluations)
    if args.review_csv:
        write_review_csv(args.review_csv, drafts, evaluations)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

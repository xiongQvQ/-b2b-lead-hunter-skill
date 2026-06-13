"""Small runtime contracts for B2B lead hunter script boundaries.

The project intentionally avoids external dependencies, so these validators
cover the strict subset of JSON schema rules needed by the pipeline: required
fields, allowed fields, primitive types, enums, and non-empty lists.
"""

from __future__ import annotations

import re
from typing import Any


class ContractError(ValueError):
    """Raised when a script input or output record violates a pipeline contract."""


def _fail(path: str, message: str) -> None:
    raise ContractError(f"{path}: {message}")


def _require_keys(obj: dict[str, Any], keys: set[str], path: str) -> None:
    missing = sorted(key for key in keys if key not in obj)
    if missing:
        _fail(path, "missing required field(s): " + ", ".join(missing))


def _allow_only(obj: dict[str, Any], keys: set[str], path: str) -> None:
    extra = sorted(key for key in obj if key not in keys)
    if extra:
        _fail(path, "unknown field(s): " + ", ".join(extra))


def _type(obj: dict[str, Any], key: str, expected: type | tuple[type, ...], path: str, *, required: bool = False) -> None:
    if key not in obj:
        if required:
            _fail(path, f"missing required field: {key}")
        return
    if not isinstance(obj[key], expected):
        names = expected.__name__ if isinstance(expected, type) else "|".join(t.__name__ for t in expected)
        _fail(path, f"{key} must be {names}")


def _enum(obj: dict[str, Any], key: str, allowed: set[str], path: str, *, required: bool = False) -> None:
    if key not in obj:
        if required:
            _fail(path, f"missing required field: {key}")
        return
    value = obj[key]
    if value not in allowed:
        _fail(path, f"{key} must be one of {sorted(allowed)}, got {value!r}")


def _string_list(obj: dict[str, Any], key: str, path: str, *, required: bool = False, non_empty: bool = False) -> None:
    if key not in obj:
        if required:
            _fail(path, f"missing required field: {key}")
        return
    value = obj[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _fail(path, f"{key} must be an array of strings")
    if non_empty and not value:
        _fail(path, f"{key} must not be empty")


def _object_list(obj: dict[str, Any], key: str, path: str, *, required: bool = False, non_empty: bool = False) -> None:
    if key not in obj:
        if required:
            _fail(path, f"missing required field: {key}")
        return
    value = obj[key]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        _fail(path, f"{key} must be an array of objects")
    if non_empty and not value:
        _fail(path, f"{key} must not be empty")


DECISION_MAKER_FIELDS = {
    "decision_maker_id",
    "lead_id",
    "company_name",
    "company_domain",
    "name",
    "title",
    "role_category",
    "seniority",
    "email",
    "email_type",
    "email_confidence",
    "phone",
    "linkedin",
    "xing",
    "source_type",
    "source_url",
    "source_query",
    "evidence_text",
    "contactability",
    "send_allowed",
    "confidence",
    "created_at",
}
DECISION_MAKER_REQUIRED = {
    "decision_maker_id",
    "lead_id",
    "company_name",
    "company_domain",
    "name",
    "role_category",
    "email_type",
    "source_type",
    "source_url",
    "contactability",
    "send_allowed",
    "confidence",
    "created_at",
}


def validate_decision_maker(row: dict[str, Any], path: str = "decision_maker") -> None:
    _allow_only(row, DECISION_MAKER_FIELDS, path)
    _require_keys(row, DECISION_MAKER_REQUIRED, path)
    for key in (
        "decision_maker_id",
        "lead_id",
        "company_name",
        "company_domain",
        "name",
        "role_category",
        "email_type",
        "source_type",
        "source_url",
        "contactability",
        "created_at",
    ):
        _type(row, key, str, path, required=key in DECISION_MAKER_REQUIRED)
    _enum(row, "role_category", {"procurement", "purchasing", "sourcing", "owner", "management", "product", "technical", "sales", "operations", "unknown"}, path, required=True)
    _enum(row, "seniority", {"executive", "director", "manager", "staff", "unknown"}, path)
    _enum(row, "email_type", {"public", "inferred", "unknown", "none"}, path, required=True)
    _enum(row, "source_type", {"official_site", "pdf", "directory", "linkedin", "xing", "search_snippet", "manual", "inferred"}, path, required=True)
    _enum(row, "contactability", {"email_public", "email_inferred", "profile_only", "phone_public", "name_only"}, path, required=True)
    _type(row, "send_allowed", bool, path, required=True)
    _score(row, "email_confidence", path)
    _score(row, "confidence", path, required=True)
    if row.get("send_allowed") and row.get("email_type") != "public":
        _fail(path, "send_allowed=true requires email_type=public")
    if row.get("send_allowed") and not row.get("email"):
        _fail(path, "send_allowed=true requires email")
    if row.get("email_type") == "inferred" and row.get("send_allowed"):
        _fail(path, "inferred email cannot be send_allowed")


LEAD_FIELDS = {
    "lead_id",
    "company_name",
    "website",
    "country",
    "region",
    "business_type",
    "industry",
    "description",
    "fit_score",
    "contactability_score",
    "evidence_score",
    "priority",
    "review_required",
    "uncertainty_reason",
    "missing_evidence",
    "source_quality",
    "official_site_found",
    "emails",
    "phones",
    "social",
    "decision_makers",
    "address",
    "source_queries",
    "source_urls",
    "evidence",
    "reject_reasons",
    "fit_reason_zh",
    "contact_source",
    "notes",
}
LEAD_REQUIRED = {"company_name", "website", "fit_score", "contactability_score", "priority"}


def _score(obj: dict[str, Any], key: str, path: str, *, required: bool = False) -> None:
    _type(obj, key, (int, float), path, required=required)
    if key in obj and not 0 <= float(obj[key]) <= 1:
        _fail(path, f"{key} must be between 0 and 1")


def validate_lead(row: dict[str, Any], path: str = "lead") -> None:
    _allow_only(row, LEAD_FIELDS, path)
    _require_keys(row, LEAD_REQUIRED, path)
    for key in ("company_name", "website"):
        _type(row, key, str, path, required=True)
    _score(row, "fit_score", path, required=True)
    _score(row, "contactability_score", path, required=True)
    _score(row, "evidence_score", path)
    _enum(row, "priority", {"high", "medium", "low", "reject"}, path, required=True)
    _type(row, "review_required", bool, path)
    _enum(row, "source_quality", {"official", "platform", "directory", "snippet", "mixed", "unknown"}, path)
    _type(row, "official_site_found", bool, path)
    _string_list(row, "business_type", path)
    _string_list(row, "missing_evidence", path)
    _string_list(row, "source_queries", path)
    _string_list(row, "source_urls", path)
    _object_list(row, "evidence", path)
    _object_list(row, "emails", path)
    _object_list(row, "decision_makers", path)
    if row.get("priority") != "reject":
        if not row.get("source_urls"):
            _fail(path, "non-reject lead requires at least one source_url")
        if not row.get("evidence") and not any(str(row.get(k) or "").strip() for k in ("description", "fit_reason_zh", "notes")):
            _fail(path, "non-reject lead requires evidence or fit text")
    if row.get("priority") in {"low"} and row.get("review_required") is not True:
        _fail(path, "low priority lead requires review_required=true")
    for i, item in enumerate(row.get("evidence") or []):
        item_path = f"{path}.evidence[{i}]"
        _require_keys(item, {"claim", "source_url"}, item_path)
        _type(item, "claim", str, item_path, required=True)
        _type(item, "source_url", str, item_path, required=True)
    for i, email in enumerate(row.get("emails") or []):
        email_path = f"{path}.emails[{i}]"
        _require_keys(email, {"email", "type", "source_url", "domain_relation", "verification", "confidence"}, email_path)
        _type(email, "email", str, email_path, required=True)
        _enum(email, "type", {"generic", "person", "inferred"}, email_path, required=True)
        _enum(email, "domain_relation", {"same_domain", "parent_domain", "third_party", "free_mail", "unknown"}, email_path, required=True)
        _enum(email, "verification", {"format_only"}, email_path, required=True)
        _score(email, "confidence", email_path, required=True)
    for i, dm in enumerate(row.get("decision_makers") or []):
        dm_path = f"{path}.decision_makers[{i}]"
        if any(key in dm for key in DECISION_MAKER_REQUIRED):
            validate_decision_maker(dm, dm_path)
        else:
            for key in ("name", "title", "email", "linkedin", "source_url"):
                _type(dm, key, str, dm_path)


OUTREACH_CANDIDATE_FIELDS = {
    "candidate_id",
    "lead_id",
    "company_name",
    "company_domain",
    "country",
    "priority",
    "selected_channel",
    "selected_recipient_email",
    "recipient_type",
    "domain_relation",
    "recipient_rank",
    "recipient_risk",
    "draft_allowed",
    "auto_send_allowed",
    "selection_reason",
    "blocked_reason",
    "source_urls",
    "created_at",
}
OUTREACH_CANDIDATE_REQUIRED = {
    "candidate_id",
    "lead_id",
    "company_name",
    "company_domain",
    "priority",
    "selected_channel",
    "draft_allowed",
    "selection_reason",
    "created_at",
}


def validate_outreach_candidate(row: dict[str, Any], path: str = "outreach_candidate") -> None:
    _allow_only(row, OUTREACH_CANDIDATE_FIELDS, path)
    _require_keys(row, OUTREACH_CANDIDATE_REQUIRED, path)
    for key in ("candidate_id", "lead_id", "company_name", "company_domain", "created_at"):
        _type(row, key, str, path, required=key in OUTREACH_CANDIDATE_REQUIRED)
    _enum(row, "priority", {"high", "medium", "low", "reject"}, path, required=True)
    _enum(row, "selected_channel", {"email", "contact_form", "review_only", "skip"}, path, required=True)
    _enum(row, "recipient_type", {"generic", "person", "inferred", "none"}, path)
    _enum(row, "domain_relation", {"same_domain", "parent_domain", "third_party", "free_mail", "unknown", "none"}, path)
    _enum(row, "recipient_risk", {"low", "medium", "high"}, path)
    _type(row, "recipient_rank", int, path)
    _type(row, "draft_allowed", bool, path, required=True)
    _type(row, "auto_send_allowed", bool, path)
    _string_list(row, "source_urls", path)
    if row.get("selected_channel") == "email" and not row.get("selected_recipient_email"):
        _fail(path, "email channel requires selected_recipient_email")
    if row.get("draft_allowed") and row.get("selected_channel") not in {"email", "contact_form"}:
        _fail(path, "draft_allowed=true requires selected_channel=email or contact_form")
    if row.get("auto_send_allowed") and not row.get("draft_allowed"):
        _fail(path, "auto_send_allowed=true requires draft_allowed=true")


OUTREACH_DRAFT_FIELDS = {
    "draft_id",
    "draft_version",
    "template_id",
    "template_cluster_key",
    "lead_id",
    "candidate_id",
    "company_domain",
    "company_name",
    "website",
    "country",
    "region",
    "recipient_email",
    "recipient_type",
    "recipient_name",
    "recipient_title",
    "language",
    "language_confidence",
    "language_reason",
    "fallback_language",
    "localization_risk",
    "subject",
    "body_text",
    "personalization_points",
    "source_urls",
    "claims_made",
    "offer_angle",
    "cta",
    "opt_out_line",
    "send_recommendation",
    "risk_flags",
    "approval_status",
    "state",
    "approved_by",
    "approved_at",
    "approved_body_hash",
    "review_notes",
    "created_at",
    "sent_at",
    "send_result",
}


OUTREACH_TEMPLATE_FIELDS = {
    "template_id",
    "cluster_key",
    "country",
    "language",
    "buyer_role",
    "product_angle",
    "subject_template",
    "body_template",
    "required_variables",
    "tone_notes",
    "claim_boundaries",
    "created_at",
}
OUTREACH_TEMPLATE_REQUIRED = OUTREACH_TEMPLATE_FIELDS


def validate_outreach_template(row: dict[str, Any], path: str = "outreach_template") -> None:
    _allow_only(row, OUTREACH_TEMPLATE_FIELDS, path)
    _require_keys(row, OUTREACH_TEMPLATE_REQUIRED, path)
    for key in (
        "template_id",
        "cluster_key",
        "country",
        "language",
        "buyer_role",
        "product_angle",
        "subject_template",
        "body_template",
        "created_at",
    ):
        _type(row, key, str, path, required=True)
        if not str(row.get(key) or "").strip():
            _fail(path, f"{key} must not be empty")
    _string_list(row, "required_variables", path, required=True, non_empty=True)
    _string_list(row, "tone_notes", path, required=True)
    _string_list(row, "claim_boundaries", path, required=True)
    for required in ("company_name", "product", "application", "personalization_reason", "cta", "signature", "opt_out"):
        if required not in row["required_variables"]:
            _fail(path, f"required_variables must include {required}")
    template_text = row["subject_template"] + "\n" + row["body_template"]
    for variable in row["required_variables"]:
        if "{" + variable + "}" not in template_text:
            _fail(path, f"template does not use required variable {{{variable}}}")
    placeholders = set(re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", template_text))
    missing_variables = sorted(placeholders - set(row["required_variables"]))
    if missing_variables:
        _fail(path, "template placeholders missing from required_variables: " + ", ".join(missing_variables))


OUTREACH_DRAFT_REQUIRED = {
    "draft_id",
    "draft_version",
    "lead_id",
    "company_name",
    "website",
    "country",
    "recipient_email",
    "recipient_type",
    "language",
    "language_confidence",
    "language_reason",
    "subject",
    "body_text",
    "personalization_points",
    "source_urls",
    "offer_angle",
    "cta",
    "send_recommendation",
    "approval_status",
    "state",
    "created_at",
}


def validate_outreach_draft(row: dict[str, Any], path: str = "outreach_draft") -> None:
    _allow_only(row, OUTREACH_DRAFT_FIELDS, path)
    _require_keys(row, OUTREACH_DRAFT_REQUIRED, path)
    for key in (
        "draft_id",
        "lead_id",
        "company_name",
        "website",
        "country",
        "recipient_email",
        "language",
        "language_reason",
        "subject",
        "body_text",
        "offer_angle",
        "cta",
        "created_at",
    ):
        _type(row, key, str, path, required=key in OUTREACH_DRAFT_REQUIRED)
    _type(row, "draft_version", int, path, required=True)
    _enum(row, "recipient_type", {"generic", "person", "inferred"}, path, required=True)
    _enum(row, "language_confidence", {"high", "medium", "low"}, path, required=True)
    _enum(row, "localization_risk", {"low", "medium", "high"}, path)
    _enum(row, "send_recommendation", {"send", "review", "skip"}, path, required=True)
    _enum(row, "approval_status", {"pending", "approved", "rejected"}, path, required=True)
    _enum(
        row,
        "state",
        {
            "drafted",
            "review_pending",
            "approved",
            "dry_run_checked",
            "queued",
            "sending",
            "sent",
            "failed_retryable",
            "failed_final",
            "suppressed",
            "skipped",
        },
        path,
        required=True,
    )
    _object_list(row, "personalization_points", path, required=True, non_empty=True)
    _string_list(row, "source_urls", path, required=True, non_empty=True)
    _object_list(row, "claims_made", path)
    _string_list(row, "risk_flags", path)
    if row.get("approval_status") == "approved" and not row.get("approved_body_hash"):
        _fail(path, "approved draft requires approved_body_hash")
    for i, point in enumerate(row.get("personalization_points", [])):
        _require_keys(point, {"claim", "source_url"}, f"{path}.personalization_points[{i}]")
        _type(point, "claim", str, f"{path}.personalization_points[{i}]", required=True)
        _type(point, "source_url", str, f"{path}.personalization_points[{i}]", required=True)
    for i, claim in enumerate(row.get("claims_made", []) or []):
        claim_path = f"{path}.claims_made[{i}]"
        _require_keys(claim, {"claim", "claim_type", "support", "risk"}, claim_path)
        _enum(claim, "claim_type", {"about_sender", "about_recipient", "about_fit"}, claim_path, required=True)
        _enum(claim, "risk", {"low", "medium", "high"}, claim_path, required=True)


def validate_approved_outreach(row: dict[str, Any], path: str = "approved_outreach") -> None:
    validate_outreach_draft(row, path)
    if row.get("approval_status") != "approved":
        _fail(path, "approved-outreach record requires approval_status=approved")
    if row.get("state") != "approved":
        _fail(path, "approved-outreach record requires state=approved")
    if row.get("send_recommendation") != "send":
        _fail(path, "approved-outreach record requires send_recommendation=send")
    if not row.get("approved_by"):
        _fail(path, "approved-outreach record requires approved_by")
    if not row.get("approved_at"):
        _fail(path, "approved-outreach record requires approved_at")


SENT_LOG_FIELDS = {
    "event_id",
    "event_type",
    "draft_id",
    "lead_id",
    "recipient_email",
    "company_domain",
    "subject",
    "approved_body_hash",
    "message_id",
    "smtp_response",
    "timestamp",
    "result",
    "error",
}
SENT_LOG_REQUIRED = {"event_id", "event_type", "draft_id", "lead_id", "recipient_email", "company_domain", "timestamp", "result"}


def validate_sent_log_event(row: dict[str, Any], path: str = "sent_log_event") -> None:
    _allow_only(row, SENT_LOG_FIELDS, path)
    _require_keys(row, SENT_LOG_REQUIRED, path)
    _enum(
        row,
        "event_type",
        {
            "dry_run",
            "queued",
            "send_attempt",
            "send_success",
            "send_failure",
            "suppressed",
            "duplicate_skipped",
            "hash_mismatch",
            "evaluation_missing",
            "approval_missing",
        },
        path,
        required=True,
    )
    _enum(row, "result", {"ok", "skipped", "failed"}, path, required=True)
    for key in SENT_LOG_FIELDS:
        if key in row:
            _type(row, key, str, path)


SMTP_CONFIG_FIELDS = {
    "smtp_host",
    "smtp_port",
    "use_ssl",
    "use_starttls",
    "username",
    "password_env",
    "from_name",
    "from_email",
    "reply_to",
    "daily_limit",
    "delay_seconds",
    "max_per_company",
}


def validate_smtp_config(row: dict[str, Any], path: str = "smtp_config") -> None:
    _allow_only(row, SMTP_CONFIG_FIELDS, path)
    _require_keys(row, {"smtp_host", "smtp_port", "username", "password_env", "from_email"}, path)
    for key in ("smtp_host", "username", "password_env", "from_email"):
        _type(row, key, str, path, required=True)
        if not str(row.get(key) or "").strip():
            _fail(path, f"{key} must not be empty")
    for key in ("smtp_port", "daily_limit", "delay_seconds", "max_per_company"):
        _type(row, key, int, path)
    _type(row, "use_ssl", bool, path)
    _type(row, "use_starttls", bool, path)


SENDER_PROFILE_FIELDS = {
    "company_name",
    "website",
    "sender_name",
    "sender_title",
    "from_email",
    "reply_to",
    "product_lines",
    "target_applications",
    "strengths",
    "certifications",
    "allowed_claims",
    "forbidden_claims",
    "localized_product_lines",
    "localized_target_applications",
    "catalog_url",
    "signature",
}


def validate_sender_profile(row: dict[str, Any], path: str = "sender_profile") -> None:
    _allow_only(row, SENDER_PROFILE_FIELDS, path)
    _require_keys(row, {"company_name", "website", "sender_name", "sender_title", "from_email", "reply_to", "product_lines", "allowed_claims", "forbidden_claims", "signature"}, path)
    for key in ("company_name", "website", "sender_name", "sender_title", "from_email", "reply_to", "signature"):
        _type(row, key, str, path, required=True)
        if not str(row.get(key) or "").strip():
            _fail(path, f"{key} must not be empty")
    for key in ("product_lines", "target_applications", "strengths", "certifications", "allowed_claims", "forbidden_claims"):
        _string_list(row, key, path, required=key in {"product_lines", "allowed_claims", "forbidden_claims"})
    for key in ("localized_product_lines", "localized_target_applications"):
        if key in row:
            _type(row, key, dict, path)
            for lang, values in row[key].items():
                if not isinstance(lang, str) or not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                    _fail(path, f"{key} must map language strings to arrays of strings")
    if not row.get("product_lines"):
        _fail(path, "product_lines must not be empty")


CUSTOMS_VERIFICATION_FIELDS = {
    "company_name",
    "confirmed_import_activity",
    "confirmed_asia_import_signal",
    "fit_score_adjustment",
    "evidence",
}
CUSTOMS_EVIDENCE_FIELDS = {
    "source_url",
    "platform",
    "title",
    "shipment_count",
    "latest_shipment_date",
    "hs_codes",
    "suppliers",
    "asia_origin_terms",
    "snippet",
    "confidence",
}


def validate_customs_verification(row: dict[str, Any], path: str = "customs_verification") -> None:
    _allow_only(row, CUSTOMS_VERIFICATION_FIELDS, path)
    _require_keys(row, CUSTOMS_VERIFICATION_FIELDS, path)
    _type(row, "company_name", str, path, required=True)
    _type(row, "confirmed_import_activity", bool, path, required=True)
    _type(row, "confirmed_asia_import_signal", bool, path, required=True)
    _type(row, "fit_score_adjustment", int, path, required=True)
    if row["fit_score_adjustment"] not in {0, 1, 2}:
        _fail(path, "fit_score_adjustment must be 0, 1, or 2")
    _object_list(row, "evidence", path, required=True)
    for i, item in enumerate(row.get("evidence") or []):
        item_path = f"{path}.evidence[{i}]"
        _allow_only(item, CUSTOMS_EVIDENCE_FIELDS, item_path)
        _require_keys(item, CUSTOMS_EVIDENCE_FIELDS, item_path)
        _enum(item, "platform", {"panjiva", "importgenius", "importyeti", "uktradeinfo", "web"}, item_path, required=True)
        for key in ("source_url", "title", "latest_shipment_date", "snippet"):
            _type(item, key, str, item_path, required=True)
        if item["shipment_count"] is not None and not isinstance(item["shipment_count"], int):
            _fail(item_path, "shipment_count must be integer or null")
        _string_list(item, "hs_codes", item_path, required=True)
        _string_list(item, "suppliers", item_path, required=True)
        _string_list(item, "asia_origin_terms", item_path, required=True)
        _type(item, "confidence", (int, float), item_path, required=True)
        if not 0 <= float(item["confidence"]) <= 1:
            _fail(item_path, "confidence must be between 0 and 1")


OUTREACH_EVALUATION_FIELDS = {
    "evaluation_id",
    "draft_id",
    "lead_id",
    "company_name",
    "recipient_email",
    "language",
    "evaluated_body_hash",
    "language_fit_score",
    "personalization_score",
    "claim_risk_score",
    "spam_risk_score",
    "reply_likelihood_score",
    "overall_score",
    "decision",
    "blocking_reasons",
    "review_reasons",
    "recommended_actions",
    "created_at",
}
OUTREACH_EVALUATION_REQUIRED = OUTREACH_EVALUATION_FIELDS


def validate_outreach_evaluation(row: dict[str, Any], path: str = "outreach_evaluation") -> None:
    _allow_only(row, OUTREACH_EVALUATION_FIELDS, path)
    _require_keys(row, OUTREACH_EVALUATION_REQUIRED, path)
    for key in ("evaluation_id", "draft_id", "lead_id", "company_name", "recipient_email", "language", "evaluated_body_hash", "created_at"):
        _type(row, key, str, path, required=True)
    for key in (
        "language_fit_score",
        "personalization_score",
        "claim_risk_score",
        "spam_risk_score",
        "reply_likelihood_score",
        "overall_score",
    ):
        _type(row, key, (int, float), path, required=True)
        if not 0 <= float(row[key]) <= 1:
            _fail(path, f"{key} must be between 0 and 1")
    _enum(row, "decision", {"pass", "review", "reject"}, path, required=True)
    _string_list(row, "blocking_reasons", path, required=True)
    _string_list(row, "review_reasons", path, required=True)
    _string_list(row, "recommended_actions", path, required=True)
    if row["decision"] == "pass" and row["blocking_reasons"]:
        _fail(path, "decision=pass requires empty blocking_reasons")
    if row["decision"] == "reject" and not row["blocking_reasons"]:
        _fail(path, "decision=reject requires at least one blocking_reason")

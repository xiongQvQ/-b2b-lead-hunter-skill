# Outreach Compliance

This skill may support B2B outreach only as an explicit, approved stage. The default mode is draft generation.

## Mandatory Rules

- Use public business contact data only.
- Send only from an authorized mailbox controlled by the user.
- Identify the sender truthfully; do not imply a prior relationship.
- Include a simple opt-out line in every first-touch email.
- Do not send to suppressed emails, domains, or companies.
- Do not send to inferred emails automatically.
- Do not use SMTP ping verification.
- Do not attach files unless the user explicitly approves the attachment and recipient list.
- Do not bypass privacy, anti-spam, platform, or mailbox provider limits.

## Regional Caution

For EU/UK leads, keep the message clearly B2B, relevant to the recipient's role/company, and easy to opt out from. Use official company emails or role inboxes when possible.

For US/Canada/Australia leads, include truthful sender information, no misleading subject lines, and an opt-out/stop-contact mechanism.

For regions where local language or consent rules are unclear, generate drafts for manual review instead of sending.

## Approval Gate

Before any send, verify:

- `priority` is `high` or strong `medium`.
- `source_urls` support the business fit and personalization.
- Recipient email is not `inferred`, `free_mail`, or third-party-only.
- `approval_status=approved`.
- `approved_body_hash` matches the exact recipient, subject, body, and opt-out line.
- `language_confidence=high`; medium or low confidence requires manual editing/review.
- No `claims_made` item has `risk=high`.
- The recipient, domain, and company are not suppressed.
- Prior `sent-log.jsonl` does not show an earlier first-touch email to the same company.

Suppression matching order:

1. Exact recipient email.
2. Exact normalized domain.
3. Normalized company name.

## Logging

Every dry run and send attempt should be recorded with timestamp, recipient, company, subject, draft id, action, result, and error if any. Also log skipped sends caused by suppression, duplicate detection, missing approval, or body-hash mismatch. Logs are audit records and should not be rewritten.

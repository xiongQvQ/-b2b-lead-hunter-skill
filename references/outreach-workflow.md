# Outreach Workflow

Outreach is a separate stage after lead qualification. Do not generate or send emails from raw search results, candidates, rejected leads, or directory-only records.

For concrete command parameters, sender profile fields, SMTP config, regional template generation, approval hashes, and sending gates, see `outreach-parameter-guide.md`.

## Inputs

Required files:

- `brief.json`: seller context, product, ICP, regions, negative criteria.
- `leads.jsonl`: qualified lead records with evidence, contacts, and priority.
- `sender-profile.json`: sender identity, offer, allowed claims, forbidden claims, and signature.

Optional files:

- `suppression-list.csv`: emails, domains, and companies that must not be contacted.
- Prior `sent-log.jsonl`: used to prevent duplicate outreach.

Recommended file flow:

```text
leads.jsonl
  -> outreach-candidates.jsonl
  -> outreach-templates.jsonl
  -> outreach-drafts.jsonl
  -> outreach-evaluations.jsonl
  -> outreach-review.csv
  -> approved-outreach.jsonl
  -> sent-log.jsonl
  -> outreach-report.md
```

## Stable IDs

Every outreach-capable lead should have a stable `lead_id`. If missing, derive it from normalized company domain plus a short hash of company name and country. Every draft must have a stable `draft_id` derived from `lead_id`, recipient email hash, language, and `draft_version`.

Use stable IDs for dedupe, approval, log correlation, and reruns.

## Stage 1: Select Outreach Candidates

Generate `outreach-candidates.jsonl` before drafting. This stage decides which recipient, if any, should receive the first-touch email.

Allowed for draft generation:

- `priority=high`, or strong `priority=medium`.
- Official website found.
- Buyer-role evidence exists.
- At least one same-domain business email, contact form, or named professional contact.

Keep in review:

- Generic email only.
- Local-language uncertainty.
- Weak personalization evidence.
- Decision maker found but email is inferred.

Skip:

- `low` or `reject`.
- Directory-only records.
- Free-mail-only contacts.
- Inferred-only emails.
- Competitor manufacturers unless user explicitly wants channel mapping.

Recipient selection priority:

1. Same-domain named decision maker email with public role evidence from `decision_makers`.
2. Same-domain role inbox related to sales, purchase, sourcing, info, or general business contact.
3. Official contact form when no email is available.
4. Generic directory or third-party email only for manual review.

Do not select `inferred` recipients for automatic sending.

## Stage 2: Generate Regional Templates

Generate `outreach-templates.jsonl` before final drafts. Use one base template per:

```text
country + language + buyer_role + product_angle
```

Templates control regional language, greeting style, formality, subject shape, CTA wording, opt-out wording, and claim boundaries. Templates must not be sent directly. They are only used to render company-specific drafts.

Required template variables:

- `company_name`
- `country`
- `greeting`
- `sender_company`
- `product`
- `application`
- `personalization_reason`
- `cta`
- `signature`
- `opt_out`

## Stage 2.5: Generate Company Drafts

Hermes generates `outreach-drafts.jsonl` from `outreach-templates.jsonl`, `outreach-candidates.jsonl`, `leads.jsonl`, and `sender-profile.json`. Each draft must include:

- Recipient email and type.
- Language decision, confidence, and reason.
- Subject and plain-text body.
- Product/offer angle.
- One to three personalization points tied to `source_urls`.
- Claims made about sender, recipient, and fit, each with source or sender-profile support.
- Clear CTA, normally asking whether they handle this category or want a catalog/spec sheet.
- Truthful sender identity.
- Opt-out/stop-contact sentence.
- `send_recommendation`: `send`, `review`, or `skip`.
- `template_id` and `template_cluster_key` when rendered from a regional template.

Do not invent certifications, customers, prices, stock, local offices, or prior relationship.

Language gate:

- `language_confidence=high`: eligible for approval.
- `language_confidence=medium`: review required.
- `language_confidence=low`: do not send; regenerate in English or keep for manual editing.

## Stage 2.75: Evaluate Drafts

Run `evaluate_outreach_drafts.py` after draft generation. It writes `outreach-evaluations.jsonl` and optional `outreach-review.csv`.

SMTP dry-run and sending require a matching evaluation with `decision=pass` for each `draft_id`. A human-approved record without a passing evaluation remains blocked.

The evaluation is bound to the exact email content by `evaluated_body_hash`. If subject, body, recipient, or opt-out changes after evaluation, rerun evaluation and approval.

## Stage 3: Human Approval

The user or reviewer moves approved records into `approved-outreach.jsonl`. Do not send records with `approval_status=pending`, `approval_status=rejected`, or `send_recommendation=review|skip`.

Approval should verify:

- The company is a plausible buyer or channel partner.
- The language is appropriate.
- The personalization claim is supported by a source URL.
- The CTA is low-pressure and commercially relevant.
- No suppression entry matches the email, domain, or company.
- The exact approved body is locked by `approved_body_hash`.

Approval fields:

- `approved_by`
- `approved_at`
- `approved_body_hash`
- `draft_version`

If subject, body, recipient, or opt-out line changes after approval, the body hash is invalid and the draft must be reviewed again.

## Stage 3.5: State Machine

Use these states consistently in draft, review, and send logs:

```text
drafted
review_pending
approved
dry_run_checked
queued
sending
sent
failed_retryable
failed_final
suppressed
skipped
```

Sending scripts must be idempotent: rerunning a command must not resend a draft already logged as `sent`.

## Stage 4: SMTP Sending

SMTP sending is deterministic plumbing. It must:

- Read credentials from environment variables or local untracked config.
- Support dry-run mode.
- Send only `approval_status=approved`.
- Verify `approved_body_hash` against the exact recipient, subject, body, and opt-out line.
- Enforce one first-touch email per company by default.
- Apply daily limits and delay between sends.
- Check `suppression-list.csv` and prior `sent-log.jsonl`.
- Write every attempt to `sent-log.jsonl`.

Recommended command shape for future scripts:

```bash
python scripts/send_smtp.py \
  --drafts lead-runs/<slug>/approved-outreach.jsonl \
  --smtp-config smtp-config.json \
  --sent-log lead-runs/<slug>/sent-log.jsonl \
  --dry-run
```

Use `--send-approved` only after reviewing the dry run.

# Outreach Parameter Guide

This guide explains how to configure outreach after qualified `leads.jsonl` exists. The required generation strategy is:

```text
regional/language template + company-specific personalization variables
```

Do not send a pure regional template. Do not send a fully free-written email unless it has passed `evaluate_outreach_drafts.py` and manual approval.

## Required Files

Create these files in one run directory:

```text
lead-runs/<slug>/
├── leads.jsonl
├── sender-profile.json
├── suppression-list.csv
└── sent-log.jsonl              # can be empty or absent before first run
```

SMTP config can be per-run or shared:

```text
lead-runs/<slug>/smtp-config.json          # per-run override
hermes-skills/business/b2b-lead-hunter/_shared/smtp-config.json  # shared default in source repo
<hermes-skill-install>/_shared/smtp-config.json                   # shared default after install
```

Generated files:

```text
lead-runs/<slug>/
├── outreach-candidates.jsonl
├── outreach-templates.jsonl
├── outreach-drafts.jsonl
├── outreach-evaluations.jsonl
├── outreach-review.csv
├── approved-outreach.jsonl
└── sent-log.jsonl
```

## Sender Profile

`sender-profile.json` controls identity and allowed claims. The scripts will not invent sender facts.

Minimal example:

```json
{
  "company_name": "Example Export Co.",
  "website": "https://www.example-export.com",
  "sender_name": "Sales Team",
  "sender_title": "Export Sales",
  "from_email": "sales@example-export.com",
  "reply_to": "sales@example-export.com",
  "product_lines": ["electrical switches"],
  "target_applications": ["industrial equipment, appliances, and control panels"],
  "localized_product_lines": {
    "de": ["elektrische Schalter"],
    "pl": ["przelaczniki elektryczne"]
  },
  "localized_target_applications": {
    "de": ["Industrieanlagen, Haushaltsgeraete und Schalttafeln"],
    "pl": ["urzadzenia przemyslowe, AGD i panele sterowania"]
  },
  "strengths": ["OEM/ODM support", "export packaging", "small-batch trial orders"],
  "certifications": [],
  "allowed_claims": [
    "We supply electrical switches for industrial equipment, appliances, and control panels.",
    "We can provide catalog, specifications, and quotation details on request."
  ],
  "forbidden_claims": [
    "Do not claim local stock unless confirmed.",
    "Do not claim certifications unless listed in this profile.",
    "Do not mention existing customers unless provided by the user."
  ],
  "catalog_url": "",
  "signature": "Sales Team\nExample Export Co.\nsales@example-export.com\nhttps://www.example-export.com"
}
```

Validate:

```bash
python scripts/validate_artifact.py sender-profile lead-runs/<slug>/sender-profile.json
```

`localized_product_lines` and `localized_target_applications` are optional but recommended for non-English outreach. They prevent mixed-language emails where the template is local-language but product/application variables stay in English.

## SMTP Config

`smtp-config.json` controls sending. Do not put a plaintext password in this file. Use `password_env`.

Resolution order used by `send_smtp.py`:

1. `--smtp-config <path>` if provided.
2. `$B2B_LEAD_HUNTER_SMTP_CONFIG` if set.
3. `<skill>/_shared/smtp-config.json`.

```json
{
  "smtp_host": "smtp.example.com",
  "smtp_port": 587,
  "use_starttls": true,
  "username": "sales@example.com",
  "password_env": "SMTP_APP_PASSWORD",
  "from_name": "Example Export Co.",
  "from_email": "sales@example.com",
  "reply_to": "sales@example.com",
  "daily_limit": 20,
  "delay_seconds": 120,
  "max_per_company": 1
}
```

For SSL-only providers (e.g., QQ Exmail port 465), use `use_ssl` instead:

```json
{
  "smtp_host": "smtp.exmail.qq.com",
  "smtp_port": 465,
  "use_ssl": true,
  "username": "linda@gdushun.com",
  "password_env": "SMTP_APP_PASSWORD",
  "from_name": "Sales Team",
  "from_email": "linda@gdushun.com",
  "reply_to": "linda@gdushun.com",
  "daily_limit": 20,
  "delay_seconds": 120,
  "max_per_company": 1
}
```

Do not set both `use_ssl` and `use_starttls` — they are mutually exclusive. See `references/smtp-qq-exmail.md` for QQ Exmail specifics.

Set the password in the shell:

```bash
export SMTP_APP_PASSWORD='your-mailbox-app-password'
```

Validate:

```bash
python scripts/validate_artifact.py smtp-config _shared/smtp-config.json
```

## Suppression List

`suppression-list.csv` blocks emails, domains, or companies.

```csv
type,value,reason
email,buyer@example.com,opt-out
domain,example.com,opt-out
company,Example GmbH,opt-out
```

Use exact normalized domains, not URLs, when possible.

## Outreach Candidate Parameters

Command:

```bash
python scripts/validate_artifact.py leads lead-runs/<slug>/leads.jsonl

python scripts/prepare_outreach.py lead-runs/<slug>/leads.jsonl \
  --suppression-list lead-runs/<slug>/suppression-list.csv \
  --sent-log lead-runs/<slug>/sent-log.jsonl \
  --output lead-runs/<slug>/outreach-candidates.jsonl
```

Parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `leads_jsonl` | yes | Qualified lead records. Use strict/high-quality `leads.jsonl`, not raw candidates. |
| `--suppression-list` | recommended | Blocks known opt-outs and excluded domains/companies. |
| `--sent-log` | recommended | Prevents duplicate first-touch emails to the same company. |
| `--output` | yes | Destination JSONL. |

Rules enforced:

- `low` and `reject` leads are not draftable.
- Directory/snippet-only leads are blocked.
- Inferred, free-mail, and third-party emails are not selected for sending.
- Same-domain person emails rank above generic role inboxes.

Validate:

```bash
python scripts/validate_artifact.py outreach-candidates lead-runs/<slug>/outreach-candidates.jsonl
```

## Template Cluster Parameters

Command:

```bash
python scripts/generate_outreach_templates.py \
  --leads lead-runs/<slug>/leads.jsonl \
  --candidates lead-runs/<slug>/outreach-candidates.jsonl \
  --sender-profile lead-runs/<slug>/sender-profile.json \
  --template-library lead-runs/<slug>/template-library \
  --output lead-runs/<slug>/outreach-templates.jsonl
```

Optional language override:

```bash
python scripts/generate_outreach_templates.py \
  --leads lead-runs/<slug>/leads.jsonl \
  --candidates lead-runs/<slug>/outreach-candidates.jsonl \
  --sender-profile lead-runs/<slug>/sender-profile.json \
  --language de \
  --output lead-runs/<slug>/outreach-templates.jsonl
```

Parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `--leads` | yes | Lead data used to identify country and buyer role. |
| `--candidates` | yes | Outreach candidates used to select email-capable leads. |
| `--sender-profile` | yes | Product, application, identity, claim boundaries. |
| `--output` | yes | Destination `outreach-templates.jsonl`. |
| `--language` | optional | Force one language for all template clusters. Use sparingly. |
| `--template-library` | optional | JSON/JSONL file or directory of human-maintained templates. Matching `cluster_key` overrides generated defaults. |

Default language selection:

| Country | Template language |
| --- | --- |
| Germany, Austria, Switzerland | `de` |
| France | `fr` |
| Spain | `es` |
| Italy | `it` |
| Poland | `pl` |
| Netherlands | `nl` |
| Portugal, Brazil | `pt` |
| Turkey | `tr` |
| Japan | `ja` |
| Korea | `ko` |
| US, UK, Canada, Australia, Singapore, UAE, Hong Kong | `en` |
| Unknown country | `en` |

Cluster key format:

```text
country-language-buyer_role-product_angle
```

Example:

```text
germany-de-distributor-electrical-switches
```

Validate:

```bash
python scripts/validate_artifact.py outreach-templates lead-runs/<slug>/outreach-templates.jsonl
```

Human-maintained template library records must follow `templates/outreach-template.schema.json`. The most important field is `cluster_key`, for example:

```text
germany-de-distributor-electrical-switches
```

If a library template matches the generated cluster key, it is used instead of the default deterministic template.

## Draft Generation Parameters

Command:

```bash
python scripts/generate_outreach_drafts.py \
  --leads lead-runs/<slug>/leads.jsonl \
  --candidates lead-runs/<slug>/outreach-candidates.jsonl \
  --sender-profile lead-runs/<slug>/sender-profile.json \
  --templates lead-runs/<slug>/outreach-templates.jsonl \
  --require-template \
  --output lead-runs/<slug>/outreach-drafts.jsonl
```

Parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `--leads` | yes | Lead evidence and company data. |
| `--candidates` | yes | Selected contact channel and recipient. |
| `--sender-profile` | yes | Sender identity and allowed claims. |
| `--templates` | yes for stable operation | Regional/language templates from the prior stage. |
| `--require-template` | strongly required | Fail if a candidate has no matching template. Prevents silent fallback to free-form English. |
| `--language` | optional | Force language if not using generated templates. Prefer template stage instead. |
| `--output` | yes | Destination `outreach-drafts.jsonl`. |

Company-specific variables filled into templates:

| Variable | Source |
| --- | --- |
| `company_name` | `outreach-candidates.company_name` |
| `country` | candidate or lead country |
| `greeting` | named recipient if available, otherwise team |
| `sender_company` | `sender-profile.company_name` |
| `product` | first `sender-profile.product_lines` item |
| `application` | first `sender-profile.target_applications` item |
| `personalization_reason` | `lead.evidence[0].claim`, or fallback company-fit text |
| `cta` | localized low-friction routing CTA |
| `signature` | `sender-profile.signature` |
| `opt_out` | localized opt-out sentence |

Important behavior:

- With `--require-template`, missing template means hard failure.
- Drafts include `template_id` and `template_cluster_key`.
- Non-English template variables are localized conservatively. Chinese `fit_reason_zh` is not copied into a German/French/etc. email body.
- If `sender-profile.json` has `localized_product_lines` or `localized_target_applications`, those values are used in matching language drafts.
- Drafts remain `approval_status=pending`.

Validate:

```bash
python scripts/validate_artifact.py outreach-drafts lead-runs/<slug>/outreach-drafts.jsonl
```

## Evaluation Parameters

Command:

```bash
python scripts/evaluate_outreach_drafts.py \
  --drafts lead-runs/<slug>/outreach-drafts.jsonl \
  --output lead-runs/<slug>/outreach-evaluations.jsonl \
  --review-csv lead-runs/<slug>/outreach-review.csv \
  --min-pass-score 0.72
```

Parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `--drafts` | yes | Drafts to score. |
| `--output` | yes | Evaluation JSONL. |
| `--review-csv` | recommended | Human review queue. |
| `--min-pass-score` | optional | Default `0.72`. Raises or lowers automatic pass threshold. |

Scores:

| Score | Meaning |
| --- | --- |
| `language_fit_score` | Region/language fit. |
| `personalization_score` | Source-backed, company-specific relevance. |
| `claim_risk_score` | Whether claims are safe and supported. |
| `spam_risk_score` | Spam-like phrases, length, links, opt-out. |
| `reply_likelihood_score` | CTA quality and recipient specificity. |
| `overall_score` | Weighted final quality score. |
| `evaluated_body_hash` | Hash of recipient, subject, body, and opt-out at evaluation time. Must match approval hash before send. |

Decisions:

| Decision | Sendable? | Meaning |
| --- | --- | --- |
| `pass` | yes, after human approval | Eligible for `approved-outreach.jsonl`. |
| `review` | no | Rewrite, local-language review, or find a better contact. |
| `reject` | no | Missing hard requirement such as opt-out or source-backed personalization. |

Validate:

```bash
python scripts/validate_artifact.py outreach-evaluations lead-runs/<slug>/outreach-evaluations.jsonl
```

## Approval Parameters

To approve a draft, copy only `decision=pass` records from `outreach-drafts.jsonl` into `approved-outreach.jsonl` and set:

```json
{
  "approval_status": "approved",
  "state": "approved",
  "send_recommendation": "send",
  "approved_by": "xiongbojian",
  "approved_at": "2026-05-26T00:00:00Z",
  "approved_body_hash": "..."
}
```

Compute hashes:

```bash
python scripts/send_smtp.py \
  --drafts lead-runs/<slug>/outreach-drafts.jsonl \
  --print-approval-hashes
```

Validate:

```bash
python scripts/validate_artifact.py approved-outreach lead-runs/<slug>/approved-outreach.jsonl
```

## Sending Parameters

Dry-run is mandatory before real sending:

```bash
python scripts/send_smtp.py \
  --drafts lead-runs/<slug>/approved-outreach.jsonl \
  --sent-log lead-runs/<slug>/sent-log.jsonl \
  --evaluations lead-runs/<slug>/outreach-evaluations.jsonl \
  --suppression-list lead-runs/<slug>/suppression-list.csv \
  --dry-run
```

Send:

```bash
python scripts/send_smtp.py \
  --drafts lead-runs/<slug>/approved-outreach.jsonl \
  --sent-log lead-runs/<slug>/sent-log.jsonl \
  --evaluations lead-runs/<slug>/outreach-evaluations.jsonl \
  --suppression-list lead-runs/<slug>/suppression-list.csv \
  --send-approved
```

Parameters:

| Parameter | Required | Meaning |
| --- | --- | --- |
| `--drafts` | yes | Must be `approved-outreach.jsonl` for dry-run/send. |
| `--smtp-config` | optional | Per-run SMTP config. If omitted, uses `$B2B_LEAD_HUNTER_SMTP_CONFIG`, then `<skill>/_shared/smtp-config.json`. |
| `--sent-log` | yes | Append-only audit log and duplicate prevention. |
| `--evaluations` | yes | Hard gate. Each `draft_id` must have `decision=pass`. |
| `--suppression-list` | recommended | Blocks opt-outs and excluded domains. |
| `--dry-run` | one of dry-run/send | Validate and log without sending. |
| `--send-approved` | one of dry-run/send | Actually send approved records. |
| `--limit` | optional | Per-run cap; cannot exceed `daily_limit`. |

Hard gates before send:

- `approved-outreach` record must validate.
- Matching `outreach-evaluations` record must have `decision=pass`.
- Matching `outreach-evaluations.evaluated_body_hash` must equal the approved/current body hash.
- `approval_status=approved`.
- `state=approved`.
- `send_recommendation=send`.
- `approved_body_hash` must match exact recipient, subject, body, and opt-out.
- `language_confidence=high`.
- No high-risk claims.
- Recipient must not be inferred.
- Recipient/domain/company must not be suppressed.
- Company must not already have `send_success` in `sent-log.jsonl`.

Validate sent log:

```bash
python scripts/validate_artifact.py sent-log lead-runs/<slug>/sent-log.jsonl
```

## Recommended Defaults

| Setting | Default |
| --- | --- |
| `daily_limit` | `20` for a warmed mailbox; `5-10` for a new mailbox |
| `delay_seconds` | `120` or higher |
| `max_per_company` | `1` |
| `--min-pass-score` | `0.72` |
| Template strategy | generated templates + `--require-template` |
| First-touch recipient | same-domain named person, then same-domain role inbox |

## Common Failure Messages

| Message | Meaning | Fix |
| --- | --- | --- |
| `missing outreach template for cluster_key=...` | Draft generation has no matching regional template. | Regenerate templates or remove/adjust `--language`. |
| `approved-outreach record requires send_recommendation=send` | Record is not truly approved for sending. | Review and set only after human approval. |
| `missing passing outreach evaluation for draft_id` | Send gate did not find `decision=pass`. | Run evaluation and approve only pass records. |
| `approved_body_hash does not match` | Draft changed after approval. | Recompute hash and reapprove. |
| `passing evaluation hash does not match approved draft body` | The `evaluated_body_hash` in evaluations was computed from a different body than the approved draft's actual body. The hashes must be identical. | **Pitfall**: `body_hash()` in `send_smtp.py` hashes `recipient_email + \"\\n\" + subject + \"\\n\" + body_text + \"\\n\" + opt_out_line`. If you computed the hash manually using only `body_text`, it will never match. Use `--print-approval-hashes` to get the correct hash, then copy it into both `outreach-evaluations.jsonl` (`evaluated_body_hash`) and `approved-outreach.jsonl` (`approved_body_hash`). |
| `recipient email domain is suppressed` | Suppression matched. | Do not send unless suppression is intentionally removed. |
| `company already has a successful first-touch send` | Duplicate prevention. | Do not send another first-touch email to same company. |`

---

## Pitfalls

### SMTP password not visible in subprocess

Inline `VAR=val python3` syntax (without `export`) may not propagate the variable to the Python subprocess depending on the shell context. Use explicit export:

```bash
# CORRECT (works reliably):
export SMTP_APP_PASSWORD='your-password' && python3 scripts/send_smtp.py ...
```

`execute_code` may have different network access than the Hermes `terminal` tool. If SMTP connection succeeds in `execute_code` but times out in `terminal`, use `execute_code` for the actual send. The `send_smtp.py` script can still be used for validation and hash generation via `terminal`.

### SMTP SSL vs STARTTLS

- Port 587 + `use_starttls: true` → SMTP with STARTTLS upgrade (standard, but some providers fail after TLS handshake)
- Port 465 + `use_ssl: true` → SMTP_SSL (implicit TLS from the start, works with QQ Exmail and others)
- The two modes are mutually exclusive in the config

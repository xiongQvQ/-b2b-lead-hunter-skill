# Output Schema

Use JSONL for machine-readable lead storage. Each line is one lead object.

## Accepted Lead Fields

Required:

- `company_name`: best known legal or trading name.
- `website`: official company website when available.
- `country`: country name or ISO code if known.
- `business_type`: array of roles such as `distributor`, `importer`, `wholesaler`, `retailer`, `installer`, `integrator`, `oem`, `end_user`, `manufacturer`, `service`.
- `fit_score`: 0.0-1.0.
- `contactability_score`: 0.0-1.0.
- `priority`: `high`, `medium`, `low`, or `reject`.
- `review_required`: boolean. Required true for `low` or uncertain leads in `leads_all.csv`.
- `uncertainty_reason`: why the lead is not strict enough, especially for `low`.
- `missing_evidence`: array of missing proof items.
- `source_quality`: `official`, `platform`, `directory`, `snippet`, or `mixed`.
- `official_site_found`: boolean.
- `source_queries`: search queries that found or enriched the company.
- `source_urls`: URLs used as evidence.
- `evidence`: array of `{claim, source_url}`.

Recommended:

- `industry`
- `description`
- `emails`
- `phones`
- `social`
- `decision_makers`
- `address`
- `notes`
- `reject_reasons`

## Email Object

```json
{
  "email": "sales@example.com",
  "type": "generic",
  "source_url": "https://example.com/contact",
  "domain_relation": "same_domain",
  "verification": "format_only",
  "confidence": 0.85
}
```

Allowed `type` values:

- `generic`: shared inbox such as `sales@`, `info@`, `export@`.
- `person`: direct personal or employee email found on a public source.
- `inferred`: pattern-derived personal email. Use only when a same-domain employee pattern was observed.

Allowed `domain_relation` values:

- `same_domain`: email domain matches the company website domain.
- `parent_domain`: email domain is a parent/related domain.
- `third_party`: email belongs to a platform, agency, or unrelated domain.
- `free_mail`: free mailbox provider.
- `unknown`: no website/domain context available.

Default `verification` is `format_only`. Do not imply deliverability unless a later verifier explicitly checks it.

## Decision Maker Object

```json
{
  "name": "Jane Smith",
  "title": "Purchasing Manager",
  "email": "",
  "linkedin": "https://www.linkedin.com/in/...",
  "source_url": "https://example.com/team"
}
```

Only include people who appear to represent the company professionally. Avoid unrelated personal data.

## Rejected Record

Rejected candidates should be JSONL too:

```json
{
  "company_name": "",
  "website": "",
  "source_queries": [],
  "source_urls": [],
  "reject_reasons": ["directory page, not a company"],
  "raw": {}
}
```

Do not delete rejections; they guide the next search round.

## File Policy

### `leads.jsonl`

Canonical full lead store. May include high, medium, and low accepted/reviewable records. Do not include clear rejects.

### `leads.csv`

Strict human/CRM view. Include only:

- `priority=high`
- `priority=medium`

Exclude `low` unless the user explicitly asks for a non-strict file.

### `leads_all.csv`

Full human review view. Include:

- `high`
- `medium`
- `low`

Low rows must have:

- `review_required=true`
- `uncertainty_reason`
- `missing_evidence`

### `review.jsonl`

Use for low or ambiguous candidates that may still be valuable. Keep full evidence and raw context where useful.

### `rejected.jsonl`

Use for clear non-leads. Always include `reject_reasons`.

## Recommended CSV Fields

```text
company_name
website
country
business_type
industry
priority
review_required
fit_score
contactability_score
evidence_score
emails
phones
decision_makers
social
source_urls
source_quality
official_site_found
uncertainty_reason
missing_evidence
fit_reason_zh
contact_source
notes
```

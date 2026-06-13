---
name: b2b-lead-hunter
description: Use when researching foreign-trade B2B leads, buyer companies, distributors, importers, wholesalers, reachable decision makers, customs/import signals, and outreach-ready contacts from product, region, ICP, website, or document inputs. Use for evidence-backed lead hunting, qualification, exportable lead files, regional/language email templates, company-personalized email drafts, and controlled SMTP sending after approval.
version: 1.0.0
author: xiongbojian
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [b2b, foreign-trade, lead-generation, search, jina, serper, contacts, sales, outreach]
    related_skills: [hermes-agent, searxng-search, domain-intel]
---

# B2B Lead Hunter

## Purpose

Research foreign-trade B2B prospects and contact channels for physical-product export, distributor discovery, importer discovery, and outreach preparation.

Hermes owns judgment, evidence review, search iteration, language choice, and approval decisions. Scripts own deterministic normalization, page reading, contact extraction, dedupe, validation, template rendering, draft evaluation, export, and SMTP plumbing.

Default objective: produce a traceable lead file where every company, contact channel, decision maker, score, and outreach draft is tied to source URLs and structured artifacts. Quality gates override target count.

## User Workflow Preference

User prefers continuous-cycle execution: mine leads → find decision makers → generate emails → send, all in one loop. Do not pause between stages unless the user explicitly asks to stop. After sending one batch, immediately resume mining the next. The cycle is:

```
search new leads → get contact emails → send generic emails
    → search decision makers → infer/find DM emails → send DM emails
    → search new leads (next country/niche) → repeat
```

Do not ask "continue or pause?" after each batch — just keep going until the user says stop.

## Non-Negotiable Rules

- Use `scripts/read_jina.py` as the primary reader for every website or URL: seller site, candidate website, contact page, product page, directory profile, or source article. Use browser tools only when Jina fails or interaction is required.
- Use Hermes native web search for search queries. Do not open Google, Bing, or other search engines in a browser.
- Keep lead discovery, outreach drafting, human approval, and SMTP sending as separate stages with separate files.
- Do not send email unless the user explicitly requests sending, SMTP config exists, approved records exist, suppression checks run, and `send_smtp.py` receives matching passing evaluations.
- Never auto-send to inferred emails, free-mail addresses, low/reject leads, directory-only leads, records without source URLs, or records without buyer-role evidence.
- A lead cannot enter strict `leads.csv` unless company reality, buyer-role evidence, contactability, and source URLs are present.
- Do not relax gates to satisfy `target_count`.
- Directories and B2B platforms are discovery sources, not final truth. Confirm with official or strong independent evidence before accepting.
- Customs/trade evidence is useful buying intent, but absence of customs data is not a rejection reason.
- Every outreach message must include truthful sender identity, source-backed personalization, a low-pressure CTA, and a clear opt-out line.

## Reference Router

Read only the reference files needed for the current stage. Do not load all references by default.

| User Goal | Read First | Key Scripts |
| --- | --- | --- |
| Full run or unclear request | `references/reference-router.md`, `references/workflow.md` | `run_hunt.py`, `validate_artifact.py` |
| Search planning | `references/query-lanes.md` (includes Brand Distributor Networks lane), `references/region-language-map.md`, `references/search-resilience.md` | `normalize_search_results.py`, `serper_maps.py` |
| Company and contact research | `references/company-website-research.md`, `references/output-schema.md` | `read_jina.py`, `extract_contacts.py` |
| Decision makers | `references/decision-maker-discovery.md`, `references/chinese-founder-contact-discovery.md`, `references/contact-discovery-from-pdfs-and-directories.md` | `linkedin_dm_search.py`, `infer_email.py` |
| Chinese AI/robotics startup leads (recruitment, not B2B trade) | `references/chinese-ai-startup-leads.md` | — search lanes, sources, pitfalls only; no dedicated scripts |
| Customs/import verification | `references/customs-verification.md` | `customs_verify.py` |
| Outreach generation | `references/outreach-workflow.md`, `references/outreach-parameter-guide.md`, `references/email-localization.md` | `prepare_outreach.py`, `generate_outreach_templates.py`, `generate_outreach_drafts.py`, `evaluate_outreach_drafts.py` |
| SMTP sending | `references/outreach-compliance.md`, `references/outreach-parameter-guide.md`, `references/smtp-quirks.md` | `send_smtp.py`, `validate_artifact.py` |

## Required Inputs

Ask for missing high-impact inputs, but proceed with conservative defaults if the user wants execution:

- `product`: concrete product or product family.
- `seller_context`: seller website, product page, catalog text, or short description.
- `target_regions`: countries or regions.
- `target_customer_profile`: importer, distributor, wholesaler, installer, integrator, OEM, or end user.
- `negative_criteria`: direct competitors, B2C-only stores, unsupported countries, tiny local services, or other knockouts.
- `target_count`: default 30 for MVP runs.
- `round_limits`: default pilot first, then 3 rounds, 6-10 queries per round, 10-20 results per query.

Default ICP: importers, distributors, wholesalers, and agents. Include installers, integrators, OEMs, or end users only when buying, resale, procurement, or project-use evidence exists.

## Artifact Contract

Create a run directory:

```text
lead-runs/<slug>-YYYYMMDD-HHMM/
├── brief.json
├── search-plan.md
├── raw-search.jsonl
├── candidates.jsonl
├── enriched.jsonl
├── leads.jsonl
├── leads.csv
├── leads_all.csv
├── review.jsonl
├── rejected.jsonl
└── run-report.md
```

Optional outreach artifacts:

```text
lead-runs/<slug>-YYYYMMDD-HHMM/
├── sender-profile.json
├── outreach-candidates.jsonl
├── outreach-templates.jsonl
├── outreach-drafts.jsonl
├── outreach-evaluations.jsonl
├── outreach-review.csv
├── approved-outreach.jsonl
├── sent-log.jsonl
├── suppression-list.csv
└── outreach-report.md
```

Validate handoffs whenever artifacts already exist, before export, and before any SMTP dry-run/send. Use `scripts/validate_artifact.py <artifact-type> <path>`. Exact command examples live in `references/outreach-parameter-guide.md`.

## Lead Research State Machine

1. Build `brief.json` from user input and seller context. If seller website exists, read it with `scripts/read_jina.py` first.
2. Write `search-plan.md` using at least three lanes unless the user requests a narrow run.
3. Run a pilot: 5-8 queries, 5-10 results per query, inspect 20-40 candidates.
4. Stop and ask before full scale if pilot candidates are mostly wrong, B2C-only, direct manufacturers, directories, region drift, or contact-poor.
5. Normalize search results to `raw-search.jsonl`.
6. Build and triage `candidates.jsonl`; reject only clear mismatches at discovery stage.
7. Research official websites and important pages with Jina first.
8. Extract contacts and classify email type: `generic`, `person`, or `inferred`.
9. Score from evidence: fit, contactability, evidence quality, priority.
10. Export strict and review views, then write `run-report.md`.

Acceptance gate for strict leads:

- Real company evidence.
- Buyer-role evidence.
- At least one contact channel.
- Source URL for every key claim.

## Decision Maker Rules

Decision-maker discovery is mandatory phase-two enrichment for high and strong medium leads. Do it immediately after the generic email batch is sent, before moving to the next round of lead discovery. The cycle is:

```
send generic email batch → immediately search decision makers for those companies → send DM emails → then start next round of lead mining
```

Do not separate these stages — the user expects them back-to-back. After sending DM emails, immediately resume mining new leads (new countries, new niches, new search lanes).

Preferred order:

1. Official website pages: contact, team, management, Ansprechpartner, Impressum, brochures, catalog PDFs.
2. Industry directories and supplier linecard directories.
3. LinkedIn/native web/Tavily search for role-specific profiles.
4. Email pattern detection from known same-domain employee emails.
5. Email inference only when a same-domain employee pattern is observed.

Inferred personal emails are auxiliary only. They cannot be the only contact channel for a high lead and cannot be auto-sent.

Use `scripts/enrich_decision_makers.py` to generate role-based search plans and merge public employee contacts back into leads. Search pattern: role + company first, then person + company/domain to find public contact channels.

## Customs Verification Rules

Use customs/trade data as a buying-intent signal after a company already looks plausible. Extract shipment count, supplier names, origin country, HS/product clues, date recency, and source URL.

Do not downgrade a company only because customs data is unavailable. Many valid European distributors, agents, and wholesalers do not appear in free customs portals.

Use `scripts/customs_verify.py` only on normalized search results for a target company. See `references/customs-verification.md`.

## Outreach State Machine

Outreach starts only after `leads.jsonl` exists and has passed validation.

```text
leads.jsonl
  -> outreach-candidates.jsonl
  -> outreach-templates.jsonl
  -> outreach-drafts.jsonl
  -> outreach-evaluations.jsonl
  -> outreach-review.csv
  -> approved-outreach.jsonl
  -> sent-log.jsonl
```

Run the outreach scripts in the exact order shown above. Use `--require-template` when rendering drafts so every email comes from a regional/language template. See `references/outreach-parameter-guide.md` for concrete command lines and parameters.

## Email Generation Strategy

Use hybrid generation:

- One base template per `country + language + buyer_role + product_angle` cluster.
- One final email per company by filling source-backed company variables into that regional/language template.
- Never send a pure regional template with no company-specific evidence.
- Avoid fully free-writing every company email unless the account is high value; it increases variance and review cost.

Required company variables:

- `company_name`
- `recipient_email`
- concrete source-backed fit reason
- product/application angle from `sender-profile.json`
- low-friction CTA
- opt-out line

Template controls:

- language and greeting style
- directness/formality
- subject shape
- CTA wording
- opt-out wording
- allowed claims and forbidden phrases

Prefer local language when confidence is high. Use English when local-language confidence is medium/low, the contact page is English, or the product category is commonly handled in English.

## Mandatory Outreach Gate Before Sending

SMTP dry-run and real sending are blocked unless all are true:

- User explicitly requested sending.
- SMTP config is present. Prefer per-run `lead-runs/<slug>/smtp-config.json`; otherwise use `$B2B_LEAD_HUNTER_SMTP_CONFIG` or shared `<skill>/_shared/smtp-config.json`.
- `approved-outreach.jsonl` exists and every record has `approval_status=approved`.
- `outreach-evaluations.jsonl` exists.
- Each approved `draft_id` has a matching evaluation with `decision=pass`.
- The passing evaluation hash matches the exact current recipient, subject, body, and opt-out line.
- `approved_body_hash` matches the exact current recipient, subject, body, and opt-out line.
- WARNING: `body_hash()` in `send_smtp.py` uses `recipient+subject+body+opt_out` concatenated, NOT just the body text. Always use `--print-approval-hashes` to get the correct hash rather than computing manually.
- Suppression and prior sent-log checks run.
- Dry-run succeeds before `--send-approved`.

Always run `send_smtp.py --dry-run` successfully before `--send-approved`. Both commands must include `--evaluations`, `--suppression-list`, and `--sent-log`. Pass `--smtp-config` for per-run config, or rely on `$B2B_LEAD_HUNTER_SMTP_CONFIG` / `<skill>/_shared/smtp-config.json`. Exact command examples live in `references/outreach-parameter-guide.md`.

**SMTP troubleshooting**: See `references/smtp-quirks.md` for QQ exmail port 465 SSL, hash computation formula, env var propagation, and common failure patterns.

## Output Policy

- `leads.jsonl`: canonical lead data.
- `leads.csv`: strict view with high and medium only.
- `leads_all.csv`: full view including low, visibly marked.
- `review.jsonl`: uncertain/low leads needing human review.
- `rejected.jsonl`: clear non-leads with concrete reasons.
- `run-report.md`: Chinese-readable summary, metrics, top queries, bad queries, evidence gaps, next actions.
- `outreach-drafts.jsonl`: draft-only email records following `templates/outreach-draft.schema.json`.
- `outreach-evaluations.jsonl`: deterministic quality gate for draft emails.
- `approved-outreach.jsonl`: manually approved subset allowed for SMTP dry-run/sending.
- `sent-log.jsonl`: append-only log of dry runs, sends, skips, suppression hits, duplicate blocks, failures, and message IDs.

Never hide rejected records. Keep rejected records with reasons so the next round can improve.

## Stop Conditions

Stop and ask for confirmation before spending more calls or sending anything when:

- Pilot candidates are over 60% wrong customer type.
- Results are mostly direct manufacturers, B2C-only shops, local services, or directories.
- Target region drifts badly.
- Most candidates have no usable contact channel.
- Search/Jina failures, 429s, or costs are abnormal.
- Outreach evaluations produce many `review` or `reject` decisions.
- SMTP dry-run reports suppression, duplicate, hash mismatch, missing evaluation, or config problems.

## Compliance Boundaries

- Collect only publicly available business contact information.
- Do not bypass authentication, paywalls, robots restrictions, CAPTCHAs, or access controls.
- Do not generate deceptive identities, fake relationships, fake offices, fake stock, fake certifications, or unsupported claims.
- Respect opt-out requests and regional email/privacy laws.
- Avoid personal data unrelated to B2B purchasing or company representation.
- Keep sending low-volume, reviewable, logged, and reversible.

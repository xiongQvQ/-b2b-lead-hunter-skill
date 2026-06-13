# Reference Router

Use this file when the task is broad, ambiguous, or crosses multiple stages. Do not load every reference by default. Pick the smallest set that matches the current stage.

## Stage Selection

| Stage | User Intent | Read |
| --- | --- | --- |
| Brief and plan | Product, website, region, ICP, target count | `workflow.md`, `query-lanes.md`, `region-language-map.md` |
| Search resilience | Search provider fails, blocked results, weak results | `search-resilience.md`, `search-fallback.md` |
| Company research | Verify company reality, buyer role, product fit, contactability | `company-website-research.md`, `output-schema.md` |
| Lead scoring | Decide high, medium, low, reject | `scoring-rubric.md`, `output-schema.md` |
| Decision makers | Find named buyers, procurement, management, public emails | `decision-maker-discovery.md`, `contact-discovery-from-pdfs-and-directories.md`; scripts: `enrich_decision_makers.py`, `linkedin_dm_search.py`, `infer_email.py` |
| Customs signals | Verify imports, Asia/China buying signal, shipment evidence | `customs-verification.md` |
| Outreach setup | User wants email generation or sending | `outreach-workflow.md`, `outreach-parameter-guide.md`, `email-localization.md` |
| Lead sources & channels | Finding distributors via brand networks, trade fairs, vertical niches | `lead-source-channels.md` |
| SMTP setup & sending | SMTP config, password, send_smtp.py, dry-run, approval, QQ exmail | `outreach-parameter-guide.md`, `smtp-troubleshooting.md` |
| Specific domain hints | Fasteners, consumer electronics, or another known prior hunt | Matching domain insight file only |

## Execution Rules

- Start from `SKILL.md` for hard gates and state machines.
- Load only the references for the current stage.
- Prefer scripts for deterministic transforms and validation.
- If a reference conflicts with a script contract or schema, trust the script/schema and update the reference before continuing.
- Keep generated artifacts in `lead-runs/<slug>-YYYYMMDD-HHMM/`.
- Validate artifacts before handoff between stages.

## Minimal Reference Bundles

Lead research bundle:

- `workflow.md`
- `query-lanes.md`
- `company-website-research.md`
- `scoring-rubric.md`
- `output-schema.md`

Decision-maker bundle:

- `decision-maker-discovery.md`
- `contact-discovery-from-pdfs-and-directories.md`
- `output-schema.md`

Outreach bundle:

- `outreach-workflow.md`
- `outreach-parameter-guide.md`
- `email-localization.md`
- `outreach-compliance.md`

Sending bundle:

- `outreach-parameter-guide.md`
- `outreach-compliance.md`
- `compliance-boundaries.md`

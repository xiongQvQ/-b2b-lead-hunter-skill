# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This project also supports **Cursor** (see `.cursor/rules/b2b-lead-hunter.mdc`) and **Cline** (see `.clinerules` / `CLINE.md`).

## Commands

```bash
pip3 install requests           # Install the only external dependency
python -m py_compile scripts/*.py  # Syntax validation for all scripts
python scripts/validate_artifact.py leads path/to/leads.jsonl  # Validate artifact by type
```

Smoke test the outreach pipeline:
```bash
python scripts/prepare_outreach.py ... && \
python scripts/generate_outreach_templates.py ... && \
python scripts/generate_outreach_drafts.py ... && \
python scripts/evaluate_outreach_drafts.py ... && \
python scripts/send_smtp.py --dry-run ...
```

Valid artifact types: `lead`, `brief`, `decision-maker`, `customs-verification`, `outreach-candidate`, `outreach-template`, `outreach-draft`, `outreach-evaluation`, `sender-profile`, `sent-log`, `smtp-config`.

## Architecture

**Hermes/Judgment vs Scripts/Deterministic split** — Hermes (the AI) owns search strategy, fit scoring, language choice, and approval decisions. Python scripts own normalization, page reading, contact extraction, deduplication, validation, template rendering, draft evaluation, export, and SMTP plumbing.

**Pipeline stages**: brief → search → read websites → score/split → export → decision-maker discovery → customs verification → outreach preparation → templates → drafts → evaluate → approve → send

**Artifact contracts** — Each stage reads/writes JSONL files validated against JSON schemas in `templates/`. The schemas are enforced at runtime by `scripts/contracts.py` (695 lines, imported by 8+ scripts). This is the central dependency — know it before modifying any script that touches artifacts.

**Hard gates** — Quality overrides target count. Leads cannot enter strict CSV without company reality, buyer-role evidence, contactability, and source URLs. SMTP sending is blocked by multiple hash-locked gates (evaluation hash, approval hash, suppression check, duplicate check, dry-run success). Never auto-sends to inferred emails or free-mail addresses.

**Key reference files**:
- `SKILL.md` — Hermes skill entrypoint with state machines, hard gates, stage router
- `references/reference-router.md` — maps each pipeline stage to its guidance reference
- `references/output-schema.md` — JSONL artifact structure documentation
- `references/decisions.md` — design decision log
- `references/compliance-boundaries.md` — compliance rules for outreach

**Script dependency graph**: `contracts.py` is imported by `validate_artifact.py`, `send_smtp.py`, `generate_outreach_drafts.py`, `generate_outreach_templates.py`, `evaluate_outreach_drafts.py`, `prepare_outreach.py`, `enrich_decision_makers.py`, `customs_verify.py`.

**JSONL is the universal data format** — every stage reads/writes JSON Lines with schemas in `templates/`. External APIs needed: Jina Reader (`JINA_API_KEY`), Serper (`SERPER_API_KEY`), Tavily (`TAVILY_API_KEY`), SMTP (`SMTP_APP_PASSWORD`).

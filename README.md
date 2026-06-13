# B2B Lead Hunter

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform: Claude Code](https://img.shields.io/badge/Claude%20Code-ready-black)](#)
[![Platform: Cursor](https://img.shields.io/badge/Cursor-ready-blueviolet)](#)
[![Platform: Cline](https://img.shields.io/badge/Cline-ready-orange)](#)
[![中文文档](https://img.shields.io/badge/中文-README-red)](README.zh.md)

**An AI Agent Skill — not a standalone app.** It runs inside Claude Code, Cursor, Cline, or Hermes to automate foreign-trade B2B lead research, decision-maker discovery, customs/import signal checks, outreach draft generation, and controlled SMTP sending.

From the team behind [b2binsights.io](https://b2binsights.io) — B2B export intelligence for Chinese manufacturers.

Designed for export sales teams, founders, and B2B sellers who need traceable, verifiable leads — not spam lists. Every company, contact, score, decision maker, and outreach draft is tied to source URLs and structured artifacts. Quality gates override target count.

## Features

| # | Feature | What It Means |
|---|---------|---------------|
| 1 | **AI + Code Separation** | AI owns strategy, judgment, language choice. Python scripts own deterministic work (reading, extracting, validating, sending). Neither can fully operate without the other — no black-box prompts, no blind automation. |
| 2 | **Multi-Platform** | One skill runs on **Claude Code**, **Cursor**, **Cline**, and **Hermes**. Platform-specific files adapt the same pipeline to each agent's capabilities. |
| 3 | **Evidence-Driven** | Every company, contact, score, and outreach draft is tied to source URLs. No unverifiable claims. Full audit trail from search to send. |
| 4 | **Compliance-First** | Hash-locked sending gates, suppression lists, opt-out enforcement, no auto-send to inferred emails. Built for legal B2B outreach, not spam. |
| 5 | **Deterministic Pipeline** | 18 Python scripts (4,872 lines) handle all data transformation. Schema validation at every stage via `contracts.py`. Results are reproducible, not probabilistic. |
| 6 | **Quality Gates** | Hard acceptance gates override target counts. A lead cannot enter strict output unless company reality, buyer-role evidence, contactability, and source URLs all exist. Never relax to hit a number. |
| 7 | **Full Coverage** | From product brief → multi-lane search → website reading → contact extraction → scoring → decision-maker discovery → customs signals → outreach templates → personalized drafts → evaluation → approval → SMTP sending — one unified workflow. |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-username/b2b-lead-hunter.git
cd b2b-lead-hunter
pip install -r requirements.txt

# 2. Verify setup
python -m py_compile scripts/*.py
python scripts/validate_artifact.py smtp-config templates/smtp-config.example.json

# 3. Run a demo pilot
python scripts/run_hunt.py example/brief.json \
  --out lead-runs/demo/ \
  --queries example/queries.csv \
  --pilot

# 4. See what you got
cat lead-runs/demo/pilot-stats.json
```

---

## Installation by Platform

This is an **AI agent skill** — it runs inside an agent, not as a standalone app. Here's how to install it on each platform.

### Claude Code

```bash
# Option A: Open project directly (CLAUDE.md loads automatically)
cd b2b-lead-hunter
claude

# Option B: Install as a Claude Code project (accessible from anywhere)
claude project add b2b-lead-hunter --path /path/to/b2b-lead-hunter
claude project use b2b-lead-hunter

# Option C: From another directory, reference this repo
claude --project /path/to/b2b-lead-hunter
```

Once loaded, Claude Code reads [`CLAUDE.md`](CLAUDE.md) for context. It uses `WebSearch` tool for queries, terminal for running Python scripts, and file ops for reading/writing artifacts.

### Cursor

```bash
# Open the project folder in Cursor
cursor /path/to/b2b-lead-hunter
```

The rules in `.cursor/rules/b2b-lead-hunter.mdc` are loaded automatically when Cursor Agent operates on files matching the `globs` pattern. Use `@web()` for search queries.

### Cline (VS Code)

```bash
# Open the project folder in VS Code with Cline installed
code /path/to/b2b-lead-hunter
```

Cline auto-loads [`.clinerules`](.clinerules) at the project root on startup. No additional config needed. Use `@web` for search queries and the terminal for Python scripts.

### Hermes

```bash
# Clone the skill into your Hermes skills directory
git clone https://github.com/your-username/b2b-lead-hunter.git hermes-skills/business/b2b-lead-hunter/
```

Hermes reads [`SKILL.md`](SKILL.md) as the skill entrypoint. No other setup required. The `name` field in `SKILL.md` metadata registers it as `b2b-lead-hunter`.

---

> All platforms share the same `scripts/`, `references/`, and `templates/` directories. Platform-specific files (`CLAUDE.md`, `.clinerules`, `.cursor/rules/`, `SKILL.md`) each contain the same pipeline logic adapted to that agent's capabilities.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI / Agent Layer                         │
│  (search strategy, fit scoring, language choice, approval)       │
└─────────────────────────────────────────────────────────────────┘
                              │
    ┌────────────┬────────────┼────────────┬────────────┐
    ▼            ▼            ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐
│ Search  │ │ Website │ │ Contact │ │ DM       │ │ Score & │
│ Plan    │ │ Read    │ │ Extract │ │ Discover │ │ Decide  │
│ (AI)    │ │(jina.py)│ │(extract)│ │(enrich)  │ │ (AI)    │
└─────────┘ └─────────┘ └─────────┘ └──────────┘ └─────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Deterministic Python Layer                    │
│  (normalize, validate, dedupe, template, export, SMTP)            │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

```
brief.json
  → search-plan.md (AI: research strategy)
  → raw-search.jsonl (normalize search results)
  → candidates.jsonl (dedupe + structure)
  → enriched.jsonl (read websites + extract contacts)
  → leads.jsonl (AI: score + classify)
  → [decision-maker discovery]
  → [customs/import verification]
  → outreach-candidates.jsonl
  → outreach-templates.jsonl
  → outreach-drafts.jsonl
  → outreach-evaluations.jsonl (deterministic quality gate)
  → approved-outreach.jsonl (human approval)
  → sent-log.jsonl (SMTP with hash-locked gates)
```

### Key Design Decisions

- **AI + Code separation**: AI owns strategy and judgment. Python scripts own deterministic work (reading, extracting, validating, sending). Neither can fully operate without the other.
- **JSONL everywhere**: Every artifact is JSON Lines with a strict schema enforced by `scripts/contracts.py`.
- **Runtime validation**: Every stage validates its output before handoff. No trust between stages.
- **Hash-locked sending**: Every sent email requires matching hashes from evaluation and approval stages. If the body changes after approval, sending is blocked.
- **Compliance-first**: Suppression lists, opt-out enforcement, no auto-send to inferred emails, truthful sender identity.

---

## Directory Structure

```
b2b-lead-hunter/
├── CLAUDE.md              # Claude Code agent instructions
├── .clinerules            # Cline / Codex agent instructions
├── .cursor/rules/         # Cursor agent rules
├── SKILL.md               # Original Hermes skill definition
├── scripts/               # 18 deterministic Python helpers
│   ├── contracts.py       # Runtime contract validators (central dependency)
│   ├── run_hunt.py        # Lightweight orchestrator
│   ├── read_jina.py       # Website reader via Jina API
│   ├── extract_contacts.py
│   ├── normalize_search_results.py
│   ├── dedupe_leads.py
│   ├── export_leads.py
│   ├── enrich_decision_makers.py
│   ├── linkedin_dm_search.py
│   ├── infer_email.py
│   ├── customs_verify.py
│   ├── prepare_outreach.py
│   ├── generate_outreach_templates.py
│   ├── generate_outreach_drafts.py
│   ├── evaluate_outreach_drafts.py
│   ├── send_smtp.py
│   ├── serper_maps.py
│   └── validate_artifact.py
├── references/            # 28 detailed stage guidance files
├── templates/             # JSON schemas and example artifacts
├── example/               # Demo input files
├── _shared/               # Shared SMTP config
├── pyproject.toml
├── requirements.txt
├── Makefile
└── LICENSE
```

---

## Demo

Run the built-in demo to see real output:

```bash
# Install, then:
python scripts/run_hunt.py example/brief.json \
  --out lead-runs/demo/ \
  --queries example/queries.csv \
  --pilot

# View results
cat lead-runs/demo/pilot-stats.json
# → {"query_count": 3, "raw_result_count": ..., "candidate_count": ...}
```

Check [`example/`](example/) for sample input files you can adapt to your own product and target markets.

---

## Requirements

- Python 3.10+
- `requests` library (`pip install -r requirements.txt`)

### Optional API Keys

| Key | Used By | Get One |
|-----|---------|---------|
| `JINA_API_KEY` | Website reading | [jina.ai](https://jina.ai) (free tier available) |
| `SERPER_API_KEY` | Maps/local search | [serper.dev](https://serper.dev) |
| `TAVILY_API_KEY` | Decision-maker search | [tavily.com](https://tavily.com) |
| SMTP password | Email sending | your email provider |

---

## Compliance

This tool is designed for **legal, ethical B2B outreach only**:

- Collects only publicly available business contact information
- Never bypasses authentication, paywalls, or access controls
- Never generates deceptive identities, fake claims, or unsupported statements
- Respects opt-out requests and regional privacy laws
- Every outreach must include truthful sender identity, source-backed personalization, a low-pressure CTA, and a clear opt-out line
- Auto-sending requires: [user approval → hash-locked evaluation → dry-run → approval hash → suppression check → duplicate check] — all gates must pass

---

## Contributing

Contributions are welcome. Please open an issue or PR.

- Keep the compliance-first design intact
- Preserve the AI/code separation pattern
- Add or update schema validators in `contracts.py` when adding new fields
- Run `make check` before submitting

---

## License

MIT © [xiongbojian](LICENSE)

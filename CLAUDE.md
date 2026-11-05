# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`b2b-lead-hunter` is a host-assisted (Claude Code / Codex) B2B prospecting skill, packaged as a local Python runtime. The Python side owns networking, state, cost accounting, caching, evidence storage, and send gates; the host (the LLM) reads evidence batches and writes structured results. There is deliberately no autonomous generator process and no background daemon.

`README.md`, `SKILL.md`, and `references/*.md` are written in Chinese and are the authoritative operating protocol. `SKILL.md` is the host-facing workflow; `references/host-protocol.md` defines the exact `HostResult` shapes; `references/acceptance.md` records what is and is not verified.

## Setup and commands

Python 3.11+ is required (the macOS system Python is older — always use the venv).

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install pytest==8.4.2
cp .env.example .env && chmod 600 .env      # never overwrite an existing .env
.venv/bin/python scripts/leadctl.py doctor check --json
```

Run the entry point from any cwd (`scripts/leadctl.py` resolves paths itself):

```bash
.venv/bin/python scripts/leadctl.py --json <group> <action> ...
```

All output is JSON. `--json` is accepted anywhere and stripped. Exit codes: 2 input/contract, 3 conflict/state, 4 dependency/runtime, 5 incompatible DB schema.

Common commands:

```bash
# Offline end-to-end demo (synthetic data, no network, no SMTP)
.venv/bin/python scripts/demo.py --state-dir /abs/tmp/lead-hunter-demo --endpoint drafts

# Plan/run lifecycle
.venv/bin/python scripts/leadctl.py plan create --file /abs/plan.json
.venv/bin/python scripts/leadctl.py plan authorize --campaign-id ID --plan-hash HASH --actor user --decision-ref "..."
.venv/bin/python scripts/leadctl.py run create --campaign-id ID
.venv/bin/python scripts/leadctl.py run advance --run-id ID --seconds 30

# Host task queue
.venv/bin/python scripts/leadctl.py host-task list --run-id ID
.venv/bin/python scripts/leadctl.py host-task claim --task-id ID --owner session-1
.venv/bin/python scripts/leadctl.py host-task submit --file /abs/host-result.json

# Regenerate JSON Schemas from Pydantic models
.venv/bin/python scripts/leadctl.py schema export
```

Tests (offline only, fixture mode, no paid calls):

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_workflow.py::test_endpoint_end_to_end -q
```

`pyproject.toml` sets `pythonpath = ["src"]`, so pytest works from the repo root once deps are installed.

## Architecture

### Run lifecycle and state machine

`src/lead_hunter/service.py` is the core. A campaign is an immutable, authorized `Plan`; a run snapshots that plan plus the industry pack and a config fingerprint. `Service.advance(run_id, seconds)` is a deterministic phase machine:

`queries → discovery → read → judge → qualified → contacts → contact_reviewed → drafted → finish`

- `queries`: either imports `plan.seeds`, or enqueues a `plan_queries` host task.
- `discovery`: Serper search per query; only hostname-deduped companies are added; social/directory hosts are skipped.
- `read`: Jina fetch of the company homepage plus observed same-host links (procurement/contact pages prioritized).
- `judge`: Jev produces typed `fit`/`sufficiency` answers; failure policy is `block` by default, `host` only if explicitly configured (run becomes `degraded`).
- `qualified`: deterministic sort into A/B/C via `intent_tier()`; selects up to `target_count`.
- `contacts`: Treg people search → optional email find → email verify, with domain-conflict and inferred-email handling.
- `contact_reviewed` / `drafted`: enqueue host tasks; drafts are frozen into RFC822 messages.

Waiting states are first-class: `waiting_host`, `waiting_provider`, `waiting_approval`, plus `paused/cancelled/completed/partial`. A time slice stops only at safe phase checkpoints; in-flight paid calls are never aborted.

### Endpoint gates

`Plan.endpoint` caps what the run may do: `accounts` (no Treg, no messages), `contacts` (no messages), `drafts` (no sending), `first_outreach` (approval + send). The gate is enforced both in workflow branches and in `Providers.request()` (defense in depth). `research/compare/outcome` CLI groups exist only to fail with `capability_unavailable` (V1.0-B scope).

### Contracts, evidence, and host tasks

`src/lead_hunter/contracts.py` is the single source of truth for all shapes (strict Pydantic: `extra="forbid", strict=True`). `schemas/generated/*.json` are exported artifacts — after changing a model, run `schema export`.

Host work is batched through the `work_items` table. The protocol is: `claim` (returns revision, `input_hash`, `lease_token`) → host builds a `HostResult` → `submit`. Submissions are rejected on stale revision/token/hash or expired lease. Repeated identical results are idempotent; different results are refused.

Evidence integrity is enforced, not advisory:
- `Store.evidence()` stores verbatim text in content-addressed blobs (`blobs/sha256/...`).
- Every host quote must be a literal substring of the cited evidence blob and belong to the promised subject (`validate_quotes`).
- `evidence_refs` must be in the task's `allowed_evidence_ids`.
- `fit=qualified` additionally requires confirmed entity, country match, an allowed `buyer_role`, and at least one `web`-sourced quote.
- `published_at` only counts toward A/B if the same ISO date appears in a web quote (`date_grounded`).

### Storage and money

`src/lead_hunter/storage.py`: single SQLite DB in WAL mode (`state.sqlite3`) under `LEAD_HUNTER_STATE_DIR`, which must be outside the skill root. It uses `BEGIN IMMEDIATE` transactions, an `fcntl` scheduler lock, an append-only `event_log`, and immutable blobs.

All costs are integer micro-USD. `Store.reserve()` atomically checks both the run budget and the local account budget before any paid call; a reservation is not released until the operation is settled with an actual amount. Unknown cost is never treated as zero — it stays reserved and is reported as unpriced. A higher DB schema version is rejected at startup (no migrations in this version).

### Providers

`src/lead_hunter/providers.py` wraps Serper (search), Jina Reader (fetch), Jev (typed judge), and Treg (people/email). Jev is provider-selectable: `JEV_PROVIDER=typesafe` uses the native typed API; `openrouter` or `openai_compatible` use an OpenAI-compatible chat completion and normalize the JSON reply into the same `answers` contract. Key rules:
- Paid POSTs never auto-retry or silently fail over. A stable `op_key` and Treg `Idempotency-Key` prevent double-charging.
- `202`/pending and timeouts become `waiting_provider` / `unknown_external_result`; recovery queries the original remote call ID and never re-submits the paid request.
- Treg actual cost comes from `X-Treg-Cost-Micro`; only `https://treg.to` is accepted as the REST host.
- `public_url()` blocks non-global/private addresses and credentials before Jina fetches arbitrary sites.
- Responses reuse the provider cache keyed by provider/action/body/scope and are refreshed only after TTL expiry, preserving the original verification timestamp.

### Sending

`src/lead_hunter/sending.py` freezes the message (body + signature + postal address + unsubscribe line) at draft time. Sending is gated by a long checklist in `gates()`: endpoint, human-reviewed qualified account, contact identity (`person_confirmed`/`employment_confirmed`/`role_relevant`), current `valid` verification, source policy, suppression, sender config, evidence freshness, and a content-hash + dependency-digest approval.

Approval is bound to `content_hash` and `dependency_digest` (plan hash, account payload/revision, contact payload/revision, sender config); any change invalidates it. Only the user's explicit decision may be recorded as approval — a model's own pass is not an approval.

First-touch is enforced globally by partial unique indexes on `messages.company_touch` and `messages.email_touch`; a reservation is taken before dispatch intent and is never released on an unknown outcome. `accepted` means SMTP accepted, not delivered. `unknown`/`dispatching` are never auto-retried; reconcile manually with the original Message-ID.

### Configuration

`src/lead_hunter/config.py` loads `.env` from the skill root (or `--env-file`), with precedence: CLI flags > process env > selected `.env` > defaults. The state dir must be outside the skill root. `LEAD_HUNTER_MODE=fixture` uses synthetic providers and forbids sending. Config values are fingerprinted into each run; changing configuration mid-run yields `config_changed` and requires a new run. Jev selection uses `JEV_PROVIDER` (`typesafe`/`openrouter`/`openai_compatible`), `JEV_API_KEY` (overrides the provider-specific key), `JEV_BASE_URL` (optional), and `JEV_MODEL`.

Industry packs live in `config/industry/<id>.json` (data only). Adding one also requires extending the `industry` `Literal` in `Plan` (`contracts.py`); packs are validated against `IndustryPack`.

## Invariants worth preserving

- Never claim provider/business results as verified unless a real live call produced them; fixture mode and `degraded` runs must stay labeled as such.
- Never manufacture facts (compatibility, certifications, stock, lead time, prices) — `product_facts` must trace to the user.
- Do not write secrets or `.env` contents into plans, host results, reports, or chat.
- A/B/C scores are ordering heuristics, not reply probabilities.
- `run advance` output is the state summary; the DB is authoritative over the projected `host-tasks/*.json` files.

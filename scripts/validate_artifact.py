#!/usr/bin/env python3
"""Validate B2B lead hunter JSON/JSONL artifacts against runtime contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contracts import (
    ContractError,
    validate_approved_outreach,
    validate_customs_verification,
    validate_decision_maker,
    validate_lead,
    validate_outreach_evaluation,
    validate_outreach_template,
    validate_outreach_candidate,
    validate_outreach_draft,
    validate_sender_profile,
    validate_sent_log_event,
    validate_smtp_config,
)


VALIDATORS = {
    "outreach-candidates": validate_outreach_candidate,
    "outreach-drafts": validate_outreach_draft,
    "outreach-evaluations": validate_outreach_evaluation,
    "outreach-templates": validate_outreach_template,
    "approved-outreach": validate_approved_outreach,
    "sent-log": validate_sent_log_event,
    "sender-profile": validate_sender_profile,
    "smtp-config": validate_smtp_config,
    "customs-verification": validate_customs_verification,
    "decision-makers": validate_decision_maker,
    "leads": validate_lead,
}


def read_json_or_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith(("[", "{")):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    rows = []
    for i, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ContractError(f"{path}:{i}: expected JSON object")
            rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=sorted(VALIDATORS))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    validator = VALIDATORS[args.kind]
    try:
        rows = read_json_or_jsonl(args.path)
        for i, row in enumerate(rows, start=1):
            validator(row, f"{args.kind}[{i}]")
    except (ContractError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"kind": args.kind, "path": str(args.path), "records": len(rows), "valid": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

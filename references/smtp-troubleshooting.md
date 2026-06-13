# SMTP Troubleshooting & Configuration

## QQ Exmail (腾讯企业邮箱) Specifics

QQ exmail uses `smtp.exmail.qq.com`. Port 587 with STARTTLS often times out during the TLS handshake on some networks (observed on macOS terminal sandbox environments). The reliable configuration is:

```json
{
  "smtp_host": "smtp.exmail.qq.com",
  "smtp_port": 465,
  "use_ssl": true,
  "username": "your-user@your-domain.com",
  "password_env": "SMTP_APP_PASSWORD",
  "from_name": "Your Company Sales Team",
  "from_email": "your-user@your-domain.com",
  "reply_to": "your-user@your-domain.com",
  "daily_limit": 20,
  "delay_seconds": 120,
  "max_per_company": 1
}
```

Key differences from standard config:
- Port 465 instead of 587
- `use_ssl: true` instead of `use_starttls: true`
- The `send_smtp.py` script and `contracts.py` schema were patched to support `use_ssl` — ensure you have the latest versions

## Environment Variable Passing

The SMTP password must be accessible to the Python subprocess. The correct pattern is:

```bash
# CORRECT: export first, then run
export SMTP_APP_PASSWORD=$(grep 'SMTP_APP_PASSWORD' ~/.zshrc | sed 's/.*SMTP_APP_PASSWORD=//' | tr -d '\n')
python3 scripts/send_smtp.py --send-approved ...

# WRONG: inline VAR=val does NOT propagate to Python subprocess on macOS
SMTP_APP_PASSWORD=xxx python3 scripts/send_smtp.py ...  # fails with "missing SMTP password"
```

If the password line in .zshrc has NO quotes around the value, use:
```bash
sed 's/.*SMTP_APP_PASSWORD=//' | tr -d '\n'
```

If it has quotes, use:
```bash
sed 's/.*SMTP_APP_PASSWORD="\([^"]*\)".*/\1/'
```

## body_hash Computation

The `send_smtp.py` script computes `body_hash` as SHA256 of these 4 fields joined by newlines:
1. `recipient_email` (lowercased, stripped)
2. `subject`
3. `body_text`
4. `opt_out_line`

This hash is used to lock the approved draft to its exact content. If any of these fields change, the hash breaks and sending is blocked. The `evaluated_body_hash` in `outreach-evaluations.jsonl` and `approved_body_hash` in `approved-outreach.jsonl` must match the script's computation.

To get the correct hash, use:
```bash
python3 scripts/send_smtp.py --drafts approved-outreach.jsonl --print-approval-hashes
```

## Schema Strictness

The outreach evaluation schema (`templates/outreach-evaluation.schema.json`) has `additionalProperties: false`. All required fields must be present and no extra fields allowed. The required fields are:
evaluation_id, draft_id, lead_id, company_name, recipient_email, language, evaluated_body_hash, language_fit_score, personalization_score, claim_risk_score, spam_risk_score, reply_likelihood_score, overall_score, decision, blocking_reasons, review_reasons, recommended_actions, created_at.

## send_smtp.py send_attempt + send_failure Pattern

When `--send-approved` runs, a single draft generates TWO log events:
1. `send_attempt` with `result: ok` — the send was attempted
2. Either `send_success` or `send_failure` — the actual result

A `send_failure` with `"missing SMTP password"` means the password_env variable was not accessible to the Python process — check your export pattern.

## Network-Specific Issues

If port 587 STARTTLS hangs (observed on macOS Hermes terminal sandbox), verify with:
```python
import smtplib
smtp = smtplib.SMTP_SSL("smtp.exmail.qq.com", 465, timeout=10)
smtp.login("user@domain.com", "password")
```

If the terminal environment cannot reach the SMTP server but `execute_code` can, use `execute_code` as a fallback sending channel.

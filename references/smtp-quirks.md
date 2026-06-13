# SMTP Quirks & Troubleshooting

## QQ Exmail (腾讯企业邮箱) — smtp.exmail.qq.com

- **Port 587 + STARTTLS**: EHLO works, STARTTLS works, but the TLS handshake on 587 hangs and times out in terminal environments. The execute_code sandbox can reach it but the agent's terminal cannot.
- **Port 465 + SSL (SMTP_SSL)**: Works reliably from both terminal and execute_code. Use this.
- **Config**: `"smtp_port": 465, "use_ssl": true` (NOT `use_starttls`)
- **Password**: Store in `SMTP_APP_PASSWORD` env var. Must use `export VAR=value && command` (inline `VAR=value command` does not propagate to Python subprocess in Zsh terminal).

## Hash Computation for Approval Gate

`send_smtp.py` computes `body_hash()` from a **4-component payload**:
```
recipient_email (lowercased) + "\n" + subject + "\n" + body_text + "\n" + opt_out_line
```

Not just the body text. If you manually compute `evaluated_body_hash` or `approved_body_hash`, use this same formula.

To get the correct hash for an existing draft, use:
```bash
python scripts/send_smtp.py --drafts approved-outreach.jsonl --print-approval-hashes
```

This outputs `draft_id`, `recipient_email`, and the correct `approved_body_hash`.

## Environment Variable Propagation

```bash
# WRONG — Python subprocess won't see it in some terminal shells
SMTP_APP_PASSWORD=xxx python3 scripts/send_smtp.py ...

# RIGHT — export first, then run
export SMTP_APP_PASSWORD=xxx && python3 scripts/send_smtp.py ...
```

## Port 587 STARTTLS Timeout Pattern

If you see:
```
EHLO: 250 smtp.qq.com
STARTTLS: 220 Ready to start TLS
FAILED: Connection unexpectedly closed: The read operation timed out
```

Switch to port 465 SSL. The TLS handshake after STARTTLS is blocked by network filtering in some environments.

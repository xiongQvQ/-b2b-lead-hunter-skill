# Shared Config

Copy `smtp-config.example.json` from the templates directory and save it as `smtp-config.json` here to share SMTP configuration across runs:

```bash
cp templates/smtp-config.example.json _shared/smtp-config.json
```

Then set `B2B_LEAD_HUNTER_SMTP_CONFIG` to point here, or the send scripts will find this path by default.

**Do not commit `smtp-config.json`** — it contains real credentials. The `.gitignore` already excludes it.

# Compliance Boundaries

This skill is for public B2B research, manual review, and explicitly approved outreach.

Allowed:

- Search public web pages, company websites, public B2B profiles, exhibitor pages, and public directories.
- Extract business emails, public phone numbers, public social/company profiles, and named professional contacts when relevant to company representation.
- Store source URLs and snippets for auditability.
- Draft outreach only after the user asks, with claim checking and opt-out language.
- Send approved B2B outreach only after explicit user approval, mailbox authorization, suppression checks, rate limits, and append-only logging.
- Export leads for manual review.

Not allowed:

- Bypassing login, paywalls, CAPTCHA, robots restrictions, or technical access controls.
- Collecting unrelated personal data.
- Using deceptive identities or pretending to have a prior relationship.
- Auto-sending email during discovery or from unapproved drafts.
- Operating bulk SMTP/IMAP campaigns without explicit user approval, suppression handling, rate limits, and logs.
- Running SMTP ping verification by default.
- Ignoring opt-outs, unsubscribe requests, or region-specific privacy/email rules.

Operational rules:

- Default to draft-only.
- Send only to qualified B2B leads with public business contact evidence.
- Never auto-send to inferred emails, free-mail addresses, low/reject leads, or directory-only records.
- Keep opt-outs in `suppression-list.csv` and check it before every send.
- When in doubt, keep the record for manual review rather than automating outreach.

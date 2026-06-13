# QQ Exmail (腾讯企业邮箱) SMTP Configuration

## Connection

QQ Exmail requires **SMTP_SSL on port 465** — STARTTLS on port 587 may hang after the TLS handshake.

```json
{
  "smtp_host": "smtp.exmail.qq.com",
  "smtp_port": 465,
  "use_ssl": true,
  "username": "linda@gdushun.com",
  "password_env": "SMTP_APP_PASSWORD",
  "from_name": "Sales Team",
  "from_email": "linda@gdushun.com",
  "reply_to": "linda@gdushun.com",
  "daily_limit": 20,
  "delay_seconds": 120,
  "max_per_company": 1
}
```

## Password

The SMTP password is the **authorization code** (授权码) from QQ Exmail settings, NOT the login password. Set it in `~/.zshrc`:

```bash
export SMTP_APP_PASSWORD="your-16-char-code"
```

## Validation

Test connectivity before sending:

```python
import smtplib
with smtplib.SMTP_SSL("smtp.exmail.qq.com", 465, timeout=30) as smtp:
    smtp.login("linda@gdushun.com", "your-code")
    print("OK")
```

## Sending Rate

- Daily limit on QQ Exmail: ~500 outbound
- Recommended in-config limit: `daily_limit: 20` for new domains
- `delay_seconds: 120` between sends to avoid triggering spam filters

from __future__ import annotations
import os
from pathlib import Path
from dotenv import dotenv_values
from .contracts import Failure, digest

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = {
    "LEAD_HUNTER_STATE_DIR": "~/.local/share/b2b-lead-hunter", "LEAD_HUNTER_MODE": "live",
    "LEAD_HUNTER_CONCURRENCY": "4", "LEAD_HUNTER_TIMEOUT": "25",
    "LEAD_HUNTER_MAX_RESPONSE_BYTES": "2000000", "LEAD_HUNTER_ACCOUNT_LIMIT_MICRO": "10000000",
    "JEV_MODEL": "jev-latest", "JEV_PROVIDER": "typesafe", "JEV_BASE_URL": "", "TREG_BASE_URL": "https://treg.to", "JEV_FAILURE_POLICY": "block",
    "SMTP_PORT": "587", "SMTP_SECURITY": "starttls", "SENDER_NAME": "David", "SENDER_SIGNATURE": "David",
    "UNSUBSCRIBE_LINE": 'If this is not relevant, reply "no" and I will not contact you again.',
    "SENDER_TIMEZONE": "Asia/Shanghai", "SEND_DAILY_LIMIT": "10", "SEND_MIN_INTERVAL_SECONDS": "60",
    "CONTACT_POLICY": "public_only", "ALLOW_ROLE_EMAIL": "false",
}
SECRET_KEYS = {"SERPER_API_KEY", "JINA_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "JEV_API_KEY", "TREG_TOKEN", "SMTP_PASSWORD", "SMTP_USERNAME"}

class Settings:
    def __init__(self, env_file=None, state_dir=None, mode=None):
        # Explicit --env-file selects one dotenv; process environment overrides dotenv.
        self.values = DEFAULTS | {k: v for k, v in dotenv_values(env_file or ROOT / ".env").items() if v is not None} | dict(os.environ)
        if state_dir: self.values["LEAD_HUNTER_STATE_DIR"] = str(state_dir)
        if mode: self.values["LEAD_HUNTER_MODE"] = mode
        self.state = Path(self.get("LEAD_HUNTER_STATE_DIR")).expanduser().resolve()
        if self.state == ROOT or ROOT in self.state.parents:
            raise Failure("unsafe_state_path", "State directory must be outside the skill installation")
        if self.get("LEAD_HUNTER_MODE") not in ("live", "fixture"): raise Failure("invalid_mode")
        if self.get("CONTACT_POLICY") not in ("public_only", "provider_verified"): raise Failure("invalid_contact_policy")
        if self.get("SMTP_SECURITY") not in ("starttls", "ssl"): raise Failure("smtp_tls_required")
        if self.get("JEV_FAILURE_POLICY") not in ("block", "host"): raise Failure("invalid_jev_policy")
        if self.get("JEV_PROVIDER") not in ("typesafe", "openrouter", "openai_compatible"): raise Failure("invalid_jev_provider")
        for key in ("LEAD_HUNTER_CONCURRENCY", "LEAD_HUNTER_TIMEOUT", "SEND_DAILY_LIMIT"):
            if self.integer(key) <= 0: raise Failure("invalid_config", key)
    def get(self, key, default=""): return self.values.get(key, default)
    def integer(self, key, default=0):
        try: return int(self.get(key, str(default)))
        except ValueError: raise Failure("invalid_config", key)
    @property
    def fixture(self): return self.get("LEAD_HUNTER_MODE") == "fixture"
    def fingerprint(self):
        keys = set(DEFAULTS) | {"SERPER_CALL_CAP_MICRO", "JINA_CALL_CAP_MICRO", "JEV_CALL_CAP_MICRO", "TREG_CALL_CAP_MICRO", "SERPER_FIXED_COST_MICRO", "JINA_FIXED_COST_MICRO"}
        return digest({k:self.get(k) for k in sorted(keys)})
    def sender(self):
        return {k:self.get(k) for k in ("SENDER_EMAIL", "SENDER_NAME", "SENDER_SIGNATURE", "SENDER_POSTAL_ADDRESS", "UNSUBSCRIBE_LINE", "CONTACT_POLICY", "ALLOW_ROLE_EMAIL", "SENDER_TIMEZONE", "SEND_DAILY_LIMIT", "SEND_MIN_INTERVAL_SECONDS")}

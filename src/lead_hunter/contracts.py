"""Authoritative v2 contracts. Generate JSON schemas via leadctl schema export."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT = "2.0"
ENDPOINTS = ("accounts", "contacts", "drafts", "first_outreach")

class Failure(Exception):
    def __init__(self, code, message=None, exit_code=2):
        self.code, self.message, self.exit_code = code, message or code, exit_code
        super().__init__(code + (": " + self.message if self.message != code else ""))

def now():
    return datetime.now(timezone.utc).isoformat()

def uid(prefix):
    return prefix + "_" + uuid4().hex

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def domain(value):
    parsed = urlsplit(value if "://" in value else "https://" + value)
    if not parsed.hostname or parsed.username or parsed.password:
        raise Failure("invalid_domain")
    host = parsed.hostname.rstrip(".").encode("idna").decode().lower()
    return host[4:] if host.startswith("www.") else host

def email_normalize(value):
    value = value.strip()
    if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value) or any(c in value for c in "\r\n"):
        raise Failure("invalid_email")
    local, host = value.rsplit("@", 1)
    return local + "@" + domain(host)

def observed_emails(text):
    # Accept plain text and Markdown mailto labels without swallowing brackets/punctuation.
    matches=re.findall(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",text)
    return {email_normalize(m) for m in matches}

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class ProductFact(Strict):
    id: str
    text: str = Field(min_length=1)
    source: str = Field(min_length=1)
    kind: Literal["user_claim", "observed_fact"] = "user_claim"

class Query(Strict):
    lane: Literal["buyer", "trigger", "rfq", "channel", "ecosystem"]
    text: str = Field(min_length=3, max_length=500)

class Seed(Strict):
    name: str = Field(min_length=1)
    domain: str
    country: str
    source: str
    @field_validator("domain")
    @classmethod
    def normalize(cls, v): return domain(v)

class Plan(Strict):
    contract_version: Literal["2.0"] = CONTRACT
    entry: Literal["acquisition", "enrichment"] = "acquisition"
    product_name: str = Field(min_length=1)
    product_facts: list[ProductFact] = Field(min_length=1)
    country: str = Field(min_length=2, max_length=2, pattern="^[A-Z]{2}$")
    country_name: str
    language: str = "en"
    icp: str = Field(min_length=5)
    buyer_roles: list[str] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    endpoint: Literal["accounts", "contacts", "drafts", "first_outreach"] = "contacts"
    target_count: int = Field(default=10, ge=1, le=100)
    candidate_limit: int = Field(default=30, ge=1, le=300)
    pages_per_company: int = Field(default=3, ge=1, le=6)
    contacts_per_company: int = Field(default=2, ge=1, le=3)
    budget_micro: int = Field(default=1000000, ge=0)
    max_calls: int = Field(default=100, ge=1, le=1000)
    industry: Literal["generic", "optical-transceiver"] = "generic"
    queries: list[Query] = Field(default_factory=list, max_length=20)
    seeds: list[Seed] = Field(default_factory=list, max_length=300)
    @model_validator(mode="after")
    def check(self):
        if self.candidate_limit < self.target_count:
            raise ValueError("candidate_limit must cover target_count")
        if self.entry == "enrichment" and not self.seeds:
            raise ValueError("enrichment requires seeds")
        if len({f.id for f in self.product_facts}) != len(self.product_facts):
            raise ValueError("duplicate product fact IDs")
        return self

class Quote(Strict):
    evidence_id: str
    text: str = Field(min_length=5, max_length=2000)

class Signal(Strict):
    kind: Literal["rfq", "tender", "project", "expansion", "replacement", "hiring", "catalog", "other"]
    statement: str
    published_at: str | None = None
    quotes: list[Quote] = Field(min_length=1)

class AccountReview(Strict):
    company_id: str
    entity_status: Literal["confirmed", "conflict", "unknown"]
    country_match: bool
    buyer_role: str
    fit: Literal["qualified", "rejected", "unknown"]
    fit_quotes: list[Quote]
    signals: list[Signal] = Field(default_factory=list)
    counter_evidence: list[Quote] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)

class ContactReview(Strict):
    contact_id: str
    person_confirmed: bool
    employment_confirmed: bool
    role_relevant: bool
    quotes: list[Quote]
    unknowns: list[str] = Field(default_factory=list)

class Draft(Strict):
    company_id: str
    contact_id: str
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=30, max_length=5000)
    observation: str
    hypothesis: str
    hook: str
    evidence_quotes: list[Quote] = Field(min_length=1)
    product_fact_ids: list[str] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    @field_validator("subject")
    @classmethod
    def no_newline(cls, v):
        if "\n" in v or "\r" in v: raise ValueError("header injection")
        return v

class HostResult(Strict):
    task_id: str
    input_hash: str
    expected_revision: int
    lease_token: str
    result_status: Literal["completed", "insufficient_evidence", "cannot_complete"]
    evidence_refs: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    queries: list[Query] = Field(default_factory=list)
    accounts: list[AccountReview] = Field(default_factory=list)
    contacts: list[ContactReview] = Field(default_factory=list)
    drafts: list[Draft] = Field(default_factory=list)

class IndustryPack(Strict):
    id: str
    version: str
    product_fields: list[str]
    buyer_roles: list[str]
    evidence_rules: list[str]
    negative_signals: list[str]
    query_lanes: list[str]
    role_mapping: dict[str,str]
    insight_questions: list[str]
    language_terms: dict[str,list[str]]

SCHEMAS = {c.__name__: c for c in (Plan, HostResult, AccountReview, ContactReview, Draft, IndustryPack)}

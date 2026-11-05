"""Local WAL repository, atomic budgets, immutable blobs and audit history."""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from .contracts import Failure, canonical, digest, now, uid

DDL = """
CREATE TABLE schema_metadata(version INTEGER NOT NULL);
INSERT INTO schema_metadata VALUES(1);
CREATE TABLE campaigns(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, authorization TEXT, created_at TEXT NOT NULL);
CREATE TABLE runs(id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id), status TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE work_items(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), stage TEXT NOT NULL, subject TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL, input_hash TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, lease_owner TEXT, lease_token TEXT, lease_until REAL, UNIQUE(run_id,stage,subject,input_hash));
CREATE TABLE companies(id TEXT PRIMARY KEY, domain TEXT NOT NULL, name TEXT NOT NULL, country TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX company_domain ON companies(domain);
CREATE TABLE campaign_accounts(run_id TEXT NOT NULL REFERENCES runs(id),company_id TEXT NOT NULL REFERENCES companies(id), revision INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,company_id));
CREATE TABLE contacts(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), company_id TEXT NOT NULL REFERENCES companies(id), revision INTEGER NOT NULL, payload TEXT NOT NULL);
CREATE TABLE evidence(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), subject TEXT NOT NULL, source_type TEXT NOT NULL, source_ref TEXT NOT NULL, content_hash TEXT NOT NULL, blob_ref TEXT NOT NULL, retrieved_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE messages(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),company_id TEXT NOT NULL REFERENCES companies(id), contact_id TEXT NOT NULL REFERENCES contacts(id),revision INTEGER NOT NULL, state TEXT NOT NULL, content_hash TEXT NOT NULL, dependency_digest TEXT NOT NULL, payload TEXT NOT NULL, approval TEXT, company_touch TEXT, email_touch TEXT, quota_day TEXT, sender_scope TEXT, intent_at REAL);
CREATE UNIQUE INDEX company_first_touch ON messages(company_touch) WHERE company_touch IS NOT NULL;
CREATE UNIQUE INDEX email_first_touch ON messages(email_touch) WHERE email_touch IS NOT NULL;
CREATE TABLE suppression(kind TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(kind,target));
CREATE TABLE provider_operations(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),provider TEXT NOT NULL, op_key TEXT NOT NULL UNIQUE, status TEXT NOT NULL, cap INTEGER NOT NULL, actual INTEGER, remote_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE budget_entries(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),op_id TEXT NOT NULL REFERENCES provider_operations(id),kind TEXT NOT NULL,amount INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(op_id,kind));
CREATE TABLE cache_entries(key TEXT PRIMARY KEY,expires_at REAL NOT NULL,payload TEXT NOT NULL);
CREATE TABLE event_log(id TEXT PRIMARY KEY,run_id TEXT,event_type TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
"""

def unpack(row):
    if row is None: raise Failure("not_found")
    result = dict(row)
    for key in ("payload", "result", "authorization", "approval"):
        if result.get(key) is not None: result[key] = json.loads(result[key])
    return result

class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.path = self.root / "state.sqlite3"
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=10000")
        # Serialize initialization as well, avoiding a partially created schema.
        with self.lock("schema"):
            exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_metadata'").fetchone()
            if not exists:
                self.db.executescript("BEGIN IMMEDIATE;" + DDL + "COMMIT;")
            version = self.db.execute("SELECT version FROM schema_metadata").fetchone()[0]
            if version != 1: raise Failure("unsupported_db_schema", exit_code=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        os.chmod(self.path, 0o600)
    def close(self): self.db.close()
    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
    @contextmanager
    def lock(self, name="scheduler"):
        with open(self.root / (name + ".lock"), "a+") as handle:
            try: fcntl.flock(handle, fcntl.LOCK_EX | (0 if name=="schema" else fcntl.LOCK_NB))
            except BlockingIOError: raise Failure("scheduler_busy", exit_code=3)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)
    def one(self, sql, args=()): return unpack(self.db.execute(sql, args).fetchone())
    def all(self, sql, args=()): return [unpack(r) for r in self.db.execute(sql, args)]
    def event(self, run, kind, payload):
        self.db.execute("INSERT INTO event_log VALUES(?,?,?,?,?)", (uid("ev"),run,kind,canonical(payload),now()))
    def blob(self, content):
        content = content.encode() if isinstance(content,str) else content
        h = hashlib.sha256(content).hexdigest()
        folder = self.root / "blobs" / "sha256"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / h
        if not path.exists():
            fd, tmp = tempfile.mkstemp(dir=folder)
            with os.fdopen(fd,"wb") as f:
                f.write(content); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path)
        return h,str(path.relative_to(self.root))
    def evidence(self, run, subject, source_type, source_ref, text, meta=None):
        h, path = self.blob(text)
        eid = "evd_" + digest([run,subject,source_ref,h])[:28]
        retrieved=(meta or {}).get("observed_at") or now()
        self.db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?,?)", (eid,run,subject,source_type,source_ref,h,path,retrieved,canonical(meta or {})))
        return eid
    def materials(self, run, subject=None):
        rows = self.all("SELECT * FROM evidence WHERE run_id=?" + (" AND subject=?" if subject else ""), (run,subject) if subject else (run,))
        for r in rows:
            r["text"] = (self.root/r["blob_ref"]).read_text(encoding="utf-8")
        return rows
    def put_run(self, run, payload, status=None):
        if status:
            self.db.execute("UPDATE runs SET payload=?,status=?,revision=revision+1 WHERE id=?",(canonical(payload),status,run))
        else: self.db.execute("UPDATE runs SET payload=?,revision=revision+1 WHERE id=?",(canonical(payload),run))
    def account(self, run, company, payload):
        self.db.execute("INSERT INTO campaign_accounts VALUES(?,?,1,?) ON CONFLICT(run_id,company_id) DO UPDATE SET payload=excluded.payload,revision=campaign_accounts.revision+1",(run,company,canonical(payload)))
    def cost(self, run=None):
        where, args = (" WHERE run_id=?",(run,)) if run else ("",())
        rows = self.db.execute("SELECT status,cap,actual FROM provider_operations"+where,args).fetchall()
        return {"currency":"USD", "scope":run or "provider_account_local_db",
                "spent_micro":sum(r["actual"] or 0 for r in rows),
                "reserved_micro":sum(r["cap"] for r in rows if r["actual"] is None),
                "has_unpriced_usage":any(r["actual"] is None for r in rows),
                "calls":len(rows)}
    def reserve(self, run, provider, op_key, cap, request, run_limit, account_limit, max_calls):
        with self.tx():
            old=self.db.execute("SELECT * FROM provider_operations WHERE op_key=?",(op_key,)).fetchone()
            if old: return unpack(old), False
            rc, ac = self.cost(run), self.cost()
            if rc["calls"] >= max_calls: raise Failure("call_limit_exhausted",exit_code=4)
            if rc["spent_micro"]+rc["reserved_micro"]+cap > run_limit or ac["spent_micro"]+ac["reserved_micro"]+cap > account_limit:
                raise Failure("budget_exhausted",exit_code=4)
            oid=uid("op")
            self.db.execute("INSERT INTO provider_operations VALUES(?,?,?,?,?,?,?,?,?,?)",(oid,run,provider,op_key,"dispatching",cap,None,None,canonical({"request":request}),now()))
            self.db.execute("INSERT INTO budget_entries VALUES(?,?,?,?,?,?)",(uid("be"),run,oid,"reserve",cap,now()))
        return self.one("SELECT * FROM provider_operations WHERE id=?",(oid,)),True
    def settle(self, oid, status, response, actual=None, remote_id=None):
        with self.tx():
            op=self.one("SELECT * FROM provider_operations WHERE id=?",(oid,))
            p=op["payload"] | {"response":response}
            if actual is not None and (type(actual) is not int or actual < 0): raise Failure("invalid_provider_cost")
            if op["actual"] is not None and actual!=op["actual"]: raise Failure("settled_cost_immutable",exit_code=3)
            self.db.execute("UPDATE provider_operations SET status=?,payload=?,actual=?,remote_id=COALESCE(?,remote_id) WHERE id=?",(status,canonical(p),actual,remote_id,oid))
            if actual is not None:
                self.db.execute("INSERT OR IGNORE INTO budget_entries VALUES(?,?,?,?,?,?)",(uid("be"),op["run_id"],oid,"settle",actual,now()))
                if actual>op["cap"]: self.event(op["run_id"],"cost_cap_violation",{"operation":oid,"actual":actual,"cap":op["cap"]})
    def cached(self, key):
        r=self.db.execute("SELECT payload FROM cache_entries WHERE key=? AND expires_at>?",(key,time.time())).fetchone()
        return json.loads(r[0]) if r else None
    def cache(self, key, payload, ttl):
        self.db.execute("INSERT OR REPLACE INTO cache_entries VALUES(?,?,?)",(key,time.time()+ttl,canonical(payload)))
    def backup(self):
        folder=self.root/"backups";folder.mkdir(exist_ok=True)
        p=folder/(uid("backup")+".sqlite3")
        with sqlite3.connect(p) as target: self.db.backup(target)
        return str(p)

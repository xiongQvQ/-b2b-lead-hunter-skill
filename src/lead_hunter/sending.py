"""Frozen RFC822 manifests, bound approvals, first-touch reservations and SMTP."""
from __future__ import annotations
import base64
import json
import re
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, formatdate, make_msgid
from zoneinfo import ZoneInfo
from .contracts import Failure, canonical, digest, domain, email_normalize, now

def freeze_message(settings,draft,recipient):
    sender=settings.get("SENDER_EMAIL")
    recipient=email_normalize(recipient)
    if sender: sender=email_normalize(sender)
    for key in ("SENDER_NAME","SENDER_EMAIL"):
        if any(c in settings.get(key) for c in "\r\n"): raise Failure("header_injection")
    footer="\n\n"+settings.get("SENDER_SIGNATURE")
    if settings.get("SENDER_POSTAL_ADDRESS"): footer+="\n"+settings.get("SENDER_POSTAL_ADDRESS")
    footer+="\n\n"+settings.get("UNSUBSCRIBE_LINE")
    body=draft["body"].rstrip()+footer
    mime=EmailMessage(policy=SMTP)
    mime["From"]=formataddr((settings.get("SENDER_NAME"),sender or "unconfigured@invalid.example"))
    mime["To"]=recipient;mime["Subject"]=draft["subject"]
    mime["Date"]=formatdate(localtime=False)
    mime["Message-ID"]=make_msgid(domain=domain(sender.rsplit("@",1)[1]) if sender else "invalid.example")
    mime.set_content(body)
    return {"canonicalization_version":"1","sender":sender,"recipient":recipient,"subject":draft["subject"],"body":body,"message_id":mime["Message-ID"],"mime_b64":base64.b64encode(mime.as_bytes()).decode(),"draft":draft,"attachments":[],"sender_policy":settings.sender()}

class Sender:
    def __init__(self,service): self.app,self.s,self.db=service,service.s,service.db
    def get(self,mid): return self.db.one("SELECT * FROM messages WHERE id=?",(mid,))
    def gates(self,m,require_approval=True):
        reasons=[];r=self.db.one("SELECT * FROM runs WHERE id=?",(m["run_id"],))
        try: self.app.check_run(r)
        except Failure as e: reasons.append(e.code)
        if r["payload"]["plan"]["endpoint"]!="first_outreach": reasons.append("endpoint_gate")
        if r["status"] in ("paused","cancelled"): reasons.append("run_not_active")
        if self.s.fixture: reasons.append("fixture_send_forbidden")
        if m["state"] not in ("draft","ready"): reasons.append("outbox_state_"+m["state"])
        payload=m["payload"]
        if digest(payload)!=m["content_hash"]: reasons.append("content_hash_mismatch")
        dep=self.app.dependency(m["run_id"],m["company_id"],m["contact_id"])
        if dep!=m["dependency_digest"]: reasons.append("stale_dependencies")
        a=self.db.one("SELECT * FROM campaign_accounts WHERE run_id=? AND company_id=?",(m["run_id"],m["company_id"]))
        if not a["payload"].get("human_reviewed") or a["payload"].get("fit")!="qualified": reasons.append("account_human_review_required")
        c=self.db.one("SELECT * FROM contacts WHERE id=?",(m["contact_id"],));d=c["payload"]
        if not self.app.draft_allowed(c): reasons.append("contact_identity_gate")
        v=d.get("verification",{})
        if v.get("verdict")!="valid" or v.get("expires_at",0)<=time.time(): reasons.append("verification_not_current_valid")
        if d.get("email")!=payload["recipient"]: reasons.append("recipient_mismatch")
        if d.get("source")!="public" and self.s.get("CONTACT_POLICY")=="public_only": reasons.append("provider_contact_policy_block")
        if d.get("source") not in ("public","provider"): reasons.append("contact_source_block")
        try:
            checked=datetime.fromisoformat(d.get("reviewed_at","")).timestamp()
            if time.time()-checked>7*86400: reasons.append("employment_review_expired")
        except ValueError: reasons.append("employment_review_missing")
        if self.s.get("ALLOW_ROLE_EMAIL")!="true" and payload["recipient"].split("@")[0].lower() in ("info","sales","contact","support","admin","hello","office"):
            reasons.append("role_email_policy_block")
        for key in ("SMTP_HOST","SENDER_EMAIL","SENDER_POSTAL_ADDRESS","UNSUBSCRIBE_LINE"):
            if not self.s.get(key): reasons.append("missing_"+key.lower())
        if payload["sender"]!=self.s.get("SENDER_EMAIL") or payload["sender_policy"]!=self.s.sender(): reasons.append("sender_changed")
        materials=self.db.materials(m["run_id"],m["company_id"])
        if not any(x["source_type"]=="web" and time.time()-datetime.fromisoformat(x["retrieved_at"]).timestamp()<30*86400 for x in materials): reasons.append("company_evidence_expired")
        company=self.db.one("SELECT * FROM companies WHERE id=?",(m["company_id"],))
        for kind,target in (("email",payload["recipient"]),("domain",company["domain"]),("company",m["company_id"])):
            if self.db.db.execute("SELECT 1 FROM suppression WHERE kind=? AND target=?",(kind,target)).fetchone(): reasons.append("suppressed_"+kind)
        if require_approval:
            a=m.get("approval")
            if not a or a.get("revoked_at") or a.get("expires_at",0)<=time.time() or a.get("content_hash")!=m["content_hash"] or a.get("dependency_digest")!=dep or a.get("message_revision")!=m["revision"]:
                reasons.append("message_approval_required_or_stale")
        # Global history across campaigns, aliases and senders for the same sales purpose.
        ct="sales:domain:"+company["domain"]
        et="sales:email:"+payload["recipient"]
        if self.db.db.execute("SELECT 1 FROM messages WHERE id!=? AND (company_touch=? OR email_touch=?)",(m["id"],ct,et)).fetchone(): reasons.append("first_touch_exists")
        return sorted(set(reasons))
    def prepare(self,mid):
        m=self.get(mid)
        return {"message_id":mid,"revision":m["revision"],"content_hash":m["content_hash"],"dependency_digest":m["dependency_digest"],"manifest":m["payload"],"blocking_reasons":self.gates(m,False),"note":"Approve only after reviewing the exact recipient, subject and rendered body."}
    def approve(self,mid,actor,reference,content_hash,dependency_digest,ttl=86400):
        with self.db.tx():
            m=self.get(mid)
            if content_hash!=m["content_hash"] or dependency_digest!=m["dependency_digest"]: raise Failure("approval_hash_mismatch",exit_code=3)
            reasons=self.gates(m,False)
            if reasons: raise Failure("send_gate_blocked",",".join(reasons),3)
            approval={"approval_type":"message_send","approved_by":actor,"user_decision_ref":reference,"approved_at":now(),"expires_at":time.time()+ttl,"content_hash":content_hash,"dependency_digest":dependency_digest,"message_revision":m["revision"],"sender":m["payload"]["sender"],"recipient":m["payload"]["recipient"],"revoked_at":None}
            self.db.db.execute("UPDATE messages SET approval=?,state='ready' WHERE id=?",(canonical(approval),mid))
            self.db.event(m["run_id"],"message_approved",{"message":mid,"approval":approval})
        return {"status":"approved","message_id":mid}
    def revoke(self,mid,reference):
        with self.db.tx():
            m=self.get(mid);a=m["approval"] or {};a|={"revoked_at":now(),"revocation_ref":reference}
            self.db.db.execute("UPDATE messages SET approval=? WHERE id=?",(canonical(a),mid))
            self.db.event(m["run_id"],"message_approval_revoked",{"message":mid,"reference":reference})
        return {"status":"revoked"}
    def dry_run(self,mid):
        m=self.get(mid);reasons=self.gates(m)
        return {"status":"blocked" if reasons else "ready","message_id":mid,"blocking_reasons":reasons,"content_hash":m["content_hash"],"recipient":m["payload"]["recipient"],"quota_consumed":False,"sent":False}
    def dispatch(self,mid):
        # One SMTP action at a time across hosts; never hold SQLite tx over network.
        with self.db.lock("sender"):
            blocked=[]
            with self.db.tx():
                m=self.get(mid);reasons=self.gates(m)
                if reasons: raise Failure("send_gate_blocked",",".join(reasons),3)
                scope=digest([self.s.get("SMTP_HOST"),self.s.get("SMTP_USERNAME") or self.s.get("SENDER_EMAIL")])
                day=datetime.now(ZoneInfo(self.s.get("SENDER_TIMEZONE"))).date().isoformat()
                rows=self.db.all("SELECT * FROM messages WHERE sender_scope=? AND quota_day=?",(scope,day))
                if len(rows)>=self.s.integer("SEND_DAILY_LIMIT"): raise Failure("daily_quota_exhausted",exit_code=3)
                latest=max([x["intent_at"] or 0 for x in rows],default=0)
                if time.time()-latest<self.s.integer("SEND_MIN_INTERVAL_SECONDS"): raise Failure("send_interval_wait",exit_code=3)
                company=self.db.one("SELECT * FROM companies WHERE id=?",(m["company_id"],))
                self.db.db.execute("UPDATE messages SET state='reserved',company_touch=?,email_touch=?,quota_day=?,sender_scope=?,intent_at=? WHERE id=?",("sales:domain:"+company["domain"],"sales:email:"+m["payload"]["recipient"],day,scope,time.time(),mid))
                self.db.event(m["run_id"],"send_reserved",{"message":mid,"message_id_header":m["payload"]["message_id"]})
            with self.db.tx():
                # Recheck suppression and revocation after reservation, immediately before dispatch intent.
                mm=self.get(mid);mm["state"]="ready"
                reasons=self.gates(mm)
                if reasons:
                    self.release(mid,"blocked");blocked=reasons
                else:
                    self.db.db.execute("UPDATE messages SET state='dispatching' WHERE id=?",(mid,))
                    self.db.event(m["run_id"],"smtp_dispatch_intent",{"message":mid})
            if blocked: raise Failure("send_gate_blocked",",".join(blocked),3)
            try: result=self.transport(m["payload"])
            except BaseException:
                # Even cancellation after dispatch intent retains the touch and quota.
                self.db.db.execute("UPDATE messages SET state='unknown' WHERE id=?",(mid,))
                self.db.event(m["run_id"],"smtp_unknown",{"message":mid})
                raise
            with self.db.tx():
                if result["status"]=="failed": self.release(mid,"failed")
                else: self.db.db.execute("UPDATE messages SET state=? WHERE id=?",(result["status"],mid))
                self.db.event(m["run_id"],"smtp_"+result["status"],{"message":mid,"result":result})
            return result|{"message_id":mid,"delivered":False}
    def release(self,mid,status):
        self.db.db.execute("UPDATE messages SET state=?,company_touch=NULL,email_touch=NULL,quota_day=NULL,sender_scope=NULL,intent_at=NULL WHERE id=?",(status,mid))
    def transport(self,manifest):
        client=None;data_started=False
        try:
            context=ssl.create_default_context()
            if self.s.get("SMTP_SECURITY")=="ssl": client=smtplib.SMTP_SSL(self.s.get("SMTP_HOST"),self.s.integer("SMTP_PORT"),timeout=30,context=context)
            else:
                client=smtplib.SMTP(self.s.get("SMTP_HOST"),self.s.integer("SMTP_PORT"),timeout=30)
                client.ehlo();client.starttls(context=context);client.ehlo()
            if self.s.get("SMTP_USERNAME"): client.login(self.s.get("SMTP_USERNAME"),self.s.get("SMTP_PASSWORD"))
            code,_=client.mail(manifest["sender"])
            if code!=250: return {"status":"failed","phase":"mail_from","smtp_code":code}
            code,_=client.rcpt(manifest["recipient"])
            if code not in (250,251): return {"status":"failed","phase":"rcpt_to","smtp_code":code}
            data_started=True
            code,_=client.data(base64.b64decode(manifest["mime_b64"]))
            return {"status":"accepted" if code==250 else "failed","phase":"data_response","smtp_code":code}
        except smtplib.SMTPResponseException as e:
            return {"status":"failed","phase":"data_response" if data_started else "before_data","smtp_code":e.smtp_code,"error_type":type(e).__name__}
        except (smtplib.SMTPException,OSError) as e:
            return {"status":"unknown" if data_started else "failed","phase":"after_data" if data_started else "before_data","error_type":type(e).__name__}
        finally:
            if client:
                try: client.close()
                except OSError: pass
    def reconcile(self,mid,outcome,actor,reference):
        with self.db.lock("sender"),self.db.tx():
            m=self.get(mid)
            if m["state"] not in ("dispatching","unknown","reserved","needs_review"): raise Failure("not_reconcilable",exit_code=3)
            if outcome=="failed": self.release(mid,"failed")
            else: self.db.db.execute("UPDATE messages SET state=? WHERE id=?",(outcome,mid))
            self.db.event(m["run_id"],"manual_send_reconciliation",{"message":mid,"outcome":outcome,"actor":actor,"evidence_ref":reference})
        return {"status":outcome,"retry_automatic":False}

"""Fixed V1-A workflow and host bridge. No autonomous generator process."""
from __future__ import annotations
import asyncio
import csv
import io
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from .config import ROOT
from .contracts import (CONTRACT, ENDPOINTS, Failure, HostResult, IndustryPack, Plan, canonical,
                        digest, domain, email_normalize, observed_emails, now, uid)
from .providers import Providers

def intent_tier(account):
    """Heuristic priority, never a probability of conversion."""
    if account.get("fit")!="qualified": return {"tier":"review" if account.get("fit")!="rejected" else "excluded","score":0,"reason":"Buyer fit is unconfirmed or rejected"}
    recent=[]
    for s in account.get("signals",[]):
        try:
            dt=datetime.fromisoformat(s["published_at"].replace("Z","+00:00"))
            dt=dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            age=(datetime.now(timezone.utc)-dt).days
        except (ValueError,KeyError,TypeError): continue
        if 0<=age<=90 and s.get("date_grounded"): recent.append(s["kind"])
    if any(x in recent for x in ("rfq","tender","replacement")):
        return {"tier":"A","score":85,"reason":"Matching buyer with dated direct purchasing signal within 90 days; interest still requires reply validation"}
    if any(x in recent for x in ("project","expansion")):
        return {"tier":"B","score":65,"reason":"Matching buyer with dated project/expansion signal; procurement is a hypothesis"}
    return {"tier":"C","score":40,"reason":"Matching buyer; current purchasing intent is unknown"}

class Service:
    def __init__(self, settings, store): self.s,self.db=settings,store
    def create_plan(self, data):
        if data.get("endpoint")=="research": raise Failure("capability_unavailable","Research is V1.0-B")
        p=Plan.model_validate(data)
        pid=uid("campaign")
        self.db.db.execute("INSERT INTO campaigns VALUES(?,1,?,NULL,?)",(pid,canonical(p.model_dump()),now()))
        return {"campaign_id":pid,"plan_hash":digest(p.model_dump()),"plan":p.model_dump(),"status":"draft"}
    def authorize(self, cid, actor, decision_ref, plan_hash):
        c=self.db.one("SELECT * FROM campaigns WHERE id=?",(cid,))
        if digest(c["payload"])!=plan_hash: raise Failure("plan_hash_mismatch",exit_code=3)
        a={"type":"plan_scope","approved_by":actor,"user_decision_ref":decision_ref,"approved_at":now(),"plan_hash":plan_hash,"revision":c["revision"]}
        self.db.db.execute("UPDATE campaigns SET authorization=? WHERE id=?",(canonical(a),cid))
        self.db.event(None,"plan_authorized",{"campaign":cid,"authorization":a})
        return a
    def create_run(self,cid):
        c=self.db.one("SELECT * FROM campaigns WHERE id=?",(cid,))
        self.check_campaign(c)
        rid=uid("run")
        industry=IndustryPack.model_validate(json.loads((ROOT/"config"/"industry"/(c["payload"]["industry"]+".json")).read_text())).model_dump()
        snapshot={"plan":c["payload"],"plan_hash":digest(c["payload"]),"campaign_revision":c["revision"],"config_hash":self.s.fingerprint(),"industry_pack":industry,"industry_hash":digest(industry),"mode":"fixture" if self.s.fixture else "live", "phase":"queries","query_index":0,"queries":c["payload"]["queries"],"errors":[],"degraded":False,"versions":{"contract":"2.0","db":1,"stage":"1","mapping":"1","industry_pack":industry["version"]}}
        self.db.db.execute("INSERT INTO runs VALUES(?,?,?,1,?,?)",(rid,cid,"planned",canonical(snapshot),now()))
        self.db.event(rid,"run_created",{"plan_hash":snapshot["plan_hash"]})
        return self.status(rid)
    def check_campaign(self,c):
        if not c["authorization"] or c["authorization"]["plan_hash"]!=digest(c["payload"]): raise Failure("plan_authorization_required",exit_code=3)
    def check_run(self,r):
        self.check_campaign(self.db.one("SELECT * FROM campaigns WHERE id=?",(r["campaign_id"],)))
        if r["payload"]["config_hash"]!=self.s.fingerprint(): raise Failure("config_changed","Use a new Run to preserve the authorized configuration snapshot",3)
        if r["payload"]["mode"]!=("fixture" if self.s.fixture else "live"): raise Failure("run_mode_mismatch",exit_code=3)
    def task(self,run,stage,inputs):
        h=digest(inputs)
        old=self.db.db.execute("SELECT * FROM work_items WHERE run_id=? AND stage=? AND subject='batch' AND input_hash=?",(run,stage,h)).fetchone()
        if old: return dict(old)["id"]
        tid=uid("ht")
        payload={"contract_version":CONTRACT,"inputs":inputs,"output_schema":"HostResult","allowed_evidence_ids":[r["id"] for r in self.db.materials(run)],"instructions_version":"1"}
        self.db.db.execute("INSERT INTO work_items(id,run_id,stage,subject,state,revision,input_hash,payload) VALUES(?,?,?,'batch','waiting_host',1,?,?)",(tid,run,stage,h,canonical(payload)))
        self.db.event(run,"host_usage_unpriced",{"task_id":tid,"stage":stage})
        self.project_task(tid)
        return tid
    def project_task(self,tid):
        t=self.db.one("SELECT * FROM work_items WHERE id=?",(tid,))
        folder=self.db.root/"runs"/t["run_id"]/"host-tasks";folder.mkdir(parents=True,exist_ok=True)
        path=folder/(tid+".json");path.write_text(canonical(t),encoding="utf-8")
        return str(path)
    def claim(self,tid,owner,lease_seconds=900):
        with self.db.tx():
            t=self.db.one("SELECT * FROM work_items WHERE id=?",(tid,))
            run=self.db.one("SELECT * FROM runs WHERE id=?",(t["run_id"],))
            if run["status"] in ("paused","cancelled"): raise Failure("run_not_active",exit_code=3)
            if t["state"]=="succeeded": return t
            if t["lease_until"] and t["lease_until"]>time.time(): raise Failure("lease_busy",exit_code=3)
            token=uid("lease")
            self.db.db.execute("UPDATE work_items SET state='leased',revision=revision+1,lease_owner=?,lease_token=?,lease_until=? WHERE id=?",(owner,token,time.time()+lease_seconds,tid))
        self.project_task(tid)
        return self.db.one("SELECT * FROM work_items WHERE id=?",(tid,))
    def validate_quotes(self, run, quotes, allowed, subject=None):
        if not quotes: raise Failure("evidence_required")
        for q in quotes:
            q=q.model_dump() if hasattr(q,"model_dump") else q
            if q["evidence_id"] not in allowed: raise Failure("evidence_out_of_scope")
            e=self.db.one("SELECT * FROM evidence WHERE id=? AND run_id=?",(q["evidence_id"],run))
            if subject and e["subject"]!=subject: raise Failure("evidence_subject_mismatch")
            text=(self.db.root/e["blob_ref"]).read_text()
            if q["text"] not in text: raise Failure("quote_not_found",q["evidence_id"])
    def submit(self, data):
        res=HostResult.model_validate(data)
        with self.db.tx():
            t=self.db.one("SELECT * FROM work_items WHERE id=?",(res.task_id,))
            h=digest(res.model_dump())
            if t["state"]=="succeeded":
                if t["result"]["accepted_hash"]==h: return {"status":"idempotent","task_id":res.task_id}
                raise Failure("result_already_accepted",exit_code=3)
            r=self.db.one("SELECT * FROM runs WHERE id=?",(t["run_id"],));self.check_run(r)
            if r["status"] in ("paused","cancelled"): raise Failure("run_not_active",exit_code=3)
            if t["state"]!="leased" or t["lease_token"]!=res.lease_token or t["revision"]!=res.expected_revision or t["input_hash"]!=res.input_hash or t["lease_until"]<time.time():
                raise Failure("stale_submission",exit_code=3)
            allowed=t["payload"]["allowed_evidence_ids"]
            if not set(res.evidence_refs)<=set(allowed): raise Failure("evidence_out_of_scope")
            inputs=t["payload"]["inputs"];stage=t["stage"];p=r["payload"];run=r["id"]
            if res.unknowns: p.setdefault("unknowns",[]).extend(res.unknowns)
            if res.result_status!="completed":
                p["errors"].append({"code":res.result_status,"stage":stage,"unknowns":res.unknowns})
                p["phase"]="finish"; self.db.put_run(run,p,"partial")
            elif stage=="plan_queries":
                if not res.queries: raise Failure("queries_required")
                p["queries"]=[q.model_dump() for q in res.queries];p["phase"]="discovery";self.db.put_run(run,p,"running")
            elif stage in ("review_fit","review_fit_degraded"):
                expected={a["company_id"] for a in inputs["accounts"]}
                if {x.company_id for x in res.accounts}!=expected or len(res.accounts)!=len(expected): raise Failure("batch_subject_mismatch")
                for a in res.accounts:
                    if a.buyer_role not in p["plan"]["buyer_roles"]+["none","unknown"]: raise Failure("buyer_role_out_of_scope")
                    d=a.model_dump();cid=a.company_id
                    if a.fit=="qualified":
                        if a.entity_status!="confirmed" or not a.country_match or a.buyer_role in ("none","unknown"): raise Failure("qualification_gate")
                        self.validate_quotes(run,a.fit_quotes,allowed,cid)
                        if not any(self.db.one("SELECT * FROM evidence WHERE id=?",(q.evidence_id,))["source_type"]=="web" for q in a.fit_quotes): raise Failure("primary_evidence_required")
                    for s in a.signals:
                        self.validate_quotes(run,s.quotes,allowed,cid)
                    if a.counter_evidence: self.validate_quotes(run,a.counter_evidence,allowed,cid)
                    for s in d["signals"]:
                        s["date_grounded"]=bool(s["published_at"] and any(s["published_at"][:10] in q["text"] and self.db.one("SELECT * FROM evidence WHERE id=?",(q["evidence_id"],))["source_type"]=="web" for q in s["quotes"]))
                    previous=self.db.one("SELECT * FROM campaign_accounts WHERE run_id=? AND company_id=?",(run,cid))["payload"]
                    d|={"jev":previous.get("jev"),"human_reviewed":False,"host_reviewed":True}
                    if stage!="review_fit_degraded" and d["fit"]=="qualified":
                        answers=(d.get("jev") or {}).get("answers",{})
                        if answers.get("fit",{}).get("choice")!="qualified" or answers.get("sufficiency",{}).get("choice")!="sufficient" or answers.get("fit",{}).get("confidence",0)<0.7:
                            d["fit"]="unknown";d["unknowns"].append("Jev and host judgment require reconciliation")
                    d["intent"]=intent_tier(d)
                    self.db.account(run,cid,d)
                p["phase"]="qualified";self.db.put_run(run,p,"running")
            elif stage=="review_contacts":
                expected={c["id"] for c in inputs["contacts"]}
                if {c.contact_id for c in res.contacts}!=expected or len(res.contacts)!=len(expected): raise Failure("batch_subject_mismatch")
                for c in res.contacts:
                    old=self.db.one("SELECT * FROM contacts WHERE id=? AND run_id=?",(c.contact_id,run))
                    d=old["payload"]
                    self.validate_quotes(run,c.quotes,allowed,old["company_id"])
                    if c.employment_confirmed and d.get("employment_domain")!=self.db.one("SELECT * FROM companies WHERE id=?",(old["company_id"],))["domain"] and not any(self.db.one("SELECT * FROM evidence WHERE id=?",(q.evidence_id,))["source_type"]=="web" for q in c.quotes):
                        raise Failure("employment_domain_conflict")
                    d["review"]=c.model_dump();d["reviewed_at"]=now()
                    self.db.db.execute("UPDATE contacts SET payload=?,revision=revision+1 WHERE id=?",(canonical(d),c.contact_id))
                p["phase"]="contact_reviewed";self.db.put_run(run,p,"running")
            elif stage=="generate_drafts":
                pairs={(c["company_id"],c["id"]) for c in inputs["contacts"]}
                seen=set()
                for d in res.drafts:
                    if (d.company_id,d.contact_id) not in pairs or d.company_id in seen: raise Failure("draft_subject_mismatch")
                    seen.add(d.company_id)
                    self.validate_quotes(run,d.evidence_quotes,allowed,d.company_id)
                    facts={f["id"] for f in p["plan"]["product_facts"]}
                    if not set(d.product_fact_ids)<=facts: raise Failure("product_fact_out_of_scope")
                    self.save_message(run,d.model_dump())
                p["phase"]="drafted";self.db.put_run(run,p,"running")
            else: raise Failure("unsupported_host_task")
            self.db.db.execute("UPDATE work_items SET state='succeeded',result=? WHERE id=?",(canonical({"accepted_hash":h,"output":res.model_dump()}),res.task_id))
            self.db.event(run,"host_result_accepted",{"task":res.task_id,"hash":h})
        return {"status":"accepted","task_id":res.task_id}
    def dependency(self, run, company, contact):
        r=self.db.one("SELECT * FROM runs WHERE id=?",(run,))
        a=self.db.one("SELECT * FROM campaign_accounts WHERE run_id=? AND company_id=?",(run,company))
        c=self.db.one("SELECT * FROM contacts WHERE id=? AND run_id=?",(contact,run))
        return digest([r["payload"]["plan_hash"],a["revision"],a["payload"],c["revision"],c["payload"],self.s.sender()])
    def save_message(self, run, d):
        from .sending import freeze_message
        c=self.db.one("SELECT * FROM contacts WHERE id=? AND run_id=?",(d["contact_id"],run))
        if not self.draft_allowed(c): raise Failure("contact_not_draftable")
        m=freeze_message(self.s,d,c["payload"]["email"])
        mid=uid("msg");dep=self.dependency(run,d["company_id"],d["contact_id"])
        self.db.db.execute("INSERT INTO messages(id,run_id,company_id,contact_id,revision,state,content_hash,dependency_digest,payload) VALUES(?,?,?,?,1,'draft',?,?,?)",(mid,run,d["company_id"],d["contact_id"],digest(m),dep,canonical(m)))
        return mid
    @staticmethod
    def draft_allowed(c):
        d=c["payload"];review=d.get("review",{})
        return bool(d.get("email") and d.get("source") in ("public","provider") and review.get("person_confirmed") and review.get("employment_confirmed") and review.get("role_relevant") and not d.get("domain_conflict"))
    def add_company(self, run, name, host, country, source):
        cid="co_"+digest([host,name.strip().casefold(),country])[:28]
        self.db.db.execute("INSERT OR IGNORE INTO companies VALUES(?,?,?,?,?)",(cid,host,name,country,canonical({"identity_status":"candidate","sources":[source]})))
        self.db.db.execute("INSERT OR IGNORE INTO campaign_accounts VALUES(?,?,1,?)",(run,cid,canonical({"fit":"unknown","sources":[source],"read_done":False,"judge_done":False})))
        return cid
    async def advance(self,rid,seconds=30):
        with self.db.lock():
            r=self.db.one("SELECT * FROM runs WHERE id=?",(rid,));self.check_run(r)
            if r["status"] in ("paused","cancelled","completed","partial"): return self.status(rid)
            p=r["payload"];plan=Plan.model_validate(p["plan"]);deadline=time.monotonic()+seconds
            providers=Providers(self.s,self.db,rid,plan)
            try:
                while time.monotonic()<deadline:
                    phase=p["phase"]
                    if phase=="queries":
                        if plan.seeds:
                            for s in plan.seeds:
                                cid=self.add_company(rid,s.name,s.domain,s.country,s.source)
                                self.db.evidence(rid,cid,"import",s.source,canonical(s.model_dump()),{"claimed_country":s.country})
                            if plan.entry=="enrichment": p["phase"]="read";self.db.put_run(rid,p,"running");continue
                        if not p["queries"]:
                            self.task(rid,"plan_queries",{"plan":plan.model_dump(),"industry_pack":p["industry_pack"]});self.db.put_run(rid,p,"waiting_host");break
                        p["phase"]="discovery"
                    elif phase=="discovery":
                        if p["query_index"]>=len(p["queries"]) or self.count(rid)>=plan.candidate_limit:
                            p["phase"]="read";self.db.put_run(rid,p,"running");continue
                        q=p["queries"][p["query_index"]]
                        response,hits=await providers.search(q["text"])
                        seen={row["domain"] for row in self.db.all("SELECT c.* FROM companies c JOIN campaign_accounts a ON a.company_id=c.id WHERE a.run_id=?",(rid,))}
                        for hit in hits:
                            try: host=domain(hit["url"])
                            except Failure: continue
                            if host in seen or host in ("linkedin.com","facebook.com","alibaba.com","amazon.com","youtube.com","made-in-china.com"): continue
                            if self.count(rid)>=plan.candidate_limit: break
                            cid=self.add_company(rid,hit["name"],host,plan.country,hit["url"]);seen.add(host)
                            self.db.evidence(rid,cid,"search",hit["url"],canonical(hit),{"query":q,"operation_id":response["operation_id"]})
                        p["query_index"]+=1
                    elif phase=="read":
                        rows=self.db.all("SELECT a.*,c.domain,c.name FROM campaign_accounts a JOIN companies c ON c.id=a.company_id WHERE a.run_id=?",(rid,))
                        pending=[a for a in rows if not a["payload"].get("read_done")]
                        if not pending: p["phase"]="judge";self.db.put_run(rid,p,"running");continue
                        async def read_one(a):
                            cid=a["company_id"];d=a["payload"]
                            blocked=False
                            url="https://"+a["domain"]
                            try:
                                resp=await providers.read(url);text=resp["data"].get("text",canonical(resp["data"]))
                                self.db.evidence(rid,cid,"web",url,text,{"operation_id":resp["operation_id"],"observed_at":resp.get("observed_at")})
                                # Follow only observed same-host links and prioritize procurement/use-case pages.
                                links=re.findall(r"\]\((https?://[^\s)]+|/[^\s)]*)\)",text)
                                links=sorted(set(urljoin(url,l) for l in links),key=lambda l:0 if re.search(r"contact|about|project|procure|tender|product|network|transceiver",l,re.I) else 1)
                                for link in [l for l in links if domain(l)==a["domain"] and l.rstrip("/")!=url][:plan.pages_per_company-1]:
                                    try:
                                        more=await providers.read(link)
                                        self.db.evidence(rid,cid,"web",link,more["data"].get("text",canonical(more["data"])),{"operation_id":more["operation_id"],"observed_at":more.get("observed_at")})
                                    except Failure as e:
                                        d.setdefault("read_errors",[]).append(e.code)
                                        blocked|=e.code in ("waiting_provider","unknown_external_result","integration_blocked","cost_quote_required","budget_exhausted","call_limit_exhausted")
                            except Failure as e:
                                d.setdefault("read_errors",[]).append(e.code)
                                blocked|=e.code in ("waiting_provider","unknown_external_result","integration_blocked","cost_quote_required","budget_exhausted","call_limit_exhausted")
                            d["read_done"]=not blocked;self.db.account(rid,cid,d)
                        await asyncio.gather(*(read_one(a) for a in pending[:self.s.integer("LEAD_HUNTER_CONCURRENCY")]))
                        stalled=[a for a in self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,)) if not a["payload"].get("read_done") and a["payload"].get("read_errors")]
                        if stalled:
                            p["stop_reason"]=stalled[0]["payload"]["read_errors"][-1]
                            self.db.put_run(rid,p,"partial" if p["stop_reason"] in ("budget_exhausted","call_limit_exhausted") else "waiting_provider");break
                    elif phase=="judge":
                        accounts=self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,))
                        pending=[a for a in accounts if not a["payload"].get("judge_done")]
                        if pending:
                            async def judge_one(a):
                                d=a["payload"];cid=a["company_id"]
                                mats=self.db.materials(rid,cid)
                                state={"company":self.db.one("SELECT * FROM companies WHERE id=?",(cid,)),"scope":{"country":plan.country,"icp":plan.icp,"buyer_roles":plan.buyer_roles,"exclusions":plan.exclusions},"evidence":[{"id":m["id"],"source_type":m["source_type"],"text":m["text"][:12000]} for m in mats]}
                                try:
                                    res=await providers.judge(state);d["jev"]=res["data"];d["judge_done"]=True
                                except Failure as e:
                                    d["judge_error"]=e.code
                                    if self.s.get("JEV_FAILURE_POLICY")=="host": d["judge_done"]=True;p["degraded"]=True
                                self.db.account(rid,cid,d)
                            await asyncio.gather(*(judge_one(a) for a in pending[:self.s.integer("LEAD_HUNTER_CONCURRENCY")]))
                            remaining=[a for a in self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,)) if not a["payload"].get("judge_done")]
                            if remaining and any(a["payload"].get("judge_error") for a in remaining):
                                p["stop_reason"]="integration_blocked";self.db.put_run(rid,p,"waiting_provider");break
                            self.db.put_run(rid,p,"running");continue
                        if not accounts: p["phase"]="finish";continue
                        self.task(rid,"review_fit_degraded" if p["degraded"] else "review_fit",{"plan":plan.model_dump(),"accounts":accounts,"materials":self.db.materials(rid)})
                        p["phase"]="await_fit";self.db.put_run(rid,p,"waiting_host");break
                    elif phase in ("await_fit","await_contacts","await_drafts"):
                        self.db.put_run(rid,p,"waiting_host");break
                    elif phase=="qualified":
                        qualified=[a for a in self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,)) if a["payload"].get("fit")=="qualified"]
                        qualified.sort(key=lambda a:-a["payload"]["intent"]["score"])
                        p["selected"]=[a["company_id"] for a in qualified[:plan.target_count]]
                        p["phase"]="finish" if plan.endpoint=="accounts" else "contacts"
                    elif phase=="contacts":
                        if plan.endpoint=="accounts": raise Failure("endpoint_gate")
                        selected=p.get("selected",[])
                        pending=[]
                        for cid in selected:
                            a=self.db.one("SELECT * FROM campaign_accounts WHERE run_id=? AND company_id=?",(rid,cid))
                            if not a["payload"].get("contacts_done"): pending.append((cid,a))
                        if pending:
                            async def contacts_one(cid,a):
                                d=a["payload"];company=self.db.one("SELECT * FROM companies WHERE id=?",(cid,))
                                try:
                                    response=await providers.people(company)
                                    eid=self.db.evidence(rid,cid,"provider","treg:"+response["operation_id"],canonical(response["data"]),{"operation_id":response["operation_id"],"observed_at":response.get("observed_at")})
                                    people=providers.people_rows(response)
                                    for item in people[:plan.contacts_per_company]:
                                        email=item.get("email");domain_conflict=False;ids=[eid]
                                        if not email:
                                            f=await providers.find_email(item["name"],company)
                                            ids.append(self.db.evidence(rid,cid,"provider","treg:"+f["operation_id"],canonical(f["data"])))
                                            email=f["data"].get("output",{}).get("email")
                                            if providers.inferred_email(f["data"].get("output",{})): item["source"]="inferred"
                                            domain_conflict=f["data"].get("_treg",{}).get("domain_match") is False
                                        if not email: continue
                                        try: email=email_normalize(email)
                                        except Failure: continue
                                        domain_conflict|=domain(email.rsplit("@",1)[1])!=company["domain"]
                                        v=await providers.verify(email)
                                        ids.append(self.db.evidence(rid,cid,"provider","treg:"+v["operation_id"],canonical(v["data"])))
                                        public=[m["id"] for m in self.db.materials(rid,cid) if m["source_type"]=="web" and email in observed_emails(m["text"])]
                                        contact_id="ct_"+digest([rid,cid,email,item["name"]])[:28]
                                        observed=v.get("observed_at") or self.db.one("SELECT * FROM provider_operations WHERE id=?",(v["operation_id"],))["created_at"]
                                        payload=item|{"email":email,"domain_conflict":domain_conflict,"source":"public" if public else item["source"],"evidence_ids":ids+public,"verification":{"verdict":providers.verdict(v),"checked_at":observed,"expires_at":datetime.fromisoformat(observed).timestamp()+86400,"provider":"treg","operation_id":v["operation_id"]},"review":{},"mapper_version":"1"}
                                        self.db.db.execute("INSERT OR IGNORE INTO contacts VALUES(?,?,?,1,?)",(contact_id,rid,cid,canonical(payload)))
                                    d["contacts_done"]=True
                                except Failure as e:
                                    d["contact_error"]=e.code
                                    p["errors"].append({"code":e.code,"company_id":cid,"stage":"contacts"})
                                    d["contacts_done"]=e.code not in ("waiting_provider","unknown_external_result","integration_blocked","cost_quote_required","budget_exhausted","call_limit_exhausted")
                                self.db.account(rid,cid,d)
                            await asyncio.gather(*(contacts_one(cid,a) for cid,a in pending[:2]))
                            stalled=[a for a in self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,)) if a["company_id"] in selected and not a["payload"].get("contacts_done") and a["payload"].get("contact_error")]
                            if stalled:
                                p["stop_reason"]=stalled[0]["payload"]["contact_error"]
                                self.db.put_run(rid,p,"partial" if p["stop_reason"] in ("budget_exhausted","call_limit_exhausted") else "waiting_provider");break
                            self.db.put_run(rid,p,"running");continue
                        contacts=self.db.all("SELECT * FROM contacts WHERE run_id=?",(rid,))
                        if not contacts: p["phase"]="finish";continue
                        self.task(rid,"review_contacts",{"plan":plan.model_dump(),"contacts":contacts,"materials":self.db.materials(rid)})
                        p["phase"]="await_contacts";self.db.put_run(rid,p,"waiting_host");break
                    elif phase=="contact_reviewed":
                        if plan.endpoint=="contacts": p["phase"]="finish";continue
                        contacts=[c for c in self.db.all("SELECT * FROM contacts WHERE run_id=?",(rid,)) if self.draft_allowed(c)]
                        if not contacts: p["phase"]="finish";continue
                        self.task(rid,"generate_drafts",{"plan":plan.model_dump(),"contacts":contacts,"accounts":self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,)),"materials":self.db.materials(rid),"sender":self.s.sender()})
                        p["phase"]="await_drafts";self.db.put_run(rid,p,"waiting_host");break
                    elif phase=="drafted":
                        if plan.endpoint=="first_outreach":
                            messages=self.db.all("SELECT * FROM messages WHERE run_id=? AND state!='stale'",(rid,))
                            if self.summary(rid)["sender_accepted"]>=plan.target_count or not messages or all(m["state"]=="accepted" for m in messages):
                                p["phase"]="finish";self.db.put_run(rid,p,"running");continue
                            if any(m["state"] in ("unknown","dispatching","reserved","needs_review") for m in messages):
                                p["stop_reason"]="send_reconciliation_required";self.db.put_run(rid,p,"waiting_provider");break
                            self.db.put_run(rid,p,"waiting_approval");break
                        p["phase"]="finish"
                    elif phase=="finish":
                        stats=self.summary(rid);key={"accounts":"qualified_count","contacts":"reachable_count","drafts":"draft_count","first_outreach":"sender_accepted"}[plan.endpoint]
                        done=stats[key]>=plan.target_count and not p["degraded"]
                        p["stop_reason"]="target_reached" if done else "target_not_met_or_unresolved"
                        self.db.put_run(rid,p,"completed" if done else "partial");break
                    else: raise Failure("invalid_run_phase",phase)
                    self.db.put_run(rid,p,"running")
            except Failure as e:
                p["errors"].append({"code":e.code,"stage":p["phase"],"message":e.message})
                p["stop_reason"]=e.code
                self.db.put_run(rid,p,"partial" if e.code in ("budget_exhausted","call_limit_exhausted") else "waiting_provider")
            finally: await providers.close()
            return self.status(rid)
    def count(self,rid): return self.db.db.execute("SELECT count(*) FROM campaign_accounts WHERE run_id=?",(rid,)).fetchone()[0]
    def summary(self,rid):
        a=self.db.all("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,));c=self.db.all("SELECT * FROM contacts WHERE run_id=?",(rid,));m=self.db.all("SELECT * FROM messages WHERE run_id=?",(rid,))
        return {"candidate_count":len(a),"qualified_count":sum(x["payload"].get("fit")=="qualified" for x in a),"human_reviewed_count":sum(x["payload"].get("human_reviewed",False) for x in a),"high_intent_signal_count":sum(x["payload"].get("intent",{}).get("tier")=="A" for x in a),"intent_tiers":{tier:sum(x["payload"].get("intent",{}).get("tier")==tier for x in a) for tier in ("A","B","C","review","excluded")},"reachable_count":len({x["company_id"] for x in c if self.draft_allowed(x) and x["payload"].get("verification",{}).get("verdict")=="valid" and x["payload"].get("verification",{}).get("expires_at",0)>time.time()}),"draft_count":len({x["company_id"] for x in m}),"sender_accepted":sum(x["state"]=="accepted" for x in m),"unknown_send_count":sum(x["state"] in ("unknown","dispatching") for x in m)}
    def status(self,rid):
        r=self.db.one("SELECT * FROM runs WHERE id=?",(rid,));tasks=self.db.all("SELECT id,stage,state,revision FROM work_items WHERE run_id=? AND state!='succeeded'",(rid,))
        cost=self.db.cost(rid);cost["limit_micro"]=r["payload"]["plan"]["budget_micro"]
        has_host=self.db.db.execute("SELECT 1 FROM work_items WHERE run_id=? LIMIT 1",(rid,)).fetchone() is not None
        cost["host_usage_unpriced"]=has_host
        cost["provider_usage_unpriced"]=cost["has_unpriced_usage"]
        cost["has_unpriced_usage"]|=has_host
        calls=self.db.all("SELECT provider,status,payload FROM provider_operations WHERE run_id=?",(rid,))
        live={x["provider"] for x in calls if x["status"]=="ok" and not x["payload"].get("response",{}).get("fixture",True)}
        next_action="export run" if r["status"] in ("completed","partial") else "provider operations / send reconcile" if r["status"]=="waiting_provider" else "host-task claim" if tasks else "approval prepare" if r["status"]=="waiting_approval" else "run advance"
        return {"run_id":rid,"status":r["status"],"revision":r["revision"],"phase":r["payload"]["phase"],"mode":r["payload"]["mode"],"integration_status":"fixture_only" if r["payload"]["mode"]=="fixture" else "degraded" if r["payload"]["degraded"] else "live_calls_observed" if {"jev","treg"}<=live else "not_verified","summary":self.summary(rid),"cost":cost,"host_tasks":tasks,"stop_reason":r["payload"].get("stop_reason"),"errors":r["payload"]["errors"],"unknowns":r["payload"].get("unknowns",[]),"next_action":next_action}
    def control(self,rid,action):
        # Serialize against advance; a pause never drops paid in-flight operations.
        with self.db.lock():
            r=self.db.one("SELECT * FROM runs WHERE id=?",(rid,))
            if action=="resume" and r["status"]=="cancelled": raise Failure("cancelled_run",exit_code=3)
            status={"pause":"paused","cancel":"cancelled","resume":"running"}[action]
            self.db.put_run(rid,r["payload"],status)
            self.db.event(rid,"run_"+action,{})
        return self.status(rid)
    def review_account(self,rid,cid,decision,actor,reference):
        with self.db.tx():
            a=self.db.one("SELECT * FROM campaign_accounts WHERE run_id=? AND company_id=?",(rid,cid));d=a["payload"]
            if decision=="accept" and d.get("fit")!="qualified": raise Failure("qualification_required")
            d|={"human_reviewed":decision=="accept","human_decision":decision,"reviewer":actor,"decision_ref":reference,"reviewed_at":now()}
            if decision=="reject": d["fit"]="rejected"
            d["intent"]=intent_tier(d)
            self.db.account(rid,cid,d)
            self.db.event(rid,"account_review",{"company_id":cid,"decision":decision,"actor":actor,"reference":reference})
            r=self.db.one("SELECT * FROM runs WHERE id=?",(rid,))
            if decision!="accept" and r["status"]=="completed":
                r["payload"]["stop_reason"]="review_changed_after_completion"
                self.db.put_run(rid,r["payload"],"partial")
        return {"status":"recorded","message_approvals_stale":True}
    def export(self,rid):
        r=self.db.one("SELECT * FROM runs WHERE id=?",(rid,))
        folder=self.db.root/"runs"/rid/"exports";folder.mkdir(parents=True,exist_ok=True)
        accounts=self.db.all("SELECT a.*,c.domain,c.name,c.country FROM campaign_accounts a JOIN companies c ON c.id=a.company_id WHERE a.run_id=?",(rid,));contacts=self.db.all("SELECT * FROM contacts WHERE run_id=?",(rid,));messages=self.db.all("SELECT * FROM messages WHERE run_id=?",(rid,))
        artifacts=[]
        for name,rows in (("accounts",accounts),("contacts",contacts),("messages",messages),("evidence",self.db.all("SELECT * FROM evidence WHERE run_id=?",(rid,)))):
            path=folder/(name+".jsonl");path.write_text("\n".join(canonical(x) for x in rows)+"\n",encoding="utf-8");artifacts.append(str(path))
        out=folder/"leads.csv"
        def safe(v):
            v=str(v if v is not None else "")
            return "'"+v if v.lstrip().startswith(("=","+","-","@","\t","\r")) else v
        with out.open("w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f);w.writerow(["company_id","company","domain","country","fit","intent_tier","intent_reason","human_reviewed","contacts","email_status","sources","unknowns"])
            for a in accounts:
                d=a["payload"];cs=[c for c in contacts if c["company_id"]==a["company_id"]]
                w.writerow([safe(v) for v in (a["company_id"],a["name"],a["domain"],a["country"],d.get("fit"),d.get("intent",{}).get("tier"),d.get("intent",{}).get("reason"),d.get("human_reviewed"),"; ".join(c["payload"].get("email","") for c in cs),"; ".join(c["payload"].get("verification",{}).get("verdict","") for c in cs),"; ".join(m["source_ref"] for m in self.db.materials(rid,a["company_id"])),"; ".join(d.get("unknowns",[])))])
        artifacts.append(str(out))
        status=self.status(rid);report=folder/"report.md"
        report.write_text("# 外贸获客运行报告\n\n"+"\n".join(f"- {k}: {v}" for k,v in status.items() if k not in ("summary","host_tasks"))+"\n\n```json\n"+json.dumps(status["summary"],ensure_ascii=False,indent=2)+"\n```\n\nA/B/C 是线索优先级，非回复概率。SMTP accepted 只表示服务器受理。真实采购意愿需要询盘/回复验证。\n",encoding="utf-8")
        artifacts.append(str(report))
        (folder.parent/"manifest.json").write_text(canonical({"run_id":rid,"plan":r["payload"]["plan"],"status":status}),encoding="utf-8")
        return {"status":"exported","artifacts":artifacts}

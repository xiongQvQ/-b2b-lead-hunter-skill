"""Machine-readable CLI. Every accepted write goes through the same services."""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
import httpx
from pydantic import ValidationError
from . import __version__
from .config import ROOT, Settings
from .contracts import CONTRACT, Draft, Failure, Plan, SCHEMAS, canonical, digest, domain, email_normalize, now, uid
from .providers import Providers
from .service import Service
from .sending import Sender
from .storage import Store

def read_json(path):
    if path=="-": return json.load(sys.stdin)
    with open(path,encoding="utf-8") as f: return json.load(f)

def parser():
    p=argparse.ArgumentParser(description="Evidence-first B2B lead hunter V1.0-A")
    p.add_argument("--env-file");p.add_argument("--state-dir");p.add_argument("--mode",choices=("live","fixture"));p.add_argument("--json",action="store_true")
    groups=p.add_subparsers(dest="group",required=True)
    def cmd(group,actions):
        g=groups.add_parser(group);sub=g.add_subparsers(dest="action",required=True)
        return {a:sub.add_parser(a) for a in actions}
    def flag(c,*names,**kw): c.add_argument(*names,**kw)
    def ident(c,name): flag(c,"--"+name,required=True)
    def decision(c): ident(c,"actor");ident(c,"decision-ref")
    cs=cmd("doctor",["check"])
    cs=cmd("plan",["create","validate","show","authorize","diff"])
    for a in ("create","validate"): ident(cs[a],"file")
    for a in ("show","authorize","diff"): ident(cs[a],"campaign-id")
    decision(cs["authorize"]);ident(cs["authorize"],"plan-hash");ident(cs["diff"],"file")
    cs=cmd("campaign",["show","coverage"])
    for c in cs.values(): ident(c,"campaign-id")
    cs=cmd("run",["create","advance","status","pause","cancel","resume"])
    ident(cs["create"],"campaign-id")
    for a,c in cs.items():
        if a!="create": ident(c,"run-id")
    flag(cs["advance"],"--seconds",type=int,default=30)
    cs=cmd("host-task",["list","show","claim","submit"])
    ident(cs["list"],"run-id")
    for a in ("show","claim"): ident(cs[a],"task-id")
    ident(cs["claim"],"owner");flag(cs["claim"],"--lease-seconds",type=int,default=900);ident(cs["submit"],"file")
    cs=cmd("review",["export","submit"])
    for c in cs.values(): ident(c,"run-id")
    ident(cs["submit"],"company-id");flag(cs["submit"],"--decision",required=True,choices=("accept","reject","needs_review"));decision(cs["submit"])
    cs=cmd("message",["list","show","revise"])
    ident(cs["list"],"run-id");ident(cs["show"],"message-id");ident(cs["revise"],"message-id");ident(cs["revise"],"file")
    cs=cmd("approval",["prepare","record","revoke"])
    for c in cs.values(): ident(c,"message-id")
    decision(cs["record"]);ident(cs["record"],"content-hash");ident(cs["record"],"dependency-digest");flag(cs["record"],"--ttl-seconds",type=int,default=86400);ident(cs["revoke"],"decision-ref")
    cs=cmd("send",["dry-run","dispatch","reconcile"])
    for c in cs.values(): ident(c,"message-id")
    decision(cs["reconcile"]);flag(cs["reconcile"],"--outcome",choices=("accepted","failed","needs_review"),required=True)
    cs=cmd("suppression",["add","list"])
    flag(cs["add"],"--kind",choices=("email","domain","company"),required=True);ident(cs["add"],"target");ident(cs["add"],"reason")
    cs=cmd("export",["run"]);ident(cs["run"],"run-id")
    cs=cmd("schema",["export"]);flag(cs["export"],"--directory")
    cs=cmd("state",["backup"])
    cs=cmd("provider",["catalog","probe","operations","recover","reconcile"])
    flag(cs["catalog"],"--endpoint",choices=("treg.people.search","treg.people.email.find","treg.people.email.verify"),required=True)
    for a in ("operations","probe"): ident(cs[a],"run-id")
    flag(cs["probe"],"--capability",choices=("search","read","judge","people","find-email","verify"),required=True);ident(cs["probe"],"file");flag(cs["probe"],"--authorized-cost-micro",type=int,required=True)
    for a in ("recover","reconcile"): ident(cs[a],"operation-id")
    flag(cs["recover"],"--remote-id")
    ident(cs["reconcile"],"file");flag(cs["reconcile"],"--actual-micro",required=True,type=int);decision(cs["reconcile"])
    cs=cmd("migrate",["legacy-import"])
    ident(cs["legacy-import"],"file");flag(cs["legacy-import"],"--kind",choices=("sent","unknown-send","suppression"),required=True);ident(cs["legacy-import"],"source-ref")
    # Unsupported milestones fail explicitly rather than presenting fake successful jobs.
    for group in ("research","compare","outcome"):
        g=groups.add_parser(group);g.add_argument("remainder",nargs=argparse.REMAINDER)
    return p

def doctor(s,db):
    provider=s.get("JEV_PROVIDER")
    jev_key={"typesafe":"TYPESAFE_API_KEY","openrouter":"OPENROUTER_API_KEY"}.get(provider,"JEV_API_KEY")
    needs={"search":["SERPER_API_KEY","SERPER_CALL_CAP_MICRO"],"reader":["JINA_API_KEY","JINA_CALL_CAP_MICRO"],"jev":[jev_key,"JEV_CALL_CAP_MICRO"],"treg":["TREG_TOKEN","TREG_CALL_CAP_MICRO"],"smtp":["SMTP_HOST","SENDER_EMAIL","SENDER_POSTAL_ADDRESS"]}
    caps={}
    for capability,keys in needs.items():
        missing=[k for k in keys if not s.get(k) or (k.endswith("CAP_MICRO") and s.integer(k)<=0)]
        if capability=="jev" and s.get("JEV_API_KEY"): missing=[k for k in missing if not k.endswith("API_KEY")]
        caps[capability]={"configured":not missing,"missing":missing,"online_verified":False}
    if provider=="openai_compatible" and not s.get("JEV_BASE_URL"):
        caps["jev"]["configured"]=False;caps["jev"]["missing"].append("JEV_BASE_URL")
    return {"status":"fixture_ready" if s.fixture else "configured" if all(caps[k]["configured"] for k in ("search","reader","jev","treg")) else "integration_blocked","version":__version__,"contract_version":CONTRACT,"db_schema_version":1,"state_dir":str(db.root),"mode":"fixture" if s.fixture else "live","capabilities":caps,"jev_provider":provider,"jev_base_url":s.get("JEV_BASE_URL"),"treg_rest_host":s.get("TREG_BASE_URL"),"supported_endpoints":["accounts","contacts","drafts","first_outreach"],"research":"capability_unavailable","paid_calls_made":0,"config_hash":s.fingerprint(),"contact_policy":s.get("CONTACT_POLICY")}

async def recover(s,db,oid,remote_id):
    op=db.one("SELECT * FROM provider_operations WHERE id=?",(oid,))
    if op["provider"]!="treg": raise Failure("manual_reconciliation_required",exit_code=4)
    rid=remote_id or op["remote_id"]
    if not rid or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in rid): raise Failure("valid_remote_call_id_required")
    if not s.get("TREG_TOKEN"): raise Failure("integration_blocked",exit_code=4)
    # Query original operation. Never repeat the paid /call submission here.
    async with httpx.AsyncClient(timeout=25,follow_redirects=False,trust_env=False) as client:
        r=await client.get("https://treg.to/calls/"+rid+"/result",headers={"X-Treg-Token":s.get("TREG_TOKEN")})
        if r.status_code in (202,404,409): return {"status":"waiting_provider","remote_id":rid,"no_paid_resubmission":True}
        if not r.is_success: raise Failure("provider_recovery_failed",str(r.status_code),4)
        if len(r.content)>s.integer("LEAD_HUNTER_MAX_RESPONSE_BYTES"): raise Failure("response_too_large",exit_code=4)
        recovered=r.json()
        path=db.root/"runs"/op["run_id"]/"recovered";path.mkdir(parents=True,exist_ok=True)
        f=path/(oid+".json");f.write_text(canonical(recovered))
        db.event(op["run_id"],"provider_result_recovered",{"operation":oid,"remote_id":rid,"blob":db.blob(canonical(recovered))[1]})
        return {"status":"recovered_for_review","artifact":str(f),"next_action":"provider reconcile with actual charged amount and normalized result envelope","no_paid_resubmission":True}

def legacy(db,args):
    raw=Path(args.file).read_bytes();file_hash=digest(raw.hex());backup=db.backup()
    rows=[json.loads(x) for x in raw.decode("utf-8-sig").splitlines() if x.strip()]
    imported=0
    with db.tx():
        for i,row in enumerate(rows,1):
            key=digest([file_hash,i,"legacy-1"])
            if db.db.execute("SELECT 1 FROM event_log WHERE id=?",("migration_"+key,)).fetchone(): continue
            # Historic contacts block new sends; never upgrade legacy assertions to verified facts.
            targets=[]
            if row.get("email"): targets.append(("email",email_normalize(row["email"])))
            if row.get("domain"): targets.append(("domain",domain(row["domain"])))
            if not targets: raise Failure("legacy_target_missing","line "+str(i))
            for kind,target in targets:
                db.db.execute("INSERT OR IGNORE INTO suppression VALUES(?,?,?,?)",(kind,target,"legacy_"+args.kind+":"+args.source_ref,now()))
            db.db.execute("INSERT INTO event_log VALUES(?,NULL,'legacy_import',?,?)",("migration_"+key,canonical({"source_file_hash":file_hash,"line_no":i,"source_ref":args.source_ref,"legacy_id":row.get("id"),"kind":args.kind,"trusted_status":"legacy_unknown","raw_blob":db.blob(canonical(row))[1]}),now()))
            imported+=1
    return {"status":"imported","rows_imported":imported,"backup":backup,"policy":"Conservative suppression of legacy sent/unknown/suppressed contacts. No verification or approvals promoted."}

def execute(args,s,db):
    app=Service(s,db);sender=Sender(app);g=args.group;a=getattr(args,"action",None)
    if g in ("research","compare","outcome"): raise Failure("capability_unavailable",g+" is outside V1.0-A")
    if g=="doctor": return doctor(s,db)
    if g=="plan":
        if a=="create": return app.create_plan(read_json(args.file))
        if a=="validate":
            p=Plan.model_validate(read_json(args.file));return {"status":"valid","plan_hash":digest(p.model_dump())}
        if a=="authorize": return app.authorize(args.campaign_id,args.actor,args.decision_ref,args.plan_hash)
        c=db.one("SELECT * FROM campaigns WHERE id=?",(args.campaign_id,))
        if a=="show": return c
        new=Plan.model_validate(read_json(args.file)).model_dump()
        return {"old_hash":digest(c["payload"]),"new_hash":digest(new),"changed_fields":[k for k in new if new[k]!=c["payload"].get(k)],"next_action":"plan create for an immutable new scope"}
    if g=="campaign":
        c=db.one("SELECT * FROM campaigns WHERE id=?",(args.campaign_id,))
        if a=="show": return c
        return {"campaign_id":c["id"],"runs":db.all("SELECT id,status,created_at FROM runs WHERE campaign_id=?",(c["id"],)),"note":"Company facts may be reused through valid provider cache; campaign assessments remain separate."}
    if g=="run":
        if a=="create": return app.create_run(args.campaign_id)
        if a=="advance":
            if not 1<=args.seconds<=60: raise Failure("invalid_timeslice")
            return asyncio.run(app.advance(args.run_id,args.seconds))
        if a=="status": return app.status(args.run_id)
        return app.control(args.run_id,a)
    if g=="host-task":
        if a=="list": return {"tasks":db.all("SELECT id,stage,state,revision,lease_owner,lease_until FROM work_items WHERE run_id=?",(args.run_id,))}
        if a=="show": return db.one("SELECT * FROM work_items WHERE id=?",(args.task_id,))
        if a=="claim":
            if not 30<=args.lease_seconds<=3600: raise Failure("invalid_lease_duration")
            return app.claim(args.task_id,args.owner,args.lease_seconds)
        return app.submit(read_json(args.file))
    if g=="review":
        if a=="export": return {"accounts":db.all("SELECT a.*,c.name,c.domain FROM campaign_accounts a JOIN companies c ON c.id=a.company_id WHERE a.run_id=?",(args.run_id,))}
        return app.review_account(args.run_id,args.company_id,args.decision,args.actor,args.decision_ref)
    if g=="message":
        if a=="list": return {"messages":db.all("SELECT id,company_id,contact_id,state,content_hash FROM messages WHERE run_id=?",(args.run_id,))}
        if a=="show": return sender.get(args.message_id)
        draft=Draft.model_validate(read_json(args.file))
        with db.lock("sender"),db.tx():
            old=sender.get(args.message_id)
            if old["state"] not in ("draft","ready","stale","blocked","failed"): raise Failure("message_not_editable",exit_code=3)
            if draft.company_id!=old["company_id"] or draft.contact_id!=old["contact_id"]: raise Failure("message_subject_mismatch")
            refs=[x["id"] for x in db.materials(old["run_id"],old["company_id"])]
            app.validate_quotes(old["run_id"],draft.evidence_quotes,refs,old["company_id"])
            facts={x["id"] for x in db.one("SELECT * FROM runs WHERE id=?",(old["run_id"],))["payload"]["plan"]["product_facts"]}
            if not set(draft.product_fact_ids)<=facts: raise Failure("product_fact_out_of_scope")
            mid=app.save_message(old["run_id"],draft.model_dump())
            db.db.execute("UPDATE messages SET state='stale' WHERE id=?",(old["id"],))
            db.event(old["run_id"],"message_revised",{"old":old["id"],"new":mid})
        return {"message_id":mid,"status":"draft","approval_required":True}
    if g=="approval":
        if a=="prepare": return sender.prepare(args.message_id)
        if a=="revoke": return sender.revoke(args.message_id,args.decision_ref)
        if not 1<=args.ttl_seconds<=86400: raise Failure("invalid_approval_ttl")
        return sender.approve(args.message_id,args.actor,args.decision_ref,args.content_hash,args.dependency_digest,args.ttl_seconds)
    if g=="send":
        if a=="dry-run": return sender.dry_run(args.message_id)
        if a=="dispatch": return sender.dispatch(args.message_id)
        return sender.reconcile(args.message_id,args.outcome,args.actor,args.decision_ref)
    if g=="suppression":
        if a=="list": return {"suppression":db.all("SELECT * FROM suppression")}
        target=email_normalize(args.target) if args.kind=="email" else domain(args.target) if args.kind=="domain" else args.target
        db.db.execute("INSERT OR REPLACE INTO suppression VALUES(?,?,?,?)",(args.kind,target,args.reason,now()))
        db.event(None,"suppression_added",{"kind":args.kind,"target":target,"reason":args.reason})
        return {"status":"suppressed"}
    if g=="export": return app.export(args.run_id)
    if g=="schema":
        folder=Path(args.directory or db.root/"schemas");folder.mkdir(parents=True,exist_ok=True)
        files=[]
        for name,c in SCHEMAS.items():
            f=folder/(name+".schema.json");f.write_text(json.dumps(c.model_json_schema(),ensure_ascii=False,indent=2));files.append(str(f))
        return {"schemas":files,"contract_version":CONTRACT}
    if g=="state": return {"backup":db.backup(),"includes_blobs":False,"note":"Keep state blobs alongside the SQLite backup."}
    if g=="migrate": return legacy(db,args)
    if g=="provider":
        if a=="catalog":
            r=httpx.get("https://treg.to/catalog/endpoints/"+args.endpoint,timeout=25,follow_redirects=False,trust_env=False)
            r.raise_for_status();return {"status":"catalog_read","data":r.json(),"paid_calls_made":0}
        if a=="operations": return {"operations":db.all("SELECT * FROM provider_operations WHERE run_id=?",(args.run_id,))}
        if a=="recover": return asyncio.run(recover(s,db,args.operation_id,args.remote_id))
        if a=="reconcile":
            if args.actual_micro<0: raise Failure("invalid_cost")
            data=read_json(args.file)
            if not isinstance(data,dict) or not {"data","headers","status","operation_id","fixture"}<=set(data): raise Failure("normalized_envelope_required")
            with db.lock():
                op=db.one("SELECT * FROM provider_operations WHERE id=?",(args.operation_id,))
                if op["status"]=="ok" and op["actual"] is not None: raise Failure("operation_already_settled",exit_code=3)
                if data["operation_id"]!=op["id"]: raise Failure("operation_mismatch")
                data["actual_micro"]=args.actual_micro
                data.setdefault("observed_at",op["created_at"])
                db.settle(op["id"],"ok",data,args.actual_micro)
                db.event(op["run_id"],"provider_manual_reconcile",{"operation":op["id"],"actor":args.actor,"evidence_ref":args.decision_ref})
            return {"status":"reconciled","operation_id":op["id"],"note":"Resume the Run; original logical operation will be reused."}
        r=db.one("SELECT * FROM runs WHERE id=?",(args.run_id,));app.check_run(r)
        plan=Plan.model_validate(r["payload"]["plan"])
        capkey={"search":"SERPER","read":"JINA","judge":"JEV","people":"TREG","find-email":"TREG","verify":"TREG"}[args.capability]+"_CALL_CAP_MICRO"
        cap=1 if s.fixture else s.integer(capkey)
        if args.authorized_cost_micro<cap or cap<=0: raise Failure("probe_cost_authorization_insufficient")
        if args.capability in ("people","find-email","verify") and plan.endpoint=="accounts": raise Failure("endpoint_gate")
        data=read_json(args.file)
        async def probe():
            with db.lock():
                p=Providers(s,db,r["id"],plan)
                try:
                    if args.capability=="search": result=await p.search(data["query"])
                    elif args.capability=="read": result=await p.read(data["url"])
                    elif args.capability=="judge": result=await p.judge(data["state"])
                    elif args.capability=="people": result=await p.people(data["company"])
                    elif args.capability=="find-email": result=await p.find_email(data["name"],data["company"])
                    else: result=await p.verify(data["email"])
                    db.event(r["id"],"explicit_provider_probe",{"capability":args.capability,"authorized_cost_micro":args.authorized_cost_micro})
                    return {"status":"probe_completed","result":result,"real_integration_verified":not s.fixture}
                finally: await p.close()
        return asyncio.run(probe())
    raise Failure("unsupported_command")

def main(argv=None):
    # Accept --json anywhere without printing prose alongside JSON.
    argv=[x for x in (sys.argv[1:] if argv is None else argv) if x!="--json"]
    db=None;exit_code=0
    try:
        args=parser().parse_args(argv)
        os.umask(0o077)
        s=Settings(args.env_file,args.state_dir,args.mode);db=Store(s.state)
        result=execute(args,s,db)
        output={"contract_version":CONTRACT,"request_id":uid("req"),"errors":[],**result}
    except Failure as e:
        exit_code=e.exit_code;output={"contract_version":CONTRACT,"status":"error","errors":[{"code":e.code,"message":e.message,"retryable":False}]}
    except ValidationError as e:
        exit_code=2;output={"contract_version":CONTRACT,"status":"error","errors":[{"code":"contract_error","details":e.errors(include_input=False,include_context=False)}]}
    except (OSError,sqlite3.Error,httpx.HTTPError,json.JSONDecodeError,KeyError,ValueError) as e:
        # Exceptions may include auth URLs, raw SMTP responses or user data. Emit class only.
        exit_code=4;output={"contract_version":CONTRACT,"status":"error","errors":[{"code":"runtime_error","error_type":type(e).__name__,"message":"Check configuration/input and inspect protected state; secrets are omitted."}]}
    finally:
        if db: db.close()
    print(json.dumps(output,ensure_ascii=False,indent=2,default=str))
    raise SystemExit(exit_code)

if __name__=="__main__": main()

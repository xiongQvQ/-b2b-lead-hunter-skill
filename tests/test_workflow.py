import asyncio
import copy
import importlib.util
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import httpx
import pytest
from lead_hunter.config import ROOT, Settings
from lead_hunter.contracts import Failure, Plan, canonical, digest, observed_emails
from lead_hunter.providers import Providers, public_url
from lead_hunter.service import Service, intent_tier
from lead_hunter.sending import Sender
from lead_hunter.storage import Store

spec=importlib.util.spec_from_file_location("fixture_demo",ROOT/"scripts"/"demo.py")
demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)

def setup(tmp_path,endpoint="drafts",queries=True):
    env=tmp_path/"settings.env"
    env.write_text("SENDER_EMAIL=david@supplier.example\nSMTP_HOST=smtp.supplier.example\nSENDER_POSTAL_ADDRESS=Test address\nSEND_MIN_INTERVAL_SECONDS=0\n")
    s=Settings(env_file=env,state_dir=tmp_path/"state",mode="fixture")
    db=Store(s.state);app=Service(s,db)
    data=json.loads((ROOT/"assets"/"example-plan.json").read_text());data["endpoint"]=endpoint
    if not queries: data["queries"]=[]
    p=app.create_plan(data);app.authorize(p["campaign_id"],"human","test user request",p["plan_hash"])
    rid=app.create_run(p["campaign_id"])["run_id"]
    return app,rid

def finish(app,rid,human=False):
    for _ in range(30):
        status=asyncio.run(app.advance(rid,30))
        if status["status"] in ("completed","partial","waiting_approval"): return status
        for t in status["host_tasks"]:
            task=app.claim(t["id"],"host")
            result=demo.answer_fixture(app,task);app.submit(result)
            if human and task["stage"]=="review_fit":
                for a in result["accounts"]: app.review_account(rid,a["company_id"],"accept","human","reviewed fixture")
    raise AssertionError("did not terminate")

def send_setup(tmp_path):
    app,rid=setup(tmp_path,"first_outreach")
    finish(app,rid,human=True)
    # Promote only in this test harness to exercise live policy with fake SMTP.
    app.s.values["LEAD_HUNTER_MODE"]="live"
    r=app.db.one("SELECT * FROM runs WHERE id=?",(rid,));r["payload"]["mode"]="live";r["payload"]["config_hash"]=app.s.fingerprint()
    app.db.put_run(rid,r["payload"])
    m=app.db.one("SELECT * FROM messages WHERE run_id=?",(rid,))
    sender=Sender(app);prepared=sender.prepare(m["id"])
    assert prepared["blocking_reasons"]==[]
    sender.approve(m["id"],"human","approved exact fixture",prepared["content_hash"],prepared["dependency_digest"])
    return app,rid,sender,m["id"]

@pytest.mark.parametrize("endpoint",["accounts","contacts","drafts","first_outreach"])
def test_endpoint_end_to_end(tmp_path,endpoint):
    app,rid=setup(tmp_path,endpoint);status=finish(app,rid)
    assert status["status"]==("waiting_approval" if endpoint=="first_outreach" else "completed")
    assert status["integration_status"]=="fixture_only"
    ops=app.db.all("SELECT * FROM provider_operations WHERE run_id=?",(rid,))
    if endpoint=="accounts":
        assert not any(x["provider"]=="treg" for x in ops)
        assert not app.db.all("SELECT * FROM contacts")
        async def gateway_check():
            plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
            p=Providers(app.s,app.db,rid,plan)
            try:
                with pytest.raises(Failure,match="endpoint_gate"): await p.verify("a@buyer.example")
            finally: await p.close()
        asyncio.run(gateway_check())
    if endpoint in ("accounts","contacts"): assert not app.db.all("SELECT * FROM messages")
    assert status["summary"]["sender_accepted"]==0
    exports=app.export(rid)
    assert len(exports["artifacts"])==6
    assert all(Path(p).exists() for p in exports["artifacts"])
    app.db.close()

def test_host_plan_queries_and_recovery(tmp_path):
    app,rid=setup(tmp_path,queries=False);s=finish(app,rid)
    assert s["status"]=="completed"
    app.db.close();db=Store(app.s.state)
    assert Service(app.s,db).status(rid)["summary"]["draft_count"]==1

def test_host_lease_exclusive_stale_and_idempotent(tmp_path):
    app,rid=setup(tmp_path,queries=False)
    s=asyncio.run(app.advance(rid));tid=s["host_tasks"][0]["id"]
    t=app.claim(tid,"host-a")
    with pytest.raises(Failure,match="lease_busy"): app.claim(tid,"host-b")
    output=demo.answer_fixture(app,t)
    app.db.db.execute("UPDATE work_items SET lease_until=? WHERE id=?",(time.time()-1,tid))
    with pytest.raises(Failure,match="stale_submission"): app.submit(output)
    t2=app.claim(tid,"host-b");output2=demo.answer_fixture(app,t2)
    app.submit(output2)
    assert app.submit(output2)["status"]=="idempotent"
    with pytest.raises(Failure,match="result_already_accepted"): app.submit(output)

def test_wrong_quote_and_cross_subject_blocked(tmp_path):
    app,rid=setup(tmp_path)
    s=asyncio.run(app.advance(rid));task=app.claim(s["host_tasks"][0]["id"],"host")
    result=demo.answer_fixture(app,task)
    bad=copy.deepcopy(result);bad["accounts"][0]["fit_quotes"][0]["text"]="A made-up purchase order not in the evidence"
    with pytest.raises(Failure,match="quote_not_found"): app.submit(bad)
    bad=copy.deepcopy(result);bad["accounts"][0]["company_id"]="another-company"
    with pytest.raises(Failure,match="batch_subject_mismatch"): app.submit(bad)
    app.submit(result)

def test_parallel_budget_reservations(tmp_path):
    app,rid=setup(tmp_path)
    root=app.s.state
    def reserve(i):
        db=Store(root)
        try:
            db.reserve(rid,"treg","op"+str(i),70,{},100,100,10)
            return "reserved"
        except Failure as e: return e.code
        finally: db.close()
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(reserve,range(2)))
    assert sorted(results)==["budget_exhausted","reserved"]
    assert app.db.cost(rid)["reserved_micro"]==70

def test_unknown_cost_keeps_reservation(tmp_path):
    app,rid=setup(tmp_path)
    op,_=app.db.reserve(rid,"jev","test",80,{},100,100,10)
    app.db.settle(op["id"],"unknown",{},None)
    c=app.db.cost(rid)
    assert c["reserved_micro"]==80 and c["spent_micro"]==0 and c["has_unpriced_usage"]
    with pytest.raises(Failure,match="budget_exhausted"): app.db.reserve(rid,"jev","another",30,{},100,100,10)
    app.db.settle(op["id"],"ok",{},50)
    assert app.db.cost(rid)["reserved_micro"]==0

def test_scheduler_lock(tmp_path):
    app,rid=setup(tmp_path)
    with app.db.lock():
        other=Store(app.s.state)
        with pytest.raises(Failure,match="scheduler_busy"):
            asyncio.run(Service(app.s,other).advance(rid))

def test_config_change_and_pause(tmp_path):
    app,rid=setup(tmp_path)
    app.control(rid,"pause")
    assert asyncio.run(app.advance(rid))["status"]=="paused"
    app.control(rid,"resume")
    app.s.values["TREG_CALL_CAP_MICRO"]="123"
    with pytest.raises(Failure,match="config_changed"): asyncio.run(app.advance(rid))

def test_research_and_unknown_fields_rejected(tmp_path):
    app,rid=setup(tmp_path)
    data=app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"]
    data["endpoint"]="research"
    with pytest.raises(Failure,match="capability_unavailable"): app.create_plan(data)
    data["endpoint"]="accounts";data["smtp_password"]="should-never-be-accepted"
    with pytest.raises(ValueError): Plan.model_validate(data)

def test_direct_signal_required_for_a():
    assert intent_tier({"fit":"qualified","signals":[]})["tier"]=="C"
    assert intent_tier({"fit":"unknown","signals":[{"kind":"rfq","date_grounded":True,"published_at":"2026-11-01"}]})["tier"]=="review"
    assert intent_tier({"fit":"qualified","signals":[{"kind":"rfq","date_grounded":False,"published_at":"2026-11-01"}]})["tier"]=="C"

def test_dry_run_then_opt_out_blocks_dispatch(tmp_path,monkeypatch):
    app,rid,sender,mid=send_setup(tmp_path)
    assert sender.dry_run(mid)["status"]=="ready"
    assert app.db.one("SELECT * FROM messages WHERE id=?",(mid,))["company_touch"] is None
    m=sender.get(mid)
    app.db.db.execute("INSERT INTO suppression VALUES('email',?,'opt_out','test')",(m["payload"]["recipient"],))
    called=[];monkeypatch.setattr(sender,"transport",lambda p:called.append(p))
    with pytest.raises(Failure,match="suppressed_email"): sender.dispatch(mid)
    assert called==[]

def test_accepted_blocks_other_runs_and_repeated_send(tmp_path,monkeypatch):
    app,rid,sender,mid=send_setup(tmp_path)
    monkeypatch.setattr(sender,"transport",lambda p:{"status":"accepted","smtp_code":250})
    assert sender.dispatch(mid)["status"]=="accepted"
    assert asyncio.run(app.advance(rid))["status"]=="completed"
    with pytest.raises(Failure,match="outbox_state_accepted"): sender.dispatch(mid)
    m=sender.get(mid);newid=app.save_message(rid,m["payload"]["draft"])
    assert "first_touch_exists" in sender.prepare(newid)["blocking_reasons"]
    assert app.db.db.execute("SELECT count(*) FROM messages WHERE company_touch IS NOT NULL").fetchone()[0]==1

def test_crash_after_smtp_acceptance_stays_unknown(tmp_path,monkeypatch):
    app,rid,sender,mid=send_setup(tmp_path)
    def crash(payload): raise RuntimeError("simulated process crash after SMTP DATA accepted")
    monkeypatch.setattr(sender,"transport",crash)
    with pytest.raises(RuntimeError): sender.dispatch(mid)
    m=sender.get(mid)
    assert m["state"]=="unknown" and m["company_touch"] and m["quota_day"]
    with pytest.raises(Failure,match="outbox_state_unknown"): sender.dispatch(mid)
    sender.reconcile(mid,"accepted","human","SMTP server log confirms acceptance")
    assert sender.get(mid)["state"]=="accepted"

def test_known_failure_releases_quota(tmp_path,monkeypatch):
    app,rid,sender,mid=send_setup(tmp_path)
    monkeypatch.setattr(sender,"transport",lambda p:{"status":"failed","phase":"before_data"})
    sender.dispatch(mid);m=sender.get(mid)
    assert m["state"]=="failed" and not m["company_touch"] and not m["quota_day"]

def test_dependencies_change_invalidates_approval(tmp_path):
    app,rid,sender,mid=send_setup(tmp_path);m=sender.get(mid)
    app.review_account(rid,m["company_id"],"accept","human","new review")
    assert "stale_dependencies" in sender.dry_run(mid)["blocking_reasons"]
    app.db.db.execute("UPDATE messages SET payload=? WHERE id=?",(canonical(m["payload"]|{"subject":"Changed after approval"}),mid))
    assert "content_hash_mismatch" in sender.dry_run(mid)["blocking_reasons"]

def test_provider_email_draft_allowed_send_policy_separate(tmp_path):
    app,rid,sender,mid=send_setup(tmp_path);m=sender.get(mid)
    c=app.db.one("SELECT * FROM contacts WHERE id=?",(m["contact_id"],));d=c["payload"];d["source"]="provider"
    app.db.db.execute("UPDATE contacts SET payload=? WHERE id=?",(canonical(d),c["id"]))
    assert app.draft_allowed({"payload":d})
    assert "provider_contact_policy_block" in sender.dry_run(mid)["blocking_reasons"]

def test_fixture_can_never_send(tmp_path):
    app,rid=setup(tmp_path,"first_outreach");finish(app,rid)
    m=app.db.one("SELECT * FROM messages WHERE run_id=?",(rid,))
    assert "fixture_send_forbidden" in Sender(app).prepare(m["id"])["blocking_reasons"]

def test_treg_mapping_never_promotes_catchall():
    assert Providers.verdict({"data":{"output":{"valid":True,"status":"accept_all"}}})=="accept_all"
    assert Providers.verdict({"data":{"output":{"valid":True}}})=="unknown"
    assert Providers.verdict({"data":{"output":{"valid":True,"status":"valid"},"_treg":{"verification":{"verdict":"invalid"}}}})=="invalid"
    with pytest.raises(Failure,match="provider_contract_error"): Providers.people_rows({"data":{"output":{"rows":[]}}})

def test_private_url_blocked():
    for url in ("http://127.0.0.1/admin","http://169.254.169.254/","file:///etc/passwd","https://user:pass@example.com","http://[::1]/"):
        with pytest.raises(Failure): asyncio.run(public_url(url))

def test_paid_timeout_never_blindly_resubmits(tmp_path):
    app,rid=setup(tmp_path)
    app.s.values["LEAD_HUNTER_MODE"]="live";app.s.values["TREG_TOKEN"]="mock-secret";app.s.values["TREG_CALL_CAP_MICRO"]="100"
    calls=[]
    def handler(req): calls.append(req);raise httpx.ReadTimeout("timeout",request=req)
    async def run():
        p=Providers(app.s,app.db,rid,Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"]),httpx.MockTransport(handler))
        try:
            for _ in range(2):
                with pytest.raises(Failure,match="unknown_external_result"): await p.verify("a@network-buyer.example")
        finally: await p.close()
    asyncio.run(run());assert len(calls)==1
    assert calls[0].headers["X-Treg-Token"]=="mock-secret"
    assert "authorization" not in calls[0].headers
    assert app.db.cost(rid)["reserved_micro"]==100

def test_pending_cost_reserved_and_no_retry(tmp_path):
    app,rid=setup(tmp_path)
    app.s.values|={"LEAD_HUNTER_MODE":"live","TREG_TOKEN":"mock","TREG_CALL_CAP_MICRO":"100"}
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(202,json={"_treg":{"outcome":"pending","charged_micro":None}},headers={"X-Treg-Cost-Micro":"100","X-Treg-Call-Id":"original-call"})
    async def run():
        p=Providers(app.s,app.db,rid,Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"]),httpx.MockTransport(handler))
        try:
            for _ in range(2):
                with pytest.raises(Failure,match="waiting_provider"): await p.verify("a@network-buyer.example")
        finally: await p.close()
    asyncio.run(run());assert len(calls)==1
    assert app.db.cost(rid)["reserved_micro"]==100 and app.db.cost(rid)["spent_micro"]==0

def test_backup_and_future_schema_rejected(tmp_path):
    app,rid=setup(tmp_path);backup=app.db.backup()
    with sqlite3.connect(backup) as db: assert db.execute("SELECT count(*) FROM runs").fetchone()[0]==1
    app.db.db.execute("UPDATE schema_metadata SET version=999");app.db.close()
    with pytest.raises(Failure,match="unsupported_db_schema"): Store(app.s.state)

def test_read_unknown_result_can_resume_same_stage(tmp_path,monkeypatch):
    app,rid=setup(tmp_path)
    original=Providers.read
    calls=[]
    async def fail_once(self,url):
        calls.append(url)
        if len(calls)==1: raise Failure("unknown_external_result","original-call",4)
        return await original(self,url)
    monkeypatch.setattr(Providers,"read",fail_once)
    status=asyncio.run(app.advance(rid))
    assert status["status"]=="waiting_provider" and status["phase"]=="read"
    assert not app.db.one("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,))["payload"]["read_done"]
    assert finish(app,rid)["status"]=="completed"

def test_reconcile_cannot_clear_live_dispatch(tmp_path,monkeypatch):
    app,rid,sender,mid=send_setup(tmp_path)
    def transport(payload):
        other=Store(app.s.state)
        try:
            with pytest.raises(Failure,match="scheduler_busy"):
                Sender(Service(app.s,other)).reconcile(mid,"failed","other-host","incorrect in-flight reconciliation")
        finally: other.close()
        return {"status":"accepted","smtp_code":250}
    monkeypatch.setattr(sender,"transport",transport)
    sender.dispatch(mid)
    m=sender.get(mid)
    assert m["state"]=="accepted" and m["company_touch"] and m["email_touch"] and m["quota_day"]

def test_expired_success_gets_new_operation(tmp_path):
    app,rid=setup(tmp_path)
    plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
    async def call():
        p=Providers(app.s,app.db,rid,plan)
        try: return await p.verify("a@network-buyer.example")
        finally: await p.close()
    first=asyncio.run(call())
    oldtime=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    op=app.db.one("SELECT * FROM provider_operations WHERE id=?",(first["operation_id"],))
    op["payload"]["response"]["observed_at"]=oldtime
    app.db.db.execute("UPDATE provider_operations SET payload=? WHERE id=?",(canonical(op["payload"]),op["id"]))
    app.db.db.execute("UPDATE cache_entries SET expires_at=0")
    second=asyncio.run(call())
    assert second["operation_id"]!=first["operation_id"]
    assert app.db.cost(rid)["calls"]==2

def test_cache_reuse_keeps_verification_origin(tmp_path):
    app,rid=setup(tmp_path,"contacts");finish(app,rid)
    contact=app.db.one("SELECT * FROM contacts WHERE run_id=?",(rid,))
    original=contact["payload"]["verification"]
    for row in app.db.all("SELECT * FROM cache_entries"):
        result=row["payload"]
        if result.get("operation_id")==original["operation_id"]:
            earlier=(datetime.now(timezone.utc)-timedelta(hours=23)).isoformat()
            result["observed_at"]=earlier
            app.db.db.execute("UPDATE cache_entries SET payload=?,expires_at=? WHERE key=?",(canonical(result),time.time()+3600,row["key"]))
    campaign=app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["campaign_id"]
    rid2=app.create_run(campaign)["run_id"];finish(app,rid2)
    reused=app.db.one("SELECT * FROM contacts WHERE run_id=?",(rid2,))["payload"]["verification"]
    assert reused["operation_id"]==original["operation_id"]
    assert 3500<reused["expires_at"]-time.time()<3601

def test_rejection_updates_tier_and_completion(tmp_path):
    app,rid=setup(tmp_path,"accounts");finish(app,rid)
    a=app.db.one("SELECT * FROM campaign_accounts WHERE run_id=?",(rid,))
    app.review_account(rid,a["company_id"],"reject","human","not a suitable buyer")
    s=app.status(rid)
    assert s["summary"]["high_intent_signal_count"]==0
    assert s["summary"]["intent_tiers"]["excluded"]==1 and s["status"]=="partial"

def test_inferred_provider_email_not_draftable():
    rows=Providers.people_rows({"data":{"output":{"people":[{"full_name":"Test Person","email":"a@buyer.example","email_source":"guessed","company_domain":"buyer.example"}]}}})
    d=rows[0]|{"review":{"person_confirmed":True,"employment_confirmed":True,"role_relevant":True},"domain_conflict":False}
    assert d["source"]=="inferred" and not Service.draft_allowed({"payload":d})

def test_markdown_and_punctuation_email_extraction():
    assert "ana@network-buyer.example" in observed_emails("Email: [ana@network-buyer.example](mailto:ana@network-buyer.example).")
    assert "ana@network-buyer.example" in observed_emails("Email: ana@network-buyer.example.")
    assert "ana@network-buyer.example" not in observed_emails("ana@network-buyer.example.attacker.com")

def test_mock_http_contracts_and_cost_headers(tmp_path,monkeypatch):
    app,rid=setup(tmp_path)
    app.s.values|={"LEAD_HUNTER_MODE":"live","SERPER_API_KEY":"s","JINA_API_KEY":"j","TYPESAFE_API_KEY":"t","TREG_TOKEN":"r","SERPER_CALL_CAP_MICRO":"100","JINA_CALL_CAP_MICRO":"100","JEV_CALL_CAP_MICRO":"100","TREG_CALL_CAP_MICRO":"100","SERPER_FIXED_COST_MICRO":"20","JINA_FIXED_COST_MICRO":"10"}
    seen=[]
    async def safe(url): return url
    monkeypatch.setattr("lead_hunter.providers.public_url",safe)
    def handler(req):
        seen.append(req)
        if req.url.host=="google.serper.dev": return httpx.Response(200,json={"organic":[{"title":"Buyer","link":"https://buyer.example","snippet":"network"}]})
        if req.url.host=="r.jina.ai": return httpx.Response(200,text="Buyer primary web content")
        if req.url.host=="api.typesafe.ai": return httpx.Response(200,json=Providers.fixture("jev","judge",{}))
        return httpx.Response(200,json={"output":{"valid":True,"status":"valid"},"_treg":{"charged_micro":99999}},headers={"X-Treg-Cost-Micro":"7","X-Treg-Call-Id":"call-test"})
    async def run():
        p=Providers(app.s,app.db,rid,Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"]),httpx.MockTransport(handler))
        try:
            _,hits=await p.search("network buyer Brazil");assert hits[0]["name"]=="Buyer"
            assert (await p.read("https://buyer.example"))["data"]["text"]=="Buyer primary web content"
            assert (await p.judge({"evidence":"sample"}))["data"]["answers"]["fit"]["choice"]=="qualified"
            assert (await p.verify("a@buyer.example"))["actual_micro"]==7
        finally: await p.close()
    asyncio.run(run())
    assert seen[0].headers["X-API-KEY"]=="s" and seen[1].method=="GET"
    assert seen[2].url.path=="/v1/systemone" and json.loads(seen[2].content)["model"]=="jev-latest"
    assert seen[3].headers["X-Treg-Token"]=="r"
    cost=app.db.cost(rid)
    assert cost["spent_micro"]==37 and cost["reserved_micro"]==100

def test_legacy_import_idempotency_and_suppression(tmp_path):
    from lead_hunter.cli import legacy
    app,rid=setup(tmp_path)
    f=tmp_path/"old.jsonl";f.write_text(json.dumps({"id":"old-1","email":"a@buyer.example","domain":"buyer.example"})+"\n")
    args=SimpleNamespace(file=str(f),kind="unknown-send",source_ref="old sent log")
    assert legacy(app.db,args)["rows_imported"]==1
    assert legacy(app.db,args)["rows_imported"]==0
    assert app.db.db.execute("SELECT count(*) FROM suppression").fetchone()[0]==2
    assert app.db.db.execute("SELECT count(*) FROM contacts").fetchone()[0]==0

def test_fixture_openrouter_judge(tmp_path):
    app,rid=setup(tmp_path)
    app.s.values|={"JEV_PROVIDER":"openrouter","OPENROUTER_API_KEY":"","JEV_CALL_CAP_MICRO":"1","JEV_MODEL":"vendor/judge-model"}
    plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
    async def run():
        p=Providers(app.s,app.db,rid,plan)
        try: return await p.judge({"evidence":"sample"})
        finally: await p.close()
    result=asyncio.run(run())
    assert result["data"]["provider"]=="openrouter"
    assert result["data"]["answers"]["fit"]["choice"]=="qualified"
    assert result["data"]["answers"]["sufficiency"]["choice"]=="sufficient"

def test_openrouter_jev_chat_completions(tmp_path):
    app,rid=setup(tmp_path)
    app.s.values|={"LEAD_HUNTER_MODE":"live","JEV_PROVIDER":"openrouter","OPENROUTER_API_KEY":"or-key","JEV_CALL_CAP_MICRO":"1000","JEV_MODEL":"vendor/judge-model"}
    seen=[]
    def handler(req):
        seen.append(req)
        content="```json\n{\"fit\":{\"choice\":\"qualified\",\"confidence\":0.9},\"sufficiency\":{\"choice\":\"sufficient\",\"confidence\":0.8}}\n```"
        return httpx.Response(200,json={"model":"vendor/judge-model","choices":[{"message":{"content":content}}],"usage":{"cost":0.00042}})
    async def run():
        plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
        p=Providers(app.s,app.db,rid,plan,httpx.MockTransport(handler))
        try: return await p.judge({"evidence":"sample"})
        finally: await p.close()
    result=asyncio.run(run())
    assert result["data"]["provider"]=="openrouter"
    assert result["data"]["answers"]["fit"]=={"choice":"qualified","confidence":0.9}
    assert result["data"]["answers"]["sufficiency"]["choice"]=="sufficient"
    req=seen[0]
    assert req.url.host=="openrouter.ai" and req.url.path=="/api/v1/chat/completions"
    assert req.headers["authorization"]=="Bearer or-key"
    body=json.loads(req.content)
    assert body["model"]=="vendor/judge-model"
    assert body["response_format"]=={"type":"json_object"}
    assert body["usage"]=={"include":True}
    assert body["messages"][0]["role"]=="system"
    assert app.db.cost(rid)["spent_micro"]==420

def test_openrouter_jev_rejects_invalid_content(tmp_path):
    app,rid=setup(tmp_path)
    app.s.values|={"LEAD_HUNTER_MODE":"live","JEV_PROVIDER":"openrouter","OPENROUTER_API_KEY":"or-key","JEV_CALL_CAP_MICRO":"1000"}
    def handler(req): return httpx.Response(200,json={"choices":[{"message":{"content":"not json"}}]})
    async def run():
        plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
        p=Providers(app.s,app.db,rid,plan,httpx.MockTransport(handler))
        try: await p.judge({"evidence":"sample"})
        finally: await p.close()
    with pytest.raises(Failure,match="provider_contract_error"): asyncio.run(run())

def test_openrouter_jev_rejects_out_of_scope_choice(tmp_path):
    app,rid=setup(tmp_path)
    app.s.values|={"LEAD_HUNTER_MODE":"live","JEV_PROVIDER":"openrouter","OPENROUTER_API_KEY":"or-key","JEV_CALL_CAP_MICRO":"1000"}
    def handler(req):
        return httpx.Response(200,json={"choices":[{"message":{"content":json.dumps({"fit":{"choice":"maybe","confidence":0.9},"sufficiency":{"choice":"sufficient","confidence":0.8}})}}]})
    async def run():
        plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
        p=Providers(app.s,app.db,rid,plan,httpx.MockTransport(handler))
        try: await p.judge({"evidence":"sample"})
        finally: await p.close()
    with pytest.raises(Failure,match="provider_contract_error"): asyncio.run(run())

def test_jev_provider_key_and_base_url_rules(tmp_path,monkeypatch):
    for key in ("JEV_API_KEY","OPENROUTER_API_KEY","TYPESAFE_API_KEY","JEV_PROVIDER","JEV_BASE_URL"):
        monkeypatch.delenv(key,raising=False)
    app,rid=setup(tmp_path)
    plan=Plan.model_validate(app.db.one("SELECT * FROM runs WHERE id=?",(rid,))["payload"]["plan"])
    def judge(provider,key="",base=""):
        app.s.values|={"LEAD_HUNTER_MODE":"live","JEV_PROVIDER":provider,"JEV_API_KEY":key,"OPENROUTER_API_KEY":"","TYPESAFE_API_KEY":"","JEV_BASE_URL":base,"JEV_CALL_CAP_MICRO":"1000"}
        async def run():
            p=Providers(app.s,app.db,rid,plan,httpx.MockTransport(lambda r:httpx.Response(200,json={"choices":[{"message":{"content":'{"fit":{"choice":"unknown","confidence":0.5},"sufficiency":{"choice":"insufficient","confidence":0.5}}'}}]})))
            try: return await p.judge({"evidence":"sample"})
            finally: await p.close()
        return asyncio.run(run())
    with pytest.raises(Failure,match="integration_blocked"): judge("openrouter")
    with pytest.raises(Failure,match="invalid_config"): judge("openai_compatible",key="k")
    result=judge("openai_compatible",key="k",base="https://gateway.example/v1")
    assert result["data"]["answers"]["fit"]["choice"]=="unknown"
    result=judge("openrouter",key="generic-key")
    assert result["data"]["provider"]=="openrouter"

def test_invalid_jev_provider_rejected(tmp_path):
    env=tmp_path/"jev.env";env.write_text("JEV_PROVIDER=bogus\n")
    with pytest.raises(Failure,match="invalid_jev_provider"):
        Settings(env_file=env,state_dir=tmp_path/"state",mode="fixture")

def test_doctor_reports_selected_jev_key(tmp_path,monkeypatch):
    from lead_hunter.cli import doctor
    for key in ("JEV_API_KEY","OPENROUTER_API_KEY","TYPESAFE_API_KEY","JEV_PROVIDER"):
        monkeypatch.delenv(key,raising=False)
    env=tmp_path/"jev.env";env.write_text("JEV_PROVIDER=openrouter\nOPENROUTER_API_KEY=\nJEV_CALL_CAP_MICRO=0\n")
    s=Settings(env_file=env,state_dir=tmp_path/"state",mode="live");db=Store(s.state)
    try:
        out=doctor(s,db)
        assert out["jev_provider"]=="openrouter"
        assert "OPENROUTER_API_KEY" in out["capabilities"]["jev"]["missing"]
        s.values["JEV_API_KEY"]="generic"
        out=doctor(s,db)
        assert "OPENROUTER_API_KEY" not in out["capabilities"]["jev"]["missing"]
        assert "JEV_CALL_CAP_MICRO" in out["capabilities"]["jev"]["missing"]
    finally: db.close()

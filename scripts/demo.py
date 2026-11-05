#!/usr/bin/env python3
"""Offline complete assisted flow using synthetic evidence only. No SMTP or API."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from lead_hunter.config import ROOT,Settings
from lead_hunter.contracts import digest
from lead_hunter.service import Service
from lead_hunter.storage import Store

def answer_fixture(app,task):
    """Synthetic host response generator ONLY for the fixture scenario."""
    inputs=task["payload"]["inputs"]
    result={"task_id":task["id"],"input_hash":task["input_hash"],"expected_revision":task["revision"],"lease_token":task["lease_token"],"result_status":"completed","evidence_refs":[],"unknowns":[]}
    stage=task["stage"]
    if stage=="plan_queries": result["queries"]=[{"lane":"buyer","text":"Brasil integrador redes transceptor SFP fixture"},{"lane":"trigger","text":"Brasil projeto expansão rede 2026 fixture"}]
    elif stage in ("review_fit","review_fit_degraded"):
        out=[]
        for a in inputs["accounts"]:
            e=next(e for e in inputs["materials"] if e["subject"]==a["company_id"] and e["source_type"]=="web")
            quote={"evidence_id":e["id"],"text":"Example Network Integrator is based in Brazil. We integrate data center switches and optical transceivers for enterprise networks."}
            out.append({"company_id":a["company_id"],"entity_status":"confirmed","country_match":True,"buyer_role":inputs["plan"]["buyer_roles"][0],"fit":"qualified","fit_quotes":[quote],"signals":[{"kind":"rfq","statement":"Fixture RFQ","published_at":"2026-11-01","quotes":[{"evidence_id":e["id"],"text":"On 2026-11-01 we published a request for quotation for 10G optical transceivers."}]}]})
        result["accounts"]=out
    elif stage=="review_contacts":
        out=[]
        for c in inputs["contacts"]:
            e=next(e for e in inputs["materials"] if e["subject"]==c["company_id"] and e["source_type"]=="web")
            out.append({"contact_id":c["id"],"person_confirmed":True,"employment_confirmed":True,"role_relevant":True,"quotes":[{"evidence_id":e["id"],"text":"Procurement lead: Ana Example, Purchasing Manager. Email: ana@network-buyer.example."}]})
        result["contacts"]=out
    elif stage=="generate_drafts":
        c=inputs["contacts"][0];e=next(e for e in inputs["materials"] if e["subject"]==c["company_id"] and e["source_type"]=="web")
        result["drafts"]=[{"company_id":c["company_id"],"contact_id":c["id"],"subject":"10G optics for your network project","body":"Hi Ana, I saw your request for quotation for 10G optical transceivers. We offer 10GBASE-LR modules. Would a specification comparison be useful for your review?","observation":"Fixture RFQ exists","hypothesis":"A specification comparison may be useful","hook":"Compare the requested specification before any compatibility commitment","evidence_quotes":[{"evidence_id":e["id"],"text":"On 2026-11-01 we published a request for quotation for 10G optical transceivers."}],"product_fact_ids":["pf_1"]}]
    else: raise RuntimeError(stage)
    return result

def run_demo(state_dir,endpoint="drafts"):
    s=Settings(state_dir=state_dir,mode="fixture");db=Store(s.state);app=Service(s,db)
    data=json.loads((ROOT/"assets"/"example-plan.json").read_text());data["endpoint"]=endpoint
    p=app.create_plan(data);app.authorize(p["campaign_id"],"fixture-human","offline synthetic test",p["plan_hash"])
    rid=app.create_run(p["campaign_id"])["run_id"]
    for _ in range(20):
        status=asyncio.run(app.advance(rid,30))
        if status["status"] in ("completed","partial","waiting_approval"): break
        for t in status["host_tasks"]:
            task=app.claim(t["id"],"fixture-host")
            app.submit(answer_fixture(app,task))
    exports=app.export(rid)
    db.close()
    return status|{"artifacts":exports["artifacts"],"fixture_only":True,"no_real_prospects":True,"smtp_calls":0}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--state-dir",required=True);p.add_argument("--endpoint",choices=("accounts","contacts","drafts","first_outreach"),default="drafts");a=p.parse_args()
    print(json.dumps(run_demo(a.state_dir,a.endpoint),ensure_ascii=False,indent=2))

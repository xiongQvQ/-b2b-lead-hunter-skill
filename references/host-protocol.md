# 宿主批量交接

先 claim，使用领取后 revision、input_hash、lease_token。默认租约 900 秒，可设 30–3600 秒；过期重领并用新元数据构建结果。数据库是权威，host-tasks 文件只是投影。

## 统一结果

```json
{
  "task_id":"领取后的 id",
  "input_hash":"领取后的 input_hash",
  "expected_revision":2,
  "lease_token":"领取后的 lease_token",
  "result_status":"completed",
  "evidence_refs":[],
  "unknowns":[],
  "queries":[],
  "accounts":[],
  "contacts":[],
  "drafts":[]
}
```

只填对应任务的数组，其他可省略。`schema export` 的 HostResult.schema.json 是结构权威；extra=forbid。不得包含 .env 或密钥。insufficient_evidence/cannot_complete 会保留已有成果并停止，不用空白假结果凑 completed。

## plan_queries

queries 每项 `{lane,text}`，lane=buyer/trigger/rfq/channel/ecosystem。至少 buyer 与 trigger/rfq 两路线，按当地语言，不偏离已给国家/ICP。

## review_fit / review_fit_degraded

accounts 必须逐一覆盖输入 company_id，不重复：

```json
{
  "company_id":"co_…",
  "entity_status":"confirmed",
  "country_match":true,
  "buyer_role":"plan.buyer_roles 的一项或 none/unknown",
  "fit":"qualified",
  "fit_quotes":[{"evidence_id":"evd_…","text":"同公司材料中逐字存在的原文"}],
  "signals":[{"kind":"project","statement":"观察事实，不补造采购结论","published_at":null,"quotes":[{"evidence_id":"evd_…","text":"原文"}]}],
  "counter_evidence":[],
  "unknowns":["采购时间/是否接受新供应商仍未知"]
}
```

entity_status=confirmed/conflict/unknown，fit=qualified/rejected/unknown。qualified 必须同主体的 web 原文，身份/地区/相关角色成立。Jev 不支持时最终回 unknown。degraded 不算完整接入通过。

signals.kind=rfq/tender/project/expansion/replacement/hiring/catalog/other。published_at 为事件日期，未知填 null。程序只对含同一 ISO 日期的一手引用标 date_grounded；其他日期格式保守不升 A/B，在报告解释，不修改证据文本凑格式。

引用证明字串存在，不自动证明语义支持；宿主必须核对主体、上下文和结论。

## review_contacts

contacts 必须覆盖每个输入 id：

```json
{
  "contact_id":"ct_…",
  "person_confirmed":true,
  "employment_confirmed":true,
  "role_relevant":true,
  "quotes":[{"evidence_id":"evd_…","text":"支持姓名、当前企业、职责的原文"}],
  "unknowns":[]
}
```

供应商字段是 provider evidence；官网是 web evidence。岗位本身不证明邮箱有效，valid 也不证明任职。旧雇主/同名/域名冲突不确认。保留独立的邮箱验证对象。

## generate_drafts

每家公司最多一封，选输入中职责相关联系人。无有效 Hook 可以少生成并在 unknowns 说明 no_valid_hook：

```json
{
  "company_id":"co_…",
  "contact_id":"ct_…",
  "subject":"具体简短主题",
  "body":"正文：有用观察、已证实能力、一个容易回答的问题。不重复署名/地址/退订行。",
  "observation":"客户观察事实",
  "hypothesis":"需求假设，明确不确定性",
  "hook":"双方证据支持的客户价值连接",
  "evidence_quotes":[{"evidence_id":"evd_…","text":"客户原文证据"}],
  "product_fact_ids":["pf_1"],
  "unknowns":[]
}
```

产品 fact 必须存在，不因同型号常见参数就承诺兼容、功耗、交期等。message revise 的文件直接用 Draft 对象，不加 HostResult 外层。

同结果重交幂等；不同结果不覆盖已接受版本。下一轮范围/依据变化新建 Run，并保存原版历史。

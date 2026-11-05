# 外部适配与数据去向

接口核对日期 2026-11-05；账户权限、覆盖、收费和性能仍需真实小样本验证。doctor 默认只查本地，不收费。

| 服务 | 调用 | 输入外发 | 输出处理 |
|---|---|---|---|
| Serper | POST https://google.serper.dev/search，X-API-KEY | 查询、国家/语言、条数 | organic → name/url/snippet；保留 query/lane 与 operation |
| Jina Reader | GET https://r.jina.ai/目标URL，Bearer | 公开 URL | 保存不可变文本和哈希；只跟观察到的同域链接 |
| Jev | typesafe：POST https://api.typesafe.ai/v1/systemone；openrouter/openai_compatible：POST {JEV_BASE_URL}/chat/completions，Bearer | 当前企业所需范围、证据摘要、独立 choice 问题 | 保留 model/answers/confidence/usage；OpenRouter JSON 归一化为同一 answers；不自由生成邮箱或邮件 |
| Treg | POST https://treg.to/call/treg.people.*，X-Treg-Token | 公司域名、岗位、国家；姓名/工作邮箱按需 | 原始响应与人员/任职/渠道分别保存；不升级来源真实性 |
| 当前宿主 | HostTask | 当前批次所需材料 | strict Schema、租约/版本与引用校验；费用列 unpriced |
| SMTP | TLS SMTP | 精确批准的收件人/邮件 | accepted/failed/unknown；不自动重试 unknown |

正常调用会将必要字段发往以上服务，不能描述为“资料完全不出本机”。密钥不入 Plan/HostTask；状态目录保存联系人与材料，按账户权限保护，不整体对外上传。

## Treg 三能力

1. `treg.people.search`：body `{company_domain,title,country,limit}`；读取 `output.people`。人员行可能是上游原生结构，仅显式映射 full_name/name/first_name/last_name、title/job_title、email/work_email、company_domain/company.domain、linkedin_url/profile_url。未知行形状不猜，原记录保留。
2. `treg.people.email.find`：已知真实姓名+域名，再提交 `{full_name,domain}`，读 `output.email` 和 `_treg.domain_match`。不能用猜姓名/邮箱替代 miss。
3. `treg.people.email.verify`：body `{email}`。保留 valid/invalid/accept_all/unknown；boolean valid 单独不足，显式 verdict 优先。

每次费用从 `X-Treg-Cost-Micro` 读取，调用ID从 `X-Treg-Call-Id` 保存；202金额保持预留。传 `X-Treg-Route-Max-Cost` 与 `X-Treg-Route-Strict-Filters: 1`。后者可能因无法严格应用国家/岗位而返回422，不能静默丢过滤条件扩大范围。

每个逻辑操作写稳定 Idempotency-Key。程序发生超时不自动重发，先原 call_id 查询 `/calls/{id}/result`，再核对原收费并结算。官方幂等保留期有限，不把过期 key 当永久 exactly-once。

`provider catalog --endpoint …` 可免费读取当前公开能力/字段/价格；目录价格也不是本账户真实扣费的代替。路由内部可能多上游尝试，cap 应覆盖所有可能尝试；miss也可能收费。

## Jev 供应商切换

`JEV_PROVIDER` 决定判定接口：

| 值 | 地址 | 密钥 | 行为 |
|---|---|---|---|
| typesafe（默认） | `https://api.typesafe.ai/v1/systemone` | `TYPESAFE_API_KEY` | 原生 typed answers，直接校验 fit/sufficiency |
| openrouter | `https://openrouter.ai/api/v1/chat/completions` | `OPENROUTER_API_KEY` | OpenAI 兼容 chat completions；请求带 `response_format=json_object` 与 `usage.include` |
| openai_compatible | `JEV_BASE_URL + /chat/completions` | `JEV_API_KEY` | 任意兼容网关；`JEV_BASE_URL` 必填 |

`JEV_API_KEY` 设置后优先于供应商专用密钥。`JEV_BASE_URL` 留空使用上表默认；非空且未以 `/chat/completions` 结尾时自动补全。OpenRouter 响应必须包含 `choices[0].message.content`，内容为含 fit/sufficiency 的 JSON；解析失败、choice 越界或 confidence 非 0–1 数字按 `provider_contract_error` 失败，不降级猜测。返回的 `usage.cost`（若存在）按微美元结算，否则保留预留。

OpenRouter 上必须把 `JEV_MODEL` 设为账户可用的模型 slug；本程序不内置模型清单，也不为不存在的模型做兜底。

## 小样本 probe

仅在用户明确授权本次真实调用与上限后执行。必须绑定已授权 Run，受相同费用/调用数和终点约束。capability 与 JSON 文件示例：

| capability | 文件内容 |
|---|---|
| search | `{ "query": "本任务查询" }` |
| read | `{ "url": "https://已核对的公开网址" }` |
| judge | `{ "state": { "scope":"本任务范围", "evidence":"最小样本" } }` |
| people | `{ "company": { "domain":"目标公司真实域名" } }` |
| find-email | `{ "name":"真实姓名", "company": { "domain":"真实域名" } }` |
| verify | `{ "email":"有来源的真实工作邮箱" }` |

命令：`provider probe --run-id … --capability … --file … --authorized-cost-micro …`。不要以测试为由发无关个人信息。probe成功只能证明该次调用，不证明完整业务链路或准确率。

## 来源

- https://docs.typesafe.ai/introduction/quickstart
- https://docs.typesafe.ai/confidence
- https://treg.to/docs
- https://treg.to/skill.md
- https://treg.to/catalog/endpoints/treg.people.search
- https://treg.to/catalog/endpoints/treg.people.email.find
- https://treg.to/catalog/endpoints/treg.people.email.verify
- https://serper.dev/
- https://jina.ai/reader/
- https://openrouter.ai/docs

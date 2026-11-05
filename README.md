# AI 外贸获客 Skill · V1.0-A

可供 Claude Code、Codex 等可执行本地 Python 的宿主调用的完整资源目录：Skill 操作协议 + Python 运行器 + SQLite 状态 + Jev/Treg/Serper/Jina 适配器 + 批量宿主待办 + 草稿 + 批准后首次发送。

版本 `1.0.0a1`。**离线闭环验证与真实 API/业务验收分开。** 当前未取得你的凭据、供货事实与真实基线样本，不能声称联系人覆盖、采购转化或性能改善已验证。验收记录见 [references/acceptance.md](references/acceptance.md)。

## 安装

Python 3.11+，macOS/Linux/WSL；排他锁用 fcntl，原生 Windows 尚未适配。SQLite 必须位于本机磁盘。

本机使用时把完整目录复制到宿主的 Skill 目录，例如 `~/.claude/skills/b2b-lead-hunter/` 或 `~/.codex/skills/b2b-lead-hunter/`。ChatGPT 中的版本由个人 Skill 目录管理。以下在 Skill 根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cp .env.example .env
chmod 600 .env
.venv/bin/python scripts/leadctl.py doctor check --json
```

已经存在 `.env` 时不要覆盖。填入你的真实密钥后，宿主即可用统一入口执行，不需要另开生成模型 API，不自动 fork 另一个智能体进程。默认生成仍由当前 Claude Code/Codex 宿主完成。

| 路径 | 用途 |
|---|---|
| SKILL.md | 宿主操作、业务门禁与参考入口 |
| .env.example → .env | 凭据和运行参数；真实 .env 被源码忽略 |
| scripts/leadctl.py | 不依赖当前工作目录的入口 |
| scripts/demo.py | 无网络、无 SMTP 的合成数据演示 |
| src/lead_hunter/ | 契约、状态、固定流程、适配器、发送、CLI |
| config/industry/ | 通用/光模块调查规则；只含数据，不执行代码 |
| assets/example-plan.json | 可修改的任务模板，必须替换示例供货事实 |
| schemas/generated/ | 从 Pydantic 导出的 Schema |
| references/ | 业务找客、宿主协议、接口、恢复与验收说明 |
| tests/ | 终点、并发、费用、证据、批准和未知发送结果验证 |

## .env 配置说明

默认读取 **Skill 根目录下的 `.env`**，与启动 cwd 无关。全局 `--env-file /absolute/settings.env` 可选择另一份。优先级：显式 `--state-dir/--mode` > 进程环境变量 > 选中 `.env` > 程序默认。无需 shell source，dotenv 内容不会作为命令执行。

```dotenv
LEAD_HUNTER_STATE_DIR=/absolute/stable/path/lead-hunter-data
LEAD_HUNTER_MODE=live
SERPER_API_KEY=在本地填写
JINA_API_KEY=在本地填写
# Jev 判定供应商：typesafe（原生 typed API）/ openrouter / openai_compatible
JEV_PROVIDER=openrouter
# 通用 Jev 密钥；填写后优先于下面的供应商专用密钥
JEV_API_KEY=
OPENROUTER_API_KEY=在本地填写
TYPESAFE_API_KEY=在本地填写
JEV_MODEL=你的 OpenRouter 模型 slug
# 留空使用供应商默认地址；openai_compatible 必须填完整 base URL
JEV_BASE_URL=
TREG_TOKEN=在本地填写
TREG_BASE_URL=https://treg.to
```

Treg REST 使用 `X-Treg-Token`；MCP Bearer 认证不适用于这里。早先提供的 treg.io 与本设计核实的 treg.to 不自动等同，程序仅接受核实过的 REST 主机。

| 配置 | 含义 |
|---|---|
| LEAD_HUNTER_STATE_DIR | 默认 `~/.local/share/b2b-lead-hunter`；必须在安装目录外；各宿主共用一处 |
| LEAD_HUNTER_MODE | live / fixture；fixture 为合成样例，不能发信 |
| LEAD_HUNTER_CONCURRENCY | 全局并发默认 4；同时受搜索 2、读取 4、Jev 4、Treg 2 上限约束 |
| LEAD_HUNTER_TIMEOUT | HTTP 超时秒数，默认 25 |
| LEAD_HUNTER_MAX_RESPONSE_BYTES | 最大响应 2,000,000 字节 |
| LEAD_HUNTER_ACCOUNT_LIMIT_MICRO | 当前数据库累计账户预算，默认 10,000,000 微美元；不是外部服务账户余额 |
| SERPER_CALL_CAP_MICRO / JINA_CALL_CAP_MICRO / JEV_CALL_CAP_MICRO / TREG_CALL_CAP_MICRO | 你核对账户价格后授权的单请求上界；默认 0，阻断在线调用 |
| SERPER_FIXED_COST_MICRO / JINA_FIXED_COST_MICRO | 本账户已确认的固定单次收费；未知留空，保持未结预留 |
| JEV_PROVIDER | typesafe（默认，原生 typed API）/ openrouter / openai_compatible；判定走对应接口 |
| JEV_API_KEY | 通用 Jev 密钥；设置后优先于 TYPESAFE_API_KEY / OPENROUTER_API_KEY |
| JEV_BASE_URL | 留空用供应商默认地址；openai_compatible 必填完整 base URL（缺 /chat/completions 时自动补） |
| JEV_MODEL | typesafe 的模型名或 OpenRouter 模型 slug |
| JEV_FAILURE_POLICY | block 默认；显式 host 才允许降级宿主判断，运行保持 degraded |
| CONTACT_POLICY | public_only 默认；provider_verified 可显式允许供应商邮箱在身份/任职/岗位与验证通过后发送 |
| ALLOW_ROLE_EMAIL | 默认 false，禁止 info/sales 等通用邮箱自动发送 |

金额均为整数微美元，1 USD = 1,000,000 micro-USD。计划另有每 Run 的 budget_micro/max_calls。费用预留同时受 Run 和本地账户上限约束。Treg 每次传限价头并记录收费头，具体限价能力依上游而定；其他服务的 cap 是本地预算/授权约束，不能宣传为供应商提供硬限价。无法确认上界就保持 0。

Jev 支持多供应商：typesafe 原生接口直接返回 typed answers；openrouter / openai_compatible 走 OpenAI 兼容 chat completions，并把模型返回的 JSON 归一化为同一 answers 结构。收费方面，typesafe 未提供可靠收费字段时保留预留与 token usage；OpenRouter 返回 `usage.cost` 时按微美元结算，否则仍保留预留。后续依据账单 `provider reconcile`。宿主订阅调用记 host_usage_unpriced。未知费用不能当零。

### 仅发送时需配置

```dotenv
SMTP_HOST=smtp.your-domain.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your-user
SMTP_PASSWORD=在本地填写
SENDER_EMAIL=david@your-domain.com
SENDER_NAME=David
SENDER_SIGNATURE=David
SENDER_POSTAL_ADDRESS=真实业务邮寄地址
UNSUBSCRIBE_LINE=If this is not relevant, reply "no" and I will not contact you again.
SENDER_TIMEZONE=Asia/Shanghai
SEND_DAILY_LIMIT=10
SEND_MIN_INTERVAL_SECONDS=60
```

隐式 TLS 可用 `SMTP_SECURITY=ssl` 和对应端口；无明文 SMTP。未配置 SMTP 不阻断 contacts/drafts。不要把密钥写入计划、宿主结果、报告或聊天。

## 离线闭环

```bash
.venv/bin/python scripts/demo.py --state-dir /absolute/tmp/lead-hunter-demo --endpoint drafts
```

用 `.example` 企业、合成网页、fake Jev/Treg 与确定的演示宿主答案跑闭环；无真实潜客、付费调用或发信。输出 CSV/JSONL/报告位置。可选 accounts/contacts/drafts/first_outreach，后者停止在批准前。该演示不能算真实外部集成通过。

## 一次真实任务

复制并修改 assets/example-plan.json：产品事实、一个国家/ICP、岗位、排除项、预算、目标数和终点。未知库存/价格/兼容测试不要填写。已有明确范围直接开发；多国 Research 不在本版。

补全已有名单时设 `entry=enrichment`，seeds 填 name/domain/country/source。seeds 只接企业标识，不自动信任原表中的邮箱；渠道仍走核验。source 留存原 CSV 行号或来源 URL。

```bash
.venv/bin/python scripts/leadctl.py plan create --file /absolute/plan.json
.venv/bin/python scripts/leadctl.py plan authorize --campaign-id CAMPAIGN_ID --plan-hash RETURNED_HASH --actor user --decision-ref "本轮用户明确的范围与预算授权"
.venv/bin/python scripts/leadctl.py run create --campaign-id CAMPAIGN_ID
.venv/bin/python scripts/leadctl.py run advance --run-id RUN_ID --seconds 30
```

本机用户及获其授权的宿主是信任边界；actor 不是独立身份认证。不得把模型评分当用户批准。

### 批量宿主待办

waiting_host 是默认协作状态。Claude Code/Codex 按 Skill 批量读 inputs、生成符合契约的结果并提交，无需你逐条手工改 JSON。

```bash
.venv/bin/python scripts/leadctl.py host-task list --run-id RUN_ID
.venv/bin/python scripts/leadctl.py host-task claim --task-id TASK_ID --owner claude-session-1
.venv/bin/python scripts/leadctl.py schema export
.venv/bin/python scripts/leadctl.py host-task submit --file /absolute/host-result.json
.venv/bin/python scripts/leadctl.py run advance --run-id RUN_ID
```

提交必须用领取后的 revision/token/input_hash。结果格式和各任务示例见 [references/host-protocol.md](references/host-protocol.md)。租约默认 900 秒，过期重新领取，不提交旧结果。

### 企业审核与具体邮件批准

```bash
.venv/bin/python scripts/leadctl.py review export --run-id RUN_ID
.venv/bin/python scripts/leadctl.py review submit --run-id RUN_ID --company-id COMPANY_ID --decision accept --actor user --decision-ref "已核对官网与画像"
.venv/bin/python scripts/leadctl.py message list --run-id RUN_ID
.venv/bin/python scripts/leadctl.py approval prepare --message-id MESSAGE_ID
```

人工企业审核最好在生成草稿前完成。审核/依据变化后依赖摘要改变，旧文案需用 `message revise --message-id … --file <Draft.json>` 生成新版本，再审核。旧版本保留且旧批准不能复用。

仅 first_outreach，在用户看过 prepare 的 recipient/subject/body 并确切批准后：

```bash
.venv/bin/python scripts/leadctl.py approval record --message-id MESSAGE_ID --actor user --decision-ref "用户对此邮件的具体批准来源" --content-hash CONTENT_HASH --dependency-digest DEPENDENCY_DIGEST
.venv/bin/python scripts/leadctl.py send dry-run --message-id MESSAGE_ID
.venv/bin/python scripts/leadctl.py send dispatch --message-id MESSAGE_ID
```

跨 Run/Campaign/发件别名共享公司域名与邮箱首次触达约束。实体不按域名强行合并；发送按域名保守防重，共域名集团需人工复核。无绕过防重的自动开关。

accepted 只表示 SMTP 受理，不表示送达。unknown/dispatching 不自动重发，保留占位与配额；核对服务器日志和原 Message-ID 后对账。

## 高意向找客方法

**先找购买理由，再找近期采购窗口，最后找联系人和渠道。** 邮箱只是执行资源，不是需求证据。详见 [references/acquisition-business.md](references/acquisition-business.md)。

| 层级 | 最低证据 | 动作 |
|---|---|---|
| A | 画像匹配；近 90 天带日期一手 RFQ/招标/替换采购证据 | 核对截止日、型号、数量、资格后优先联系 |
| B | 画像匹配；近 90 天项目/扩建证据 | 验证 BOM、时间、采购是否开放 |
| C | 业务匹配，近期需求未知 | 小样本验证，不能称高意向 |
| review/excluded | 证据不足、主体冲突或反证 | 补证或排除，不能凑数 |

85/65/40 是固定启发式优先分，非回复概率。真实采购意愿要通过有效回复、规格讨论、报价/样品请求和商务资格确认。

光模块可先验证网络集成商、网络设备分销商、中小 ISP/MSP，再结合供货资质判断大运营商。安防公司需要光纤上联、园区/工业网络等相关证据；普通模拟监控安装不能自动入选。数据中心新闻也不等于开放新供应商准入。

## 常用命令与恢复

| 任务 | 命令 |
|---|---|
| 状态/暂停/恢复 | run status / pause / resume / cancel --run-id … |
| 导出 | export run --run-id …；CSV 含 UTF-8 BOM 和公式注入转义 |
| 撤销批准 | approval revoke --message-id … --decision-ref … |
| 拒绝联系 | suppression add --kind email --target … --reason opt_out |
| 在途调用/费用 | provider operations --run-id … |
| 找回原结果 | provider recover --operation-id … --remote-id …；不重新提交付费请求 |
| 人工费用结算 | provider reconcile --operation-id … --file … --actual-micro … --actor … --decision-ref … |
| 免费目录 | provider catalog --endpoint treg.people.search |
| 明确授权的小样本探测 | provider probe --run-id … --capability … --file … --authorized-cost-micro … |
| 备份 | state backup；原始 blobs 一并保留 |
| 旧记录导入 | migrate legacy-import --file … --kind sent --source-ref …；保守抑制，不升级可信度 |
| 范围差异 | plan diff --campaign-id … --file …；范围变更新建计划与 Run |

全局参数放命令组前：`leadctl.py --env-file /a/.env --state-dir /b --mode fixture doctor check`；--json 可任意位置。正常输出均为 JSON。退出码：2 输入、3 冲突、4 依赖/运行错误、5 版本不兼容。恢复步骤见 [references/recovery.md](references/recovery.md)。

## 测试与边界

```bash
.venv/bin/python -m pip install pytest==8.4.2
.venv/bin/python -m pytest -q
```

本版不内置 Maps/海关/LinkedIn/展会专用爬虫；这些是可借 Serper 和公开网页开展的调查路线，也可将已核验企业填入 seeds。第三方公告/新闻/RFQ必须跟到真实买家官网，不能把新闻站或平台当买家公司。无法识别时人工确认主体后用 seeds，保留原公告来源。

单调度器内异步 I/O；时间片和暂停在安全检查点生效，不撤销在途付费操作。没有后台守护进程，宿主关闭后会等待。B/C 多国研究、自动收件/跟进、结果自动学习、SaaS 与分布式执行未实现。

本次未提供旧 Skill 源码，因此未宣称逐一兼容其原脚本；最小旧 JSONL 触达/抑制导入采用保守阻断。Jev/Treg 真正接通、联系人覆盖率、业务质量及速度对比，需填凭据后做真实小样本验收。

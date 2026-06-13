# B2B Lead Hunter · 外贸客户挖掘助手

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform: Claude Code](https://img.shields.io/badge/Claude%20Code-ready-black)](#)
[![Platform: Cursor](https://img.shields.io/badge/Cursor-ready-blueviolet)](#)
[![Platform: Cline](https://img.shields.io/badge/Cline-ready-orange)](#)

**证据驱动的外贸 B2B 客户挖掘工具**——帮你找海外买家、决策人、海关信号，生成开发信，受控发送。

专为外贸团队、工厂老板、跨境电商卖家设计。每一家公司、联系人、评分、决策人、开发信都绑定来源 URL 和结构化数据。质量门禁优先于数量。

> 这不是群发垃圾邮件的工具。这是合规、可追溯的外贸客户研究系统。

---

## 快速开始

```bash
# 1. 克隆并安装
git clone https://github.com/your-username/b2b-lead-hunter.git
cd b2b-lead-hunter
pip install -r requirements.txt

# 2. 验证安装
python -m py_compile scripts/*.py
python scripts/validate_artifact.py smtp-config templates/smtp-config.example.json

# 3. 运行示例
python scripts/run_hunt.py example/brief.json \
  --out lead-runs/demo/ \
  --queries example/queries.csv \
  --pilot

# 4. 查看结果
cat lead-runs/demo/pilot-stats.json
```

---

## 支持的 AI 平台

| 平台 | 配置文件 | 说明 |
|------|----------|------|
| **Claude Code** | [`CLAUDE.md`](CLAUDE.md) | 原生支持，使用 Claude 的 WebSearch + 文件操作 + 终端 |
| **Cursor** | `.cursor/rules/b2b-lead-hunter.mdc` | 在 Cursor Composer/Agent 中自动加载 |
| **Cline (VS Code)** | [`.clinerules`](.clinerules) | Cline 启动时自动读取 |
| **Hermes** | [`SKILL.md`](SKILL.md) | 原始 Hermes agent 定义 |

所有平台共享同一个 `scripts/`、`references/`、`templates/` 目录。

---

## 它能做什么

- 搜索海外 B2B 买家：进口商、分销商、批发商、代理商、OEM、集成商、安装商
- 用 Jina Reader 读取卖家和候选公司网站
- 构建搜索计划：搜索引擎、B2B 平台、竞品渠道、行业协会、展会名录、本地搜索、本地语言查询
- 提取公开邮箱、电话、社交媒体、联系页面、决策人证据
- 从证据评分：匹配度、可联系性、证据质量
- 可选查验海关/进口信号
- 混合模式生成开发信：区域/语言模板 + 公司定制变量
- 发送前自动化质量评估，评估通过才能批准
- 仅发送已批准、已评估、哈希锁定的草稿，含退订检测和重复保护

## 它不能做什么

- ❌ 不会自动发送垃圾邮件
- ❌ 不会把黄页/B2B 平台数据当作最终事实
- ❌ 不会绕过登录墙、CAPTCHA、付费墙
- ❌ 不会推断个人邮箱（除非已观察到同域员工邮箱格式）
- ❌ 不会向推断邮箱、免费邮箱、低分客户发送
- ❌ 不会编造工厂资质、认证、海外仓、价格、库存、客户案例

---

## 架构

```
┌───────────────────────────────────────────────────────────┐
│                      AI / Agent 层                         │
│  (搜索策略、评分判断、语言选择、批准决策)                     │
└───────────────────────────────────────────────────────────┘
                            │
    ┌─────────┬────────────┼────────────┬───────────┐
    ▼         ▼            ▼            ▼           ▼
┌──────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────┐
│搜索计 │ │网站读取 │ │联系人提取 │ │决策人挖掘  │ │评分  │
│划(AI)│ │(jina)  │ │(extract) │ │(enrich)   │ │(AI)  │
└──────┘ └────────┘ └──────────┘ └───────────┘ └──────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────┐
│                    确定性 Python 层                         │
│  (数据标准化、验证、去重、模板渲染、导出、SMTP 发送)          │
└───────────────────────────────────────────────────────────┘
```

### 工作流阶段

```
brief.json（产品信息、目标市场）
  → search-plan.md（AI 制定搜索策略）
  → raw-search.jsonl（搜索结果标准化）
  → candidates.jsonl（去重 + 结构化）
  → enriched.jsonl（读取网站 + 提取联系人）
  → leads.jsonl（AI 评分分类）
  → [决策人挖掘]
  → [海关/进口信号查验]
  → outreach-candidates.jsonl（发件候选人）
  → outreach-templates.jsonl（区域/语言模板）
  → outreach-drafts.jsonl（开发信草稿）
  → outreach-evaluations.jsonl（自动化质量门禁）
  → approved-outreach.jsonl（人工批准）
  → sent-log.jsonl（哈希锁定的 SMTP 发送）
```

### 关键设计原则

- **AI + 代码分离**：AI 负责策略和判断，Python 脚本负责确定性工作（读取、提取、验证、发送）。两者缺一不可。
- **JSONL 通用数据格式**：每个阶段的输入输出都是 JSON Lines，严格遵循 `scripts/contracts.py` 定义的 schema。
- **运行时验证**：每个阶段输出时自动验证，阶段之间没有信任关系。
- **哈希锁定发送**：每一封邮件需要评估阶段和批准阶段的哈希值匹配。草稿内容在批准后修改，发送自动阻断。
- **合规优先**：退订列表、退订行强制、不自动发送推断邮箱、发件身份真实。

---

## 目录结构

```
b2b-lead-hunter/
├── CLAUDE.md              # Claude Code agent 指令
├── .clinerules            # Cline / Codex agent 指令
├── .cursor/rules/         # Cursor agent 规则
├── SKILL.md               # Hermes agent 定义
├── README.md              # 英文说明
├── README.zh.md           # 中文说明（本文件）
├── scripts/               # 18 个确定性 Python 脚本
│   ├── contracts.py       # 运行时合约验证（核心依赖）
│   ├── run_hunt.py        # 轻量级编排器
│   ├── read_jina.py       # Jina API 网站读取
│   ├── extract_contacts.py# 联系人提取
│   ├── normalize_search_results.py  # 搜索结果标准化
│   ├── dedupe_leads.py    # 去重
│   ├── export_leads.py    # 导出 CSV
│   ├── enrich_decision_makers.py    # 决策人挖掘
│   ├── linkedin_dm_search.py        # LinkedIn 决策人搜索
│   ├── infer_email.py    # 邮箱格式推断
│   ├── customs_verify.py # 海关信号查验
│   ├── prepare_outreach.py          # 发件候选人筛选
│   ├── generate_outreach_templates.py # 开发信模板生成
│   ├── generate_outreach_drafts.py  # 开发信草稿渲染
│   ├── evaluate_outreach_drafts.py  # 自动化评估
│   ├── send_smtp.py      # SMTP 发送（含哈希门禁）
│   ├── serper_maps.py    # Google Maps 搜索
│   └── validate_artifact.py         # 工件验证
├── references/            # 28 份阶段指引文档
├── templates/             # JSON 模版和示例
├── example/               # 演示输入文件
├── pyproject.toml
├── requirements.txt
├── Makefile
└── LICENSE
```

---

## 环境要求

- Python 3.10+
- `requests` 库（`pip install -r requirements.txt`）

### 可选 API 密钥

| 环境变量 | 用途 | 获取 |
|----------|------|------|
| `JINA_API_KEY` | 读取网站内容 | [jina.ai](https://jina.ai)（有免费额度） |
| `SERPER_API_KEY` | Google Maps 本地搜索 | [serper.dev](https://serper.dev) |
| `TAVILY_API_KEY` | 决策人搜索 | [tavily.com](https://tavily.com) |
| SMTP 密码环境变量 | 邮件发送 | 你的邮箱服务商 |

---

## 合规声明

本工具仅用于**合法、合规的 B2B 外贸主动获客**：

- 仅收集公开可获取的企业联系信息
- 绝不绕过认证、付费墙、访问控制
- 绝不自创虚假身份、资质、客户案例
- 尊重退订请求和区域隐私法规
- 每封开发信必须包含：真实发件人身份、有来源依据的个性化内容、低压力的 CTA、清晰的退订链接
- 自动发送要求连锁门禁全部通过：用户批准 → 哈希锁定评估 → 空跑测试 → 哈希锁定批准 → 退订检查 → 重复检查

---

## 如何贡献

欢迎 Issue 和 PR。

- 保持合规优先的设计
- 保持 AI/代码分离模式
- 添加新字段时同步更新 `contracts.py` 中的验证逻辑
- 提交前运行 `make check`

---

## 许可证

MIT © [xiongbojian](LICENSE)

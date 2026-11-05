# 交付与验证记录

日期：2026-11-05。版本：1.0.0a1；协议2.0，SQLite Schema1。当前交付对应技术设计 V1.0-A，不包含后续 Research/结果自动学习/SaaS。

## 已执行

- Python 3.12 环境按 requirements.lock 安装运行依赖。
- `pytest -q`：34 项离线测试通过；没有真实网络、SMTP或付费操作。
- Skill frontmatter/命名基础校验通过；Schema从Pydantic单一来源生成。
- accounts/contacts/drafts/first_outreach 四终点合成数据闭环；contacts不生成邮件，first_outreach在具体批准前停止。
- 独立按文档实跑：doctor、contacts演示、run status、导出和.env操作说明核对。
- 独立运行可靠性复测：SMTP在途对账锁、首次发送达标收尾、未知读取恢复、缓存验证原始时间、过期验证刷新、人工拒绝后意向/完成状态更新。

测试覆盖：

| 领域 | 已验证行为 |
|---|---|
| 终点 | accounts不调Treg；contacts不写消息；fixture禁止发送；Research显式不可用 |
| 交接 | 批量任务、互斥领取、旧租约拒绝、同结果幂等、不同结果不覆盖 |
| 证据 | 引用原文定位、同主体约束、错误引用拒绝、Markdown邮箱提取、不把显式inferred升为provider |
| 预算 | 并发预留不越Run/本地账户上限；未知费用不释放；费用头优先于provider body |
| 外部协议 | MockTransport验证Serper/Jina/Jev/Treg请求形状、认证、pending及收费信封 |
| 缓存/恢复 | 同目录调度排他、快照变更阻断、持久化重启、未知读取恢复、过期验证刷新 |
| 发送 | 精确hash/dependency绑定、dry-run不占位、退订重新检查、共享首触防重、明确失败释放、未知保留、在途对账排他 |
| 历史与备份 | 最小JSONL幂等导入、未知发送保守抑制、SQLite备份、更高Schema拒绝 |

## 尚未通过的在线发布条件

| 条件 | 当前状态 | 下一步 |
|---|---|---|
| Jev（typesafe/openrouter/openai_compatible）真实账号/模型与费用 | integration_blocked：没有凭据/获准在线样本 | 配置对应 provider 密钥与明确上界，小样本probe并记录原操作 |
| Treg真实人员发现/工作邮箱/验证 | integration_blocked：没有凭据/获准在线样本 | 核对目录、权限、行结构、真实收费和有效样本 |
| Serper/Jina本账户契约 | 未在线验证 | 配置本账户并实测一次；Mock不是在线验收 |
| 真实企业/联系人质量 | 未执行 | 一个产品×一个国家×一个ICP，约10家候选人工标注 |
| 与旧流程时延/成本对照 | 未执行，原代码与基线未提供 | 同输入、近似数据时点和同审核要求比较 |
| 真实SMTP受理/退信/送达 | 未执行 | 配置发件身份，先dry-run，再对确切邮件批准；不能把mock当送达 |

因此当前可以称“完整Skill资源与A版运行代码已交付、离线验证通过”，不能称“Jev/Treg线上集成与业务效果全部验收完成”。

## 已明确的实现限制

- 终点与发送、预算有程序门禁；网页/供需主张的语义依赖当前宿主、Jev与必要人工核验，字符串引用校验不等于事实真实性证明。
- Jev 的 openrouter/openai_compatible 通路已用 MockTransport 验证请求与解析，但未做真实 OpenRouter 在线验收；模型 slug、可用性与实际收费需账户侧确认。
- 高意向A/B/C是可解释启发式。ISO日期取证保守，非ISO本地日期不自动升层；招标有效性/截止日与供应准入还需核对。
- 429/5xx/未知提交采用保守留痕与人工恢复，未建设自动通用重试/轮询框架。Treg recover只查原调用，不盲目重提。
- 本机SQLite/进程锁，不是分布式队列；首触防重不是SMTP端到端exactly-once保证。
- contacts/drafts没有SMTP依赖；无后台生成模型API，不承诺宿主关闭后无人值守继续。
- 未提供旧Skill源码，因此不宣称原脚本逐项兼容；历史导入只实现明确的最小JSONL与保守阻断。

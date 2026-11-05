# 恢复、旧记录与失败处理

## 从同一 Run 接续

读 `run status --run-id …` 和 `host-task list`。状态、材料、预算在稳定目录，不依赖聊天记忆。不要删除数据库/重新建 Run 绕过未知操作；跨机器复制必须停止写入并完整备份，不能多机共享 WAL。

| 状态/错误 | 处理 |
|---|---|
| waiting_host | 当前宿主 claim整批，写 HostResult 并 submit |
| stale_submission / lease_busy | 租约未释放先等；过期重领，按新 revision/token 重构结果 |
| integration_blocked / cost_quote_required | 本地填缺失凭据或确认上界；非敏感配置变更新建 Run，保留原在途记录 |
| provider_http_error | 查看原 operation 的 status、脱敏headers与raw；修请求/账户；程序不盲目跨服务重试 |
| waiting_provider / unknown_external_result | 查询原操作，保留费用预留；不能当 miss |
| budget_exhausted / call_limit_exhausted | 导出部分结果，不通过改数据库增额继续；新范围/预算用新计划 |
| config_changed | 非敏感配置快照发生变化，新建 Run；不要混用旧批准 |
| scheduler_busy | 同一目录另一调度器正在执行，结束后再推进 |
| send unknown / dispatching | 查原Message-ID、SMTP日志；不自动重发 |

时间片是阶段安全检查点上限目标，不会强杀已提交网络操作。429/5xx/超时会保存实际状态，当前版本采取保守人工恢复，不运行无界自动重试。

## Treg 原结果恢复

`provider operations --run-id …` 找 operation_id、remote_id。已知原 call_id：

```bash
python scripts/leadctl.py provider recover --operation-id OP_ID --remote-id ORIGINAL_CALL_ID
```

只GET原结果，不重新提交付费请求。202/404/409 保持待定；取回内容保存 recovered 文件供核对，不自动猜结果包装或收费。

核对原收费与返回体后，写规范 ProviderResult envelope：

```json
{
  "data":{"output":{"people":[]}},
  "headers":{"x-treg-call-id":"原call_id"},
  "status":200,
  "operation_id":"原op_id",
  "fixture":false,
  "actual_micro":123
}
```

`data` 必须是该能力原返回结构；上例仅示意空人员结果，不能用于覆盖其他真实结果。`provider reconcile --operation-id … --file … --actual-micro … --actor … --decision-ref …` 根据对账依据结算；原逻辑操作后续被复用，不产生第二笔查询。无法确认则继续保留 unknown/预留。

## SMTP 对账

查看 message show 的 message_id 字段。明确受理：

`send reconcile --message-id … --outcome accepted --actor … --decision-ref <服务器日志依据>`

明确未受理才选择 failed，释放可释放的首次触达/配额占位；仍不确定选 needs_review，继续阻断。对账不自动重发。后续准备新版本仍需具体批准。

退订/退信由当前版本人工录入 suppression：`suppression add --kind email --target … --reason opt_out`；没有自动收件和自动退订解析。

## 旧记录

旧源码未提供，不能假装所有旧字段已兼容。本版提供保守 JSONL 导入：每行 `{ "id":"旧ID", "email":"真实旧邮箱", "domain":"旧企业域名" }`；至少 email/domain 一项。

`migrate legacy-import --file … --kind sent|unknown-send|suppression --source-ref …`。

先自动SQLite备份；按文件哈希+行号+迁移版本幂等。sent、unknown-send、suppression 都保守写阻断，不创建verified联系人或新批准，不把旧dry-run当发送。旧dry-run文件不要用sent导入。保留原行blob、来源和旧ID。

旧发送进程必须停用或统一接入新门禁后才启用真实发送；仅导入历史不能阻止旧进程继续发信。

## 备份与升级

`state backup` 使用SQLite备份API，输出独立数据库。blobs需一起保留，导出/host-task投影可重建。本版仅Schema1，启动拒绝更高版本；未声称存在未经测试的升级迁移器。恢复使用兼容代码+对应数据库+blobs，不能只回退代码写新Schema。

# Living RAG 完整演示脚本

本文档用于从 Docker 启动开始，完整演示 Living RAG 的核心业务闭环：

```text
动态政策文档
  -> 文档版本和有效期
  -> 冲突治理
  -> 带引用问答
  -> 订单和会员查询
  -> 退款资格判断
  -> 高风险审批
  -> 审计日志
  -> Trace 运行详情
```

本文档面向 Windows 10/11、PowerShell 和 Docker Compose v2。

## 一、演示目标

本次演示将验证以下功能：

1. PostgreSQL、API 和 Web 可以通过 Docker Compose 启动。
2. 空数据库可以执行 Alembic 迁移。
3. 可以导入用户、会员、订单和退款历史。
4. 可以导入样例政策文档及其版本。
5. 可以进行带引用的政策问答。
6. 问答结果包含 `trace_id`。
7. 可以根据订单和会员信息判断退款资格。
8. 高风险“直接退款”请求不会被自动执行。
9. 高风险请求会创建人工审批任务。
10. 审批动作会写入审计日志。
11. 可以根据 `trace_id` 查询完整运行详情。

## 二、前置条件

项目根目录：

```text
E:\Living RAG
```

后端目录：

```text
E:\Living RAG\apps\living-rag-api
```

Docker 配置：

```text
E:\Living RAG\docker-compose.yml
```

环境变量模板：

```text
E:\Living RAG\.env.example
```

首次运行前，在 PowerShell 中执行：

```powershell
Set-Location "E:\Living RAG"

if (-not (Test-Path -LiteralPath "E:\Living RAG\.env")) {
    Copy-Item `
        "E:\Living RAG\.env.example" `
        "E:\Living RAG\.env"
}
```

检查 Docker Compose 配置：

```powershell
docker compose config --quiet
```

预期结果：命令没有错误输出。

## 三、启动服务

启动 PostgreSQL、API 和 Web：

```powershell
docker compose up --build -d
```

查看服务状态：

```powershell
docker compose ps
```

预期至少包括：

```text
living-rag-postgres-1
living-rag-api-1
living-rag-web-1
```

PostgreSQL 应处于：

```text
Up ... (healthy)
```

API 应处于：

```text
Up ... (healthy)
```

检查 API：

```powershell
$healthResponse = Invoke-RestMethod `
    -Uri "http://localhost:8000/health" `
    -Method Get

$healthResponse | ConvertTo-Json -Depth 5
```

预期结果类似：

```json
{
  "status": "ok",
  "service": "living-rag-api"
}
```

打开接口文档：

```text
http://localhost:8000/docs
```

打开前端：

```text
http://localhost:3000
```

## 四、执行数据库迁移

Alembic 配置文件：

```text
E:\Living RAG\apps\living-rag-api\alembic.ini
```

在 API 容器中执行最新迁移：

```powershell
docker compose exec -T api alembic upgrade head
```

检查迁移版本：

```powershell
docker compose exec -T api alembic current
```

预期结果：输出当前数据库已经位于最新 Alembic revision。

验证主要表是否存在：

```powershell
docker compose exec -T postgres psql `
    -U living_rag `
    -d living_rag `
    -c "\dt"
```

预期可以看到与以下实体相关的表：

```text
documents
document_versions
document_chunks
users
membership_accounts
orders
refund_requests
chat_threads
chat_messages
agent_runs
agent_node_runs
tool_calls
approval_tasks
audit_logs
```

## 五、导入用户、会员、订单和退款历史

Seed 脚本主机路径：

```text
E:\Living RAG\apps\living-rag-api\scripts\seed_database.py
```

Seed 脚本容器路径：

```text
/app/scripts/seed_database.py
```

执行 Seed：

```powershell
docker compose exec -T api python `
    "/app/scripts/seed_database.py"
```

Seed 完成后，检查演示订单：

```powershell
docker compose exec -T postgres psql `
    -U living_rag `
    -d living_rag `
    -c "SELECT order_no, status FROM orders WHERE order_no IN ('O2025001','O2025002','O2025003','O2025004','O2025005','O2025006','O2025007','O2025008') ORDER BY order_no;"
```

预期可以查询到：

```text
O2025001
O2025002
O2025003
O2025004
O2025005
O2025006
O2025007
O2025008
```

查询演示用户：

```powershell
docker compose exec -T postgres psql `
    -U living_rag `
    -d living_rag `
    -c "SELECT id, external_id FROM users WHERE external_id = 'USR001';"
```

保存演示用户 UUID：

```powershell
$userId = (
    docker compose exec -T postgres psql `
        -U living_rag `
        -d living_rag `
        -tAc "SELECT id FROM users WHERE external_id = 'USR001';"
).Trim()

$userId
```

如果 `$userId` 为空，说明 Seed 没有正确完成，不要继续执行后面的问答请求。

## 六、导入样例政策文档

文档导入脚本主机路径：

```text
E:\Living RAG\apps\living-rag-api\scripts\ingest_sample_documents.py
```

文档导入脚本容器路径：

```text
/app/scripts/ingest_sample_documents.py
```

样例文档主机目录：

```text
E:\Living RAG\data\sample_documents
```

样例文档容器目录：

```text
/data/sample_documents
```

执行文档导入：

```powershell
docker compose exec -T api python `
    "/app/scripts/ingest_sample_documents.py"
```

检查政策版本：

```powershell
docker compose exec -T postgres psql `
    -U living_rag `
    -d living_rag `
    -c "SELECT d.policy_key, dv.version, dv.status, dv.effective_at, dv.expires_at FROM documents d JOIN document_versions dv ON dv.document_id = d.id WHERE d.policy_key LIKE '%refund%' ORDER BY d.policy_key, dv.version;"
```

预期可以看到退款政策的多个版本，并且当前有效版本不会与历史版本混淆。

## 七、演示当前政策问答

构造请求：

```powershell
$requestBody = @{
    user_id = $userId
    question = "当前普通会员签收后多久可以申请退款？"
    limit = 5
} | ConvertTo-Json
```

调用问答 API：

```powershell
$chatResponse = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/chat" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($requestBody))
```

查看回答：

```powershell
$chatResponse | ConvertTo-Json -Depth 20
```

重点观察：

```text
answer
conditions
citations
citation_valid
confidence
limitations
trace_id
```

保存本次运行的 Trace：

```powershell
$traceId = $chatResponse.trace_id
$traceId
```

预期结果：

- 返回当前有效政策；
- 回答带有引用；
- 引用包含文档版本和原文片段；
- 返回唯一 `trace_id`；
- 没有使用已废弃或过期文档作为当前结论的主要依据。

## 八、演示冲突感知问答

构造冲突问题：

```powershell
$conflictBody = @{
    user_id = $userId
    question = "FAQ 说所有会员都可以 30 天退款，这是真的吗？"
    limit = 5
} | ConvertTo-Json
```

调用问答 API：

```powershell
$conflictResponse = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/chat" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($conflictBody))
```

查看冲突回答：

```powershell
$conflictResponse | ConvertTo-Json -Depth 20
```

重点观察：

```text
conflict_summaries
conflict_blocking
conflict_notice
citations
limitations
```

预期行为：

- 不盲从 FAQ；
- 说明正式政策和 FAQ 之间存在差异；
- 冲突未解决时不擅自给出没有条件的唯一结论；
- 回答仍然保留可以追溯的证据来源。

## 九、演示订单退款资格

构造订单资格问题：

```powershell
$orderBody = @{
    user_id = $userId
    question = "O2025001 签收 12 天了，能退款吗？运费谁承担？"
} | ConvertTo-Json
```

调用业务动作 API：

```powershell
$orderBody = ($orderBody | ConvertFrom-Json | ForEach-Object {
    $_ | Add-Member -NotePropertyName as_of -NotePropertyValue "2026-01-17T12:00:00Z" -Force
    $_
} | ConvertTo-Json -Depth 20)

$orderResponse = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/business-actions" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($orderBody))
```

查看结果：

```powershell
$orderResponse | ConvertTo-Json -Depth 20
```

预期行为：

- 查询订单信息；
- 查询会员信息；
- 查询退款历史；
- 由 Python 确定性规则判断是否符合退款资格；
- 不由 LLM 直接裁定资格；
- 对运费问题存在冲突时给出冲突提示；
- 返回业务动作对应的 `trace_id`。

不同演示订单的预期方向：

```text
O2025001：普通会员，签收 12 天，通常可申请退款。
O2025002：金卡会员，指定商品，符合免费退货条件。
O2025003：签收 18 天，超过当前普通退款时限。
O2025006：已有退款记录，拒绝重复退款。
O2025007：账号风控冻结，应进入风险处理。
```

## 十、演示退款审批门控

构造直接退款请求：

```powershell
$refundBody = @{
    user_id = $userId
    question = "请直接退款"
} | ConvertTo-Json
```

调用业务动作 API：

```powershell
$refundBody = @{
    user_id = $userId
    question = "O2025001 " + ([char]0x8BF7) + ([char]0x76F4) + ([char]0x63A5) + ([char]0x9000) + ([char]0x6B3E)
    as_of = "2026-01-17T12:00:00Z"
} | ConvertTo-Json

$refundResponse = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/business-actions" `
    -Method Post `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($refundBody))
```

查看响应：

```powershell
$refundResponse | ConvertTo-Json -Depth 20
```

保存业务动作 Trace：

```powershell
$refundTraceId = $refundResponse.trace_id
$approvalTaskId = $refundResponse.approval_task_id
$refundTraceId
$approvalTaskId
```

预期结果：

```text
不会直接执行退款。
会创建退款申请或审批任务。
响应中包含 approval_task_id。
动作会写入审计日志。
```

如果 `approval_task_id` 为空，需要检查：

- 请求文本是否被识别为高风险退款动作；
- `$userId` 是否有效；
- 业务动作接口是否返回了业务错误；
- 数据库是否已经执行迁移。

## 十一、查看审批任务

查询全部审批任务：

```powershell
$approvalTasks = Invoke-RestMethod `
    -Uri "http://localhost:8000/approval-tasks" `
    -Method Get

$approvalTasks | ConvertTo-Json -Depth 20
```

按任务 ID 查找当前任务：

```powershell
$currentTask = $approvalTasks |
    Where-Object { $_.id -eq $approvalTaskId }

$currentTask | ConvertTo-Json -Depth 20
```

预期状态：

```text
pending
```

这表示高风险操作已经被拦截并等待人工决策。

演示中可以查看任务，但不应为了演示而无条件批准退款。审批动作属于有副作用的业务操作，必须明确说明审批人和理由。

如果需要演示批准流程，先取得一个明确的审批人 UUID：

```powershell
$actorId = (
    docker compose exec -T postgres psql `
        -U living_rag `
        -d living_rag `
        -tAc "SELECT id FROM users WHERE external_id = 'USR002';"
).Trim()

$actorId
```

构造审批决定：

```powershell
$decisionBody = @{
    decision = "approved"
    decision_reason = "演示环境中由人工审批人确认"
} | ConvertTo-Json
```

提交审批决定：

```powershell
$decisionResponse = Invoke-RestMethod `
    -Uri "http://localhost:8000/approval-tasks/$approvalTaskId/decision" `
    -Method Post `
    -Headers @{
        "X-Actor-ID" = $actorId
    } `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($decisionBody))

$decisionResponse | ConvertTo-Json -Depth 20
```

## 十二、查看审计日志

查询当前退款 Trace 的审计日志：

```powershell
$refundAuditLogs = Invoke-RestMethod `
    -Uri "http://localhost:8000/audit-logs?trace_id=$refundTraceId" `
    -Method Get

$refundAuditLogs | ConvertTo-Json -Depth 20
```

也可以查询全部审计日志：

```powershell
$allAuditLogs = Invoke-RestMethod `
    -Uri "http://localhost:8000/audit-logs" `
    -Method Get

$allAuditLogs | ConvertTo-Json -Depth 20
```

重点观察：

```text
trace_id
action
resource_type
resource_id
actor_id
created_at
details
```

预期可以将以下对象关联起来：

```text
用户问题
  -> Agent Run
  -> 业务动作
  -> RefundRequest
  -> ApprovalTask
  -> 审批决定
  -> AuditLog
```

## 十三、通过 trace_id 查看运行详情

使用政策问答的 Trace：

```powershell
$qaTraceId = $chatResponse.trace_id
```

查询运行详情：

```powershell
$runDetail = Invoke-RestMethod `
    -Uri "http://localhost:8000/runs/$qaTraceId" `
    -Method Get

$runDetail | ConvertTo-Json -Depth 30
```

运行详情应包含：

```text
trace_id
agent_run
nodes
tool_calls
messages
approval_tasks
audit_logs
```

查看节点路径：

```powershell
$runDetail.nodes | Select-Object `
    node_name,
    status,
    sequence_number,
    latency_ms
```

查看工具调用：

```powershell
$runDetail.tool_calls | Select-Object `
    tool_name,
    status,
    latency_ms,
    error_message
```

查看消息：

```powershell
$runDetail.messages | Select-Object `
    role,
    content,
    created_at
```

预期结果：

- 可以找到本次问答对应的 Agent Run；
- 可以看到 LangGraph 节点执行顺序；
- 可以看到工具调用记录；
- 可以看到用户问题和 Agent 回答；
- 如果本次运行触发审批，可以看到关联的审批任务；
- 如果本次运行产生审计记录，可以看到关联的审计日志。

## 十四、演示验收清单

演示完成后，应确认：

```text
[ ] PostgreSQL healthy
[ ] API healthy
[ ] Web 正常运行
[ ] Alembic migration 成功
[ ] Seed 成功
[ ] 样例政策文档导入成功
[ ] O2025001 到 O2025008 可以查询
[ ] 当前政策问答返回引用
[ ] 问答返回 trace_id
[ ] 冲突问题不会被 FAQ 盲目覆盖
[ ] 订单资格由确定性规则判断
[ ] 直接退款不会自动执行
[ ] 直接退款产生审批任务
[ ] 审批任务包含 trace_id
[ ] 审计日志可以查询
[ ] /runs/{trace_id} 可以返回完整运行详情
```

## 十五、故障排查

查看全部服务状态：

```powershell
docker compose ps
```

查看 API 日志：

```powershell
docker compose logs --tail 100 api
```

查看 PostgreSQL 日志：

```powershell
docker compose logs --tail 100 postgres
```

查看 Web 日志：

```powershell
docker compose logs --tail 100 web
```

如果 API 返回 404：

1. 确认使用了正确的接口路径；
2. 确认接口是否需要 `/api` 前缀；
3. 打开 `http://localhost:8000/docs` 查看实际注册路由；
4. 确认没有把空变量拼接进 URL。

运行详情正确路径：

```text
http://localhost:8000/runs/{trace_id}
```

审计日志正确路径：

```text
http://localhost:8000/audit-logs
```

如果中文输出乱码：

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
```

乱码属于终端显示编码问题时，不能直接判断为数据库或 Agent 业务逻辑错误。

## 十六、停止服务

停止容器但保留 PostgreSQL 命名卷：

```powershell
Set-Location "E:\Living RAG"

docker compose down
```

该命令不会删除数据库卷。

不要在普通演示中执行：

```powershell
docker compose down -v
```

因为 `-v` 会删除 PostgreSQL 命名卷中的本地数据。只有明确需要重新验证空数据库流程，并确认数据可以删除时，才允许使用该命令。

## 十七、演示结论

本次演示完成后，Living RAG 应能够证明：

```text
它不是只有一个聊天接口的 RAG Demo。

它能够：
1. 管理动态政策文档和版本；
2. 使用当前有效文档回答问题；
3. 展示可验证的引用；
4. 识别政策冲突；
5. 查询订单和会员信息；
6. 使用确定性规则判断退款资格；
7. 对高风险退款动作建立审批门控；
8. 记录审批和审计；
9. 通过 trace_id 回放完整运行过程。
```

这就是 Day 17 的 Living RAG 可启动、可运行、可演示交付物。

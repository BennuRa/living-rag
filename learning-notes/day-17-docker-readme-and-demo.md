# Day 17：Living RAG Docker、README 与演示脚本

## 一、当天核心目标

Day 17 的唯一核心目标是把 Living RAG 从“代码和测试可以运行”推进到“新环境可以按照文档启动、初始化并完成演示”。

当天交付包括：

- PostgreSQL + pgvector、API 和 Web 的 Docker Compose 编排；
- 项目根 README；
- 从空数据库开始的迁移、Seed 和文档导入命令；
- 可复现的 Living RAG 完整演示脚本；
- Docker、数据库初始化和关键业务链路的真实验证。

## 二、业务场景

Living RAG 面向电商售后政策。政策会产生新版本、失效版本、FAQ 冲突和临时公告。系统除了回答政策问题，还需要查询订单和会员信息、判断退款资格，并在直接退款等高风险操作上创建人工审批任务。

Day 17 的重点不是增加新的业务规则，而是证明已经完成的业务链路可以被另一个开发者按照 README 和演示脚本重复运行。

## 三、完成的文件

### 1. Docker Compose

文件：

`E:\Living RAG\docker-compose.yml`

当前默认启动：

- PostgreSQL + pgvector；
- FastAPI API；
- Next.js Web。

API 增加了 `/health` 健康检查，Web 等待 API 进入 healthy 状态后启动。API 通过 `/shared` 只读挂载共享任务集，通过 `/data` 只读挂载样例数据。

### 2. README

文件：

`E:\Living RAG\README.md`

README 已包含：

- 问题背景；
- 项目定位和技术栈；
- 系统架构 Mermaid 图；
- LangGraph 问答流程图；
- 核心数据关系图；
- Docker 启动方法；
- 空数据库初始化；
- Seed 和文档导入；
- 测试命令；
- 风险控制；
- Ollama 说明；
- 已知限制；
- 演示脚本入口。

README 已同步实际 Compose 行为：

```powershell
docker compose up --build -d
```

不再要求通过 `web` profile 单独启动 Web。

### 3. 演示脚本

文件：

`E:\Living RAG\docs\living-rag-demo-script.md`

演示脚本覆盖：

- Docker 启动；
- API 健康检查；
- Alembic 迁移；
- Seed；
- 样例文档导入；
- 政策问答；
- 冲突问答；
- 订单资格判断；
- 高风险退款审批；
- 审批任务查询；
- 审计日志查询；
- `trace_id` 运行详情查询；
- 故障排查和服务停止。

脚本中的中文 POST 请求使用 UTF-8 字节发送，避免 Windows PowerShell 默认编码导致中文问题被服务端错误解析。

历史订单演示使用：

```text
as_of=2026-01-17T12:00:00Z
```

这是为了让 `O2025001` 的“签收 12 天”业务场景在当前系统时间变化后仍然可复现。直接退款请求包含订单号，并且预期返回 `create_approval_task`，而不是直接执行退款。

## 四、实际执行命令

项目目录：

```powershell
Set-Location "E:\Living RAG"
```

Compose 配置检查：

```powershell
docker compose config --quiet
```

数据库迁移：

```powershell
docker compose exec -T api alembic upgrade head
```

Seed：

```powershell
docker compose exec -T api python "/app/scripts/seed_database.py"
```

文档导入：

```powershell
docker compose exec -T api python "/app/scripts/ingest_sample_documents.py"
```

API 健康检查：

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/health" `
    -Method Get
```

## 五、实际验证结果

### Docker

```text
living-rag-postgres-1  Up (healthy)
living-rag-api-1       Up (healthy)
living-rag-web-1       Up
```

`docker compose config --quiet` 通过。

API 返回：

```json
{
  "status": "ok",
  "service": "living-rag-api"
}
```

### 数据库迁移

Alembic 使用 PostgreSQL transactional DDL 执行成功。数据库已经处于最新迁移版本。

### Seed

```text
users: created=0, updated=20
membership_accounts: created=0, updated=20
orders: created=0, updated=40
refund_requests: created=0, updated=6
```

Seed 可以重复执行，说明当前脚本具备幂等更新行为。

### 文档导入

```text
documents: created=0, updated=6
document_versions: created=0, unchanged=8
document_chunks: created=0, unchanged=56
```

数据库验证结果：

```text
users=20
membership_accounts=20
orders=40
refund_requests=6
documents=6
document_versions=8
document_chunks=56
```

56 个 Chunk 均已存在 embedding。

### 政策问答

使用 UTF-8 请求体调用：

```text
POST /api/chat
```

真实响应验证成功：

- 返回 `trace_id`；
- `citation_valid=true`；
- 引用版本为退款政策 v3；
- 返回有效引用 Chunk；
- `confidence` 为非零值。

首次直接使用 Windows PowerShell 默认中文请求时，服务返回了无证据结果。定位后确认是请求编码问题。使用 UTF-8 字节发送中文 JSON 后，问答恢复为有效引用结果。该问题已经记录到演示脚本中。

### 订单资格和审批

当前系统日期为 2026-08-10，直接使用 Seed 中的 2026 年 1 月订单会被正确判断为超过退款期限。演示脚本使用 `as_of=2026-01-17T12:00:00Z` 重现历史业务场景。

真实审批链路验证成功：

```text
action=create_approval_task
status=pending
trace_id=66e415fa-f512-4475-9c5c-be6a97200154
approval_task_id=73a83957-22a6-44e7-a599-eea77fb882a0
```

运行详情验证：

```text
run_detail_trace_id=66e415fa-f512-4475-9c5c-be6a97200154
nodes=0
audit_logs=1
api_audit_logs=1
```

这说明业务动作可以关联到 Agent Run 和审计日志。当前业务动作链路没有保存 LangGraph 节点记录，因此其运行详情中的 `nodes=0` 是已知限制；政策问答链路仍然保存节点运行记录。

## 六、测试和验证边界

本日志中的命令证明：

- Docker Compose 配置可以解析；
- PostgreSQL、API 和 Web 可以启动；
- API 健康检查可用；
- Alembic 迁移可执行；
- Seed 可重复执行；
- 文档导入可重复执行；
- 样例数据存在；
- 中文 UTF-8 请求可以正确进入问答和业务动作链路；
- 问答可以返回引用和 Trace；
- 高风险动作可以创建审批任务；
- 审计日志和运行详情可以通过 Trace 查询。

本日志中的命令没有证明：

- 生产环境订单或支付系统可以接入；
- Ollama 一定已经运行；
- 当前 Mock/本地模型具备生产级回答质量；
- 业务动作链路已经具备节点级 LangGraph Trace；
- 系统具备复杂权限、队列和分布式部署能力。

## 七、Day 17 验收结论

Day 17 的 Docker、README 和演示脚本交付目标已完成。Living RAG 可以从 Compose 启动开始，按 README 执行迁移、Seed 和文档导入，并完成政策问答、订单业务动作、审批门控、审计日志和 Trace 查询演示。

剩余工程动作是执行 Day 17 全量测试、检查 Git 差异并创建提交。版本标签 `living-rag-v0.1.0` 应在提交成功且验收结果确认后创建。

## 八、当天理解要点

- Docker Compose 解决的是服务编排和运行环境一致性；
- Alembic 负责数据库结构，不负责导入业务数据；
- Seed 负责用户、会员、订单和退款历史；
- 文档导入负责文档版本和 Chunk；
- README 解释项目如何启动；
- 演示脚本证明项目如何被重复运行；
- `trace_id` 负责把问答、工具、审批、回答和审计关联起来；
- 高风险操作返回审批任务，说明安全门控生效，而不是业务失败。

# Living RAG

Living RAG 是一个面向电商售后政策的动态知识库 Agent。它解决的不只是“上传文档后问答”，而是把政策版本、有效期、冲突、引用、订单会员工具、退款审批、审计和运行 Trace 放进一条可以解释和回放的业务链路。

## 数据声明

本仓库中的用户、订单、会员、政策和评测任务均为合成演示数据，不包含真实客户信息、生产订单或真实业务凭据。项目不连接真实支付、订单或 CRM 系统。

```text
All users, orders, policies, and evaluation cases in this repository are synthetic demo data.
```

## 问题背景

电商售后政策会持续更新，正式政策、FAQ、临时公告和运营通知可能出现版本差异或直接冲突。一个只依赖向量相似度和 LLM 生成的 RAG，可能引用过期政策、忽略冲突、猜测订单状态，甚至直接执行高风险退款操作。

## 项目定位

Living RAG 针对这些问题提供：

- 文档、版本和 Chunk 管理；
- 有效期和文档状态治理；
- 正式政策、FAQ 和临时公告的冲突检测；
- 人工审核任务；
- 带文档版本和原文片段的问答；
- 订单、用户、会员和退款历史查询工具；
- Python 确定性退款资格判断；
- 退款申请、审批和审计；
- LangGraph 节点级 Trace 和运行详情；
- 共享的结构化 Agent 任务集。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| API | FastAPI |
| Agent 工作流 | LangGraph |
| LLM/工具基础 | LangChain Core |
| 数据校验 | Pydantic |
| ORM | SQLAlchemy |
| 数据库 | PostgreSQL 16 + pgvector |
| 前端 | Next.js、TypeScript、Tailwind CSS |
| 测试 | pytest |
| 本地编排 | Docker Compose |
| Embedding | Mock、Ollama 或 OpenAI-compatible Provider |

## 系统架构

```mermaid
flowchart LR
    Browser["浏览器 / Next.js Web"]
    API["FastAPI API"]
    Graph["LangGraph QA Workflow"]
    Services["检索、业务工具和安全服务"]
    DB[("PostgreSQL + pgvector")]
    Shared["/shared/datasets 共享任务集"]
    Ollama["可选 Ollama"]

    Browser --> API
    API --> Graph
    Graph --> Services
    Services --> DB
    Graph --> DB
    API --> Shared
    Graph -. 可选 .-> Ollama
```

Compose 默认启动 PostgreSQL、API 和 Web。Ollama 是可选模型依赖，不阻塞基础启动。

## LangGraph 问答流程

```mermaid
flowchart TD
    Start["START"] --> Load["load_context"]
    Load --> Intent["classify_intent"]
    Intent --> Retrieve["retrieve_documents"]
    Retrieve --> Grade["grade_documents"]
    Grade --> Conflict["check_conflicts"]
    Conflict -->|存在关键冲突| Safe["safe_conflict_response"]
    Conflict -->|无关键冲突| Generate["generate_grounded_answer"]
    Safe --> Verify["verify_citations"]
    Generate --> Verify
    Verify --> Save["save_run_and_message"]
    Save --> End["END"]
```

核心约束：

- 当前有效文档优先于已废弃、过期或待审核文档；
- 引用必须能对应真实文档 Chunk；
- 冲突未解决时不能擅自给出唯一政策结论；
- 退款资格由 Python 规则服务判断，LLM 不直接裁定；
- 直接退款、删除文档和修改规则必须经过人工审批；
- 每次问答保存 `trace_id`，可以查询完整运行过程。

## 核心数据关系

```mermaid
erDiagram
    DOCUMENT ||--o{ DOCUMENT_VERSION : contains
    DOCUMENT_VERSION ||--o{ DOCUMENT_CHUNK : contains
    CHAT_THREAD ||--o{ CHAT_MESSAGE : contains
    AGENT_RUN ||--o{ AGENT_NODE_RUN : contains
    AGENT_RUN ||--o{ TOOL_CALL : records
    AGENT_RUN ||--o{ CHAT_MESSAGE : traces
    AGENT_RUN ||--o{ APPROVAL_TASK : requests
    AGENT_RUN ||--o{ AUDIT_LOG : records
    USER ||--o{ ORDER : places
    USER ||--o| MEMBERSHIP_ACCOUNT : owns
    ORDER ||--o{ REFUND_REQUEST : has
```

一次运行通过 `trace_id` 关联：

```text
AgentRun
├── AgentNodeRun
├── ToolCall
├── ChatMessage
├── ApprovalTask
└── AuditLog
```

运行详情服务文件：

```text
E:\Living RAG\apps\living-rag-api\app\services\run_detail_service.py
```

运行详情 API：

```text
GET /runs/{trace_id}
```

## 项目目录

```text
E:\Living RAG\
├── apps\living-rag-api\       FastAPI、LangGraph、RAG 和业务工具
├── apps\living-rag-web\       Next.js 前端
├── data\                       样例用户、订单和政策文档
├── shared\datasets\            两个项目共享的 Agent 任务集
├── docs\                       数据库设计和演示文档
├── learning-notes\             每日学习日志
├── infra\postgres\             PostgreSQL 初始化脚本
├── docker-compose.yml          Docker 服务编排
└── .env.example                配置模板
```

Day 16 任务集文件：

```text
E:\Living RAG\shared\datasets\qa\policy_qa.jsonl
E:\Living RAG\shared\datasets\conflict-cases\policy_conflicts.jsonl
E:\Living RAG\shared\datasets\agent-tasks\business_eligibility.jsonl
E:\Living RAG\shared\datasets\fault-injection\fault_cases.jsonl
E:\Living RAG\shared\datasets\adversarial\high_risk_and_multiturn.jsonl
```

当前共享任务集共 71 条，包含正常政策问答、版本过期、冲突、订单会员资格、高风险、多轮、故障注入和对抗任务。

## 环境要求

- Windows 10/11；
- Docker Desktop；
- Docker Compose v2；
- PowerShell；
- 可选：Node.js 20，用于不通过容器运行前端；
- 可选：Ollama 和 `nomic-embed-text` 模型。

## 配置环境变量

配置模板：

```text
E:\Living RAG\.env.example
```

创建本地配置：

```powershell
Set-Location "E:\Living RAG"

Copy-Item `
  "E:\Living RAG\.env.example" `
  "E:\Living RAG\.env"
```

不要提交：

```text
E:\Living RAG\.env
```

关键配置包括：

```text
DATABASE_URL=postgresql+psycopg://living_rag:change-me-before-production@postgres:5432/living_rag
WEB_ORIGIN=http://localhost:3000
EMBEDDING_PROVIDER=mock
OLLAMA_BASE_URL=http://host.docker.internal:11434
EMBEDDING_MODEL=nomic-embed-text
```

默认使用 Mock Embedding，保证基础 Docker 演示不依赖额外模型服务。需要真实 Embedding 时，可以将 `.env` 中的 `EMBEDDING_PROVIDER` 改为 `ollama` 或 `openai_compatible`；Ollama 不属于默认启动依赖。

## Docker 启动

Compose 文件：

```text
E:\Living RAG\docker-compose.yml
```

先检查 Compose 配置：

```powershell
Set-Location "E:\Living RAG"

docker compose config --quiet
```

启动 PostgreSQL、API 和 Web：

```powershell
docker compose up --build -d
```

查看服务：

```powershell
docker compose ps
```

期望看到：

```text
living-rag-postgres-1   Up (healthy)
living-rag-api-1        Up
living-rag-web-1        Up
```

API 健康检查：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/health" `
  -Method Get
```

访问地址：

```text
FastAPI 文档：http://127.0.0.1:8000/docs
前端：http://127.0.0.1:3000
```

停止服务：

```powershell
docker compose down
```

以上命令不会删除 PostgreSQL 命名卷。需要清空本地数据库时，必须明确执行带卷删除的命令，并确认这是可接受的破坏性操作。

## 从空数据库初始化

后端目录：

```text
E:\Living RAG\apps\living-rag-api
```

Alembic 配置和迁移目录：

```text
E:\Living RAG\apps\living-rag-api\alembic.ini
E:\Living RAG\apps\living-rag-api\alembic
```

执行数据库迁移：

```powershell
Set-Location "E:\Living RAG"

docker compose exec -T api alembic upgrade head
```

导入用户、会员、订单和退款历史：

```powershell
docker compose exec -T api python `
  "/app/scripts/seed_database.py"
```

Seed 文件：

```text
E:\Living RAG\apps\living-rag-api\scripts\seed_database.py
```

导入 Markdown 政策文档、版本和 Chunk：

```powershell
docker compose exec -T api python `
  "/app/scripts/ingest_sample_documents.py"
```

文档导入脚本：

```text
E:\Living RAG\apps\living-rag-api\scripts\ingest_sample_documents.py
```

样例输入目录：

```text
E:\Living RAG\data\sample_documents
```

容器内对应目录：

```text
/data/sample_documents
```

## API 快速验证

健康检查：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/health" `
  -Method Get
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

完整问答、审批、审计和 Trace 演示请执行：

```text
E:\Living RAG\docs\living-rag-demo-script.md
```

问答返回的 `trace_id` 可以用于查询：

```powershell
$traceId = $chatResponse.trace_id

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/runs/$traceId" `
  -Method Get
```

审计日志接口：

```text
GET /audit-logs
```

运行详情接口：

```text
GET /runs/{trace_id}
```

## 测试

测试目录：

```text
E:\Living RAG\apps\living-rag-api\tests
```

运行完整测试：

```powershell
Set-Location "E:\Living RAG"

docker compose exec -T api python -m pytest -q
```

当前 Day 16 收尾时全量测试结果：

```text
300 passed, 2 warnings
```

警告来自当前 FastAPI/Starlette TestClient 兼容提示和 LangGraph 依赖弃用提示，不影响测试通过。

## 风险控制

- LLM 不直接裁定退款资格，资格判断由 Python 确定性服务完成；
- 直接退款必须创建人工审批任务；
- 删除政策文档必须审批；
- 修改退款规则必须审批；
- 审批结果写入审计日志；
- 审批、审计、用户消息和 Agent Run 通过 `trace_id` 关联；
- 冲突未解决时不擅自选择最终政策；
- 过期、失效和待审核文档不能作为当前政策依据；
- 引用必须通过真实 Chunk 校验；
- 检索为空时保守回答，不编造结论；
- 工具失败、超时或权限拒绝时不猜测业务数据；
- 检索重写、生成修复和工具调用都有次数限制；
- `.env`、API Key、密码和本地数据库数据不提交 Git。

## 可选 Ollama

Ollama 不是基础 Docker 启动的必需服务。需要本地模型时：

1. 在 Windows 主机安装 Ollama；
2. 拉取 `nomic-embed-text`；
3. 修改本机配置文件：

```text
E:\Living RAG\.env
```

配置：

```text
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
EMBEDDING_MODEL=nomic-embed-text
```

API 容器通过 `host.docker.internal` 访问 Windows 主机上的 Ollama。没有 Ollama 时，使用 Mock 或其他兼容 Provider 不应阻塞基础演示。

## 演示脚本

完整可复现演示：

```text
E:\Living RAG\docs\living-rag-demo-script.md
```

演示顺序：

1. 启动 PostgreSQL、API 和 Web；
2. 执行迁移；
3. 导入用户、会员、订单和退款历史；
4. 导入退款政策 v1、v2、v3；
5. 导入冲突 FAQ；
6. 查看冲突审核任务；
7. 提问当前退款政策并展示引用和版本；
8. 查询订单退款资格；
9. 提交退款申请；
10. 请求直接退款并展示审批门控；
11. 查看审批任务和审计日志；
12. 使用 `trace_id` 查看完整运行详情。

## 已知限制

- 当前业务数据是模拟数据，不连接真实支付、订单或 CRM；
- Mock LLM 没有真实输入 Token、输出 Token 和成本统计；
- QA 检索主要记录在 `retrieve_documents` 节点快照中，尚未统一持久化为独立 `ToolCall`；
- Ollama 需要额外安装模型，默认演示不依赖它；
- 前端是关键流程演示页面，不是生产级后台；
- 当前没有复杂 RBAC、Redis、Celery、Nginx 或生产级任务队列；
- PowerShell 的中文显示可能受终端编码设置影响；
- 当前系统目标是稳定可演示的 MVP，不宣称生产级全功能平台。

## 当前交付状态

- Day 1 到 Day 14：Living RAG 核心 MVP 已完成；
- Day 15：Trace、日志和运行详情已完成；
- Day 16：共享任务协议、任务加载器和 71 条结构化任务已完成；
- Day 17：Docker、README 和演示脚本已完成；
- Day 18 之后：开始 Agent Reliability Lab。

## 相关文档

数据库设计：

```text
E:\Living RAG\docs\database-schema.md
```

Day 17 演示脚本：

```text
E:\Living RAG\docs\living-rag-demo-script.md
```

Day 16 学习日志：

```text
E:\Living RAG\learning-notes\day-16-automated-task-datasets.md
```

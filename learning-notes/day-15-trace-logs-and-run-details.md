# Day 15：Trace、日志与运行详情

日期：2026-08-08

## 今日目标

让任意一次 Living RAG Agent 运行都可以通过 `trace_id` 查询完整运行详情。

运行详情需要能够关联：

- AgentRun；
- LangGraph 节点运行记录；
- 工具调用；
- 用户问题和 Agent 回答；
- ApprovalTask；
- AuditLog；
- 延迟、Token、预计成本和失败原因。

## 今日完成内容

### 1. 运行详情服务

新增文件：

`E:\Living RAG\apps\living-rag-api\app\services\run_detail_service.py`

服务根据 `trace_id` 查询并组装：

- AgentRun；
- AgentNodeRun；
- ToolCall；
- ChatMessage；
- ApprovalTask；
- AuditLog。

主运行不存在时抛出 `RunNotFoundError`。关联集合为空时返回空列表，不把正常业务情况误判成错误。

### 2. 运行详情 Schema

新增文件：

`E:\Living RAG\apps\living-rag-api\app\schemas\run_detail.py`

定义了：

- `AgentRunDetail`；
- `AgentNodeRunDetail`；
- `ToolCallDetail`；
- `ChatMessageDetail`；
- `RunDetailResponse`。

Schema 使用 `from_attributes=True` 读取 SQLAlchemy ORM 对象，并将 ORM 属性 `metadata_` 输出为 API 字段 `metadata`。

### 3. 运行详情 API

新增文件：

`E:\Living RAG\apps\living-rag-api\app\api\routes\runs.py`

新增接口：

`GET /runs/{trace_id}`

行为：

- 合法 Trace 且运行存在：返回 HTTP 200；
- UUID 格式错误：FastAPI 返回 HTTP 422；
- UUID 合法但运行不存在：服务抛出 `RunNotFoundError`，路由转换为 HTTP 404；
- 数据库异常：不伪装成 404，继续交给服务器错误处理。

### 4. 路由注册

修改文件：

`E:\Living RAG\apps\living-rag-api\app\main.py`

注册 `runs_router` 后，OpenAPI 中出现：

`/runs/{trace_id}`

API 容器重启后加载了新的路由表。

## 测试结果

### 服务层测试

测试文件：

`E:\Living RAG\apps\living-rag-api\tests\test_run_detail_service.py`

验证内容：

- 不存在 Trace 时抛出 `RunNotFoundError`；
- 有效运行但关联数据为空时返回空列表；
- 完整 Trace 的节点、工具、消息、审批和审计关联；
- 节点按 `sequence_number` 排序；
- 失败 AgentRun 的错误字段保留。

结果：

`4 passed`

### Schema 测试

测试文件：

`E:\Living RAG\apps\living-rag-api\tests\test_run_detail_schema.py`

验证内容：

- ORM 对象可以转换为 Pydantic 响应；
- `metadata_` 输出为 `metadata`；
- 关联集合缺失时使用空列表；
- 负耗时被拒绝；
- 未定义的额外字段被拒绝。

结果：

`5 passed`

### API 测试

测试文件：

`E:\Living RAG\apps\living-rag-api\tests\test_runs_api.py`

验证内容：

- 完整 Trace 返回 HTTP 200；
- 空关联数据返回 HTTP 200 和空列表；
- 不存在 Trace 返回 HTTP 404；
- 非法 UUID 返回 HTTP 422。

结果：

`4 passed, 2 warnings`

警告来自 FastAPI/Starlette TestClient 和 LangGraph 依赖版本，不影响本次测试结果。

## 真实 Trace 验收

真实请求：

`POST http://127.0.0.1:8000/api/chat`

使用用户：

`USR001`

真实 Trace：

`1a991f3d-802d-4937-a895-83504d1e1f64`

随后请求：

`GET http://127.0.0.1:8000/runs/1a991f3d-802d-4937-a895-83504d1e1f64`

返回 HTTP 200，并成功查询到：

- AgentRun；
- 真实 LangGraph 节点路径；
- 节点输入和输出快照；
- 节点耗时；
- 用户消息；
- Assistant 消息；
- 引用和回答 metadata；
- 空的 ApprovalTask 集合；
- 空的 AuditLog 集合。

这证明真实聊天运行和运行详情查询已经连通。

## 已知限制

### 1. Mock 运行没有 Token 和成本统计

真实 Trace 中以下字段为空：

- `input_tokens`；
- `output_tokens`；
- `estimated_cost`。

模型和 Schema 已经支持这些字段，但当前 Mock LLM 没有提供真实 Token 使用量和价格数据。后续接入真实模型或统一模型调用记录后，再补充统计。

### 2. 当前 QA 检索没有独立 ToolCall 记录

真实 Trace 中 `tool_calls` 为空，检索行为记录在 `retrieve_documents` 节点快照中。当前 QA 图没有把检索节点额外持久化为 `ToolCall`。

这不影响节点 Trace 和运行详情查询，但后续 Reliability Lab 需要独立评估工具耗时、工具错误和工具超时，因此应在后续可靠性工作中补充统一 ToolCall 持久化。

### 3. 中文终端显示存在编码问题

PowerShell 输出中的中文出现乱码，当前优先判断为终端输入或输出编码问题。真实 Trace 结构和 HTTP 状态已经验证成功；中文语义回答还需要使用 UTF-8 请求方式重新验收。

## Day 15 验收结论

### 已完成

- [x] Trace 字段检查；
- [x] 运行详情服务；
- [x] 运行详情 Schema；
- [x] 运行详情 API；
- [x] API 路由注册；
- [x] 服务层测试；
- [x] Schema 测试；
- [x] API 测试；
- [x] 合成 Trace 查询；
- [x] 真实 Trace 查询；
- [x] 工具、审批和审计关联结构验证；
- [x] 记录 Token、成本和 ToolCall 的当前限制。

### 未作为 Day 15 阻塞项处理

- [ ] 真实模型 Token 统计；
- [ ] 独立模型调用表；
- [ ] QA 检索节点的 ToolCall 持久化；
- [ ] PowerShell 中文编码统一。

## 复习清单

- `trace_id` 是一次完整 Agent 运行的唯一追踪标识；
- `AgentRun` 表示完整工作流，`AgentNodeRun` 表示其中一个节点；
- `ToolCall` 用于记录工具参数、结果、耗时和错误；
- `ChatMessage` 通过 `trace_id` 关联用户问题和 Agent 回答；
- 服务层负责查询和组装，API 路由负责 HTTP 适配；
- Schema 负责 ORM 对象到稳定 API 响应的转换；
- 空关联数据返回空列表；
- 主运行不存在由服务层抛出异常，路由转换为 HTTP 404；
- 数据库异常不能伪装成 Trace 不存在；
- 真实 Trace 可以通过 `/runs/{trace_id}` 查询。

## 下一步

Day 16 固化共享任务集，建立至少 50 条结构化 Agent 评测任务，为 Agent Reliability Lab 批量执行和规则评测做准备。

# Day 3：领域模型扩展、共享 Schema 与可复现数据

**日期：** 2026-07-19
**投入主题：** DocumentChunk 约束、用户/订单/退款、聊天与 Agent 执行链、共享 Schema、sample data 与 PostgreSQL 回归测试。
**当天里程碑提交：** `21ecc6e feat: add reproducible sample data ingestion`

---

## 今日目标

在 Day 2 的文档基础模型之上，补齐 Living RAG 后续业务需要的领域模型，并建立可以重复执行、可以验证的共享数据基础：

- 建立用户、会员、订单、退款、聊天、Agent 运行、工具调用和审计日志模型；
- 为 `DocumentChunk` 增加数据完整性约束；
- 明确跨领域外键、枚举、状态和审计关系；
- 把跨应用共享的数据结构整理到 shared schemas；
- 编写 Schema 校验测试；
- 使用 sample data 脚本反复填充演示数据，而不是手工改数据库。

## 1. 领域模型设计

### 文档与检索基础

`Document` 表示稳定的逻辑文档身份，`DocumentVersion` 表示某次完整内容快照，`DocumentChunk` 表示具体版本切分后的检索单元：

```text
Document (1) -> DocumentVersion (N) -> DocumentChunk (N)
```

Chunk 必须关联版本，而不能只关联逻辑文档。这样检索结果才能追溯到具体版本，后续重建 embedding、处理政策冲突和回答引用时才不会丢失来源。

### 业务领域

```text
User (1) -> MembershipAccount (N)
User (1) -> Order (N) -> RefundRequest (N)
ChatThread (1) -> ChatMessage (N)
AgentRun (1) -> AgentNodeRun (N) -> ToolCall (N)
AuditLog 记录关键业务和 Agent 行为
```

这些模型先解决身份、状态和关系的可追溯性，暂不把业务流程硬编码到数据库模型中。流程规则由后续 service 层负责，模型负责持久化边界和约束。

## 2. 完成的核心内容

### 2.1 DocumentChunk 与数据库约束

Chunk 保存 `document_version_id`、版本内的 `chunk_index`、切分后的正文，以及后续用于检索的 embedding 字段。数据库约束拒绝空白 Chunk，并保证同一版本内的 Chunk 索引不会重复。这个约束不能只依赖 Python 检查，因为任何写入数据库的入口都必须遵守同一规则。

### 2.2 业务模型与状态

为用户、会员、订单、退款、聊天和 Agent 运行建立 UUID 主键、时间字段、外键和枚举状态。枚举持久化业务值，而不是 Python 成员名，避免代码重命名导致数据库含义改变。

Agent 相关模型保留执行链：

```text
AgentRun
  -> AgentNodeRun
      -> ToolCall
```

再通过 `AuditLog` 记录谁在什么时候执行了什么动作、结果是什么，为之后的可靠性分析和人工复盘提供依据。

### 2.3 共享 Schema 与 sample data

共享 Schema 约束 API、脚本和测试之间的数据契约。Schema 负责输入格式、字段类型、枚举和基础校验；ORM 模型负责数据库映射和持久化约束。两者职责不同，不能用 Schema 代替数据库约束，也不能把所有业务流程塞进 Schema。

sample data 脚本通过 ORM 和事务写入固定的演示实体，并在重复运行时保持确定性，便于本地联调、API 演示、测试数据准备和回归问题复现。

## 3. 验证方式

通过 Alembic 应用迁移，再使用 PostgreSQL 测试数据库和 pytest 验证真实约束。测试重点包括外键关系、双向 ORM 关系、非法状态、重复索引、空白 Chunk、Schema 边界值，以及 sample data 的可重复执行。

Day 3 相关提交：

```text
712f241 feat: add document chunks and constraints
51723ff feat: add users membership orders and refunds
1d596c0 feat: add chat threads and messages
7c51193 feat: add agent runs tools and audit logs
45d2612 docs: add shared schemas and database design
d1c8a4e test: add shared schema validation tests
21ecc6e feat: add reproducible sample data ingestion
```

## 4. 遇到的问题与解决方案

空白 Chunk 不能只在应用层拦截，因此把规则下沉到 PostgreSQL `CHECK` 约束，并在测试中通过 `flush()` 验证数据库行为。测试使用独立 PostgreSQL 数据库和事务回滚，避免污染开发库。共享 Schema 与 ORM 分层后，外部请求格式可以独立演进，数据库内部结构也不会直接暴露给调用方。

## 5. 今日复习清单

1. 为什么 `DocumentChunk` 必须关联 `DocumentVersion`？
2. 为什么空白内容约束要放在数据库中，而不是只放在 service？
3. ORM 模型、Pydantic Schema、Alembic migration 分别负责什么？
4. 为什么测试要使用独立 PostgreSQL 数据库并在测试结束后 rollback？
5. `AgentRun`、`AgentNodeRun`、`ToolCall` 和 `AuditLog` 如何共同支持执行追踪？
6. 为什么 sample data 脚本必须可重复执行？

## 6. 下一天的起点

进入文档摄入链路：解析上传文件、规范化正文、计算内容哈希、按段落切分 Chunk，并创建文档版本和版本内 Chunk。

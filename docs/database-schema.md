# Living RAG 数据库设计说明

## 1. 文档目的

本文档说明 Living RAG 项目的数据库结构、业务关系、字段职责、约束、索引、迁移和测试策略。

项目代码中的表名、字段名、枚举名保持英文，业务解释使用中文，方便开发、学习和面试复习。

## 2. 数据库基础信息

开发数据库：

- 数据库名：`living_rag`
- 用户名：`living_rag`
- Docker 内部主机：`postgres`
- Windows 主机工具主机：`localhost`
- 端口：`5432`

测试数据库：

- 数据库名：`living_rag_test`
- 用户名：`living_rag`
- 测试时使用独立数据库
- 测试不会污染开发数据库

项目数据库技术：

- PostgreSQL 16
- pgvector
- SQLAlchemy ORM
- Alembic
- pytest

数据库结构由 SQLAlchemy ORM 模型和 Alembic 迁移管理，不通过 DataGrip 手工修改结构。

## 3. 总体业务关系

### 3.1 文档关系

Document
  └── DocumentVersion
          └── DocumentChunk

说明：

- `documents`：稳定的逻辑文档；
- `document_versions`：文档的不同内容版本；
- `document_chunks`：某个版本切分后的文本块。

### 3.2 用户和交易关系

User
  └── MembershipAccount
          └── Order
                  └── RefundRequest

说明：

- `users`：用户身份；
- `membership_accounts`：会员账户；
- `orders`：订单；
- `refund_requests`：退款申请。

### 3.3 聊天和 Agent 关系

User
  └── ChatThread
          └── ChatMessage
                  └── AgentRun
                          ├── AgentNodeRun
                          └── ToolCall

说明：

- `chat_threads`：一次持续的对话；
- `chat_messages`：单条聊天消息；
- `agent_runs`：一次完整 Agent 执行；
- `agent_node_runs`：一次 Agent 执行中的节点；
- `tool_calls`：Agent 调用工具的记录。

### 3.4 审计关系

AuditLog
  ├── actor_type
  ├── actor_id
  ├── resource_type
  ├── resource_id
  └── trace_id

`audit_logs` 使用通用资源引用记录订单、退款、文档、Agent 和审批行为。

## 4. 数据表说明

## 4.1 documents：逻辑文档表

作用：

保存一个稳定的逻辑文档，不直接代表某一个具体版本。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 文档主键 |
| `title` | VARCHAR(255) | 否 | 文档标题 |
| `status` | `document_status` | 否 | 文档状态 |
| `metadata` | JSONB | 否 | 扩展信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `active`：当前正常使用；
- `archived`：已归档。

关系：

- 一个文档可以拥有多个版本；
- 删除文档时，文档版本级联删除。

索引：

- `ix_documents_status_created_at`

## 4.2 document_versions：文档版本表

作用：

保存一个逻辑文档的具体内容快照。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 版本主键 |
| `document_id` | UUID | 否 | 所属文档 |
| `version_number` | INTEGER | 否 | 版本号 |
| `status` | `document_version_status` | 否 | 处理状态 |
| `content` | TEXT | 否 | 完整正文 |
| `content_hash` | VARCHAR(64) | 否 | 内容哈希 |
| `metadata` | JSONB | 否 | 来源和政策信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `pending`：等待处理；
- `processing`：正在处理；
- `ready`：可以用于检索；
- `failed`：处理失败。

约束：

- `version_number > 0`；
- 同一个文档不能重复使用相同版本号；
- `(document_id, version_number)` 唯一。

关系：

- `document_versions.document_id → documents.id`；
- 删除文档时级联删除版本。

索引：

- `ix_document_versions_document_id_status`
- `ix_document_versions_content_hash`

## 4.3 document_chunks：文档切块表

作用：

保存文档版本切分后的文本片段，用于 Embedding 和检索。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | Chunk 主键 |
| `document_version_id` | UUID | 否 | 所属文档版本 |
| `chunk_index` | INTEGER | 否 | Chunk 顺序 |
| `content` | TEXT | 否 | Chunk 内容 |
| `content_hash` | VARCHAR(64) | 否 | 内容哈希 |
| `char_start` | INTEGER | 是 | 原文起始位置 |
| `char_end` | INTEGER | 是 | 原文结束位置 |
| `metadata` | JSONB | 否 | 标题等扩展信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |

约束：

- `chunk_index >= 0`；
- 内容不能是空字符串或纯空白；
- `(document_version_id, chunk_index)` 唯一。

关系：

- `document_chunks.document_version_id → document_versions.id`；
- 删除文档版本时级联删除 Chunk。

索引：

- `ix_document_chunks_content_hash`
- `ix_document_chunks_document_version_id_chunk_index`

说明：

Embedding 字段暂未加入。等 Embedding Provider 和向量维度确定后，再增加 pgvector 字段和索引。

## 4.4 users：用户表

作用：

保存系统中的用户身份，不直接保存订单和会员业务字段。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 用户主键 |
| `external_id` | VARCHAR(255) | 否 | 外部系统用户编号 |
| `email` | VARCHAR(320) | 是 | 邮箱 |
| `display_name` | VARCHAR(255) | 否 | 展示名称 |
| `status` | `user_status` | 否 | 用户状态 |
| `metadata` | JSONB | 否 | 扩展信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `active`：正常使用；
- `disabled`：被禁用，但保留历史记录。

约束：

- `external_id` 必须唯一；
- 禁用用户不应直接物理删除。

索引：

- `uq_users_external_id`
- `ix_users_status_created_at`

## 4.5 membership_accounts：会员账户表

作用：

保存用户在会员体系中的账户。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 会员账户主键 |
| `user_id` | UUID | 否 | 所属用户 |
| `membership_number` | VARCHAR(64) | 否 | 业务会员编号 |
| `tier` | `membership_tier` | 否 | 会员等级 |
| `status` | `membership_account_status` | 否 | 账户状态 |
| `points` | INTEGER | 否 | 会员积分 |
| `started_at` | TIMESTAMP | 否 | 生效时间 |
| `expires_at` | TIMESTAMP | 是 | 到期时间 |
| `metadata` | JSONB | 否 | 扩展信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

会员等级：

- `standard`：普通会员；
- `silver`：银卡会员；
- `gold`：金卡会员；
- `platinum`：铂金会员。

会员状态：

- `active`：有效；
- `suspended`：冻结；
- `expired`：过期；
- `closed`：关闭。

约束：

- 一个用户最多一个会员账户；
- `membership_number` 唯一；
- `points >= 0`。

关系：

- `membership_accounts.user_id → users.id`；
- 删除用户时级联删除会员账户。

索引：

- `uq_membership_accounts_user_id`
- `uq_membership_accounts_membership_number`
- `ix_membership_accounts_status_created_at`

## 4.6 orders：订单表

作用：

保存会员账户产生的业务订单。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 订单主键 |
| `membership_account_id` | UUID | 否 | 所属会员账户 |
| `order_number` | VARCHAR(64) | 否 | 业务订单号 |
| `status` | `order_status` | 否 | 订单状态 |
| `total_amount` | NUMERIC(12,2) | 否 | 订单总金额 |
| `currency` | VARCHAR(3) | 否 | 货币，默认 CNY |
| `ordered_at` | TIMESTAMP | 否 | 下单时间 |
| `paid_at` | TIMESTAMP | 是 | 支付时间 |
| `completed_at` | TIMESTAMP | 是 | 完成时间 |
| `metadata` | JSONB | 否 | 商品和渠道信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `pending`：待支付；
- `paid`：已支付；
- `shipped`：已发货；
- `completed`：已完成；
- `cancelled`：已取消；
- `refunded`：已全部退款；
- `partially_refunded`：部分退款。

约束：

- `order_number` 唯一；
- `total_amount >= 0`；
- 金额使用 `NUMERIC(12,2)`，不使用浮点数。

关系：

- `orders.membership_account_id → membership_accounts.id`；
- 使用 `ON DELETE RESTRICT`；
- 删除会员账户不能自动删除订单。

索引：

- `uq_orders_order_number`
- `ix_orders_membership_account_id_status`
- `ix_orders_ordered_at`

## 4.7 refund_requests：退款申请表

作用：

保存用户针对订单提交的一次退款申请。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 退款申请主键 |
| `order_id` | UUID | 否 | 所属订单 |
| `request_number` | VARCHAR(64) | 否 | 退款申请编号 |
| `status` | `refund_request_status` | 否 | 申请状态 |
| `requested_amount` | NUMERIC(12,2) | 否 | 申请金额 |
| `approved_amount` | NUMERIC(12,2) | 是 | 批准金额 |
| `reason` | TEXT | 否 | 退款原因 |
| `rejection_reason` | TEXT | 是 | 拒绝原因 |
| `requested_at` | TIMESTAMP | 否 | 申请时间 |
| `reviewed_at` | TIMESTAMP | 是 | 审核时间 |
| `completed_at` | TIMESTAMP | 是 | 完成时间 |
| `metadata` | JSONB | 否 | 政策版本等 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `pending`：待处理；
- `reviewing`：审核中；
- `approved`：审核通过；
- `rejected`：审核拒绝；
- `processing`：退款处理中；
- `completed`：退款完成；
- `cancelled`：已取消。

约束：

- `request_number` 唯一；
- `requested_amount > 0`；
- `approved_amount` 可以为空；
- `approved_amount > 0`；
- `approved_amount <= requested_amount`。

关系：

- `refund_requests.order_id → orders.id`；
- 使用 `ON DELETE RESTRICT`；
- 删除订单不能自动删除退款历史。

业务服务还需要检查：

- 订单是否允许退款；
- 历史退款加本次退款是否超过订单金额；
- 是否超过政策有效期；
- 是否需要人工审批。

索引：

- `uq_refund_requests_request_number`
- `ix_refund_requests_order_id_status`
- `ix_refund_requests_requested_at`

## 4.8 chat_threads：聊天线程表

作用：

保存一次持续的用户对话。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 线程主键 |
| `user_id` | UUID | 否 | 所属用户 |
| `title` | VARCHAR(255) | 是 | 对话标题 |
| `status` | `chat_thread_status` | 否 | 线程状态 |
| `subject` | `chat_subject` | 否 | 业务主题 |
| `last_message_at` | TIMESTAMP | 是 | 最后消息时间 |
| `metadata` | JSONB | 否 | 来源和语言 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

线程状态：

- `active`：正在使用；
- `archived`：已归档。

对话主题：

- `policy`：政策咨询；
- `order`：订单咨询；
- `refund`：退款咨询；
- `membership`：会员咨询；
- `general`：通用问题。

关系：

- `chat_threads.user_id → users.id`；
- 使用 `ON DELETE RESTRICT`；
- 用户禁用不会删除历史聊天。

索引：

- `ix_chat_threads_user_id_status`
- `ix_chat_threads_last_message_at`

## 4.9 chat_messages：聊天消息表

作用：

保存线程中的单条消息。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 消息主键 |
| `thread_id` | UUID | 否 | 所属线程 |
| `sequence_number` | INTEGER | 否 | 线程内顺序 |
| `role` | `chat_message_role` | 否 | 消息角色 |
| `content` | TEXT | 否 | 消息正文 |
| `status` | `chat_message_status` | 否 | 消息状态 |
| `trace_id` | UUID | 是 | Agent 追踪 ID |
| `citations` | JSONB | 否 | 回答引用 |
| `metadata` | JSONB | 否 | 模型和 Prompt 信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

角色：

- `user`：用户；
- `assistant`：助手；
- `system`：系统；
- `tool`：工具。

状态：

- `pending`：处理中；
- `completed`：已完成；
- `failed`：失败。

约束：

- `sequence_number > 0`；
- `(thread_id, sequence_number)` 唯一；
- 内容不能是空白；
- 删除线程时级联删除消息。

索引：

- `ix_chat_messages_thread_id_created_at`
- `ix_chat_messages_trace_id`

## 4.10 agent_runs：Agent 运行表

作用：

保存一次完整 Agent 工作流的摘要。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 运行主键 |
| `thread_id` | UUID | 否 | 所属线程 |
| `message_id` | UUID | 是 | 关联消息 |
| `trace_id` | UUID | 否 | 全链路追踪 ID |
| `status` | `agent_run_status` | 否 | 运行状态 |
| `intent` | VARCHAR(128) | 是 | 用户意图 |
| `workflow_version` | VARCHAR(64) | 否 | 工作流版本 |
| `model_name` | VARCHAR(128) | 是 | 使用的模型 |
| `prompt_version` | VARCHAR(64) | 是 | Prompt 版本 |
| `started_at` | TIMESTAMP | 是 | 开始时间 |
| `completed_at` | TIMESTAMP | 是 | 完成时间 |
| `duration_ms` | INTEGER | 是 | 执行耗时 |
| `input_tokens` | INTEGER | 是 | 输入 Token |
| `output_tokens` | INTEGER | 是 | 输出 Token |
| `estimated_cost` | NUMERIC(12,6) | 是 | 估算成本 |
| `error_code` | VARCHAR(128) | 是 | 错误编码 |
| `error_message` | TEXT | 是 | 错误信息 |
| `metadata` | JSONB | 否 | 扩展数据 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `pending`：等待执行；
- `running`：执行中；
- `succeeded`：成功；
- `failed`：失败；
- `cancelled`：取消。

约束：

- `trace_id` 唯一；
- duration 不能为负；
- Token 数不能为负。

关系：

- `thread_id → chat_threads.id`；
- `message_id → chat_messages.id`；
- 消息删除时 `message_id` 设置为 NULL；
- 线程删除受到限制。

索引：

- `ix_agent_runs_thread_id_created_at`
- `ix_agent_runs_status_created_at`

## 4.11 agent_node_runs：Agent 节点运行表

作用：

保存一次 Agent Run 中每个 LangGraph 节点的执行记录。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 节点运行主键 |
| `agent_run_id` | UUID | 否 | 所属 Agent Run |
| `node_name` | VARCHAR(128) | 否 | 节点名称 |
| `sequence_number` | INTEGER | 否 | 节点顺序 |
| `status` | `agent_node_run_status` | 否 | 节点状态 |
| `input_snapshot` | JSONB | 否 | 输入快照 |
| `output_snapshot` | JSONB | 否 | 输出快照 |
| `started_at` | TIMESTAMP | 是 | 开始时间 |
| `completed_at` | TIMESTAMP | 是 | 完成时间 |
| `duration_ms` | INTEGER | 是 | 执行耗时 |
| `error_code` | VARCHAR(128) | 是 | 错误编码 |
| `error_message` | TEXT | 是 | 错误信息 |
| `metadata` | JSONB | 否 | 扩展数据 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `pending`；
- `running`；
- `succeeded`；
- `failed`；
- `skipped`。

约束：

- `sequence_number > 0`；
- `(agent_run_id, sequence_number)` 唯一；
- 删除 Agent Run 时级联删除节点记录。

索引：

- `ix_agent_node_runs_agent_run_id_status`

## 4.12 tool_calls：工具调用表

作用：

保存 Agent 调用工具的记录。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 工具调用主键 |
| `agent_run_id` | UUID | 否 | 所属 Agent Run |
| `node_run_id` | UUID | 是 | 所属节点 |
| `tool_name` | VARCHAR(128) | 否 | 工具名称 |
| `status` | `tool_call_status` | 否 | 调用状态 |
| `arguments` | JSONB | 否 | 工具输入 |
| `result` | JSONB | 否 | 工具结果 |
| `started_at` | TIMESTAMP | 是 | 开始时间 |
| `completed_at` | TIMESTAMP | 是 | 完成时间 |
| `duration_ms` | INTEGER | 是 | 执行耗时 |
| `error_code` | VARCHAR(128) | 是 | 错误编码 |
| `error_message` | TEXT | 是 | 错误信息 |
| `metadata` | JSONB | 否 | 扩展数据 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |
| `updated_at` | TIMESTAMP | 否 | 更新时间 |

状态：

- `pending`：等待执行；
- `succeeded`：执行成功；
- `failed`：执行失败；
- `timeout`：执行超时。

关系：

- `agent_run_id → agent_runs.id`；
- `node_run_id → agent_node_runs.id`；
- Agent Run 删除时级联删除工具调用；
- 节点删除时 `node_run_id` 设置为 NULL。

索引：

- `ix_tool_calls_agent_run_id_status`
- `ix_tool_calls_tool_name_created_at`

## 4.13 audit_logs：审计日志表

作用：

记录高风险操作和关键系统行为。

字段：

| 字段 | 类型 | 是否为空 | 说明 |
|---|---|---:|---|
| `id` | UUID | 否 | 审计记录主键 |
| `actor_type` | `audit_actor_type` | 否 | 行为发起者类型 |
| `actor_id` | UUID | 是 | 行为发起者 ID |
| `action` | VARCHAR(128) | 否 | 执行动作 |
| `resource_type` | VARCHAR(128) | 否 | 资源类型 |
| `resource_id` | UUID | 是 | 资源 ID |
| `result` | `audit_result` | 否 | 执行结果 |
| `reason` | TEXT | 是 | 原因 |
| `before_snapshot` | JSONB | 否 | 操作前快照 |
| `after_snapshot` | JSONB | 否 | 操作后快照 |
| `trace_id` | UUID | 是 | Agent 追踪 ID |
| `metadata` | JSONB | 否 | 扩展信息 |
| `created_at` | TIMESTAMP | 否 | 创建时间 |

行为发起者：

- `user`；
- `agent`；
- `system`；
- `admin`。

审计结果：

- `success`：成功；
- `failure`：失败；
- `denied`：拒绝；
- `pending`：等待处理。

典型动作：

- `refund.requested`
- `refund.approval_requested`
- `refund.approved`
- `refund.denied`
- `order.status_changed`
- `document.version_archived`
- `tool.call_denied`

索引：

- `ix_audit_logs_actor_type_actor_id`
- `ix_audit_logs_resource_type_resource_id`
- `ix_audit_logs_trace_id_created_at`

## 5. 应用层共享 Schema

应用层 Schema 使用 Pydantic 定义，不会直接创建数据库表。

### Citation

表示回答使用的证据。

字段：

- `document_id`
- `document_version_id`
- `chunk_id`
- `quote`
- `relevance_score`

Citation 应该能够追溯到：

Document
  → DocumentVersion
      → DocumentChunk

### AgentTrace

表示一次完整 Agent 执行的可序列化结果。

包含：

- trace ID；
- Agent Run ID；
- 运行状态；
- 用户意图；
- 工作流版本；
- 模型版本；
- Prompt 版本；
- 节点追踪；
- 工具调用追踪；
- 耗时；
- 错误信息。

### AgentTaskCase

表示 Reliability Lab 中的一条标准测试任务。

包含：

- case ID；
- 任务名称；
- 用户输入；
- 预期意图；
- 预期行为；
- 预期引用；
- 标签；
- 扩展元数据。

### FaultInjectionConfig

表示一次可重复的故障注入配置。

支持：

- `empty_retrieval`：检索为空；
- `tool_timeout`：工具超时；
- `tool_error`：工具报错；
- `permission_denied`：权限拒绝；
- `malformed_output`：输出格式错误；
- `stale_citation`：引用过期；
- `unresolved_conflict`：冲突未解决。

## 6. 外键删除策略

### CASCADE

适合子记录无法独立存在的关系：

- Document → DocumentVersion；
- DocumentVersion → DocumentChunk；
- ChatThread → ChatMessage；
- AgentRun → AgentNodeRun；
- AgentRun → ToolCall；
- User → MembershipAccount。

### RESTRICT

适合需要保留历史业务记录的关系：

- MembershipAccount → Order；
- Order → RefundRequest；
- User → ChatThread；
- ChatThread → AgentRun。

### SET NULL

适合保留子记录但解除关联的关系：

- AgentRun.message_id → NULL；
- ToolCall.node_run_id → NULL。

## 7. Alembic 迁移链

当前迁移链：

- `0d5401da8f2c`：创建 documents 和 document_versions；
- `e010caf2d41b`：创建 document_chunks；
- `87e39f30bfec`：增强 Chunk 空白内容约束；
- `07769ae36e73`：创建 users；
- `9e7f87036215`：创建 membership_accounts；
- `f9e3f7a938ad`：创建 orders 和 refund_requests；
- `065beb2912a0`：创建 chat_threads 和 chat_messages；
- `72835e40a398`：创建 Agent Runs、节点运行、工具调用和审计日志。

完整迁移链：

0d5401da8f2c
  → e010caf2d41b
  → 87e39f30bfec
  → 07769ae36e73
  → 9e7f87036215
  → f9e3f7a938ad
  → 065beb2912a0
  → 72835e40a398

数据库结构变更必须通过 Alembic 完成，不应通过 DataGrip 手工修改表结构。

## 8. 测试策略

测试数据库：

- 数据库名：`living_rag_test`
- 与开发数据库分离；
- 测试结束后回滚事务；
- 不使用开发数据库执行自动化测试。

测试内容：

- ORM 模型创建；
- UUID 主键；
- 默认状态；
- 双向关系；
- 外键；
- 唯一约束；
- Check 约束；
- JSONB 字段；
- 金额精度；
- Pydantic Schema 校验；
- 空白内容拒绝；
- 非法金额拒绝；
- 非法节点顺序拒绝；
- 工具失败和审计拒绝。

## 9. 典型业务查询

### 查询用户、会员、订单和退款

    SELECT
        u.display_name,
        ma.membership_number,
        ma.tier AS membership_tier,
        o.order_number,
        o.status AS order_status,
        o.total_amount,
        rr.request_number,
        rr.status AS refund_status,
        rr.requested_amount
    FROM users AS u
    LEFT JOIN membership_accounts AS ma
        ON ma.user_id = u.id
    LEFT JOIN orders AS o
        ON o.membership_account_id = ma.id
    LEFT JOIN refund_requests AS rr
        ON rr.order_id = o.id
    ORDER BY
        u.created_at DESC,
        o.ordered_at DESC,
        rr.requested_at DESC;

### 查询某次 Agent Run 的完整追踪

    SELECT
        ar.trace_id,
        ar.status AS run_status,
        ar.workflow_version,
        anr.node_name,
        anr.sequence_number,
        anr.status AS node_status,
        tc.tool_name,
        tc.status AS tool_status
    FROM agent_runs AS ar
    LEFT JOIN agent_node_runs AS anr
        ON anr.agent_run_id = ar.id
    LEFT JOIN tool_calls AS tc
        ON tc.agent_run_id = ar.id
    WHERE ar.trace_id = '替换为实际 trace_id'
    ORDER BY
        anr.sequence_number,
        tc.created_at;

## 10. ORM 和数据库的对应关系

SQLAlchemy ORM 类：

    class User(Base):

对应数据库表：

    users

外键：

    ForeignKey("membership_accounts.id")

表示数据库层面的外键约束。

ORM 关系：

    relationship(...)

表示 Python 对象之间的导航关系。

双向关系：

    back_populates="orders"

表示关系的另一端。

默认排序：

    order_by="Order.ordered_at"

表示加载关联对象时的默认排序。

## 11. 数据库约束和业务规则的边界

数据库约束负责保护单条数据的基础事实：

- 订单号不能重复；
- 退款申请号不能重复；
- 金额不能为负；
- Chunk 内容不能为空；
- 节点顺序不能重复；
- Agent trace_id 不能重复；
- 外键必须指向存在的记录。

业务服务负责保护跨记录和跨流程规则：

- 累计退款不能超过订单金额；
- 订单状态是否允许退款；
- 当前有效政策是哪一个版本；
- 冲突政策是否需要人工审核；
- 高风险操作是否需要审批；
- Agent 是否允许调用某个工具。

## 12. 后续扩展

后续阶段会继续实现：

- 示例政策 Markdown；
- FAQ；
- CSV 模拟数据；
- Seed 脚本；
- 文档导入脚本；
- Embedding；
- pgvector 向量检索；
- 文档有效期过滤；
- LangGraph 问答链；
- Citation 校验；
- Agent API；
- 退款资格判断；
- 人工审批；
- 前端问答页面；
- Reliability Lab；
- 规则评测；
- LLM Judge；
- 故障注入；
- 回归比较。

Embedding 字段暂时不加入当前模型，等 Embedding Provider 和向量维度确定后再增加。

## 13. 面试总结

可以这样介绍数据库设计：

项目使用 PostgreSQL 作为持久化数据库，使用 SQLAlchemy ORM 定义领域模型，使用 Alembic 管理数据库迁移。数据库分为文档知识域、用户交易域、聊天域和 Agent 运行追踪域。文档域支持文档版本、Chunk 和引用追溯；交易域支持用户、会员、订单和退款申请；聊天域保存线程和消息；Agent 域记录运行、节点、工具调用和审计日志。项目使用 UUID、JSONB、枚举、外键、唯一约束、检查约束和索引保证数据完整性，并使用独立测试数据库验证 ORM 关系和数据库约束。
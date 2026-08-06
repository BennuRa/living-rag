# Day 14：退款审批、审计与第二周验收

日期：2026-08-06

## 今日目标

Day 14 是第二周的收尾。今天的目标不是让模型直接执行退款，而是把“查询资格”和“执行副作用操作”明确分开：

1. 用户询问“能否退款”时，只查询订单、会员、退款历史和政策规则，不创建审批任务，也不创建退款申请。
2. 用户申请退款时，由 Python 确定性规则服务计算资格，符合条件后创建 `RefundRequest`。
3. 用户要求“直接退款”时，系统拒绝直接执行，创建 `ApprovalTask` 等待人工审批。
4. 修改退款政策、删除政策文档等高风险操作必须进入人工审批。
5. 审批任务、退款申请、Agent Run、用户对话和审计日志之间可以通过 ID 与 `trace_id` 关联查询。

## 一、今天完成的核心业务

### 1. 风险门控

风险门控服务位于：

`E:\Living RAG\apps\living-rag-api\app\services\risk_gate.py`

它把用户请求分类为四类动作：

| 用户意图 | 系统动作 | 是否产生副作用 |
|---|---|---|
| 查询订单、会员或退款资格 | `read_only` | 否 |
| 申请退款 | `create_refund_request` | 是，创建退款申请 |
| 直接退款、修改政策、删除文档 | `create_approval_task` | 是，创建人工审批任务 |
| 无法安全识别或试图绕过流程 | `reject_direct_execution` | 否 |

高风险关键词优先匹配。例如“我要申请直接退款”不能被识别成普通退款申请，必须进入审批任务流程。这样可以防止模型因为关键词重叠而绕过审批。

### 2. ApprovalTask 模型

模型文件：

`E:\Living RAG\apps\living-rag-api\app\models\approval_task.py`

审批任务支持以下操作类型：

- `refund_request`：退款申请相关审批；
- `direct_refund`：用户要求直接退款；
- `modify_policy`：修改政策规则；
- `delete_document`：删除政策文档。

审批任务状态包括：

- `pending`：已创建，等待人工处理；
- `approved`：人工批准；
- `rejected`：人工拒绝；
- `cancelled`：任务被取消。

这里要区分两个状态对象：

- `RefundRequest.pending` 表示退款申请已经登记，但还没有完成退款；
- `ApprovalTask.pending` 表示该业务操作需要人工决定。

普通退款申请和直接退款并不是同一件事。普通退款申请可以先创建退款申请记录；直接退款属于高风险动作，只能创建审批任务，不能在 API 请求中直接改成已退款。

### 3. 数据库迁移

迁移文件：

`E:\Living RAG\apps\living-rag-api\alembic\versions\21f0e8383e69_add_approval_tasks.py`

今天已执行：

```powershell
Set-Location "E:\Living RAG"
docker compose exec -T api alembic upgrade head
```

数据库已经创建 `approval_tasks` 表，同时创建了审批类型、审批状态和审批决定相关的 PostgreSQL 枚举、索引以及用户和退款申请外键。

### 4. 审批服务与审批 API

审批服务文件：

`E:\Living RAG\apps\living-rag-api\app\services\approval_task_service.py`

审批路由文件：

`E:\Living RAG\apps\living-rag-api\app\api\routes\approval_tasks.py`

已实现：

- 创建审批任务；
- 查询待处理审批任务；
- 批准任务；
- 拒绝任务；
- 防止重复审批；
- 审批时同步退款申请状态；
- 为创建、批准、拒绝动作写入审计日志。

状态流转设计如下：

| 操作 | RefundRequest | ApprovalTask |
|---|---|---|
| 创建申请 | `pending` | `pending`（需要审批时） |
| 人工批准 | `approved` | `approved` |
| 人工拒绝 | `rejected` | `rejected` |
| 退款实际完成 | `completed` | `approved` |

`ApprovalTask.approved` 只代表人工已经允许执行，不能等同于退款已经完成；只有真正的退款执行完成后，`RefundRequest` 才能进入 `completed`。

### 5. 确定性退款申请服务

服务文件：

`E:\Living RAG\apps\living-rag-api\app\services\refund_request_service.py`

资格判断由 Python 规则服务完成，LLM 不直接裁定结果。当前判断顺序包括：

1. 订单是否存在，以及订单是否属于当前用户；
2. 会员信息是否存在；
3. 退款历史查询是否完整；
4. 是否已经存在已完成退款；
5. 会员账号是否为 `active`；
6. 订单是否已经签收；
7. 签收时间是否在当前退款期限内；
8. 是否为活动订单或指定免费退货商品；
9. 会员等级是否满足免费退货条件；
10. 是否存在影响结论的未决政策冲突。

账号状态优先于会员等级。金卡账号如果是 `suspended`，不能享受金卡权益，并且应转人工复核。

### 6. 业务动作返回完整事实

业务动作服务：

`E:\Living RAG\apps\living-rag-api\app\services\business_action_service.py`

业务动作 Schema：

`E:\Living RAG\apps\living-rag-api\app\schemas\business_action.py`

只读资格查询现在返回：

- 订单状态；
- 是否签收以及 `received_at`；
- 商品名称；
- `returnable`；
- 活动标签；
- 指定免费退货标记；
- 物流状态和偏远地区延迟信息；
- 会员等级与账号状态；
- 退款历史；
- `eligible`、`decision`、原因和运费承担方。

这解决了“订单工具只知道订单事实，不能单独裁定政策”的边界问题：订单工具提供事实，会员工具提供会员事实，资格服务结合政策和历史做确定性判断。

### 7. 审计与 Trace 关联

审计 Schema：

`E:\Living RAG\apps\living-rag-api\app\schemas\audit_log.py`

审计路由：

`E:\Living RAG\apps\living-rag-api\app\api\routes\audit_logs.py`

业务动作持久化服务：

`E:\Living RAG\apps\living-rag-api\app\services\business_action_persistence.py`

每次业务动作会尽量共享同一个 `trace_id`，并关联：

```text
用户问题
  -> ChatThread / ChatMessage
  -> AgentRun
  -> ApprovalTask（如果是高风险动作）
  -> AuditLog（创建、批准、拒绝等关键事件）
```

这样可以从审批任务反查是谁发起的、用户说了什么、Agent 做了什么判断，以及最终审批结果是什么。

## 二、第二周验收场景

### O2025001

普通会员，签收 12 天，普通商品：

- 订单已完成并且已签收；
- 在当前 15 天退款窗口内；
- 可以申请退款；
- 普通商品没有金卡指定免费退货权益，通常由用户承担退货运费；
- 如果用户要求“直接退款”，只创建 `direct_refund` 审批任务。

### O2025002

金卡会员，签收 14 天，指定免费退货商品：

- 可以申请退款；
- 满足指定商品免费退货条件；
- 平台承担退货运费；
- 仍然不能绕过人工审批直接完成退款。

### O2025003

签收 18 天：

- 超过当前 15 天退款窗口；
- 返回 `ineligible`；
- 不创建退款申请，也不创建审批任务。

### O2025006

已有已完成退款：

- 返回 `already_refunded`；
- 拒绝重复申请；
- 不产生新的退款申请。

### 冲突政策场景

FAQ 声称“所有会员可以 30 天退款”，正式政策 v3 是 15 天。问答链路应继续以正式政策为主要依据，同时提示 FAQ 与正式政策存在冲突；冲突影响运费或结论时，不能让模型自行选择未经审核的规则。

## 三、问题定位与修复记录

1. 测试夹具中部分风险关键词曾因复制产生乱码，导致风险门控无法识别“直接退款”“修改政策”等意图。修复后使用稳定的英文测试表达或正确关键词，并验证高风险动作优先匹配。
2. 业务测试最初使用 `O-BUSINESS-001` 一类订单号，而真实订单格式是 `O2025001`。测试数据已统一为真实订单格式。
3. 只读资格查询依赖 `as_of` 计算退款期限。旧测试使用 2026 年 1 月签收数据，却在 2026 年 8 月运行，导致正确返回超期。已将对应测试夹具的签收时间调整到运行窗口内，并断言新的 `eligible` 资格状态。
4. Python 模型属性使用 `metadata_`，数据库列名仍是 `metadata`。查询和写入时必须区分 ORM 属性名与数据库列名。
5. `ApprovalTask` 不强行关联政策冲突，因为退款审批可能没有 `conflict_id`；审批任务通过 `resource_type`、`resource_id`、`trace_id` 和审计日志关联业务来源。

## 四、测试与验证结果

定向业务回归：

```powershell
Set-Location "E:\Living RAG"
docker compose exec -T api pytest tests/test_business_actions_api.py tests/test_business_action_trace.py tests/test_business_action_read_only.py -q
```

结果：12 passed。

全量测试：

```powershell
docker compose exec -T api pytest -q
```

最终结果以本日志提交前的实际命令输出为准。测试中的两个 warning 是依赖升级提示，不是业务测试失败：一个来自 Starlette TestClient 与 httpx 的兼容性提醒，另一个来自 LangGraph 缓存序列化配置的未来默认值提醒。

## 五、Day 14 文件清单

新增或修改的核心文件包括：

- `E:\Living RAG\apps\living-rag-api\app\models\approval_task.py`：审批任务 ORM 模型与状态枚举；
- `E:\Living RAG\apps\living-rag-api\alembic\versions\21f0e8383e69_add_approval_tasks.py`：创建审批任务表；
- `E:\Living RAG\apps\living-rag-api\app\services\approval_task_service.py`：审批任务创建、查询和决策；
- `E:\Living RAG\apps\living-rag-api\app\services\risk_gate.py`：风险动作分类；
- `E:\Living RAG\apps\living-rag-api\app\services\refund_request_service.py`：退款申请与资格结果落库；
- `E:\Living RAG\apps\living-rag-api\app\services\business_action_service.py`：统一编排只读、退款申请和审批动作；
- `E:\Living RAG\apps\living-rag-api\app\services\business_action_persistence.py`：保存对话、Trace 和运行记录；
- `E:\Living RAG\apps\living-rag-api\app\api\routes\approval_tasks.py`：审批 API；
- `E:\Living RAG\apps\living-rag-api\app\api\routes\business_actions.py`：业务动作 API；
- `E:\Living RAG\apps\living-rag-api\app\api\routes\audit_logs.py`：审计日志查询 API；
- `E:\Living RAG\apps\living-rag-api\app\schemas\approval_task.py`、`audit_log.py`、`business_action.py`：请求和响应协议；
- `E:\Living RAG\apps\living-rag-api\app\main.py`、`app\models\__init__.py`：注册路由和 ORM 模型；
- `E:\Living RAG\apps\living-rag-api\tests\test_approval_task_service.py`、`test_approval_tasks_api.py`、`test_audit_logs_api.py`、`test_business_action_trace.py`、`test_business_actions_api.py`、`test_refund_request_service.py`、`test_risk_gate.py`、`test_business_action_read_only.py`：覆盖服务、API、状态流转、Trace、审计和关键订单场景。

## 六、Day 14 验收结论

Day 14 的退款审批、风险门控、审计日志、Trace 关联和第二周核心演示链路已经完成。系统不会让 LLM 直接裁定退款资格，也不会让高风险请求直接执行副作用操作。第二周里程碑达到可演示状态，Day 14 完成度：100%。

## 七、复习清单

- 能解释 `read_only`、`create_refund_request`、`create_approval_task` 和 `reject_direct_execution` 的差异；
- 能解释 `RefundRequest.pending` 与 `ApprovalTask.pending` 为什么不是同一个状态；
- 能解释为什么资格判断必须由 Python 规则服务完成；
- 能解释为什么 suspended 账号不能享受金卡权益；
- 能从 `trace_id` 找到用户对话、Agent Run、审批任务和审计日志；
- 能说明审批批准不等于退款已经完成；
- 能使用 O2025001、O2025002、O2025003、O2025006 讲清楚四个验收场景。

## 八、下一步：Day 15

Day 15 将统一完善 Trace、运行日志和运行详情查询，包括节点路径、工具调用、模型调用、延迟、Token、成本和失败原因。Day 14 的业务审批与审计链路是 Day 15 可观测性的基础。

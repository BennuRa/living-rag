# Day 11：人工审核任务与审核页面

日期：2026-08-04

## 今日目标

- 建立 `review_tasks` 审核任务表；
- 根据开放冲突自动创建人工审核任务；
- 提供待审核任务查询 API；
- 支持接受规则、驳回冲突和将文档标记为无效；
- 保存审核理由和审核完成时间；
- 让无效文档不再参与当前检索和问答引用；
- 完成最小审核前端页面。

## 今日完成内容

### 1. 审核任务模型和迁移

文件：

```text
apps/living-rag-api/app/models/review_task.py
apps/living-rag-api/alembic/versions/a17c5e8b42d1_add_review_tasks.py
```

审核任务状态：

```text
pending
in_progress
completed
cancelled
```

审核决定：

```text
approve
reject
invalidate_document
```

主要字段：

- `conflict_id`：关联政策冲突；
- `task_type`：审核任务类型；
- `status`：任务状态；
- `decision`：人工审核决定；
- `decision_reason`：审核理由；
- `created_at`：创建时间；
- `updated_at`：更新时间；
- `resolved_at`：完成时间。

Alembic head：

```text
a17c5e8b42d1
```

### 2. 自动创建审核任务

文件：

```text
apps/living-rag-api/app/services/review_task_service.py
apps/living-rag-api/app/services/policy_conflict_service.py
```

需要人工审核的冲突类型：

```text
conflict
conditional_exception
high_risk_error
```

不需要人工审核的类型：

```text
historical_difference
update
```

冲突持久化完成后会自动调用审核任务服务：

```text
persist conflict
    ↓
persist conflict evidences
    ↓
create review tasks for open conflicts
```

任务创建具有幂等性。同一个冲突已经存在未取消任务时，不会重复创建任务。

### 3. 审核查询 API

文件：

```text
apps/living-rag-api/app/api/routes/review_tasks.py
apps/living-rag-api/app/schemas/review_task.py
```

接口：

```text
GET /review-tasks
GET /review-tasks?status=pending
```

响应包含：

- 审核任务状态；
- 冲突类型和严重度；
- 规则键；
- 左右文档版本；
- 左右结构化规则；
- 冲突原因；
- 推荐处理方式；
- 原始证据。

左右规则响应字段：

```text
rule_key
value
conditions
source_quote
effective_at
expires_at
confidence
```

### 4. 审核决定 API

接口：

```text
POST /review-tasks/{task_id}/decision
```

请求：

```json
{
  "decision": "invalidate_document",
  "decision_reason": "The document contains an unsafe refund rule."
}
```

业务行为：

| 决定 | 任务状态 | 冲突状态 | 文档状态 |
|---|---|---|---|
| `approve` | `completed` | `resolved` | 不修改 |
| `reject` | `completed` | `dismissed` | 不修改 |
| `invalidate_document` | `completed` | `resolved` | `invalid` |

审核服务会拒绝：

- 不存在的任务；
- 空审核理由；
- 已完成任务重复审核；
- 已取消任务审核；
- 缺少关联冲突的任务；
- 缺少右侧文档版本的无效化操作。

### 5. 无效文档治理效果

审核人员执行：

```text
invalidate_document
```

之后：

```text
document_versions.governance_status = invalid
```

当前检索服务只会将有效的 `active` 文档作为默认当前政策返回，因此无效文档不会进入检索结果和问答引用。

真实验收结果：

```text
检索结果全部为 active 或其他允许状态
检索结果不包含 invalid 文档
高风险问答没有引用 invalid 文档
```

当证据不足时，问答会保守降级：

```text
citation_valid = false
confidence = 0.0
```

### 6. 审核前端页面

文件：

```text
apps/living-rag-web/app/review-tasks/page.tsx
apps/living-rag-web/app/globals.css
```

页面地址：

```text
http://localhost:3000/review-tasks
```

页面功能：

- 待审核任务列表；
- 冲突类型和严重度；
- 冲突原因和推荐处理方式；
- 左右规则 `value` 对比；
- 左右规则 `conditions` 对比；
- 左右规则原始证据；
- 文档版本 ID；
- 审核理由输入框；
- 接受规则按钮；
- 驳回冲突按钮；
- 标记文档无效按钮。

前端生产构建验证：

```text
Route /review-tasks generated successfully
```

## 测试结果

服务层相关测试：

```text
16 passed
```

自动创建审核任务测试：

```text
2 passed
```

全量测试：

```text
172 passed, 2 warnings
```

warning 来自第三方依赖，不影响测试通过：

- Starlette TestClient 的 httpx 弃用提示；
- LangGraph cache 的 pending deprecation 提示。

前端构建：

```text
npm run build
```

结果：

```text
Compiled successfully
Linting and checking validity of types
Generating static pages
/review-tasks
```

Docker 前端服务：

```text
living-rag-web-1 Up
```

## Day 11 验收结论

Day 11 已完成人工审核闭环：

```text
policy conflict
    ↓
review task
    ↓
human decision
    ↓
conflict status / document governance status
    ↓
retrieval and QA safety behavior
```

Day 11 完成度：

```text
100%
```

## 下一步

Day 12 将冲突治理接入 LangGraph 问答主图：

```text
retrieve
    ↓
grade_documents
    ↓
check_conflicts
    ├── key conclusion affected → safe_conflict_response
    └── no key conflict → generate_answer
```

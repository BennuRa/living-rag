Exit code: 0
Wall time: 0.4 seconds
Output:
Exit code: 0
Wall time: 0.4 seconds
Output:
Exit code: 0
Wall time: 0.5 seconds
Output:
# Day 12：将冲突治理接入 LangGraph 问答主链路

日期：2026-08-05

## 今日目标

Day 12 的目标是把 Day 10 的规则冲突和 Day 11 的人工审核结果接入问答主流程。

目标主链路：

```text
retrieve_documents
    ↓
grade_documents
    ↓
check_conflicts
    ├── 核心结论受到未决冲突影响
    │       ↓
    │   safe_conflict_response
    │
    └── 没有关键未决冲突
            ↓
        build_context
            ↓
        generate_answer

两条分支最后都经过：
validate_citations
```

本日业务要求：

- FAQ 与正式政策对同一个规则给出不同结论时，不能盲从 FAQ；
- 未决冲突影响核心结论时，不能让模型擅自裁定；
- 已解决或已驳回的冲突不能继续阻断正常问答；
- 历史版本差异和正常版本更新不能被误判为当前冲突；
- 安全回答也必须经过引用校验；
- API 和 Trace 能够记录冲突状态。

## 今日完成内容

### 1. 扩展 QA 共享 State

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\services\\qa_state.py
```

新增字段：

```python
conflict_summaries: list[str]
conflict_blocking: bool
conflict_notice: str
```

三个字段的职责不同：

| 字段 | 作用 |
|---|---|
| `conflict_summaries` | 保存当前问答相关冲突的摘要 |
| `conflict_blocking` | 控制 LangGraph 是否进入安全回答分支 |
| `conflict_notice` | 传递给回答、API 和前端的冲突提示 |

`conflict_blocking` 不是“数据库里存在任何冲突”，而是：

```text
当前有效证据涉及一个仍未解决、
并且会影响本次问答核心结论的冲突。
```

### 2. 新增冲突检查节点

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\services\\qa_nodes.py
```

新增：

```python
check_conflicts_node
```

节点读取经过筛选的：

```python
graded_results
```

而不是直接使用全部：

```python
retrieval_results
```

原因：

- `retrieval_results` 是检索候选；
- `graded_results` 才是当前回答准备使用的有效证据；
- 过期、无效、低相关内容不应触发当前问答的冲突判断。

节点从结果中提取：

```python
document_version_id
```

然后查询：

```text
left_document_version_id 在当前版本集合中
或者
right_document_version_id 在当前版本集合中
并且 status = OPEN
```

### 3. 明确冲突类型的处理规则

| 冲突类型 | 是否阻断 | 原因 |
|---|---:|---|
| `conflict` | 是 | 两个有效来源对同一规则给出不同结论 |
| `high_risk_error` | 是 | 可能造成严重业务或安全错误 |
| `historical_difference` | 否 | 历史版本之间的有效期差异 |
| `update` | 否 | 正常的政策版本更新 |
| `conditional_exception` | 否 | 需要结合订单或活动条件判断 |

`resolved` 和 `dismissed` 冲突不会阻断，因为它们已经经过人工处理。

### 4. 新增安全回答节点

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\services\\qa_nodes.py
```

新增：

```python
safe_conflict_response_node
```

安全回答会：

- 不调用普通 LLM 生成节点；
- 不擅自选择正式政策或 FAQ 的单一结论；
- 说明存在未决冲突；
- 提醒需要人工审核；
- 返回 `confidence = 0.0`；
- 返回 `limitations`；
- 为当前有效证据生成引用编号；
- 继续经过 `validate_citations_node`。

真实 API 验收时发现，安全回答最初设置了 `citation_indices`，但文本中没有 `[1]`、`[2]` 等标记，导致：

```text
citation_valid = false
```

随后补充了引用标记。现在安全回答会附加：

```text
[1] [2] [3]
```

并能够通过引用校验。

### 5. 修改 LangGraph 条件路由

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\services\\qa_graph.py
```

新增节点：

```text
check_conflicts
safe_conflict_response
```

图现在按 `conflict_blocking` 分支：

```text
grade_documents
    ↓
check_conflicts
    ├── True  → safe_conflict_response → validate_citations
    └── False → build_context → generate_answer → validate_citations
```

安全分支不经过 `generate_answer`，从图结构上防止模型在未决冲突下擅自裁定。

### 6. 修复 FAQ 被检索结果挤掉的问题

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\services\\retrieval.py
```

第一次真实 API 验收时，FAQ 数据本身是完整的：

```text
source_type = faq
governance_status = active
status = ready
chunk_count = 7
chunks_with_embedding = 7
```

但检索结果全部是 `official_policy`。

原因是原来的排序会先放入大量正式政策 Chunk，FAQ 在达到 `limit` 之前就被挤掉，导致：

```text
正式政策进入 graded_results
FAQ 不进入 graded_results
冲突节点看不到 FAQ
```

修复后：

- 退款领域查询仍然保持正式政策优先；
- 额外查询最相关的 FAQ Chunk；
- FAQ 不在最终结果时补入一个 FAQ；
- 不需要无限增大检索数量；
- 冲突治理可以同时看到正式政策和 FAQ。

真实检索已经验证可以同时返回：

```text
official_policy v3
faq v1
```

### 7. API 返回结构化冲突信息

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\schemas\\qa.py
E:\Living RAG\\apps\\living-rag-api\\app\\api\\routes\\qa.py
```

`QuestionAnswerResponse` 新增：

```python
conflict_summaries: list[str]
conflict_blocking: bool
conflict_notice: str
```

现在 `POST /api/qa/answer` 和 `POST /api/chat` 可以返回：

```json
{
  "conflict_blocking": true,
  "conflict_notice": "存在尚未完成人工审核的政策冲突。",
  "conflict_summaries": [
    "conflict (high) for refund.window_days: ..."
  ],
  "confidence": 0.0,
  "citation_valid": true,
  "trace_id": "..."
}
```

### 8. 将冲突状态保存到 Trace

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\app\\services\\qa_persistence.py
```

冲突状态现在会保存到：

- Assistant message metadata；
- Agent run metadata。

保存字段：

```text
conflict_summaries
conflict_blocking
conflict_notice
```

后续可以通过 `trace_id` 回放：

- 是否发现冲突；
- 为什么进入安全分支；
- 冲突摘要是什么；
- 最终回答是否通过引用校验。

## 新增和修改的测试

### 冲突工作流测试

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\tests\\test_qa_conflict_workflow.py
```

覆盖：

- OPEN `conflict` 阻断；
- OPEN `high_risk_error` 阻断；
- `resolved` 不阻断；
- `dismissed` 不阻断；
- `historical_difference` 不阻断；
- `update` 不阻断；
- `conditional_exception` 不直接阻断；
- 空 `graded_results` 不误报冲突；
- 安全回答包含人工审核提示；
- 没有证据时不生成虚假引用；
- 真实 FastAPI `/api/qa/answer` 集成测试；
- 结构化冲突响应；
- 安全回答的引用校验。

### 检索回归测试

文件：

```text
E:\Living RAG\\apps\\living-rag-api\\tests\\test_retrieval.py
```

新增测试验证退款查询在结果数量有限时，仍然能同时保留：

```text
正式政策
FAQ
```

避免未来调整排序逻辑时再次丢失冲突证据。

## 真实问题定位过程

第一次真实 API 请求返回：

```text
confidence = 0.85
limitations = []
citations = official_policy v3
```

说明系统走了正常回答分支，没有进入安全分支。

随后逐项检查：

```text
FAQ 文档存在：是
FAQ governance_status：active
FAQ status：ready
FAQ Chunk 数量：7
FAQ embedding 数量：7
正式政策与 FAQ 冲突关系：存在
冲突状态：resolved
```

最终发现：

1. 已有真实 `conflict` 状态是 `resolved`，按设计不应阻断；
2. 检索排序会让正式政策 Chunk 挤掉 FAQ，导致 FAQ 不进入 `graded_results`；
3. 长期运行的 API 容器没有自动加载最新代码，需要重启 API 服务；
4. 安全回答最初缺少文本引用标记，导致引用校验失败。

这些问题分别完成了修复和验证。

真实 API 使用临时 `OPEN` 冲突验收，结果为：

```text
conflict_blocking = true
confidence = 0.0
citation_valid = true
conflict_notice 非空
conflict_summaries 非空
trace_id 存在
```

验收后，数据库中的原始冲突状态恢复为：

```text
resolved
```

没有留下临时业务状态变化。

## 测试命令与结果

### 定向测试

执行：

```powershell
Set-Location "E:\Living RAG"
docker compose exec -T api pytest tests/test_qa_conflict_workflow.py tests/test_retrieval.py -q
```

结果：

```text
13 passed, 2 warnings
```

### 原有 QA 回归测试

执行：

```powershell
docker compose exec -T api pytest tests/test_qa_workflow.py -q
```

结果：

```text
10 passed
```

### 全量后端测试

执行：

```powershell
docker compose exec -T api pytest -q
```

结果：

```text
184 passed, 2 warnings
```

### Python 编译检查

执行：

```powershell
docker compose exec -T api python -m compileall app/services/retrieval.py app/services/qa_nodes.py app/services/qa_graph.py app/schemas/qa.py app/api/routes/qa.py app/services/qa_persistence.py
```

结果：通过。

### Git 检查

执行：

```powershell
git diff --check
git status --short
```

结果：Day 12 修改已提交，工作树干净。

## 第三方警告

全量测试中的两个 warning 来自第三方依赖，不影响测试结果：

```text
Starlette TestClient 使用 httpx 的弃用提醒
LangGraph cache 默认 allowed_objects 未来会变化的提醒
```

它们记录为后续依赖升级事项，当前不阻塞项目主线。

## Day 12 验收结论

Day 12 已完成：

```text
有效证据
    ↓
冲突检查
    ↓
安全分支或正常分支
    ↓
引用校验
    ↓
API 返回
    ↓
Trace 持久化
```

Day 12 完成度：

```text
100%
```

Git 提交：

```text
315c634 Complete Day 12 conflict-aware QA workflow
```

## 复习清单

- [x] 能解释为什么冲突信息必须进入 LangGraph State。
- [x] 能区分 `retrieval_results` 和 `graded_results`。
- [x] 能解释为什么冲突查询使用 `document_version_id`。
- [x] 能解释为什么只查询 `OPEN` 冲突。
- [x] 能区分历史差异、版本更新、条件例外和真正冲突。
- [x] 能解释 `add_conditional_edges` 的路由机制。
- [x] 能解释为什么安全回答不能绕过引用校验。
- [x] 能根据 Trace 判断本次问答是否进入安全分支。
- [x] 能定位 FAQ 没有进入检索结果的原因。
- [x] 能说明规则测试和真实 API 验收的区别。

## 下一步：Day 13

Day 13 开始接入订单、会员和退款历史工具：

```text
get_order
get_user
get_membership
get_refund_history
```

退款资格判断必须由确定性 Python 规则服务完成，不能让 LLM 直接裁定：

```text
是否已签收
是否在退款期限内
是否属于活动订单
是否满足金卡免费退货条件
是否已经退款
账号是否被冻结
是否存在影响结论的未决冲突
```

Day 13 的起点是当前已经完成版本治理、冲突检测、人工审核和安全问答分支的 Living RAG。

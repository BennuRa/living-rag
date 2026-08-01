# Day 8：文档版本治理与历史有效性检索

日期：2026-08-01

## 今日目标

按照 30 天学习计划，完成 Living RAG 的文档版本识别与有效性治理：

1. 根据内容哈希和版本号识别新增、重复、更新和疑似冲突；
2. 非连续版本号的导入请求进入疑似冲突分支；
3. 新版本导入时将旧版本标记为 `superseded`；
4. 建立 `supersedes` 版本关系；
5. 当前检索默认只使用最新有效版本；
6. 支持通过 `as_of_date` 查询指定日期有效的历史规则。

## 今日完成内容

### 1. 版本变化分类

在 `apps/living-rag-api/app/services/document_ingestion.py` 中新增 `VersionChangeType`：

```python
class VersionChangeType(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    UPDATE = "update"
    POSSIBLE_CONFLICT = "possible_conflict"
```

分类顺序：

```text
相同 content_hash
→ DUPLICATE

没有历史版本
→ NEW

请求版本号等于最新版本号 + 1
→ UPDATE

其他非连续版本
→ POSSIBLE_CONFLICT
```

### 2. 疑似冲突接入导入主流程

`ingest_content()` 现在会先调用 `classify_version_change()`。

当结果为 `POSSIBLE_CONFLICT` 时，系统拒绝导入并返回：

```text
Requested version change is a possible conflict.
```

这样可以避免非连续版本直接绕过版本治理进入知识库。

### 3. superseded 状态和版本链

创建新版本时：

- 最新旧版本标记为 `SUPERSEDED`；
- 新版本标记为 `ACTIVE`；
- 新版本的 `supersedes_version_id` 指向旧版本。

退款政策形成：

```text
v1 → v2 → v3
```

当前状态为：

```text
v1.superseded
v2.superseded
v3.active
```

### 4. 当前和历史检索

在 `apps/living-rag-api/app/services/retrieval.py` 中增加可选参数：

```python
as_of_date: datetime | None = None
```

检索规则：

当前查询：

```text
as_of_date 为空
→ 只允许 ACTIVE
→ 使用当前时间判断 effective_at / expires_at
```

历史查询：

```text
as_of_date 不为空
→ 允许 ACTIVE 和 SUPERSEDED
→ 使用 as_of_date 判断有效期
→ 同一 Document 只选择指定日期下版本号最高的有效版本
```

在 `apps/living-rag-api/app/schemas/retrieval.py` 中增加：

```python
as_of_date: datetime | None = None
```

在 `apps/living-rag-api/app/api/routes/retrieval.py` 中将请求日期传给检索服务：

```python
as_of_date=request.as_of_date
```

## 自动化测试结果

### 文档导入测试

```text
28 passed
```

覆盖：

- 新版本分类；
- 重复内容分类；
- 连续版本更新；
- 非连续版本疑似冲突；
- superseded 状态；
- supersedes 关系；
- 文档 Chunk 创建。

### 完整测试集

```text
113 passed, 2 warnings in 2.03s
```

warning 来自第三方依赖：

- Starlette TestClient 与 httpx 的弃用提示；
- LangGraph `allowed_objects` 默认值未来变化提示。

两个 warning 不影响 Day 8 功能正确性。

### 历史检索数据库测试

测试文件：

`apps/living-rag-api/tests/test_retrieval.py`

结果：

```text
1 passed in 0.98s
```

测试使用真实 PostgreSQL 和 768 维 pgvector，验证：

```text
当前查询 → v3
2025-02-01 → v1
2025-05-01 → v2
2025-08-01 → v3
```

### API 手工验收

接口：

```text
POST /api/retrieval/search
```

开发数据库中的真实版本时间线：

| 版本 | 生效时间 | 失效时间 | 当前状态 |
| --- | --- | --- | --- |
| v1 | 2025-01-01 | 2025-03-31 | superseded |
| v2 | 2025-04-01 | 2025-06-30 | superseded |
| v3 | 2025-07-01 | 无 | active |

API 验收结果：

```text
当前查询：
3, 3, 3, 3, 3

2025-02-01 历史查询：
1, 1, 1, 1, 1

2025-05-01 历史查询：
2, 2, 2, 2, 2

2025-08-01 历史查询：
3, 3, 3, 3, 3
```

这证明同一次查询返回的 Chunk 没有混入不同政策版本。

## 关键设计决策

### 当前查询和历史查询分开处理

不能简单地把所有 `SUPERSEDED` 版本重新放入当前检索，否则当前问答可能同时使用 v1、v2 和 v3。

因此：

```text
当前查询只看 ACTIVE
历史查询允许 ACTIVE + SUPERSEDED
```

历史查询还需要结合有效时间和版本号，选择指定日期下真正生效的最高版本。

### 版本号和有效期同时使用

只看版本号会把未来版本错误地用于过去的问题；只看有效期又可能在旧版本没有设置 `expires_at` 时同时返回多个版本。

因此使用以下条件共同确定历史版本：

```text
effective_at
+ expires_at
+ 同一 Document 下最高 version_number
```

### 疑似冲突暂不自动解决

Day 8 只负责识别 `POSSIBLE_CONFLICT`，不会自动决定哪份非连续版本是正确的，也不会提前进入 Day 10 的冲突证据或人工审核。

## 当前限制

1. `as_of_date` 已接入 `/api/retrieval/search`，但当前 `/api/chat` 仍然使用默认当前时间查询；
2. `/api/chat` 的历史问答参数可以在后续需要时接入；
3. 还没有实现 Day 9 的结构化规则抽取；
4. 还没有实现 Day 10 的规则差异和冲突检测；
5. 当前依赖中的两个弃用 warning 尚未处理。

## Day 8 结论

Day 8 的核心计划已经完成：

```text
版本识别：完成
重复检测：完成
疑似冲突识别：完成
superseded 状态：完成
supersedes 关系：完成
当前版本检索：完成
历史日期检索：完成
自动化测试：完成
API 手工验收：完成
```

下一步进入 Day 9：

```text
结构化规则抽取
```

Day 9 将从退款政策 v3 中抽取：

- `refund.window_days`；
- `refund.return_shipping_payer`；
- `refund.member_free_return_tier`；
- 其他最小规则字段。

Day 8 不提前进入 Day 9 的冲突检测或人工审核。

# Day 5：Embedding、pgvector 与检索 API

## 一、今日目标

1. 完成 Embedding Provider 抽象接口。
2. 支持 Mock Embedding 和 Ollama `nomic-embed-text`。
3. 保留 OpenAI-compatible Embedding 适配接口。
4. 将向量写入 `document_chunks.embedding`。
5. 使用 pgvector 实现相似度检索。
6. 实现 `POST /api/retrieval/search`，并过滤无效、过期、被替代和待审核版本。

## 二、完成内容

### 1. Embedding Provider

完成 `EmbeddingProvider` 抽象接口，并实现：

- `MockEmbeddingProvider`
- `OllamaEmbeddingProvider`
- `OpenAICompatibleEmbeddingProvider`

Provider 统一接收一组文本，返回一一对应的向量列表。当前向量维度为 `768`。

### 2. pgvector 与数据库

在 `document_chunks` 中增加：

```python
embedding: Mapped[list[float] | None] = mapped_column(
    Vector(768),
    nullable=True,
```

)
Alembic revision：`b6253fb946c2`。

为解决测试数据库缺少 `vector` 类型的问题，在 migration 中先执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

然后添加 `VECTOR(768)` 列。

### 3. Embedding 写入

完成 `embed_pending_chunks()`：

- 查询 `embedding IS NULL` 的 Chunk；
- 按批次生成向量；
- 校验输入与输出数量一致；
- 写回 Chunk；
- 使用 `flush()`，由调用方负责 `commit()`。

真实验证：

```text
total_chunks: 56
embedded_chunks: 56
pending_chunks: 0
min_dimension: 768
max_dimension: 768
```

### 4. Ollama

真实使用本地 Ollama `nomic-embed-text`：

```text
ollama version: 0.32.1
embedding count: 1
embedding dimension: 768
provider: OllamaEmbeddingProvider
re-embedded chunks: 56
```

### 5. Provider Factory

`embedding_factory.py` 已支持：

```text
mock -> MockEmbeddingProvider
ollama -> OllamaEmbeddingProvider
openai_compatible -> OpenAICompatibleEmbeddingProvider
```

Factory 只负责根据配置创建 Provider，不负责发送请求或写数据库。

### 6. 检索 API

实现：

```text
POST /api/retrieval/search
```

返回文档标题、版本号、来源类型、治理状态、生效时间、过期时间、Chunk 文本、相似度和 Chunk ID。

检索过滤条件：

- `embedding IS NOT NULL`；
- 版本状态为 `READY`；
- 治理状态为 `ACTIVE`；
- `effective_at` 为空或已经生效；
- `expires_at` 为空或尚未过期。

## 三、验证命令与结果

### 构建 API 镜像

```powershell
docker compose build api
```

结果：

```text
Image living-rag-api Built
```

### Factory 三分支验证

结果：

```text
mock -> MockEmbeddingProvider
ollama -> OllamaEmbeddingProvider
openai_compatible -> OpenAICompatibleEmbeddingProvider
```

### 全量测试

```powershell
docker compose run --rm api pytest -q
```

结果：

```text
95 passed, 1 warning in 3.50s
```

warning 是 Starlette 与 httpx 的弃用提示，不影响测试通过。

### API 端到端检索

查询：`退款时限是多少`

第一名结果：

```text
document: 退款与退货政策
version: 3
source_type: official_policy
governance_status: active
similarity: 0.7067421706202623
```

验收结论：当前退款政策 v3 命中；退款政策 v1 没有作为结果返回。FAQ v1 出现是正常的，因为它是另一份文档。

## 四、问题与解决方案

### 1. PowerShell 中文显示乱码

使用 Windows PowerShell 调用 API 时，中文可能显示为乱码。这是终端编码显示问题，不是数据库内容错误。API 字段、版本号、状态和相似度均已正确验证。

### 2. 测试数据库缺少 vector 类型

最初测试失败：

```text
psycopg.errors.UndefinedObject: type "vector" does not exist
```

原因是测试数据库重建 schema 时没有安装 pgvector 扩展。修复 Alembic migration 后，全量测试通过。

## 五、复习问题

1. 为什么需要 `EmbeddingProvider` 抽象接口？
2. 为什么 Mock Embedding 必须确定性？
3. 为什么 `embedding` 允许为空？
4. 为什么 Service 使用 `flush()` 而不是直接 `commit()`？
5. cosine distance 越小代表什么？
6. 为什么检索要过滤生效时间和过期时间？
7. 为什么 migration 必须先创建 `vector` 扩展？
8. 为什么更换 Embedding 模型时必须检查向量维度？
9. Factory 和 Provider 各自负责什么？
10. 为什么 FAQ v1 不等于退款政策 v1？

## 六、面试表达

我实现了可插拔的 Embedding Provider 抽象，通过 Factory 支持 Mock、Ollama 和 OpenAI-compatible 服务。文档 Chunk 使用 pgvector 保存 768 维向量，并通过 cosine distance 实现相似度检索。检索层结合文档版本状态、治理状态、生效时间和过期时间过滤无效知识，确保用户查询退款时限时命中当前有效的退款政策 v3，而不是已被替代的旧版本。整个链路通过独立测试数据库、Alembic migration 和 API 端到端验证。

## 七、今日进度

```text
Day 5 完成：100%
Day 5 剩余：0%
全量测试：95 passed, 1 warning
API 检索：通过
Ollama：通过
pgvector：通过
版本过滤：通过
OpenAI-compatible Factory：通过
Git 提交：尚未提交
```

## 八、下一天起点

Day 6 继续 Living RAG 基础 MVP：使用检索结果构造上下文，设计 LangGraph 最小问答 State，实现基于引用的回答，并增加引用完整性校验。优先使用 Mock LLM，避免真实模型服务阻塞主线。

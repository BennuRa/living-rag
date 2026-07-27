# Day 6：LangGraph 最小问答链与引用校验

## 一、今日目标

1. 定义 LangGraph 问答 State。
2. 将 Day 5 检索结果转换成 LLM 上下文。
3. 定义 LLM Provider 抽象和 Mock LLM。
4. 实现答案引用校验和 Citation 构造。
5. 使用 LangGraph 编排上下文、回答和引用校验节点。
6. 实现 `POST /api/qa/answer`。

## 二、完成内容

### 1. QAState

定义问答工作流共享状态：

- `question`
- `retrieval_results`
- `context`
- `answer`
- `citations`
- `citation_valid`
- `error`

使用 `TypedDict(total=False)`，允许 State 在节点之间逐步补充字段。

### 2. 检索上下文

完成 `build_retrieval_context()`，把 `RetrievalResult` 列表转换成引用友好的文本上下文，并保留：

- 文档标题；
- 文档版本；
- 来源类型；
- 治理状态；
- Chunk ID；
- 相似度；
- Chunk 正文。

当前使用英文标签，避免 Windows PowerShell 中文编码损坏。

### 3. LLM Provider

定义 `LLMProvider` 抽象接口：

```python
generate_answer(question, context) -> str
```

实现确定性的 `MockLLMProvider`：

- 空问题直接拒绝；
- 没有上下文时返回安全降级答案；
- 有上下文时返回带 `[1]` 引用的确定性答案。

### 4. Citation 校验

完成：

- `validate_answer_citations()`；
- `build_citations_from_answer()`。

校验规则：

- 空答案无效；
- 没有引用标记无效；
- 引用编号必须在检索结果范围内；
- 重复引用去重；
- 合法编号映射为真实文档、版本和 Chunk ID。

### 5. LangGraph

完成三个节点：

```text
build_context_node
    ↓
generate_answer_node
    ↓
validate_citations_node
```

完成 `build_qa_graph()`，连接：

```text
START → build_context → generate_answer → validate_citations → END
```

通过依赖注入传入 `LLMProvider`，当前图使用 `MockLLMProvider`。

### 6. 问答 API

完成：

```text
POST /api/qa/answer
```

请求 Schema：

```json
{
  "question": "退款时限是多少",
  "limit": 2
}
```

响应包含：

- `answer`；
- `citation_valid`；
- `citations`。

路由已在 `main.py` 注册。

## 三、验证结果

### 1. 无检索结果的 LangGraph 验证

结果：

```text
graph execution: ok
context empty: True
answer: I do not have enough grounded evidence to answer this question.
citation_valid: False
citations: []
```

说明没有证据时不会编造答案。

### 2. 有真实检索结果的 LangGraph 验证

结果：

```text
retrieval result count: 2
graph execution: ok
citation_valid: True
citation count: 1
```

真实 Chunk ID：

```text
ad3be9e9-2f73-4f5b-9a26-9d5fd0500acf
```

真实相似度：

```text
0.7067421706202623
```

### 3. HTTP API 验证

调用：

```text
POST /api/qa/answer
```

结果：

```text
answer：已返回
citation_valid：true
citations：1 条
chunk_id：真实 UUID
relevance_score：0.7067421706202623
```

### 4. 全量测试

```powershell
docker compose run --rm api pytest -q
```

结果：

```text
95 passed, 2 warnings in 1.91s
```

Warning：

- Starlette/httpx 弃用提示；
- LangGraph `allowed_objects` 默认值未来变化提示。

两个 warning 都没有导致测试失败。

## 四、问题与解决方案

### 1. Windows 中文编码问题

PowerShell 和文件保存过程中出现过中文乱码。为保证代码稳定，`qa_context.py` 的上下文标签改用英文；业务字段、Chunk ID、版本和相似度均验证正确。

### 2. Mock LLM 暂不生成真实业务答案

当前答案是确定性的测试答案，不是生产级自然语言答案。它的目标是验证：

```text
检索结果 → 上下文 → LLM → 引用校验
```

后续只需替换 LLM Provider。

## 五、复习问题

1. 为什么 LangGraph State 使用 `TypedDict`？
2. 为什么 State 使用 `total=False`？
3. 为什么没有上下文时必须拒绝编造答案？
4. 为什么 LLM Provider 需要抽象接口？
5. 为什么答案中的 `[1]` 不能直接被信任？
6. 为什么引用编号要减一才能访问 Python 列表？
7. 为什么重复 Citation 要去重？
8. 为什么问答路由先使用真实 Embedding，再使用 Mock LLM？
9. 为什么 API Request 和 LangGraph State 不能混为一谈？
10. 为什么 Citation 必须保留 `document_version_id` 和 `chunk_id`？

## 六、面试表达

我在 Living RAG 中使用 LangGraph 将问答流程拆成上下文构造、答案生成和引用校验三个节点。检索结果会保留文档版本、治理状态和 Chunk ID，并被格式化成引用友好的上下文。LLM Provider 通过抽象接口注入，当前使用 Mock LLM 保证测试确定性。回答生成后，系统会验证 `[1]` 等引用编号是否指向本次真实检索结果，并转换成带文档、版本和 Chunk 身份的 Citation，从而避免返回无法追溯的回答。

## 七、今日进度

```text
功能完成：100%
今日总进度：96.875%
剩余：3.125%
全量测试：95 passed, 2 warnings
LangGraph：通过
问答 API：通过
Citation 校验：通过
学习日志：待复制到项目目录
Git 提交：尚未提交
```

## 八、下一天起点

Day 7：Living RAG 基础 MVP 收尾与最小前端联调，重点完成问答结果展示、引用展示、健康检查和演示流程，为 Day 8 的动态知识与业务安全做准备。

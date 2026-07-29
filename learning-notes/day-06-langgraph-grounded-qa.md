# Day 6：LangGraph 最小问答链、引用校验与运行追踪

## 一、今日目标

Day 6 完成 Living RAG 的最小问答 Agent 闭环：

1. 定义强类型 LangGraph State；
2. 检索当前有效的文档 Chunk；
3. 对检索结果进行相关性评分；
4. 构造 LLM 上下文；
5. 定义 LLM Provider 抽象和 Mock LLM；
6. 生成结构化回答；
7. 校验答案引用；
8. 提供问答 API；
9. 保存 Chat、Agent Run 和节点级运行记录；
10. 使用 trace_id 追踪完整 Agent 执行过程。

当前问答图：

START
→ load_context
→ classify_intent
→ retrieve_documents
→ grade_documents
→ build_context
→ generate_answer
→ validate_citations
→ END

## 二、完成内容

### 1. LivingRAGState

文件：

apps/living-rag-api/app/services/qa_state.py

共享 State 当前包含：

question
user_id
trace_id
limit
intent
retrieval_results
graded_results
context
answer
conditions
citation_indices
citations
confidence
limitations
citation_valid
error

使用 TypedDict(total=False)，允许 State 在节点之间逐步补充字段。

### 2. load_context

文件：

apps/living-rag-api/app/services/qa_nodes.py

load_context_node 负责：

- 去除问题前后的空格；
- 拒绝空问题；
- 给缺失的 limit 设置默认值 5；
- 验证 limit 必须是正整数；
- 标准化 user_id；
- 标准化 trace_id。

### 3. 意图分类

使用安全优先的确定性规则，将请求分类为：

high_risk_operation
refund_request
order_membership
policy_qa
unknown

已验证：

删除退款政策 -> high_risk_operation
我要申请退款 -> refund_request
O2025001 能退款吗 -> order_membership
退款时限是多少 -> policy_qa

### 4. 文档检索与评分

文件：

apps/living-rag-api/app/services/qa_nodes.py

retrieve_documents_node 负责：

1. 读取用户问题；
2. 调用 Embedding Provider；
3. 执行 pgvector 相似度检索；
4. 过滤当前有效版本；
5. 转换为 RetrievalResult；
6. 写入 retrieval_results。

实际运行使用：

Ollama nomic-embed-text

grade_documents_node 只保留：

governance_status == active
content 非空
similarity >= 0.2

评分结果写入 graded_results。

### 5. 检索上下文

文件：

apps/living-rag-api/app/services/qa_context.py

build_retrieval_context() 将 RetrievalResult 列表转换成 LLM 可读取的上下文，并保留：

document_title
version_number
source_type
governance_status
chunk_id
similarity
content

当前使用英文标签，避免 Windows PowerShell 中文编码显示问题。

### 6. LLM Provider 与结构化回答

文件：

apps/living-rag-api/app/services/llm.py

定义 LLMProvider 抽象接口，并实现 MockLLMProvider。

没有上下文时：

返回保守拒答
citation_indices = []
confidence = 0.0

有上下文时返回：

answer
conditions
citation_indices
confidence
limitations

Mock LLM 的目标是稳定验证：

检索
→ 上下文
→ 结构化回答
→ Citation
→ Citation 校验
→ 持久化

### 7. Citation 校验

文件：

apps/living-rag-api/app/services/citation_validation.py

完成：

validate_answer_citations()
build_citations_from_answer()

校验规则：

- 答案不能为空；
- 没有引用标记时无效；
- 引用编号必须在结果范围内；
- 引用编号不能越界；
- 引用编号必须是严格整数；
- 文档治理状态必须为 active；
- 文档版本必须已经生效且未过期；
- 引用内容不能为空；
- 重复引用需要去重；
- Citation 必须来自真实检索结果。

Citation 保留：

document_id
document_version_id
chunk_id
quote
relevance_score

### 8. LangGraph

文件：

apps/living-rag-api/app/services/qa_graph.py

当前注册 7 个节点：

load_context
classify_intent
retrieve_documents
grade_documents
build_context
generate_answer
validate_citations

通过依赖注入传入：

LLMProvider
EmbeddingProvider
SQLAlchemy Session

### 9. 问答 API

文件：

apps/living-rag-api/app/api/routes/qa.py

当前提供两个接口：

POST /api/qa/answer
POST /api/chat

两个接口共享 _run_question_answer()，没有复制两套问答逻辑。

请求包含：

user_id
question
limit

响应包含：

trace_id
answer
conditions
citation_valid
citations
confidence
limitations

### 10. QA 持久化

文件：

apps/living-rag-api/app/services/qa_persistence.py

保存：

ChatThread
ChatMessage
AgentRun
AgentNodeRun

通过 trace_id 可以反查：

用户消息
助手消息
AgentRun
每个 LangGraph 节点
Citation
节点输入快照
节点输出快照
节点时间
节点耗时

当前保存流程是：

LangGraph 执行完成
→ save_qa_run()
→ 数据库事务提交

计划图中把保存表示为 save_run_and_message 节点，当前实现由 API 路由在图执行完成后调用 save_qa_run()。这是实现位置差异，不是功能缺失。当前已经完成完整保存、Trace 关联、事务提交、异常回滚和节点记录。

### 11. 节点快照与耗时

文件：

apps/living-rag-api/app/api/routes/qa.py

每个节点保存：

node_name
sequence_number
status
input_snapshot
output_snapshot
started_at
completed_at
duration_ms

真实 Trace 中：

retrieve_documents duration_ms = 2004

说明 Embedding 调用和 pgvector 检索耗时已经被记录。其他极快节点可能显示 0 毫秒，因为执行时间小于 1 毫秒。

## 三、验证结果

### 1. 无检索结果

graph execution: ok
context empty: True
answer: I do not have enough grounded evidence to answer this question.
citation_valid: False
citations: []

说明无证据时不会编造答案。

### 2. 真实检索结果

retrieval result count: 2
graph execution: ok
citation_valid: True
citation count: 1

真实 Chunk ID：

ad3be9e9-2f2e-4f5b-9a26-9d5fd0500acf

真实相似度：

0.7067421706202623

### 3. API 验证

POST /api/chat 验证成功。

最近一次验证 Trace：

8c3548fe-6de3-4e40-9983-611c79b6b13e

结果：

answer：成功返回
citation_valid：true
citations：1 条
confidence：0.85

POST /api/qa/answer 兼容接口验证成功，说明新接口没有破坏旧接口。

### 4. Python 语法检查

命令：

docker compose run --rm api python -m compileall app

结果：

通过

### 5. 全量测试

命令：

docker compose run --rm api pytest -q

结果：

107 passed, 2 warnings

Warning：

- Starlette/httpx 弃用提示；
- LangGraph allowed_objects 默认值未来变化提示。

两个 Warning 均没有导致测试失败。

### 6. Docker 验证

命令：

docker compose build api
docker compose up -d --force-recreate api

结果：

Image living-rag-api Built
Container living-rag-api-1 Recreated

### 7. PostgreSQL Trace 验证

Trace：

8c3548fe-6de3-4e40-9983-611c79b6b13e

保存了 7 个节点：

1. load_context
2. classify_intent
3. retrieve_documents
4. grade_documents
5. build_context
6. generate_answer
7. validate_citations

所有节点满足：

status = succeeded
input_snapshot 存在
output_snapshot 存在
completed_at >= started_at

## 四、问题与解决方案

### 1. Windows 中文编码问题

PowerShell 和文件复制过程中出现过中文乱码。主要是终端编码显示问题，不代表数据库中的业务内容损坏。为保证上下文输出稳定，qa_context.py 使用英文标签。

### 2. Mock LLM

当前使用 MockLLMProvider，目标是稳定验证检索、上下文、结构化回答、Citation、Citation 校验和持久化。后续可以只替换 LLM Provider，不需要重写主图。

### 3. 节点耗时问题

最初计时位置错误，导致 duration_ms 一直为 0。修复后，retrieve_documents 节点记录到 duration_ms = 2004，说明真实 Embedding 和检索耗时已经被捕获。

## 五、复习问题

1. 为什么 LangGraph State 使用 TypedDict？
2. 为什么 State 使用 total=False？
3. 为什么 load_context 要放在 classify_intent 前面？
4. 为什么没有上下文时必须拒绝编造答案？
5. 为什么 LLM Provider 需要抽象接口？
6. 为什么答案中的 [1] 不能直接被信任？
7. 为什么引用编号要减一才能访问 Python 列表？
8. 为什么重复 Citation 要去重？
9. 为什么 API Request 和 LangGraph State 不能混为一谈？
10. 为什么 Citation 必须保留 document_version_id 和 chunk_id？
11. 为什么使用真实 Embedding 和 Mock LLM？
12. 为什么节点耗时不能在 graph.stream 返回结果后才开始计时？
13. 为什么需要记录 input_snapshot 和 output_snapshot？
14. 为什么 trace_id 能关联一次完整 Agent 运行？
15. 为什么数据库异常时必须 rollback？

## 六、面试表达

我在 Living RAG 中使用 LangGraph 编排问答流程，将上下文标准化、意图识别、向量检索、文档评分、上下文构造、结构化回答和引用校验拆成独立节点。

检索结果会保留文档版本、治理状态和 Chunk ID，并被格式化成引用友好的上下文。LLM Provider 通过抽象接口注入，当前使用 Mock LLM 保证测试确定性。回答生成后，系统会验证 [1] 等引用编号是否指向本次真实检索结果，并转换成带文档、版本和 Chunk 身份的 Citation，从而避免返回无法追溯的回答。

系统还为每次请求生成 trace_id，并将用户消息、助手消息、AgentRun 和每个 LangGraph 节点的输入输出快照保存到数据库，使一次回答可以被追踪、回放和审计。

## 七、今日进度

Day 6 功能完成度：100%
Day 6 代码验证：100%
Day 6 数据库验证：100%
Day 6 自动化测试：100%
Day 6 Git 提交：100%
Day 7：0%

验证结果：

Python compileall：通过
全量测试：107 passed, 2 warnings
/api/chat：通过
/api/qa/answer：通过
Citation 校验：通过
QA 持久化：通过
Trace 查询：通过
节点输入输出快照：通过
节点耗时：通过

Git 提交：

73fe899 feat: complete grounded QA workflow

上一条相关提交：

20bac60 feat: persist grounded QA runs

Day 7 前端文件暂未提交：

apps/living-rag-web/app/page.tsx

## 八、下一天起点

Day 7：Living RAG 第一周 MVP 收尾与最小前端联调。

重点：

输入问题
→ 调用 /api/chat
→ 展示回答
→ 展示适用条件
→ 展示引用卡片
→ 展示文档版本
→ 展示治理状态
→ 展示原文片段
→ 展示 trace_id

Day 7 初始状态：

后端问答 API：已完成
前端页面：已有未提交修改
前端 API 联调：待完成
引用卡片展示：待完成
第一周验收测试：待完成
Day 7 完成度：0%


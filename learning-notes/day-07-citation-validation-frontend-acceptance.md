# Living RAG Day 7 学习日志

日期：2026-07-30

## 一、当天目标

完成第一周可演示的最小前端和问答验收闭环：

- 中文前端问答工作台；
- 调用 `POST /api/chat`；
- 展示回答、条件、引用和 Trace ID；
- 展示 loading、失败状态和 `citation_valid=false` 安全状态；
- 引用卡展示标题、版本、来源类型、治理状态、有效期、原文和相关度；
- 前端构建通过；
- 完成 10 条正常、3 条无关、3 条过期规则、2 条诱导编造验收；
- 完成日志并提交 Git。

## 二、完成内容

### 前端

文件：

- `E:\Living RAG\apps\living-rag-web\app\page.tsx`
- `E:\Living RAG\apps\living-rag-web\app\globals.css`

已完成：

- 中文问答页面；
- 用户 ID、问题和 limit 输入；
- 调用 `POST /api/chat`；
- answer、conditions、limitations 展示；
- 引用卡片展示；
- Trace ID 展示；
- loading 和失败状态；
- `citation_valid=false` 安全展示。

### 后端回答与安全降级

修改文件：

- `E:\Living RAG\apps\living-rag-api\app\services\llm.py`
- `E:\Living RAG\apps\living-rag-api\app\services\qa_nodes.py`
- `E:\Living RAG\apps\living-rag-api\app\services\retrieval.py`

已完成：

- 普通会员退款期限：7 天；
- 银卡会员退款期限：10 天；
- 金卡会员退款期限：15 天；
- 铂金会员退款期限：20 天；
- 空证据返回中文保守回答；
- 未知意图清空证据，避免无关问题被低相关结果污染；
- 修复无政策领域时产生 `CASE ELSE` 非法 SQL 的问题。

### Citation 协议

修改文件：

- `E:\Living RAG\apps\living-rag-api\app\schemas\citation.py`
- `E:\Living RAG\apps\living-rag-api\app\services\citation_validation.py`

当前 Citation 返回：

- `document_title`
- `version_number`
- `source_type`
- `governance_status`
- `effective_at`
- `expires_at`
- `quote`
- `relevance_score`

## 三、真实接口验证

真实请求：

```text
POST http://127.0.0.1:8000/api/chat
问题：目前普通会员签收后多久可以申请退款？
```

真实结果：

- `citation_valid=true`
- `confidence=0.9`
- `version_number=3`
- `source_type=official_policy`
- `governance_status=active`
- `expires_at=null`
- 回答命中普通会员 7 天规则；
- Citation 元数据完整返回。

真实 Trace：

```text
7b71c236-82eb-4c10-9216-7073ad4344b1
```

## 四、构建和测试

前端命令：

```powershell
npm.cmd run build
```

结果：

- Next.js 编译通过；
- TypeScript 检查通过；
- 静态页面生成通过。

QA Workflow 测试：

```text
10 passed in 0.20s
```

Docker 内完整后端测试：

```powershell
docker compose exec -T api pytest
```

结果：

```text
107 passed, 2 warnings in 2.69s
```

测试结论：

- failed：0；
- errors：0；
- 文档、模型、API、Seed、持久化、QA 和共享 Schema 测试全部通过。

## 五、18 条第一周验收

### 10 条正常问答

- 全部 HTTP 200；
- 全部返回有效引用；
- 退款问题命中退款政策 v3；
- 普通、银卡、金卡、铂金会员期限分别命中 7、10、15、20 天；
- Citation 元数据完整。

### 3 条无关问题

天气、写诗和世界最高山问题均：

- HTTP 200；
- `citation_valid=false`；
- `citations=[]`；
- `confidence=0.0`；
- 没有知识库外编造答案。

### 3 条过期规则问题

- 全部 HTTP 200；
- 有效引用为当前 `version_number=3`；
- `governance_status=active`；
- 没有使用 v1 或 v2 作为当前有效引用。

按历史日期查询旧版本属于 Day 8，本日不扩展。

### 2 条诱导编造问题

- 没有输出“无限期退款”；
- 没有输出“999 天”；
- 回答仍受当前有效政策证据约束；
- 没有执行用户诱导的无证据结论。

当前限制：诱导问题可能返回当前政策引用，而不是完全拒答。Day 7 的核心要求是不能编造，已经满足；更强的诱导识别属于后续可靠性增强。

## 六、Day 7 完成情况

| 任务 | 状态 |
|---|---|
| 中文前端问答页面 | 已完成 |
| 调用 `/api/chat` | 已完成 |
| 展示回答、条件和引用 | 已完成 |
| 展示 Citation 元数据 | 已完成 |
| 展示 Trace ID | 已完成 |
| loading 和失败状态 | 已完成 |
| 安全拒答状态 | 已完成 |
| 前端 build | 已完成 |
| 18 条第一周验收 | 已完成 |
| Day 7 学习日志 | 本文件 |
| Git 提交 | 待执行 |

代码与测试完成度：100%。

Git 提交完成前，不宣布当天最终 100%。

## 七、今日学习总结

1. 向量检索结果不等于有效证据，必须经过意图分类和评分。
2. 未知意图不能继续使用低相关检索结果。
3. Citation 校验需要检查编号、文本、状态、生效时间、失效时间和内容。
4. 前端引用卡片依赖后端完整返回版本和治理元数据。
5. Docker 内部的 `postgres` 服务名不能被 Windows 主机直接解析。
6. 依赖数据库的完整测试应在 API 容器内运行。
7. 真实验收不能只看 HTTP 200，还要检查引用版本和安全行为。

## 八、下一步

仍然停留在 Day 7，只做 Git 收尾：

```powershell
Set-Location "E:\Living RAG"

git status --short
git diff --stat
git log --oneline -5
```

确认没有混入 Day 6 后，再提交 Day 7 代码和日志。只有提交成功并再次检查 Git 状态后，才能宣布 Day 7 100% 完成。
# Day 16：Living RAG 自动化测试与任务集固化

日期：2026-08-09

## 今日核心目标

把 Living RAG 的关键行为固化为可重复执行的结构化 Agent 任务集，为后续 Agent Reliability Lab 的批量运行、Trace 关联和规则评测提供稳定输入。

Day 16 的完成标准不是简单保存问题文本，而是每条任务都同时描述输入、上下文、预期路由、预期引用、期望行为、禁止行为和失败判定条件。

## 今日完成内容

### 1. 扩展任务协议

文件：

`E:\Living RAG\apps\living-rag-api\app\schemas\agent_task_case.py`

新增任务类别：

- `normal_policy_qa`
- `version_and_stale_content`
- `conflict_case`
- `order_membership_eligibility`
- `high_risk_action`
- `multi_turn`
- `fault_injection`
- `adversarial`

任务协议现在支持：

- 稳定字符串 `case_id`；
- 用户输入和业务上下文；
- 预期路由；
- 按政策标识和版本描述的预期引用；
- 多条期望行为；
- 禁止行为；
- 失败条件；
- 故障注入配置；
- 标签和扩展元数据。

保留了 `expected_intent`、默认任务类别和默认路由，以兼容 Day 1 到 Day 15 已有共享 Schema 测试。

### 2. 新增任务集加载服务

文件：

`E:\Living RAG\apps\living-rag-api\app\services\task_dataset_loader.py`

服务支持：

- 读取 JSON 数组文件；
- 读取 JSONL 文件；
- 按扩展名自动选择解析器；
- 加载单个分类目录；
- 加载整个任务集根目录；
- 按任务类别筛选；
- 检测重复 `case_id`；
- 报告文件路径、任务序号和 JSONL 行号；
- 使用 `TaskDatasetLoadError` 与 HTTP 层解耦。

### 3. 固化共享任务集

共享目录：

`E:\Living RAG\shared\datasets`

目录包含：

- `qa`：正常政策问答；
- `conflict-cases`：冲突和条件性例外；
- `agent-tasks`：订单、会员和退款资格；
- `fault-injection`：检索为空、工具超时、工具错误和权限拒绝；
- `adversarial`：版本过期、高风险操作、多轮对话和对抗输入。

任务总数：71 条。

数量分布：

| 类别 | 数量 |
|---|---:|
| 正常政策问答 | 15 |
| 版本与过期内容 | 8 |
| 冲突问题 | 10 |
| 订单会员资格 | 10 |
| 高风险操作 | 8 |
| 多轮对话 | 5 |
| 故障注入 | 5 |
| 对抗任务 | 10 |

其中故障注入和对抗任务合计 15 条，满足 Day 16 计划要求；总任务数 71 条，超过至少 50 条的验收线。

### 4. 接入 Docker 共享目录

文件：

`E:\Living RAG\docker-compose.yml`

API 容器新增只读挂载：

```text
E:\Living RAG\shared
→ /shared
```

这样 API 容器和后续 Reliability Lab 都可以读取同一份共享任务集，任务数据不会复制成两套。

## 测试结果

任务协议测试文件：

`E:\Living RAG\apps\living-rag-api\tests\test_agent_task_case_schema.py`

结果：

`10 passed`

任务加载服务测试文件：

`E:\Living RAG\apps\living-rag-api\tests\test_task_dataset_loader.py`

结果：

`17 passed`

任务集库存测试文件：

`E:\Living RAG\apps\living-rag-api\tests\test_task_dataset_inventory.py`

结果：

`3 passed`

Day 16 全量测试结果：

`300 passed, 2 warnings`

警告来自当前 FastAPI/Starlette TestClient 兼容提示和 LangGraph 依赖弃用提示，不影响测试通过结果。

## 今天学到的关键设计

`AgentTaskCase` 负责定义一条任务的结构和字段校验；`task_dataset_loader.py` 负责从文件系统读取多条任务并统一转换；任务集库存测试负责验证数量、类别、目录和唯一 ID；真正的 Agent 执行和规则评测属于后续 Reliability Lab 阶段。

任务集文件不使用数据库 UUID 作为预期引用的唯一依据，而使用 `policy_key`、版本号、来源类型和引用片段关键词。这样任务集可以在重新迁移数据库或不同环境中复用。

## 已知限制

- 当前任务集只固化输入和预期标准，还没有批量执行器；
- 当前任务集库存测试直接使用容器路径 `/shared/datasets`；
- 任务集还没有导入数据库的需求，后续 Reliability Lab 会直接读取文件并调用 Living RAG；
- 规则评测器会在 Day 21 实现；
- LLM Judge、故障注入运行器和回归比较不属于 Day 16。

## Day 16 验收结论

- [x] 任务协议扩展；
- [x] JSON/JSONL 加载服务；
- [x] 共享任务集五类目录；
- [x] 至少 50 条结构化任务；
- [x] 每条任务具备输入、上下文、预期路由、预期引用、期望行为、禁止行为和失败条件；
- [x] 任务集库存测试；
- [x] Docker API 容器只读挂载共享任务集；
- [x] 专项测试；
- [x] 全量测试；
- [x] 中文学习日志。

Day 16 为后续 Reliability Lab 的批量执行和规则评测准备好了稳定任务输入。

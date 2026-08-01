# Day 9：结构化规则抽取与持久化

日期：2026-08-01

## 今日目标

在 Living RAG 中建立最小的结构化政策规则能力：

- 定义受 Pydantic 校验的规则 Schema；
- 建立 `policy_rules` 数据表；
- 从退款政策文档版本中抽取结构化规则；
- 保存规则的文档版本、条件、原始证据、生效期和置信度；
- 支持同一文档版本的幂等刷新；
- 用真实的退款政策 v3 完成数据库验收。

## 今日完成内容

### 1. 规则 Schema

文件：

```text
apps/living-rag-api/app/schemas/policy_rule.py
```

定义了 `PolicyRuleKey` 枚举，当前支持：

```text
refund.window_days
refund.return_shipping_payer
refund.member_free_return_tier
refund.excluded_categories
delivery.delay_compensation
exchange.window_days
membership.benefit
```

定义了 `PolicyRuleExtraction`，字段包括：

- `rule_key`：结构化规则类型；
- `value`：规则值；
- `conditions`：适用条件；
- `source_quote`：原始证据片段；
- `document_version_id`：所属文档版本；
- `effective_at`：生效时间；
- `expires_at`：失效时间；
- `confidence`：抽取置信度。

Schema 使用 `extra="forbid"`，并限制置信度范围为 `0.0` 到 `1.0`。

### 2. PolicyRule ORM 模型

文件：

```text
apps/living-rag-api/app/models/policy_rule.py
```

创建了 `policy_rules` 表模型，主要字段包括：

- `document_version_id`：外键指向 `document_versions.id`；
- `rule_key`：规则键；
- `value`：JSONB 规则值；
- `conditions`：JSONB 适用条件；
- `source_quote`：原始证据；
- `effective_at` / `expires_at`：规则有效期；
- `confidence`：规则置信度；
- `created_at` / `updated_at`：时间字段。

数据库约束保证：

```text
confidence >= 0.0 AND confidence <= 1.0
```

同时为文档版本、规则键和生效时间建立索引。

### 3. Alembic migration

文件：

```text
apps/living-rag-api/alembic/versions/c4d9a8e71f10_add_policy_rules.py
```

迁移版本：

```text
c4d9a8e71f10
```

父版本：

```text
b6253fb946c2
```

已执行：

```powershell
docker compose exec -T api alembic upgrade head
```

数据库已验证：

```text
c4d9a8e71f10 (head)
```

`policy_rules` 表已包含预期字段、外键、检查约束和索引。

### 4. 确定性规则抽取

文件：

```text
apps/living-rag-api/app/services/policy_rule_extraction.py
```

第一版抽取器使用确定性正则表达式识别退款政策 Markdown 表格：

```python
r"\| *(standard|silver|gold|platinum) *\| *(\d+)"
```

当前可以识别四种会员等级及退款天数，并生成四条：

```text
refund.window_days
```

每条规则通过条件区分会员等级，例如：

```json
{
  "membership_tier": "gold"
}
```

同时识别包含 `gold` 和 `platinum` 的会员免费退货证据行，生成：

```text
refund.member_free_return_tier
```

其结构化结果为：

```json
{
  "value": "gold",
  "conditions": {
    "includes": "platinum"
  }
}
```

如果找不到会员退款期限表格，抽取器会明确抛出：

```text
Refund membership window table was not found.
```

### 5. 规则持久化服务

文件：

```text
apps/living-rag-api/app/services/policy_rule_service.py
```

核心函数：

```python
replace_policy_rules_for_document_version(
    db,
    document_version,
)
```

处理流程：

```text
抽取当前文档版本规则
    ↓
删除当前 document_version_id 的旧规则
    ↓
将 PolicyRuleExtraction 转换为 PolicyRule ORM
    ↓
批量 add_all
    ↓
flush
    ↓
返回规则列表
```

该服务不调用 `commit()`，事务提交由更高层负责。

幂等行为已经验证：同一版本重复执行不会把 5 条规则变成 10 条；刷新一个版本也不会删除其他版本的规则。

### 6. 真实 v3 持久化验收脚本

文件：

```text
apps/living-rag-api/scripts/persist_refund_policy_rules.py
```

脚本查询：

```text
policy_key = REFUND-POLICY
version_number = 3
```

然后调用规则持久化服务并提交事务。

运行命令：

```powershell
docker compose exec -T api python -m scripts.persist_refund_policy_rules
```

真实执行结果：

```text
saved_rules=5
refund.window_days 7 {'membership_tier': 'standard'}
refund.window_days 10 {'membership_tier': 'silver'}
refund.window_days 15 {'membership_tier': 'gold'}
refund.window_days 20 {'membership_tier': 'platinum'}
refund.member_free_return_tier gold {'includes': 'platinum'}
```

## 真实数据库验收

开发数据库中的退款政策版本链为：

```text
v1：2025-01-01，superseded
v2：2025-04-01，superseded
v3：2025-07-01，active
```

针对 v3 查询 `policy_rules`，结果为 5 条：

```text
refund.member_free_return_tier | "gold" | {"includes": "platinum"}
refund.window_days              | 15      | {"membership_tier": "gold"}
refund.window_days              | 20      | {"membership_tier": "platinum"}
refund.window_days              | 10      | {"membership_tier": "silver"}
refund.window_days              | 7       | {"membership_tier": "standard"}
```

每条记录的置信度为：

```text
0.95
```

## 测试结果

新增测试包括：

- `tests/test_policy_rule_schemas.py`：规则 Schema 校验；
- `tests/test_policy_rule_extraction.py`：规则抽取；
- `tests/test_policy_rule_service.py`：规则持久化、幂等和版本隔离。

Day 9 全量测试命令：

```powershell
docker compose exec -T api pytest
```

最终结果：

```text
122 passed, 2 warnings in 2.00s
```

警告来自第三方依赖：

- Starlette TestClient 的 httpx 兼容性提醒；
- LangGraph cache 的 pending deprecation 提醒。

当前警告不影响测试结果和 Day 9 功能验收。

## 遇到的问题与解决

### 1. 正则表达式中的反斜杠

初始版本中 `\\s` 的含义不符合预期，导致 Markdown 表格匹配失败。最终使用更直观的写法：

```python
r"\| *(standard|silver|gold|platinum) *\| *(\d+)"
```

### 2. 脚本模块导入问题

直接执行：

```powershell
python scripts/persist_refund_policy_rules.py
```

可能导致：

```text
ModuleNotFoundError: No module named 'app'
```

最终使用模块方式执行：

```powershell
python -m scripts.persist_refund_policy_rules
```

这样容器工作目录 `/app` 会作为 Python 模块根目录。

### 3. main 函数没有被调用

脚本最初虽然定义了 `main()`，但缺少模块入口：

```python
if __name__ == "__main__":
    main()
```

补充后脚本才真正执行数据库查询和持久化。

### 4. 误生成的空文件

仓库根目录曾出现一个 0 字节的 `python` 文件。确认不是项目文件后已删除，避免误提交。

## Git 检查结果

Day 9 文件已经暂存，包含 10 个文件：

```text
10 files changed, 895 insertions(+)
```

暂存区检查：

```powershell
git diff --cached --check
```

结果无输出，说明没有发现 trailing whitespace 或文件末尾空白问题。

## Day 9 结论

Day 9 已完成结构化规则抽取与持久化闭环：

```text
文档版本
→ 规则抽取
→ Pydantic 校验
→ PolicyRule 持久化
→ 保留原始证据和适用条件
→ 真实 v3 验收
→ 全量测试通过
```

当前系统已经可以回答结构化规则问题，例如：

```text
金卡会员的退款期限是多少？
```

结构化结果为：

```text
15 天
```

且可以追溯到：

```text
REFUND-POLICY v3
原始证据：| gold | 15
置信度：0.95
```

## 下一步

进入 Day 10：差异比较与冲突检测。

Day 10 的第一步不是直接写冲突算法，而是先定义规则差异的业务分类：

```text
更新
历史差异
条件性例外
真正冲突
高风险错误
```

Day 10 暂不实现人工审核页面，人工审核属于 Day 11。

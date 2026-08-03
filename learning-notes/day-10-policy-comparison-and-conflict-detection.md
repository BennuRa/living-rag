# Day 10：规则差异比较与冲突检测

日期：2026-08-03

## 今日目标

- 比较两个政策版本中的结构化规则；
- 区分版本更新、历史差异、条件性例外、真正冲突和高风险错误；
- 保存冲突、严重度、原因、推荐处理方式和原始证据；
- 用真实退款政策、FAQ、双十一公告和无限期退款通知完成验收。

## 今日完成

### 1. 规则比较服务

文件：

```text
apps/living-rag-api/app/services/policy_rule_comparison.py
```

比较逻辑包含：

- 有效期不重叠：`historical_difference`；
- 新版本独有规则：`update`；
- 更具体的条件规则：`conditional_exception`；
- 有效期和条件重叠但值不同：`conflict`；
- 无限期、永久或无时间限制退款：`high_risk_error`。

规则匹配使用：

```text
rule_key + conditions
```

避免只使用 `rule_key` 导致不同会员等级或不同活动条件的规则被错误覆盖。

### 2. v1 自然语言规则抽取

v1 使用自然语言表达：

```text
standard、silver、gold 和 platinum 会员均适用 7 个自然日的退款申请期限。
```

抽取器现在同时支持：

- Markdown 表格格式；
- 中文自然语言会员期限格式。

v1 成功抽取 4 条规则，v3 成功抽取 5 条规则。

### 3. 冲突数据库

新增：

```text
conflicts
conflict_evidences
```

每条比较结果保存：

- 比较类型；
- 严重度；
- rule_key；
- 左右规则 ID；
- 左右文档版本 ID；
- 原因；
- 推荐处理方式；
- 原始证据引用。

Alembic head：

```text
d8a4f6b921c7
```

### 4. 真实业务验收

数据库中最终保存：

| 类型 | 数量 | 场景 |
|---|---:|---|
| `historical_difference` | 4 | v1 的 7 天与 v3 的会员期限差异 |
| `update` | 1 | v3 新增金卡免费退货规则 |
| `conflict` | 1 | FAQ 金卡 30 天与正式政策 15 天冲突 |
| `conditional_exception` | 1 | 双十一活动订单 30 天 |
| `high_risk_error` | 1 | 无限期退款错误通知 |

证据数量：

- 历史差异每条 2 条证据；
- 更新规则 1 条证据；
- 冲突、条件例外和高风险错误各 2 条证据。

## 测试结果

```text
160 passed, 2 warnings
```

warning 来自第三方依赖，不影响测试通过。

## Day 10 验收结论

Day 10 已完成 100%。

Day 11 从人工审核任务开始，使用 Day 10 已经持久化的 `conflicts` 和 `conflict_evidences` 数据。

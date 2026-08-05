# Day 13：订单、会员查询工具与确定性退款资格判定

日期：2026-08-05

## 今日目标

Day 13 完成订单、用户、会员、退款历史查询工具，以及 Python 确定性退款资格服务。

## 今日完成内容

- 查询真实订单、会员、用户和退款历史数据；
- 确认 Python 属性名与 PostgreSQL 列名的差异；
- 实现 get_order、get_user、get_membership、get_refund_history；
- 实现确定性退款资格服务；
- 测试四个核心演示订单；
- 测试未签收、冻结会员、重复退款、未决冲突和缺失事实；
- 在 Docker 容器中完成编译检查、定向测试和全量回归。

## 一、真实数据分析

### 1. Python 字段名与数据库列名

第一次查询时把 Python 字段 metadata_ 当成了数据库列名，PostgreSQL 报错并提示真实列名是 metadata。

模型中使用：

~~~python
metadata_
~~~

数据库中使用：

~~~sql
metadata
~~~

原因是 SQLAlchemy 模型把 Python 属性 metadata_ 映射到了数据库列 metadata。

| 代码层 | 数据库层 |
|---|---|
| order.metadata_ | orders.metadata |
| user.metadata_ | users.metadata |
| membership.metadata_ | membership_accounts.metadata |
| refund_request.metadata_ | refund_requests.metadata |

这个问题提醒我：不能只根据 Python 属性名猜 SQL 列名，查询数据库时必须以真实表结构为准。

### 2. 演示订单

| 订单 | 状态 | 签收 | 关键场景 |
|---|---|---|---|
| O2025001 | completed | 是 | 普通会员，签收 12 天 |
| O2025002 | completed | 是 | 金卡，签收 14 天，指定免费退货商品 |
| O2025003 | completed | 是 | 银卡，签收 18 天 |
| O2025004 | completed | 是 | 双十一活动订单 |
| O2025005 | shipped | 否 | 运输中 |
| O2025006 | refunded | 是 | 已完成退款，重复申请 |
| O2025007 | completed | 是 | 金卡账号 suspended |
| O2025008 | shipped | 否 | 偏远地区物流延迟 |

订单 metadata 中确认了：

~~~text
received_at
returnable
product_name
designated_free_return
campaign_tags
shipping_status
region_type
estimated_delay_days
~~~

received_at 用于计算退款期限，designated_free_return 用于判断免费退货权益，campaign_tags 用于识别活动订单。

### 3. 会员状态

| 订单 | 会员等级 | 会员账号状态 |
|---|---|---|
| O2025001 | standard | active |
| O2025002 | gold | active |
| O2025003 | silver | active |
| O2025004 | platinum | active |
| O2025006 | silver | active |
| O2025007 | gold | suspended |

O2025007 说明会员等级和会员账号状态必须同时判断：

~~~text
tier = gold 不等于当前可以使用金卡权益
status = suspended 时必须限制或转人工审核
~~~

### 4. 退款状态

只有以下条件成立时，才表示退款已经完成：

~~~text
refund_requests.status = completed
completed_at 有值
~~~

approved 只表示审批通过，不一定表示退款资金流程已经完成。O2025006 因为订单状态 refunded 且退款记录 completed，必须拒绝重复退款。

## 二、四个查询工具

文件：

~~~text
E:\Living RAG\apps\living-rag-api\app\services\business_tools.py
~~~

### get_order

使用 Order.order_number 查询业务订单号，不使用内部 UUID。工具只返回订单事实，不直接返回 eligible。

重点判断：

~~~python
if order is None:
    return {"found": False}

received_at = metadata.get("received_at")
is_received = received_at is not None
return {"found": True, "is_received": is_received}
~~~

因此 O2025005 是 found=True、is_received=False，而不存在的 O2025999 才是 found=False。

### get_user

业务用户编号 USR001 这类业务编号使用 User.external_id 查询。返回 database_id、external_id、email、display_name、status 和 metadata。

### get_membership

会员查询必须经过：

~~~text
users.external_id -> users.id
users.id -> membership_accounts.user_id
~~~

membership_accounts.user_id 保存的是数据库 UUID，不能直接使用 USR002 查询。

工具必须同时返回 tier 和 status。只返回 gold 会绕过 suspended 账号的安全限制。

### get_refund_history

退款历史查询经过：

~~~text
orders.order_number -> orders.id
orders.id -> refund_requests.order_id
~~~

一个订单可能有多条退款记录，因此使用 db.scalars(statement).all()。订单存在但没有退款申请时，返回 found=True 和空列表，而不是订单不存在。

## 三、确定性资格服务

文件：

~~~text
E:\Living RAG\apps\living-rag-api\app\services\refund_eligibility.py
~~~

LLM 负责理解问题、调用工具和组织回答；Python 负责判断是否在期限内、是否已退款、账号是否正常以及运费由谁承担。

### 1. 判断优先级

~~~text
订单是否存在
    ↓
会员信息是否存在
    ↓
退款历史查询是否成功
    ↓
是否已经完成退款
    ↓
会员账号是否 active
    ↓
订单是否签收
    ↓
商品是否允许退货
    ↓
签收时间是否存在
    ↓
是否超过 15 天
    ↓
是否存在阻断性冲突
    ↓
计算退货运费承担方
    ↓
返回最终资格
~~~

已完成退款必须先于期限判断。即使订单仍在 15 天内，也不能重复退款。

### 2. 决策类型

| decision | 含义 |
|---|---|
| eligible | 明确符合当前规则 |
| ineligible | 明确不符合当前规则 |
| not_ready | 事实不足，例如尚未签收 |
| not_found | 订单不存在 |
| manual_review | 数据、账号或政策存在风险，需要人工处理 |

典型结果：

~~~text
订单不存在 -> not_found
订单尚未签收 -> not_ready
超过 15 天 -> ineligible
会员账号 suspended -> manual_review
查询结果不一致 -> manual_review
~~~

### 3. 使用 as_of

资格服务不直接调用 datetime.now()，而是接收固定的 as_of。这样相同的订单事实在不同时间运行时仍能得到可重复结果，也能支持历史日期判断。

例如：

~~~text
received_at = 2026-01-09
as_of = 2026-01-21
elapsed_days = 12
~~~

### 4. 运费规则

平台承担运费需要同时满足：

~~~python
membership["tier"] in {"gold", "platinum"}
membership["status"] == "active"
order["designated_free_return"] is True
~~~

否则用户承担运费。因此 O2025001 返回 customer，O2025002 返回 platform。

## 四、测试文件

查询工具测试：

~~~text
E:\Living RAG\apps\living-rag-api\tests\test_business_tools.py
~~~

资格服务测试：

~~~text
E:\Living RAG\apps\living-rag-api\tests\test_refund_eligibility.py
~~~

Day 13 集成验收：

~~~text
E:\Living RAG\apps\living-rag-api\tests\test_day13_acceptance.py
~~~

集成测试真实创建并关联：

~~~text
User -> MembershipAccount -> Order -> RefundRequest
~~~

然后依次调用四个查询工具和资格服务。

## 五、核心订单验收

| 订单 | 预期结果 |
|---|---|
| O2025001 | eligible，用户承担退货运费 |
| O2025002 | eligible，平台承担退货运费 |
| O2025003 | ineligible，超过 15 天期限 |
| O2025006 | ineligible，拒绝重复退款 |

## 六、问题定位与修复

### 问题 1：metadata_ 不是数据库列名

修复：Python 使用 metadata_，SQL 使用 metadata。

### 问题 2：未签收订单被误判为不存在

修复：先判断 order 是否为空，再根据 received_at 计算 is_received。

### 问题 3：使用不存在的 User.user_id

修复：业务用户编号使用 User.external_id。

### 问题 4：会员外键使用错误 ID

修复：先通过 external_id 找到 User，再使用 user.id 查询 MembershipAccount.user_id。

### 问题 5：把 approved 当成已退款

修复：只有 completed 才表示退款完成。

### 问题 6：使用 datetime.now() 导致测试不稳定

修复：资格服务接收固定的 as_of。

## 七、测试结果

### Day 13 定向测试

运行：

~~~powershell
Set-Location "E:\Living RAG"
docker compose exec -T api pytest tests/test_business_tools.py tests/test_refund_eligibility.py tests/test_day13_acceptance.py -q
~~~

结果：

~~~text
25 passed
~~~

### 编译检查

~~~powershell
docker compose exec -T api python -m compileall app/services/business_tools.py app/services/refund_eligibility.py tests/test_business_tools.py tests/test_refund_eligibility.py tests/test_day13_acceptance.py
~~~

结果：Day 13 服务和测试文件全部编译通过。

### 全量回归

~~~powershell
docker compose exec -T api pytest -q
~~~

结果：

~~~text
209 passed, 2 warnings
~~~

两个 warning 是已有依赖的弃用提示，不影响测试结果。

## 八、Day 13 文件清单

~~~text
E:\Living RAG\apps\living-rag-api\app\services\business_tools.py
E:\Living RAG\apps\living-rag-api\app\services\refund_eligibility.py
E:\Living RAG\apps\living-rag-api\tests\test_business_tools.py
E:\Living RAG\apps\living-rag-api\tests\test_refund_eligibility.py
E:\Living RAG\apps\living-rag-api\tests\test_day13_acceptance.py
E:\Living RAG\learning-notes\day-13-order-membership-eligibility.md
~~~

## 九、Day 13 验收结论

Day 13 的核心任务完成：

- 四个只读查询工具可以工作；
- 查询工具只返回事实，不直接裁定资格；
- 退款资格由 Python 确定性规则服务计算；
- 已完成退款会拒绝重复申请；
- 未签收订单不会被误判为不存在；
- suspended 账号不会直接享受金卡权益；
- 普通会员和金卡指定商品的运费承担方不同；
- 数据不一致和未决冲突会安全降级为人工审核；
- 四个核心演示订单通过集成验收；
- 全量回归测试 209 passed。

Day 13 完成度：

~~~text
100%
~~~

## 十、复习清单

1. 为什么 get_order 不能直接返回 eligible？
2. 为什么未签收订单是 found=True？
3. 为什么会员查询要区分 tier 和 status？
4. 为什么会员外键查询使用 user.id？
5. 为什么 approved 不等于 completed？
6. 为什么资格服务需要 as_of？
7. 为什么订单不存在是 not_found？
8. 为什么 suspended 账号进入 manual_review？
9. 为什么测试不应依赖开发数据库 Seed？
10. 为什么资格判断使用 Python 而不是让 LLM 自由决定？

## 十一、下一步：Day 14

Day 14 才开始处理：

~~~text
“能否退款？” -> 只读资格查询
“我要申请退款” -> 创建退款申请
“直接退款” -> 创建人工审批任务
“删除政策文档” -> 高风险审批
“修改退款规则” -> 高风险审批
~~~

Day 14 的重点是 approval_tasks、审批列表、批准与拒绝、高风险门控、审计日志，以及 Agent Run、用户对话和审批记录的关联。

Day 13 的资格服务只负责回答当前事实下是否符合退款条件，不会创建退款申请，也不会执行退款操作。

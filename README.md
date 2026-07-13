# Living RAG

> 面向动态知识库的事实保鲜、版本管理与冲突治理 Agent。

Living RAG 聚焦电商售后与会员服务场景，处理退款、配送、换货和会员权益等政策在持续更新时产生的版本混乱、过期内容、FAQ 冲突与高风险业务操作问题。

它不是普通的“上传文档后问答”RAG，而是一个具备知识治理、证据引用、业务工具校验、人工审批和审计能力的 LangGraph Agent。

## 项目目标

系统将逐步实现：

- 文档上传、解析、切块、Embedding 与 pgvector 检索；
- 政策文档版本管理、生效期与失效期治理；
- 结构化规则抽取、新旧版本对比和冲突检测；
- 正式政策、FAQ、临时公告冲突的人工审核闭环；
- 基于 LangGraph 的检索、评分、查询重写、生成与引用校验；
- 基于订单与会员信息的退款资格判断；
- 高风险操作的权限控制、人工审批与审计日志；
- 多轮会话、Trace、评测与故障注入。

## 项目关系

```text
Living RAG
  └── 被 Agent Reliability Lab 持续评测、故障注入与回归保障
```

后续的 Agent Reliability Lab 将接入 Living RAG，记录 Agent 运行节点、模型调用、工具调用、Token、延迟、成本和失败原因，并提供规则评测、LLM Judge、Trace 回放与回归比较。

## 当前进度

### Day 1：工程底座完成

- [x] PostgreSQL 16 + pgvector Docker 容器；
- [x] FastAPI 后端容器与 `/health` 接口；
- [x] pytest 自动化健康检查测试；
- [x] Next.js + TypeScript + Tailwind CSS 前端；
- [x] 前端实时检查 FastAPI 健康状态；
- [x] 验证 API 正常、停止和恢复三种状态；
- [x] 根目录 Monorepo Git 仓库与环境变量忽略规则。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python、FastAPI、Pydantic、SQLAlchemy、LangGraph |
| RAG | LangChain Core、PostgreSQL、pgvector、Ollama Embedding |
| 前端 | Next.js、TypeScript、Tailwind CSS |
| 数据库 | PostgreSQL 16 + pgvector |
| 测试 | pytest、后续规则评测与 LLM-as-Judge |
| 部署 | Docker Compose |

## 本地启动

### 1. 创建环境变量文件

```powershell
Copy-Item .env.example .env
```

不要提交 `.env`。其中会包含数据库密码以及后续模型 API Key。

### 2. 启动数据库与后端

```powershell
docker compose up --build -d postgres api
```

验证后端：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

FastAPI API 文档：

```text
http://localhost:8000/docs
```

### 3. 启动前端

```powershell
Set-Location .\apps\living-rag-web
npm.cmd install
npm.cmd run dev
```

浏览器打开：

```text
http://localhost:3000
```

## 目录结构

```text
Living RAG/
├── apps/
│   ├── living-rag-api/      # FastAPI、LangGraph、RAG 与业务工具
│   └── living-rag-web/      # Next.js 前端
├── docs/                    # 架构、API、演示脚本和技术决策
├── infra/                   # Docker、PostgreSQL 等基础设施配置
├── outputs/                 # 截图、评测报告和演示产物
├── shared/                  # 两个项目共享的数据 Schema、Prompt 和测试集
├── .env.example             # 可提交的配置模板
└── docker-compose.yml
```

## 安全原则

- 不提交 `.env`、`.env.local`、API Key 和本地数据库数据；
- 高风险操作不会由模型直接执行，必须经过权限检查、人工审批和审计；
- 规则冲突不能由模型擅自裁定，必须进入人工审核；
- 检索、查询重写、工具调用和生成修复均会设置明确上限，避免无限循环与成本失控。
# Day 1：Living RAG 工程底座

**日期：** 2026-07-13
**投入主题：** Docker、PostgreSQL + pgvector、FastAPI、pytest、Next.js、前后端健康检查、Git Monorepo。
**当天里程碑提交：** `0307838 feat: bootstrap Living RAG foundation`

---

## 1. 今天的目标

今天不实现 RAG、模型调用或业务规则，而是先搭建一个可运行、可验证、可持续迭代的工程底座：

```text
浏览器（Next.js，localhost:3000）
        ↓ HTTP 请求
FastAPI（Docker，localhost:8000）
        ↓ Docker Compose 网络
PostgreSQL + pgvector（Docker，localhost:5432）
```

完成标准：

- PostgreSQL 容器健康且启用了 `vector` 扩展；
- FastAPI 的 `GET /health` 返回 HTTP 200；
- pytest 自动化验证健康接口；
- Next.js 首页可启动；
- 前端实际请求后端健康接口，并能展示服务正常/不可用；
- 根目录有唯一 Git 仓库，真实环境变量不会被提交。

---

## 2. 最终项目结构

```text
E:\Living RAG\
├── apps/
│   ├── living-rag-api/          # FastAPI、LangGraph、RAG、业务工具与测试
│   └── living-rag-web/          # Next.js、TypeScript、Tailwind 前端
├── docs/                        # 架构、API、演示脚本和技术决策
├── infra/
│   └── postgres/                # pgvector 初始化 SQL
├── learning-notes/              # 每日学习与复习记录
├── outputs/                     # 截图、报告、演示产物
├── shared/                      # 两个项目共享的数据、Schema、Prompt、测试集
├── work/                        # 临时脚本和草稿
├── .env                         # 本机真实配置，Git 忽略
├── .env.example                 # 可提交的配置模板
├── .gitattributes               # 跨平台文本行尾规则
├── .gitignore                   # 忽略密钥、依赖、构建缓存等
├── docker-compose.yml           # PostgreSQL、API、Web 容器编排
└── README.md                    # 项目总说明
```

### 目录职责

| 目录 | 用途 |
|---|---|
| `E:\Living RAG` | 执行 `docker compose`、`git` 等项目级命令。 |
| `apps/living-rag-api` | 后端代码。当前通过 Docker 运行，后续放 SQLAlchemy、Alembic、LangGraph 和 RAG。 |
| `apps/living-rag-web` | 前端代码。执行 `npm.cmd run dev` 的位置。 |
| `shared` | Living RAG 与 Agent Reliability Lab 共用的领域 Schema、数据集和 Prompt。 |
| `learning-notes` | 每日复习日志，不放密钥。 |

---

## 3. 今天完成的内容

### 3.1 数据库：PostgreSQL + pgvector

使用 Docker Compose 启动：

```powershell
Set-Location "E:\Living RAG"
docker compose up -d postgres
docker compose ps
```

结果：

```text
living-rag-postgres-1 ... Up (healthy)
```

验证 pgvector：

```powershell
docker compose exec postgres psql -U living_rag -d living_rag -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

结果：

```text
vector | 0.8.5
```

理解：

- `pgvector` 是 PostgreSQL 扩展，后续用于保存文档 Chunk 的 Embedding 向量并做相似度检索；
- `healthy` 不只是“容器进程在运行”，还代表 PostgreSQL 已能接受连接；
- Docker Compose 的 `postgres_data` Volume 保存数据库数据；`docker compose down` 不会删除它；只有 `docker compose down -v` 才会删除数据卷。

### 3.2 后端：FastAPI 健康检查

后端关键文件：

```text
apps/living-rag-api/
├── Dockerfile
├── pyproject.toml
├── app/main.py
├── app/core/config.py
├── app/api/routes/health.py
└── tests/test_health.py
```

启动后端：

```powershell
Set-Location "E:\Living RAG"
docker compose up --build -d api
```

验证接口：

```powershell
Invoke-RestMethod http://localhost:8000/health
```

结果示例：

```text
status    : ok
service   : living-rag-api
timestamp : 2026-07-13T09:11:49.955127Z
```

核心理解：

```python
@router.get("/health")
async def read_health() -> HealthResponse:
```

表示 FastAPI 收到 `GET /health` 时执行该函数。`main.py` 通过：

```python
app.include_router(health_router)
```

将这个路由注册到整个 API 应用中。

Dockerfile 中：

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

表示容器启动时，Uvicorn 会导入 `app/main.py` 中名为 `app` 的 FastAPI 实例，并在容器内的 8000 端口监听请求。

### 3.3 自动化测试：pytest

创建并运行：

```powershell
docker compose exec api pytest -q
```

结果：

```text
1 passed
```

测试验证内容：

- `/health` 返回 HTTP 200；
- JSON 的 `status` 是 `ok`；
- JSON 的 `service` 是 `living-rag-api`；
- JSON 包含 `timestamp`。

遇到的问题：第一次输出 `no tests ran`。

原因：`tests/test_health.py` 当时尚未在正确目录保存或尚未被重新构建进容器。

解决：确认唯一正确路径：

```text
E:\Living RAG\apps\living-rag-api\tests\test_health.py
```

保存后重新执行：

```powershell
docker compose up --build -d api
docker compose exec api pytest -q
```

### 3.4 前端：Next.js + TypeScript + Tailwind CSS

在前端目录初始化：

```powershell
Set-Location "E:\Living RAG\apps\living-rag-web"
npx.cmd create-next-app@15.2.4 . --ts --tailwind --eslint --app --use-npm --import-alias "@/*" --no-src-dir
```

交互选择：

```text
Would you like to use Turbopack for `next dev`? → No
```

原因：当前阶段优先选择稳定、易排错的默认开发方式。

初始 Next.js 版本有安全提示，随后执行受控升级：

```powershell
npm.cmd install next@15.5.7
npm.cmd audit fix
npm.cmd ls next
```

最终版本：

```text
next@15.5.20
```

注意：没有执行 `npm audit fix --force`。因为 npm 给出的强制“修复”会降级到 `next@9.3.3`，会破坏当前 Next.js 15 的 App Router 工程。

启动前端：

```powershell
Set-Location "E:\Living RAG\apps\living-rag-web"
npm.cmd run dev
```

访问：

```text
http://localhost:3000
```

注意：在根目录 `E:\Living RAG` 运行 `npm.cmd run dev` 会报错，因为根目录没有 `package.json`。前端 npm 命令必须在 `apps/living-rag-web` 内执行。

### 3.5 前端真实健康检查与故障降级

前端在 `.env.local` 中使用：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`NEXT_PUBLIC_` 前缀表示该变量可在浏览器端代码中读取。

首页 `app/page.tsx` 使用：

- `"use client"`：允许该组件使用浏览器交互能力；
- `useState`：维护 `checking` / `online` / `offline` 三种状态；
- `useEffect`：组件首次加载时仅请求一次 `/health`；
- `fetch`：真实访问 FastAPI；
- `AbortController`：组件卸载时取消未完成请求。

验证过程：

```powershell
# API 正常时：浏览器显示“FastAPI 服务正常”
docker compose stop api

# 刷新浏览器后：显示“FastAPI 服务不可用”
docker compose start api

# 再刷新：恢复“FastAPI 服务正常”
```

这证明首页不是写死“服务正常”，而是有真实前后端联动和失败状态。

### 3.6 CSS 类型声明问题

VS Code 曾提示：

```text
找不到“./globals.css”的副作用导入的模块或类型声明。ts(2882)
```

但浏览器页面已能正确加载 CSS。这说明 Next.js 编译器理解 CSS 导入，但 VS Code TypeScript 服务暂时缺少相应类型声明。

解决：创建：

```text
apps/living-rag-web/types/styles.d.ts
```

写入：

```ts
declare module "*.css";
```

然后运行 VS Code 命令：

```text
TypeScript: Restart TS Server
```

结果：红色波浪线消失，错误计数归零。

### 3.7 Git、忽略规则与跨平台行尾

前端脚手架自动创建了嵌套 Git 仓库并带有模板提交：

```text
apps/living-rag-web/.git
3b40f87 Initial commit from Create Next App
```

由于本项目是 Monorepo，移除了前端嵌套 Git 元数据，并在根目录初始化唯一仓库：

```powershell
Set-Location "E:\Living RAG"
git init -b main
```

当前默认分支：

```text
main
```

实际验证忽略规则：

```powershell
git check-ignore -v .env
git check-ignore -v apps/living-rag-web/.env.local
git check-ignore -v apps/living-rag-web/node_modules
git check-ignore -v apps/living-rag-web/.next
```

确认不提交：

- `.env`；
- `.env.local`；
- `node_modules`；
- `.next`。

新增 `.gitattributes`，统一规则：

```gitattributes
* text=auto eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
*.ps1 text eol=crlf
```

作用：Docker/Linux 容器中的 Python、YAML、SQL、TypeScript、Dockerfile 等文本以 LF 保存；Windows 原生脚本保留 CRLF，避免跨平台产生整文件无意义 diff。

最终提交：

```text
0307838 feat: bootstrap Living RAG foundation
```

提交后：

```powershell
git status --short
```

没有任何输出，代表工作区干净。

---

## 4. 高频命令速查

### 回到项目根目录

```powershell
Set-Location "E:\Living RAG"
```

### 启动 / 查看 / 停止 Docker 服务

```powershell
docker compose up -d postgres api
docker compose ps
docker compose logs api
docker compose down
```

说明：`docker compose down` 不会删数据库 Volume；不要随意使用 `docker compose down -v`。

### 启动前端

```powershell
Set-Location "E:\Living RAG\apps\living-rag-web"
npm.cmd run dev
```

### 运行后端测试

```powershell
Set-Location "E:\Living RAG"
docker compose exec api pytest -q
```

### 检查服务

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### Git 日常检查

```powershell
Set-Location "E:\Living RAG"
git status --short
git log --oneline --max-count=5
```

---

## 5. 复习问题

尝试在不看答案的情况下回答：

1. 为什么 Docker Compose 中 API 连接数据库时使用主机名 `postgres`，而不是 `localhost`？
2. `pgvector` 在 Living RAG 后续的检索链路中负责什么？
3. `docker compose down` 和 `docker compose down -v` 的区别是什么？
4. `GET /health` 为什么既要手动请求验证，又要编写 pytest？
5. 为什么前端需要在 `apps/living-rag-web` 目录中运行 `npm.cmd run dev`？
6. 为什么给浏览器端环境变量加 `NEXT_PUBLIC_` 前缀？哪些信息绝不能使用这个前缀？
7. `"use client"` 的作用是什么？为什么不要给所有组件都加它？
8. 前端健康检查中 `useEffect(..., [])` 最后的空数组意味着什么？
9. `AbortController` 解决了什么异步资源问题？
10. 为什么不执行 `npm audit fix --force`？
11. 为什么删除前端的嵌套 `.git`，而在项目根目录创建唯一 Git 仓库？
12. `.gitignore` 与 `.gitattributes` 分别解决什么问题？

---

## 6. Day 2 起点

下一阶段目标：**数据库模型、Alembic 迁移与共享领域协议**。

计划创建的第一批核心表：

```text
documents
document_versions
document_chunks

users
membership_accounts
orders
refund_requests

chat_threads
chat_messages
agent_runs
agent_node_runs
tool_calls
audit_logs
```

Day 2 开始前的启动命令：

```powershell
Set-Location "E:\Living RAG"
docker compose up -d postgres api

Set-Location "E:\Living RAG\apps\living-rag-web"
npm.cmd run dev
```

Day 2 完成后应能通过 Alembic 在 PostgreSQL 中创建第一批领域表，并理解“逻辑文档”和“具体文档版本”必须分表的原因。

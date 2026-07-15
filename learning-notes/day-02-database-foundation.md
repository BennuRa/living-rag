# Day 2：数据库基础、ORM 模型与迁移

## 今日目标

完成 Living RAG 的第一组数据库基础能力：

- 使用 SQLAlchemy 2.x 定义 `Document` 与 `DocumentVersion`；
- 明确逻辑文档与内容版本的边界；
- 使用 Alembic 管理数据库结构迁移；
- 在 PostgreSQL 中验证主键、外键、枚举、JSONB、索引和约束；
- 为模型测试建立独立的 PostgreSQL 测试数据库与事务隔离。

## 核心领域设计

`Document` 表表示稳定的逻辑文档身份，例如《会员退款政策》；`DocumentVersion` 表表示该文档在某个时间点的完整内容快照，例如 v1、v2、v3。

关系为：

```text
documents (1) -> document_versions (N)
```

未来的 `document_chunks` 必须关联 `document_versions.id`，而不能只关联 `documents.id`。因为 chunk 是某个具体版本正文切分出来的结果。只有绑定具体版本，RAG 回答才能追溯到“哪份文档的哪一版内容”，并且可以在版本更新、重建 embedding 或排查冲突时复现来源。

## ORM 模型

模型文件：

```text
apps/living-rag-api/app/models/__init__.py
apps/living-rag-api/app/models/document.py
```

### Document

- `id` 使用 PostgreSQL 原生 UUID 主键，并通过 `uuid4` 自动生成；
- `title` 是稳定的文档标题；
- `status` 为 `active` / `archived`；
- `metadata_` 映射到数据库列名 `metadata`，类型为 PostgreSQL `JSONB`；
- `created_at` 与 `updated_at` 使用 `timezone=True`；
- `versions` 建立到 `DocumentVersion` 的双向 ORM 关系。

### DocumentVersion

- `id` 是版本自身的 UUID 主键；
- `document_id` 外键指向 `documents.id`，并设置 `ON DELETE CASCADE`；
- `version_number` 表示该文档内部的版本序号；
- `status` 为 `pending` / `processing` / `ready` / `failed`；
- `content` 保存该版本的完整正文；
- `content_hash` 用于内容去重和定位；
- `metadata_` 保存上传文件名、解析器版本等版本级信息。

### 约束与索引

- `CHECK (version_number > 0)`：版本号从 1 开始；
- `UNIQUE (document_id, version_number)`：同一份文档不能有两个相同版本号，但不同文档可以各自拥有 v1；
- `documents(status, created_at)`：支持按文档状态与创建时间查询；
- `document_versions(document_id, status)`：支持按文档和处理状态查询版本；
- `document_versions(content_hash)`：支持内容哈希定位与去重。

`metadata_` 使用 Python 属性名，是为了避开 SQLAlchemy `Base.metadata` 的保留属性；数据库列名仍然是 `metadata`。

枚举使用 `values_callable` 保存 `.value`，因此数据库中保存的是小写业务值，而不是 Python 成员名：

```text
active / archived
pending / processing / ready / failed
```

## Alembic 迁移

迁移基础文件：

```text
apps/living-rag-api/alembic.ini
apps/living-rag-api/alembic/env.py
apps/living-rag-api/alembic/script.py.mako
apps/living-rag-api/alembic/versions/
```

`env.py` 负责：

1. 导入 `app.models`，把模型注册到 `Base.metadata`；
2. 使用应用配置中的 `DATABASE_URL`；
3. 将 `Base.metadata` 提供给 Alembic 自动比较；
4. 在线迁移直接使用 SQLAlchemy URL 创建 PostgreSQL Engine。

第一条迁移：

```text
0d5401da8f2c_create_documents_and_document_versions.py
```

迁移已经执行：

```text
docker compose exec api alembic upgrade head
```

PostgreSQL 中实际确认存在：

- `documents`；
- `document_versions`；
- `alembic_version`；
- 两个小写值 PostgreSQL 枚举；
- 三条业务索引；
- 版本号检查约束、联合唯一约束和级联外键。

## 测试隔离

测试使用独立数据库：

```text
开发库：living_rag
测试库：living_rag_test
```

fixture 文件：

```text
apps/living-rag-api/tests/conftest.py
```

测试 URL 从已验证可用的 `DATABASE_URL` 派生，只替换数据库名，从而避免单独维护一份可能过期的密码。每个测试使用外层事务，测试结束后 rollback；测试 session 可以使用 `flush()` 让 PostgreSQL 真正执行插入和约束检查，但不把测试数据永久提交。

## 今日测试

测试文件：

```text
apps/living-rag-api/tests/test_document_models.py
```

已覆盖：

1. 创建文档与 v1，验证 UUID、双向关系、默认状态和 JSONB metadata；
2. 同一文档重复 `version_number = 1` 时，数据库抛出 `IntegrityError`；
3. 使用参数化测试验证 `version_number = 0` 和 `version_number = -1` 被 `CHECK` 约束拒绝；
4. 原有 `/health` 测试继续通过。

最终结果：

```text
5 passed, 1 warning
```

warning 来自 Starlette 对 `httpx` TestClient 兼容方式的弃用提示，不影响当前功能与测试结果，后续作为依赖维护项处理。

## 今日遇到的问题与解决方式

### Docker Desktop 引擎不可用

`dockerDesktopLinuxEngine` 管道不存在或拒绝访问时，先确认 Docker Desktop 已启动，并用 `docker version` 检查 Client 与 Server 是否同时存在。

### Alembic 使用了 `driver://` 占位符

最初生成的 Alembic 模板使用了 `alembic.ini` 中的占位连接字符串。通过让 `env.py` 直接使用应用 `DATABASE_URL`，并将整个 API 项目目录挂载到容器 `/app`，解决了容器内模板与宿主机项目文件不一致的问题。

### API 容器没有看到 Alembic 文件

原先只挂载了 `app/`：

```text
./apps/living-rag-api/app:/app/app
```

因此 Alembic 初始化文件只存在于容器层。最终改为挂载整个 API 项目：

```text
./apps/living-rag-api:/app
```

### 测试数据库密码认证失败

测试 URL 曾经单独拼接密码，可能与开发 URL 使用的真实密码不一致。最终 fixture 改为从已经验证可连接的 `DATABASE_URL` 派生 SQLAlchemy `URL` 对象，仅替换数据库名，并直接把 URL 对象传给 `create_engine`。

## 今日总结

今天完成了 Living RAG 从 ORM 模型到真实 PostgreSQL schema，再到可重复测试的完整基础链路：

```text
SQLAlchemy 模型
    -> Alembic 迁移
    -> PostgreSQL 真实约束
    -> 独立测试数据库
    -> pytest 业务规则验证
```

Day 3 之前需要提交 Git，并保留这条迁移和测试结果作为数据库基础能力的版本记录。

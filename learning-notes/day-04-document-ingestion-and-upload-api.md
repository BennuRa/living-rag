# Day 4：文档解析、版本摄入与上传 API

**日期：** 2026-07-22
**投入主题：** Markdown/TXT/PDF 解析、内容 hash、段落与 Chunk 切分、版本幂等、文档上传 API、版本历史 API、Schema 校验与全量回归。
**当天里程碑提交：** `a56f615 feat: add document upload and version ingestion`

---

## 今日目标

把 Day 3 的文档模型连接成可用上传链路：上传文件、解析正文、清洗校验、计算 hash、查重、创建版本、切分 Chunk 并返回结果；同时提供按 `policy_key` 查询版本历史的接口。

## 1. 文档解析层

文件：`apps/living-rag-api/app/services/document_parsing.py`。

支持 `.md`、`.markdown`、`.txt` 和 `.pdf`。解析层只把上传字节转换成干净正文，不创建数据库对象。文本按 UTF-8 解码，PDF 使用 `pypdf` 提取文字；不支持类型、编码错误、损坏 PDF、空文档和无文字 PDF 统一转换为明确 `ValueError`。

## 2. DocumentIngestionService

文件：`apps/living-rag-api/app/services/document_ingestion.py`。

完整正文使用 SHA-256 计算 `content_hash`。同一逻辑文档下命中相同 hash 时直接返回旧版本，保证重复上传幂等，不重复创建版本和 Chunk。

新内容先校验请求版本号必须等于下一个版本号，再创建 `DocumentVersion`。新版本通过 `supersedes_version_id` 指向上一版本，形成可追溯版本链。

`split_into_paragraphs()` 按空行分段并清理首尾空白；`split_into_chunks()` 尽量把完整段落合并到 `max_chars` 限制内。单个段落超限时保留为一个 Chunk，不能先生成空 Chunk；非正限制值直接拒绝。

`create_document_chunks()` 使用 `enumerate(chunks)` 生成稳定的 `chunk_index`，同时保存 Chunk 正文和独立的 Chunk hash。

摄入顺序是：计算 hash -> 查重 -> 校验版本号 -> 创建版本 -> 切分正文 -> 创建 Chunk -> 返回版本。查重必须早于版本号校验。

## 3. 上传与版本 API

`POST /documents/upload` 使用 multipart 表单和 `UploadFile`，每个表单字段显式使用 `Form(...)`，再构造 `DocumentUploadForm` 做时区、过期时间、枚举和额外字段校验。路由调用 parser 和 ingestion service，成功 `commit()`，失败 `rollback()`，`ValueError` 返回 HTTP 422。

响应包含文档 ID、版本 ID、版本号、完整正文 hash、来源类型、生效时间、过期时间、原始文件名、内容类型和 Chunk 数量。

`GET /documents/{policy_key}/versions` 按版本号降序返回 `DocumentVersionListItem`；未知策略键返回空列表。ORM 对象先转换为 response schema，避免直接暴露数据库对象。

## 4. 测试与验证

新增测试覆盖解析、hash、段落与 Chunk 切分、版本链、重复摄入、Chunk hash、Schema、上传成功与失败、版本列表和事务回滚。

最终全量验证：

```text
95 passed, 1 warning
```

warning 是 Starlette 对当前 `httpx` TestClient 用法的弃用提示，不影响功能和测试结果。

## 5. 遇到的问题与解决方案

损坏 PDF 的底层异常被 parser 转换为业务错误；multipart 模型整体绑定导致 `body.form` 缺失，改为每个字段显式 `Form(...)`；重复内容在版本号校验前返回已有版本；`DocumentChunk` 独立模块后按真实导入路径引用。

## 6. 今日复习清单

1. 为什么完整版本 hash 和 Chunk hash 都需要保存？
2. 为什么查重必须发生在版本号校验之前？
3. `commit()`、`flush()`、`rollback()` 分别做什么？
4. 为什么上传 API 要把 parser、service 和 response schema 分层？
5. `enumerate(chunks)` 如何生成稳定的 `chunk_index`？
6. 为什么超长首段不能先追加空 Chunk？
7. 为什么未知 `policy_key` 返回空列表？

## 7. 下一天的起点

Day 4 提交：`a56f615 feat: add document upload and version ingestion`。下一步围绕版本治理状态、生效窗口、冲突判断和后续 embedding/RAG 检索展开；继续遵循一次实现一个完整核心 `def`，先审查业务代码，再编写测试。

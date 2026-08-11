"use client";

import { FormEvent, useEffect, useState } from "react";

const capabilities = [
  {
    code: "VERSIONED",
    title: "政策版本化",
    description: "每条规则都绑定具体版本、生效时间和原始文档片段。",
  },
  {
    code: "GOVERNED",
    title: "知识可治理",
    description: "正式政策、FAQ 和临时公告都可追踪、比较和人工审核。",
  },
  {
    code: "GROUNDED",
    title: "回答有依据",
    description: "每个结论都可以回溯到具体文档版本和引用原文。",
  },
];

type ApiStatus = "checking" | "online" | "offline";

type HealthResponse = {
  status: string;
  service: string;
  timestamp: string;
};

type Citation = {
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  quote: string;
  relevance_score: number | null;

  document_title?: string;
  version_number?: string | number;
  source_type?: string;
  governance_status?: string;
  effective_at?: string | null;
  expires_at?: string | null;
};

type ChatRequest = {
  user_id: string;
  question: string;
  limit: number;
};

type ChatResponse = {
  trace_id: string;
  answer: string;
  conditions: string[];
  citation_valid: boolean;
  citations: Citation[];
  confidence: number;
  limitations: string[];
};

type DemoUser = {
  id: string;
  external_id: string;
  display_name: string;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const statusLabels: Record<ApiStatus, string> = {
  checking: "正在检查后端服务",
  online: "后端服务在线",
  offline: "后端服务不可用",
};

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "接口暂未返回";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return parsedDate.toLocaleString("zh-CN");
}

export default function Home() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

  const [question, setQuestion] = useState("");
  const [userId, setUserId] = useState("");
  const [users, setUsers] = useState<DemoUser[]>([]);
  const [limit, setLimit] = useState(5);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function checkApiHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`健康检查失败：${response.status}`);
        }

        const payload = (await response.json()) as HealthResponse;

        if (payload.status !== "ok" || payload.service !== "living-rag-api") {
          throw new Error("健康检查返回内容异常");
        }

        setApiStatus("online");
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setApiStatus("offline");
      }
    }

    void checkApiHealth();

    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadUsers() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/users`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`样例用户加载失败：${response.status}`);
        }

        const payload = (await response.json()) as DemoUser[];
        setUsers(payload);
        if (payload.length > 0) {
          setUserId((current) => current || payload[0].id);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setErrorMessage("样例用户加载失败，请确认已经运行 Seed 脚本。");
      }
    }

    void loadUsers();

    return () => {
      controller.abort();
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();
    const trimmedUserId = userId.trim();

    if (!trimmedQuestion) {
      setErrorMessage("请输入问题后再提交。");
      return;
    }

    if (!trimmedUserId) {
      setErrorMessage("请输入有效的用户 ID。");
      return;
    }

    if (limit < 1 || limit > 20) {
      setErrorMessage("检索数量必须在 1 到 20 之间。");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setChatResponse(null);

    const requestBody: ChatRequest = {
      user_id: trimmedUserId,
      question: trimmedQuestion,
      limit,
    };

    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const detail = await response.text();

        throw new Error(
          detail || `问答请求失败，HTTP 状态码：${response.status}`,
        );
      }

      const payload = (await response.json()) as ChatResponse;

      setChatResponse(payload);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "问答请求失败，请稍后重试。",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="site-shell">
      <nav className="topbar" aria-label="主导航">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            LR
          </span>

          <span className="brand-name">LIVING RAG</span>
        </div>

        <p className="build-status">
          <span className="status-dot" aria-hidden="true" />
          第 7 天 / 政策问答工作台
        </p>
      </nav>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">电商售后政策智能问答</p>

          <h1>
            让知识持续更新，
            <br />
            <em>让答案有迹可循。</em>
          </h1>

          <p className="hero-description">
            面向退款、配送、会员权益和客户服务政策的动态知识库 Agent。
            <br />
            检索当前证据，返回可追溯的回答。
          </p>
        </div>

        <div className="hero-side">
          <div
            className={`api-status api-status--${apiStatus}`}
            aria-live="polite"
          >
            <span className="pulse" aria-hidden="true" />

            <code>GET /health</code>

            <span>{statusLabels[apiStatus]}</span>
          </div>

          <p className="hero-side-note">
            当前版本聚焦第一周 MVP：带引用的政策问答、证据展示和运行 Trace。
          </p>
        </div>
      </section>

      <section className="answer-workspace" aria-labelledby="answer-title">
        <div className="workspace-heading">
          <p className="eyebrow">第一周 MVP / 带引用问答</p>

          <h2 id="answer-title">向政策 Agent 提问</h2>

          <p>
            输入一个售后政策问题，系统会调用 LangGraph 工作流，返回回答、适用条件、引用证据和 Trace ID。
          </p>
        </div>

        <form className="question-form" onSubmit={handleSubmit}>
          <label htmlFor="user-id">演示用户</label>

          {users.length > 0 ? (
            <select
              id="user-id"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
            >
              {users.map((user) => (
                <option key={user.id} value={user.id}>
                  {user.external_id} - {user.display_name}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="user-id"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              placeholder="正在加载样例用户..."
              autoComplete="off"
            />
          )}

          <label htmlFor="question">你的问题</label>

          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="例如：目前普通会员签收后多久可以申请退款？"
            rows={5}
          />

          <label htmlFor="limit">检索数量</label>

          <input
            id="limit"
            type="number"
            min={1}
            max={20}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />

          <button type="submit" disabled={isLoading}>
            {isLoading ? "正在检索并生成回答…" : "提交问题"}
          </button>
        </form>

        {errorMessage ? (
          <div className="request-error" role="alert">
            <strong>请求失败</strong>
            <p>{errorMessage}</p>
          </div>
        ) : null}

        {chatResponse ? (
          <div className="answer-result">
            <div className="answer-panel">
              <div className="result-heading">
                <p className="eyebrow">Agent 回答</p>

                <span className="confidence">
                  置信度：{Math.round(chatResponse.confidence * 100)}%
                </span>
              </div>

              <p className="answer-text">{chatResponse.answer}</p>

              {chatResponse.conditions.length > 0 ? (
                <div className="conditions-block">
                  <h3>适用条件</h3>

                  <ul>
                    {chatResponse.conditions.map((condition, index) => (
                      <li key={`${condition}-${index}`}>{condition}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {chatResponse.limitations.length > 0 ? (
                <div className="limitations-block">
                  <h3>限制说明</h3>

                  <ul>
                    {chatResponse.limitations.map((limitation, index) => (
                      <li key={`${limitation}-${index}`}>{limitation}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>

            <div
              className={`citation-status ${
                chatResponse.citation_valid
                  ? "citation-status--valid"
                  : "citation-status--invalid"
              }`}
              role="status"
            >
              {chatResponse.citation_valid
                ? "引用校验通过：回答具备可追溯证据。"
                : "安全提示：引用校验未通过，当前回答不能作为可靠政策依据。"}
            </div>

            <section
              className="citations-panel"
              aria-labelledby="citations-title"
            >
              <div className="result-heading">
                <div>
                  <p className="eyebrow">来源证据</p>

                  <h3 id="citations-title">引用片段</h3>
                </div>

                <span>{chatResponse.citations.length} 条证据</span>
              </div>

              {chatResponse.citations.length === 0 ? (
                <p className="empty-state">当前回答没有可展示的引用。</p>
              ) : (
                <div className="citation-grid">
                  {chatResponse.citations.map((citation, index) => (
                    <article
                      className="citation-card"
                      key={citation.chunk_id}
                    >
                      <div className="citation-card__topline">
                        <span>
                          证据 {String(index + 1).padStart(2, "0")}
                        </span>

                        <span>
                          相关度：
                          {citation.relevance_score === null
                            ? "暂缺"
                            : citation.relevance_score.toFixed(3)}
                        </span>
                      </div>

                      <h4>
                        {citation.document_title ?? "文档标题：接口暂未返回"}
                      </h4>

                      <dl>
                        <div>
                          <dt>文档版本</dt>

                          <dd>
                            {citation.version_number ?? "接口暂未返回"}
                          </dd>
                        </div>

                        <div>
                          <dt>来源类型</dt>

                          <dd>
                            {citation.source_type ?? "接口暂未返回"}
                          </dd>
                        </div>

                        <div>
                          <dt>治理状态</dt>

                          <dd>
                            {citation.governance_status ?? "接口暂未返回"}
                          </dd>
                        </div>

                        <div>
                          <dt>生效时间</dt>

                          <dd>{formatDate(citation.effective_at)}</dd>
                        </div>

                        <div>
                          <dt>失效时间</dt>

                          <dd>{formatDate(citation.expires_at)}</dd>
                        </div>
                      </dl>

                      <blockquote>{citation.quote}</blockquote>

                      <p className="citation-identifiers">
                        文档 ID：{citation.document_id}
                        <br />
                        文档版本 ID：{citation.document_version_id}
                        <br />
                        Chunk ID：{citation.chunk_id}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <p className="trace-id">
              本次运行 Trace ID：
              <br />
              <code>{chatResponse.trace_id}</code>
            </p>
          </div>
        ) : null}
      </section>

      <section className="capability-grid" aria-label="核心能力">
        {capabilities.map((capability, index) => (
          <article className="capability-card" key={capability.code}>
            <span className="card-index">
              {String(index + 1).padStart(2, "0")}
            </span>

            <p className="capability-code">{capability.code}</p>

            <h2>{capability.title}</h2>

            <p className="capability-description">
              {capability.description}
            </p>
          </article>
        ))}
      </section>

      <footer className="footer">
        <span>30 天 Agent 系统学习计划 / Living RAG</span>
        <span>FastAPI / LangGraph / PostgreSQL / Next.js</span>
      </footer>
    </main>
  );
}

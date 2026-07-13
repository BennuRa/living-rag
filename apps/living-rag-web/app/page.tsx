"use client";

import { useEffect, useState } from "react";

const capabilities = [
  {
    code: "VERSIONED",
    title: "政策版本",
    description: "将每一项规则锚定到具体版本、生效时间与原文证据。",
  },
  {
    code: "GOVERNED",
    title: "冲突治理",
    description: "让正式政策、FAQ 与临时公告的分歧进入可审计的人工审核。",
  },
  {
    code: "GROUNDED",
    title: "可信回答",
    description: "每次结论均附带来源、适用条件和可复查的引用片段。",
  },
];

type ApiStatus = "checking" | "online" | "offline";

type HealthResponse = {
  status: string;
  service: string;
  timestamp: string;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const statusLabels: Record<ApiStatus, string> = {
  checking: "正在检查 FastAPI 服务",
  online: "FastAPI 服务正常",
  offline: "FastAPI 服务不可用",
};

export default function Home() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();

    async function checkApiHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Health check failed: ${response.status}`);
        }

        const payload = (await response.json()) as HealthResponse;

        if (payload.status !== "ok" || payload.service !== "living-rag-api") {
          throw new Error("Unexpected health response");
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
          DAY 01 / FOUNDATION
        </p>
      </nav>

      <section className="hero">
        <p className="eyebrow">E-COMMERCE POLICY INTELLIGENCE</p>

        <h1>
          让每条政策结论
          <br />
          <em>保持新鲜，也保持可追溯。</em>
        </h1>

        <p className="hero-description">
          面向退款、配送、换货与会员服务的动态知识治理 Agent。
          <br />
          今天，工程底座已经就绪。
        </p>

        <div
          className={`api-status api-status--${apiStatus}`}
          aria-live="polite"
        >
          <span className="pulse" aria-hidden="true" />
          <code>GET /health</code>
          <span>{statusLabels[apiStatus]}</span>
        </div>
      </section>

      <section className="capability-grid" aria-label="Living RAG 核心能力">
        {capabilities.map((capability, index) => (
          <article className="capability-card" key={capability.code}>
            <span className="card-index">0{index + 1}</span>
            <p className="capability-code">{capability.code}</p>
            <h2>{capability.title}</h2>
            <p className="capability-description">{capability.description}</p>
          </article>
        ))}
      </section>

      <footer className="footer">
        <span>BUILDING IN PUBLIC · 30 DAY AGENT SYSTEM</span>
        <span>FASTAPI / LANGGRAPH / PGVECTOR / NEXT.JS</span>
      </footer>
    </main>
  );
}
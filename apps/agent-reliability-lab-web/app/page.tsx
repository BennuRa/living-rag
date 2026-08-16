"use client";

import type { FormEvent, ReactNode } from "react";
import { useEffect, useState } from "react";

type TraceMessage = {
  role: string;
  content: string;
  created_at?: string | null;
};

type TraceNode = {
  node_name: string;
  status?: string | null;
  latency_ms?: number | null;
  input_summary?: string | null;
  output_summary?: string | null;
};

type TraceToolCall = {
  tool_name: string;
  status?: string | null;
  latency_ms?: number | null;
  input_summary?: string | null;
  output_summary?: string | null;
  error_message?: string | null;
};

type TraceApprovalTask = {
  approval_task_id: string;
  status?: string | null;
  action?: string | null;
  reason?: string | null;
};

type TraceAuditLog = {
  action: string;
  status?: string | null;
  actor?: string | null;
  detail?: string | null;
};

type TraceReplay = {
  trace_id: string;
  run_status: string;
  intent?: string | null;
  workflow_version?: string | null;
  final_answer?: string | null;
  messages: TraceMessage[];
  nodes: TraceNode[];
  tool_calls: TraceToolCall[];
  approval_tasks: TraceApprovalTask[];
  audit_logs: TraceAuditLog[];
  citations: Record<string, unknown>[];
};

type RunConfig = {
  workflow_version: string;
  prompt_version?: string | null;
  timeout_seconds?: number | null;
  model_name?: string | null;
  max_concurrency?: number | null;
  max_retries?: number | null;
  cost_budget?: number | null;
};

type EvaluationRun = {
  evaluation_run_id: string;
  dataset_id: string;
  config: RunConfig;
  status: string;
  total_cases: number;
  completed_cases: number;
  succeeded_cases: number;
  failed_cases: number;
  timed_out_cases: number;
  started_at?: string | null;
  completed_at?: string | null;
};

type AgentTask = {
  case_id: string;
  name: string;
  category: string;
  user_input: string;
  expected_route?: string | null;
  expected_behavior?: string[];
  tags?: string[];
};

type EvaluationCase = {
  evaluation_case_id: string;
  dataset_id: string;
  task: AgentTask;
  created_at?: string | null;
};

type AgentRunResult = {
  status: string;
  final_answer?: string | null;
  citations?: Record<string, unknown>[];
  trace_id?: string | null;
  latency_ms?: number | null;
  token_usage?: Record<string, unknown> | null;
  estimated_cost?: number | null;
  error_message?: string | null;
  raw_response?: Record<string, unknown> | null;
};

type CaseRun = {
  case_run_id: string;
  evaluation_run_id: string;
  evaluation_case_id: string;
  status: string;
  attempt_count: number;
  result?: AgentRunResult | null;
  trace_id?: string | null;
  latency_ms?: number | null;
  token_usage?: Record<string, unknown> | null;
  estimated_cost?: number | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
};

type EvaluationCaseDetail = {
  evaluation_case: EvaluationCase;
  case_run: CaseRun;
};

const demoTraceId = "dcd2f7f7-d5c5-4a8c-a13e-ac33f4429217";

function unwrapList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) {
    return payload as T[];
  }

  if (
    payload &&
    typeof payload === "object" &&
    "value" in payload &&
    Array.isArray((payload as { value: unknown }).value)
  ) {
    return (payload as { value: T[] }).value;
  }

  return [];
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    succeeded: "成功",
    failed: "失败",
    timed_out: "超时",
    pending: "等待中",
    running: "运行中",
    cancelled: "已取消",
  };

  return labels[status] || status;
}

function formatLatency(latencyMs?: number | null) {
  if (latencyMs === null || latencyMs === undefined) {
    return "未记录";
  }

  return `${latencyMs.toFixed(1)} ms`;
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) {
    return "未记录";
  }

  if (typeof value === "string") {
    return value;
  }

  return JSON.stringify(value, null, 2);
}

function formatDate(value?: string | null) {
  if (!value) {
    return "未记录";
  }

  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HomePage() {
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null);
  const [cases, setCases] = useState<EvaluationCaseDetail[]>([]);
  const [selectedCase, setSelectedCase] =
    useState<EvaluationCaseDetail | null>(null);

  const [traceId, setTraceId] = useState("");
  const [trace, setTrace] = useState<TraceReplay | null>(null);

  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingCases, setLoadingCases] = useState(false);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    void loadRuns();
  }, []);

  async function loadRuns() {
    setLoadingRuns(true);
    setErrorMessage("");

    try {
      const response = await fetch("/lab-api/evaluation-runs", {
        headers: {
          Accept: "application/json",
        },
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "评测运行列表加载失败",
        );
      }

      const nextRuns = unwrapList<EvaluationRun>(payload);
      setRuns(nextRuns);

      if (nextRuns.length > 0) {
        await selectRun(nextRuns[0]);
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "评测运行列表加载失败",
      );
    } finally {
      setLoadingRuns(false);
    }
  }

  async function selectRun(run: EvaluationRun) {
    setSelectedRun(run);
    setSelectedCase(null);
    setTrace(null);
    setTraceId("");
    setLoadingCases(true);
    setErrorMessage("");

    try {
      const response = await fetch(
        `/lab-api/evaluation-runs/${encodeURIComponent(
          run.evaluation_run_id,
        )}/cases`,
        {
          headers: {
            Accept: "application/json",
          },
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "Case 列表加载失败",
        );
      }

      setCases(unwrapList<EvaluationCaseDetail>(payload));
    } catch (error) {
      setCases([]);
      setErrorMessage(
        error instanceof Error ? error.message : "Case 列表加载失败",
      );
    } finally {
      setLoadingCases(false);
    }
  }

  async function loadTraceById(nextTraceId: string) {
    const normalizedTraceId = nextTraceId.trim();

    if (!normalizedTraceId) {
      setErrorMessage("请输入 Trace ID");
      setTrace(null);
      return;
    }

    setTraceId(normalizedTraceId);
    setLoadingTrace(true);
    setErrorMessage("");

    try {
      const response = await fetch(
        `/lab-api/traces/${encodeURIComponent(normalizedTraceId)}`,
        {
          headers: {
            Accept: "application/json",
          },
        },
      );

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string"
            ? payload.detail
            : "Trace 查询失败",
        );
      }

      setTrace(payload as TraceReplay);
    } catch (error) {
      setTrace(null);
      setErrorMessage(
        error instanceof Error ? error.message : "Trace 查询失败",
      );
    } finally {
      setLoadingTrace(false);
    }
  }

  async function loadTrace(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    await loadTraceById(traceId);
  }

  async function selectCase(caseDetail: EvaluationCaseDetail) {
    setSelectedCase(caseDetail);

    const nextTraceId =
      caseDetail.case_run.trace_id ||
      caseDetail.case_run.result?.trace_id ||
      "";

    if (nextTraceId) {
      await loadTraceById(nextTraceId);
    } else {
      setTrace(null);
      setTraceId("");
      setErrorMessage("当前 Case 没有可回放的 Trace ID");
    }
  }

  async function loadDemoTrace() {
    await loadTraceById(demoTraceId);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            RL
          </span>
          <div>
            <p className="product-name">Agent Reliability Lab</p>
            <p className="product-context">Living RAG / observability</p>
          </div>
        </div>

        <div className="connection-indicator">
          <span className="connection-dot" aria-hidden="true" />
          <span>API 8010</span>
        </div>
      </header>

      <section className="hero-row">
        <div>
          <p className="eyebrow">Evaluation console / Day 20</p>
          <h1>运行回放</h1>
          <p className="intro">
            从评测 Run 进入具体 Case，再回放 Living RAG 的原始 Trace。
            每一步都保留状态、延迟、工具、引用与风险动作。
          </p>
        </div>

        <div className="hero-meta">
          <span className="meta-label">当前工作流</span>
          <strong>Living RAG</strong>
          <span className="meta-label">运行数量</span>
          <strong>{runs.length}</strong>
        </div>
      </section>

      <section className="query-bar" aria-label="Trace 查询">
        <form onSubmit={loadTrace} className="trace-form">
          <label htmlFor="trace-id">Trace ID</label>
          <div className="input-row">
            <input
              id="trace-id"
              value={traceId}
              onChange={(event) => setTraceId(event.target.value)}
              placeholder="输入或粘贴 Trace ID"
              spellCheck={false}
            />
            <button type="submit" disabled={loadingTrace}>
              {loadingTrace ? "读取中..." : "加载 Trace"}
            </button>
          </div>
        </form>

        <button
          type="button"
          className="quiet-button"
          onClick={loadDemoTrace}
          disabled={loadingTrace}
        >
          使用最近示例
        </button>
      </section>

      {errorMessage ? (
        <section className="notice error-notice" role="alert">
          <span className="notice-symbol" aria-hidden="true">
            !
          </span>
          <div>
            <strong>无法完成查询</strong>
            <p>{errorMessage}</p>
          </div>
        </section>
      ) : null}

      <section className="lab-grid">
        <aside className="run-rail">
          <div className="rail-heading">
            <div>
              <p className="eyebrow">Runs</p>
              <h2>评测运行</h2>
            </div>
            <span className="record-count">{runs.length}</span>
          </div>

          {loadingRuns ? (
            <div className="rail-state">正在读取 Run 列表...</div>
          ) : runs.length === 0 ? (
            <div className="rail-state">
              <strong>暂无评测运行</strong>
              <span>完成一次批量运行后，这里会显示结果。</span>
            </div>
          ) : (
            <div className="run-list">
              {runs.map((run) => (
                <button
                  type="button"
                  className={`run-item ${
                    selectedRun?.evaluation_run_id === run.evaluation_run_id
                      ? "is-selected"
                      : ""
                  }`}
                  key={run.evaluation_run_id}
                  onClick={() => void selectRun(run)}
                >
                  <span className="run-item-topline">
                    <span className={`mini-status status-${run.status}`} />
                    <strong>{statusLabel(run.status)}</strong>
                    <span>{run.total_cases} cases</span>
                  </span>
                  <code>{run.evaluation_run_id}</code>
                  <span className="run-item-meta">
                    {run.config.workflow_version} ·{" "}
                    {formatDate(run.completed_at)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="case-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Cases</p>
              <h2>任务执行</h2>
            </div>

            {selectedRun ? (
              <span className="record-count">
                {selectedRun.completed_cases}/{selectedRun.total_cases} completed
              </span>
            ) : null}
          </div>

          {selectedRun ? (
            <div className="run-summary">
              <div>
                <span className="cell-label">Run ID</span>
                <code>{selectedRun.evaluation_run_id}</code>
              </div>
              <div>
                <span className="cell-label">Workflow</span>
                <strong>{selectedRun.config.workflow_version}</strong>
              </div>
              <div>
                <span className="cell-label">成功</span>
                <strong className="success-value">
                  {selectedRun.succeeded_cases}
                </strong>
              </div>
              <div>
                <span className="cell-label">失败 / 超时</span>
                <strong>
                  {selectedRun.failed_cases} / {selectedRun.timed_out_cases}
                </strong>
              </div>
            </div>
          ) : null}

          {loadingCases ? (
            <div className="panel-state">正在读取 Case 列表...</div>
          ) : cases.length === 0 ? (
            <div className="panel-state">
              <strong>暂无 Case</strong>
              <span>请选择一个评测运行查看任务执行结果。</span>
            </div>
          ) : (
            <div className="case-list">
              {cases.map((caseDetail) => {
                const task = caseDetail.evaluation_case.task;
                const caseRun = caseDetail.case_run;
                const caseTraceId =
                  caseRun.trace_id || caseRun.result?.trace_id;

                return (
                  <article
                    className={`case-item ${
                      selectedCase?.evaluation_case.evaluation_case_id ===
                      caseDetail.evaluation_case.evaluation_case_id
                        ? "is-selected"
                        : ""
                    }`}
                    key={caseDetail.evaluation_case.evaluation_case_id}
                  >
                    <button
                      type="button"
                      className="case-main-button"
                      onClick={() => void selectCase(caseDetail)}
                    >
                      <span className="case-number">{task.case_id}</span>
                      <strong>{task.name}</strong>
                      <p>{task.user_input}</p>
                    </button>

                    <div className="case-facts">
                      <span className={`status-text status-${caseRun.status}`}>
                        {statusLabel(caseRun.status)}
                      </span>
                      <span>{formatLatency(caseRun.latency_ms)}</span>
                      <span>attempt {caseRun.attempt_count}</span>
                    </div>

                    <div className="case-actions">
                      {caseTraceId ? (
                        <button
                          type="button"
                          className="trace-link"
                          onClick={() => void loadTraceById(caseTraceId)}
                        >
                          回放 Trace
                        </button>
                      ) : (
                        <span className="muted-text-small">无 Trace</span>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </section>

      {loadingTrace ? (
        <section className="loading-console" aria-live="polite">
          <span className="loading-bar" />
          <span>正在从 Living RAG 读取运行记录...</span>
        </section>
      ) : null}

      {trace ? (
        <div className="trace-workspace">
          <section className="run-overview">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Trace replay</p>
                <h2>执行概览</h2>
              </div>
              <span className={`status-badge status-${trace.run_status}`}>
                <span className="status-dot" aria-hidden="true" />
                {statusLabel(trace.run_status)}
              </span>
            </div>

            {selectedCase ? (
              <div className="selected-case-strip">
                <span>当前 Case</span>
                <strong>{selectedCase.evaluation_case.task.case_id}</strong>
                <span>{selectedCase.evaluation_case.task.name}</span>
              </div>
            ) : null}

            <div className="overview-grid">
              <div className="overview-cell trace-cell">
                <span className="cell-label">Trace ID</span>
                <code>{trace.trace_id}</code>
              </div>
              <div className="overview-cell">
                <span className="cell-label">Intent</span>
                <strong>{trace.intent || "未记录"}</strong>
              </div>
              <div className="overview-cell">
                <span className="cell-label">Workflow</span>
                <strong>{trace.workflow_version || "未记录"}</strong>
              </div>
              <div className="overview-cell">
                <span className="cell-label">Messages</span>
                <strong>{trace.messages.length}</strong>
              </div>
            </div>
          </section>

          <section className="answer-section">
            <div className="section-heading compact-heading">
              <div>
                <p className="eyebrow">Final answer</p>
                <h2>最终回答</h2>
              </div>
              <span className="record-count">
                {trace.citations.length} citations
              </span>
            </div>

            <div className="answer-panel">
              {trace.final_answer ? (
                <p>{trace.final_answer}</p>
              ) : (
                <p className="muted-text">
                  当前 Trace 没有记录最终回答。
                </p>
              )}
            </div>
          </section>

          <section className="execution-grid">
            <div className="timeline-section">
              <div className="section-heading compact-heading">
                <div>
                  <p className="eyebrow">Conversation</p>
                  <h2>消息时间线</h2>
                </div>
                <span className="record-count">
                  {trace.messages.length} records
                </span>
              </div>

              <div className="message-list">
                {trace.messages.length > 0 ? (
                  trace.messages.map((message, index) => (
                    <article
                      className="message-row"
                      key={`${message.role}-${index}`}
                    >
                      <div className="message-index">
                        {String(index + 1).padStart(2, "0")}
                      </div>
                      <div className="message-content">
                        <div className="message-header">
                          <strong>{message.role}</strong>
                          <time>{message.created_at || "时间未记录"}</time>
                        </div>
                        <p>{message.content || "空消息"}</p>
                      </div>
                    </article>
                  ))
                ) : (
                  <EmptyCollection label="消息" />
                )}
              </div>
            </div>

            <div className="evidence-column">
              <EvidenceSection
                title="节点"
                eyebrow="Nodes"
                count={trace.nodes.length}
              >
                {trace.nodes.length > 0 ? (
                  trace.nodes.map((node, index) => (
                    <article
                      className="evidence-row"
                      key={`${node.node_name}-${index}`}
                    >
                      <div className="evidence-title">
                        <strong>{node.node_name}</strong>
                        <span>{formatLatency(node.latency_ms)}</span>
                      </div>
                      <span className="evidence-status">
                        {node.status || "未记录"}
                      </span>
                      {node.output_summary ? (
                        <pre>{node.output_summary}</pre>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <EmptyCollection label="节点" />
                )}
              </EvidenceSection>

              <EvidenceSection
                title="工具调用"
                eyebrow="Tool calls"
                count={trace.tool_calls.length}
              >
                {trace.tool_calls.length > 0 ? (
                  trace.tool_calls.map((tool, index) => (
                    <article
                      className="evidence-row"
                      key={`${tool.tool_name}-${index}`}
                    >
                      <div className="evidence-title">
                        <strong>{tool.tool_name}</strong>
                        <span>{formatLatency(tool.latency_ms)}</span>
                      </div>
                      <span className="evidence-status">
                        {tool.status || "未记录"}
                      </span>
                      {tool.error_message ? (
                        <p className="error-text">{tool.error_message}</p>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <EmptyCollection label="工具调用" />
                )}
              </EvidenceSection>
            </div>
          </section>

          <section className="lower-grid">
            <EvidenceSection
              title="审批任务"
              eyebrow="Approval tasks"
              count={trace.approval_tasks.length}
            >
              {trace.approval_tasks.length > 0 ? (
                trace.approval_tasks.map((task) => (
                  <article className="detail-row" key={task.approval_task_id}>
                    <div>
                      <strong>{task.action || "未命名动作"}</strong>
                      <p>{task.reason || "没有记录原因"}</p>
                    </div>
                    <span>{task.status || "未记录"}</span>
                  </article>
                ))
              ) : (
                <EmptyCollection label="审批任务" />
              )}
            </EvidenceSection>

            <EvidenceSection
              title="审计日志"
              eyebrow="Audit logs"
              count={trace.audit_logs.length}
            >
              {trace.audit_logs.length > 0 ? (
                trace.audit_logs.map((log, index) => (
                  <article className="detail-row" key={`${log.action}-${index}`}>
                    <div>
                      <strong>{log.action}</strong>
                      <p>{log.detail || "没有记录详情"}</p>
                    </div>
                    <span>{log.status || "未记录"}</span>
                  </article>
                ))
              ) : (
                <EmptyCollection label="审计日志" />
              )}
            </EvidenceSection>
          </section>

          <section className="citations-section">
            <div className="section-heading compact-heading">
              <div>
                <p className="eyebrow">Evidence</p>
                <h2>引用</h2>
              </div>
              <span className="record-count">
                {trace.citations.length} records
              </span>
            </div>

            {trace.citations.length > 0 ? (
              <div className="citation-list">
                {trace.citations.map((citation, index) => (
                  <pre key={index}>{formatValue(citation)}</pre>
                ))}
              </div>
            ) : (
              <div className="citation-empty">
                当前 Trace 没有记录引用。
              </div>
            )}
          </section>
        </div>
      ) : null}
    </main>
  );
}

function EmptyCollection({ label }: { label: string }) {
  return (
    <div className="collection-empty">
      <span className="empty-mark" aria-hidden="true">
        -
      </span>
      <span>没有记录的{label}</span>
    </div>
  );
}

function EvidenceSection({
  title,
  eyebrow,
  count,
  children,
}: {
  title: string;
  eyebrow: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section className="evidence-section">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
        <span className="record-count">{count}</span>
      </div>
      <div className="evidence-list">{children}</div>
    </section>
  );
}
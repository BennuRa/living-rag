"use client";

import { useEffect, useMemo, useState } from "react";

type ReviewDecision = "approve" | "reject" | "invalidate_document";
type ReviewTaskStatus = "pending" | "in_progress" | "completed" | "cancelled";

type ReviewRule = {
  id: string;
  rule_key: string;
  value: unknown;
  conditions: Record<string, unknown>;
  source_quote: string;
  effective_at: string | null;
  expires_at: string | null;
  confidence: number;
};

type ConflictEvidence = {
  id: string;
  rule_id: string | null;
  document_version_id: string;
  quote: string;
  position: number;
};

type ReviewConflict = {
  id: string;
  kind: string;
  severity: string;
  rule_key: string;
  left_rule_id: string | null;
  right_rule_id: string | null;
  left_rule: ReviewRule | null;
  right_rule: ReviewRule | null;
  left_document_version_id: string;
  right_document_version_id: string;
  reason: string;
  recommended_action: string;
  status: string;
  evidences: ConflictEvidence[];
};

type ReviewTask = {
  id: string;
  conflict_id: string;
  task_type: string;
  status: ReviewTaskStatus;
  assigned_to: string | null;
  decision: ReviewDecision | null;
  decision_reason: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  conflict: ReviewConflict;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const decisionLabels: Record<ReviewDecision, string> = {
  approve: "Approve rule",
  reject: "Reject conflict",
  invalidate_document: "Invalidate document",
};

const kindLabels: Record<string, string> = {
  conflict: "Conflict",
  conditional_exception: "Conditional exception",
  high_risk_error: "High-risk error",
  update: "Update",
  historical_difference: "Historical difference",
};

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN");
}

function severityClass(severity: string): string {
  return `review-severity review-severity--${severity}`;
}

export default function ReviewTasksPage() {
  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? tasks[0] ?? null,
    [selectedTaskId, tasks],
  );

  async function loadTasks() {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/review-tasks?status=pending`, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Failed to load tasks: ${response.status}`);
      const payload = (await response.json()) as ReviewTask[];
      setTasks(payload);
      setSelectedTaskId((current) =>
        payload.some((task) => task.id === current) ? current : payload[0]?.id ?? null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to load review tasks.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadTasks();
  }, []);

  async function submitDecision(decision: ReviewDecision) {
    if (!selectedTask) return;
    if (!reason.trim()) {
      setError("Please provide a review reason.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await fetch(
        `${apiBaseUrl}/review-tasks/${selectedTask.id}/decision`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            decision,
            decision_reason: reason.trim(),
          }),
        },
      );
      if (!response.ok) {
        throw new Error((await response.text()) || `Decision failed: ${response.status}`);
      }
      setReason("");
      setSuccess(`Completed: ${decisionLabels[decision]}`);
      await loadTasks();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Decision failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="review-shell">
      <header className="review-header">
        <div>
          <p className="eyebrow">DAY 11 / HUMAN GOVERNANCE</p>
          <h1>Policy review workspace</h1>
          <p className="review-intro">
            Compare structured rules, inspect source evidence, and decide whether a policy conflict is safe to resolve.
          </p>
        </div>
        <div className="review-header__meta">
          <span className="review-header__label">PENDING TASKS</span>
          <strong>{String(tasks.length).padStart(2, "0")}</strong>
          <span>tasks awaiting review</span>
        </div>
      </header>

      {error ? <div className="review-alert review-alert--error" role="alert"><strong>Action failed</strong><span>{error}</span></div> : null}
      {success ? <div className="review-alert review-alert--success" role="status"><strong>Completed</strong><span>{success}</span></div> : null}

      <section className="review-layout">
        <aside className="review-task-list" aria-label="Pending review tasks">
          <div className="review-section-heading">
            <div><p className="eyebrow">QUEUE</p><h2>Pending</h2></div>
            <button className="review-refresh-button" type="button" onClick={() => void loadTasks()} disabled={loading || submitting}>Refresh</button>
          </div>

          {loading ? <p className="review-empty-state">Loading review tasks...</p> : tasks.length === 0 ? (
            <div className="review-empty-state"><strong>No pending review tasks</strong><span>All current conflicts have been processed.</span></div>
          ) : (
            <div className="review-task-items">
              {tasks.map((task, index) => (
                <button
                  className={`review-task-item ${task.id === selectedTask?.id ? "review-task-item--selected" : ""}`}
                  key={task.id}
                  type="button"
                  onClick={() => { setSelectedTaskId(task.id); setReason(""); setError(null); setSuccess(null); }}
                >
                  <span className="review-task-item__number">{String(index + 1).padStart(2, "0")}</span>
                  <span className="review-task-item__content">
                    <strong>{kindLabels[task.conflict.kind] ?? task.conflict.kind}</strong>
                    <span>{task.conflict.rule_key}</span>
                    <small>{task.conflict.severity}</small>
                  </span>
                  <span className={severityClass(task.conflict.severity)}>{task.conflict.severity}</span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="review-detail">
          {!selectedTask ? (
            <div className="review-detail__empty">
              <p className="eyebrow">NO ACTIVE REVIEW</p>
              <h2>No review task selected</h2>
              <p>New policy conflicts will appear here when they are detected.</p>
            </div>
          ) : (
            <>
              <div className="review-detail__topline">
                <div><p className="eyebrow">CONFLICT REVIEW</p><h2>{kindLabels[selectedTask.conflict.kind] ?? selectedTask.conflict.kind}</h2></div>
                <span className={severityClass(selectedTask.conflict.severity)}>{selectedTask.conflict.severity}</span>
              </div>

              <div className="review-facts">
                <div><span>Rule key</span><strong>{selectedTask.conflict.rule_key}</strong></div>
                <div><span>Status</span><strong>{selectedTask.conflict.status}</strong></div>
                <div><span>Created</span><strong>{formatDate(selectedTask.created_at)}</strong></div>
              </div>

              <div className="review-reason-grid">
                <article className="review-info-card"><p className="eyebrow">SYSTEM REASON</p><h3>Conflict reason</h3><p>{selectedTask.conflict.reason}</p></article>
                <article className="review-info-card review-info-card--accent"><p className="eyebrow">RECOMMENDED ACTION</p><h3>Recommended action</h3><p>{selectedTask.conflict.recommended_action}</p></article>
              </div>

              <section className="review-rules" aria-label="Left and right rule comparison">
                <div className="review-subheading"><p className="eyebrow">RULE COMPARISON</p><h3>Left and right rules</h3></div>
                <div className="review-rule-grid">
                  {(["left", "right"] as const).map((side) => {
                    const rule = side === "left" ? selectedTask.conflict.left_rule : selectedTask.conflict.right_rule;
                    const versionId = side === "left" ? selectedTask.conflict.left_document_version_id : selectedTask.conflict.right_document_version_id;
                    return (
                      <article className={`review-rule-card ${side === "right" ? "review-rule-card--right" : ""}`} key={side}>
                        <span>{side.toUpperCase()} RULE</span>
                        <strong>{rule?.rule_key ?? "Rule unavailable"}</strong>
                        <div className="review-rule-value"><small>Rule value</small><code>{rule ? formatValue(rule.value) : "Unavailable"}</code></div>
                        <div className="review-rule-value"><small>Conditions</small><code>{rule ? formatValue(rule.conditions) : "Unavailable"}</code></div>
                        <blockquote>{rule?.source_quote ?? "Source quote unavailable"}</blockquote>
                        <small>Document version: {versionId}</small>
                      </article>
                    );
                  })}
                </div>
              </section>

              <section className="review-evidence" aria-label="Source evidence">
                <div className="review-subheading"><p className="eyebrow">SOURCE EVIDENCE</p><h3>Original evidence</h3></div>
                {selectedTask.conflict.evidences.length === 0 ? <p className="review-empty-state">No evidence returned.</p> : (
                  <div className="review-evidence-list">
                    {selectedTask.conflict.evidences.map((evidence) => (
                      <blockquote className="review-evidence-item" key={evidence.id}>
                        <span>Evidence {String(evidence.position + 1).padStart(2, "0")}</span>
                        <p>{evidence.quote}</p>
                        <small>Document version ID: {evidence.document_version_id}</small>
                      </blockquote>
                    ))}
                  </div>
                )}
              </section>

              <section className="review-decision">
                <div className="review-subheading"><p className="eyebrow">HUMAN DECISION</p><h3>Submit review decision</h3></div>
                <label htmlFor="decision-reason">Review reason</label>
                <textarea id="decision-reason" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain why this rule is accepted, rejected, or invalidated." rows={4} disabled={submitting} />
                <div className="review-decision-actions">
                  <button className="review-decision-button review-decision-button--approve" type="button" onClick={() => void submitDecision("approve")} disabled={submitting}>Approve rule</button>
                  <button className="review-decision-button review-decision-button--reject" type="button" onClick={() => void submitDecision("reject")} disabled={submitting}>Reject conflict</button>
                  <button className="review-decision-button review-decision-button--invalidate" type="button" onClick={() => void submitDecision("invalidate_document")} disabled={submitting}>Invalidate document</button>
                </div>
                <p className="review-decision-note">Every decision keeps its reason. Invalidated document versions are excluded from current retrieval.</p>
              </section>
            </>
          )}
        </section>
      </section>
    </main>
  );
}

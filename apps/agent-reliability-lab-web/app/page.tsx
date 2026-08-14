const readinessItems = [
  ["任务集", "共享 Agent 任务集已接入"],
  ["Adapter", "Living RAG 调用协议已就绪"],
  ["Trace", "等待运行结果接入"],
];

export default function HomePage() {
  return (
    <main>
      <header className="topbar">
        <p className="product-name">Agent Reliability Lab</p>
        <p className="connection-state">Living RAG integration</p>
      </header>

      <section className="workspace-heading">
        <p className="eyebrow">Evaluation workspace</p>
        <h1>可靠性评测工作区</h1>
        <p className="description">
          面向 Living RAG 的任务执行、运行记录与质量验证。
        </p>
      </section>

      <section className="readiness-grid" aria-label="当前接入状态">
        {readinessItems.map(([label, detail]) => (
          <article className="readiness-item" key={label}>
            <p className="item-label">{label}</p>
            <p className="item-detail">{detail}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
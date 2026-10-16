import type { RunEvent } from "./types";

type RunNode = RunEvent & {
  started_at: string;
  completed_at: string | null;
};

function nodeLabel(value: string | null) {
  return (value ?? "Unknown node")
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function RunInspector({ events }: { events: RunEvent[] }) {
  const nodes = new Map<string, RunNode>();
  for (const event of events) {
    if (!event.node_id) continue;
    const previous = nodes.get(event.node_id);
    nodes.set(event.node_id, {
      ...previous,
      ...event,
      input_preview: event.input_preview ?? previous?.input_preview ?? null,
      output_preview: event.output_preview ?? previous?.output_preview ?? null,
      started_at: previous?.started_at ?? event.timestamp,
      completed_at:
        event.event_type === "node.completed" || event.event_type === "node.failed"
          ? event.timestamp
          : previous?.completed_at ?? null
    });
  }
  if (!nodes.size) return <p className="empty">Agent and tool progress will appear here.</p>;
  return (
    <div className="run-inspector">
      {[...nodes.values()].map((node) => (
        <details className={`run-node ${node.node_kind ?? "agent"}`} key={node.node_id} open={node.node_kind === "agent"}>
          <summary>
            <span className={`run-dot ${node.status ?? "pending"}`} />
            <span className="run-node-title">
              <strong>{nodeLabel(node.label ?? node.node_id)}</strong>
              <small>{node.node_kind === "tool" ? "Tool" : "Agent"}</small>
            </span>
            {node.duration_ms != null && <small>{Math.round(node.duration_ms)} ms</small>}
          </summary>
          <div className="run-node-details">
            {node.input_preview && (
              <section className="run-preview">
                <h4>Input</h4>
                <pre>{JSON.stringify(node.input_preview, null, 2)}</pre>
              </section>
            )}
            {node.output_preview && (
              <section className="run-preview">
                <h4>Output</h4>
                <pre>{JSON.stringify(node.output_preview, null, 2)}</pre>
              </section>
            )}
            {node.error && (
              <section className="run-preview error">
                <h4>Error</h4>
                <p>{node.error}</p>
              </section>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}

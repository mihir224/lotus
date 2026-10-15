import type { RunEvent } from "./types";

export function RunInspector({ events }: { events: RunEvent[] }) {
  const nodes = new Map<string, RunEvent>();
  for (const event of events) {
    if (event.node_id) nodes.set(event.node_id, event);
  }
  if (!nodes.size) return <p className="empty">Agent and tool progress will appear here.</p>;
  return (
    <div className="run-inspector">
      {[...nodes.values()].map((node) => (
        <details className={`run-node ${node.node_kind ?? "agent"}`} key={node.node_id} open={node.node_kind === "agent"}>
          <summary>
            <span className={`run-dot ${node.status ?? "pending"}`} />
            <strong>{node.label ?? node.node_id}</strong>
            {node.duration_ms != null && <small>{Math.round(node.duration_ms)} ms</small>}
          </summary>
          {(node.input_preview || node.output_preview) && (
            <pre>{JSON.stringify(node.output_preview ?? node.input_preview, null, 2)}</pre>
          )}
        </details>
      ))}
    </div>
  );
}

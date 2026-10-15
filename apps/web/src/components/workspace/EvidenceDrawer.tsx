import type { GroundedAnswer } from "../../types";

type EvidenceDrawerProps = {
  answer: GroundedAnswer | null;
};

export function EvidenceDrawer({ answer }: EvidenceDrawerProps) {
  return (
    <aside className="evidence" aria-label="Evidence drawer">
      <div className="drawer-head">
        <div>
          <p className="eyebrow">Evidence</p>
          <h2>Source trail</h2>
        </div>
        <span>{answer?.evidence.length ?? 0}</span>
      </div>
      {!answer && (
        <p className="empty">Sources used for an answer will appear here with scope and provenance.</p>
      )}
      {answer?.evidence.map((item, index) => (
        <article className="source" key={`${item.source_id}-${index}`}>
          <div>
            <span>[{index + 1}]</span>
            <small>{item.retrieval_method.replace("_", " ")}</small>
          </div>
          <h3>{item.title ?? item.source_id}</h3>
          <p>{item.snippet}</p>
          <footer>
            <strong>{item.source_type}</strong>
            <span>{item.source_id}</span>
          </footer>
        </article>
      ))}
    </aside>
  );
}

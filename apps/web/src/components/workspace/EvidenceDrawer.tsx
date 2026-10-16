import { RunInspector } from "../../RunInspector";
import type { GroundedAnswer, RunEvent } from "../../types";

type DrawerTab = "evidence" | "run";

type EvidenceDrawerProps = {
  answer: GroundedAnswer | null;
  events: RunEvent[];
  activeTab: DrawerTab;
  onTabChange: (tab: DrawerTab) => void;
};

export function EvidenceDrawer({ answer, events, activeTab, onTabChange }: EvidenceDrawerProps) {
  const runNodeCount = new Set(
    events.flatMap((item) => (item.node_id ? [item.node_id] : []))
  ).size;
  return (
    <aside className="evidence" aria-label="Evidence drawer">
      <div className="drawer-head">
        <div className="drawer-tabs">
          <button className={activeTab === "evidence" ? "active" : ""} onClick={() => onTabChange("evidence")}>Evidence</button>
          <button className={activeTab === "run" ? "active" : ""} onClick={() => onTabChange("run")}>Run</button>
        </div>
        <span aria-label={activeTab === "evidence" ? "Evidence count" : "Run node count"}>
          {activeTab === "evidence" ? answer?.evidence.length ?? 0 : runNodeCount}
        </span>
      </div>
      {activeTab === "run" ? (
        <RunInspector events={events} />
      ) : (
        <>
          {!answer && <p className="empty">Sources used for an answer will appear here with scope and provenance.</p>}
          {answer?.evidence.map((item, index) => (
            <article className="source" key={`${item.source_id}-${index}`}>
              <div><span>[{index + 1}]</span><small>{item.retrieval_method.replace("_", " ")}</small></div>
              <h3>{item.title ?? item.source_id}</h3>
              <p>{item.snippet}</p>
              <footer><strong>{item.source_type}</strong><span>{item.source_id}</span></footer>
            </article>
          ))}
        </>
      )}
    </aside>
  );
}

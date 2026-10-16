// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatHistoryDialog } from "./ChatHistoryDialog";
import { DebugDialog } from "./DebugDialog";
import { EvidenceDrawer } from "./EvidenceDrawer";
import type { RunEvent } from "../../types";

afterEach(cleanup);

describe("workspace dialogs", () => {
  it("resumes and deletes a conversation", () => {
    const onOpen = vi.fn();
    const onDelete = vi.fn();
    render(<ChatHistoryDialog open loading={false} currentSessionId="s1" onClose={vi.fn()} onOpen={onOpen} onDelete={onDelete} sessions={[{ session_id: "s1", title: "Retry policy", project_id: "payments", created_at: "2026-10-16T00:00:00Z", updated_at: "2026-10-16T00:00:00Z" }]} />);
    fireEvent.click(screen.getByText("Retry policy"));
    expect(onOpen).toHaveBeenCalledWith("s1");
    fireEvent.click(screen.getByLabelText("Delete Retry policy"));
    expect(onDelete).toHaveBeenCalledWith("s1");
  });

  it("toggles debug mode without exposing execution content", () => {
    const onChange = vi.fn();
    render(<DebugDialog open enabled={false} onChange={onChange} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
    expect(screen.getByText(/hidden reasoning/i)).toBeInTheDocument();
  });

  it("counts unique run nodes instead of lifecycle events", () => {
    const event = (eventType: RunEvent["event_type"], nodeId: string): RunEvent => ({
      event_type: eventType,
      execution_id: "run-1",
      session_id: "session-1",
      timestamp: "2026-10-16T00:00:00Z",
      node_id: nodeId,
      parent_id: null,
      node_kind: "agent",
      label: nodeId,
      status: eventType === "node.started" ? "running" : "completed",
      duration_ms: null,
      input_preview: null,
      output_preview: null,
      answer_delta: null,
      response: null,
      error: null
    });
    render(
      <EvidenceDrawer
        answer={null}
        activeTab="run"
        onTabChange={vi.fn()}
        events={[
          event("node.started", "planner"),
          event("node.completed", "planner"),
          event("node.started", "meeting"),
          event("node.completed", "meeting")
        ]}
      />
    );
    expect(screen.getByLabelText("Run node count")).toHaveTextContent("2");
  });

  it("preserves and labels tool input when a completion event arrives", () => {
    const base: RunEvent = {
      event_type: "node.started",
      execution_id: "run-1",
      session_id: "session-1",
      timestamp: "2026-10-16T00:00:00Z",
      node_id: "meeting.calendar_mcp",
      parent_id: "meeting",
      node_kind: "tool",
      label: "calendar_mcp",
      status: "running",
      duration_ms: null,
      input_preview: { query: "Meetings on 15 August", date_from: "2026-08-15" },
      output_preview: null,
      answer_delta: null,
      response: null,
      error: null
    };
    render(
      <EvidenceDrawer
        answer={null}
        activeTab="run"
        onTabChange={vi.fn()}
        events={[
          base,
          {
            ...base,
            event_type: "node.completed",
            timestamp: "2026-10-16T00:00:01Z",
            status: "completed",
            duration_ms: 1000,
            input_preview: null,
            output_preview: { evidence_count: 2 }
          }
        ]}
      />
    );
    fireEvent.click(screen.getByText("Calendar Mcp"));
    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(screen.getByText("Output")).toBeInTheDocument();
    expect(screen.getByText(/Meetings on 15 August/)).toBeInTheDocument();
    expect(screen.getByText(/evidence_count/)).toBeInTheDocument();
  });
});

// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatHistoryDialog } from "./ChatHistoryDialog";
import { DebugDialog } from "./DebugDialog";

afterEach(cleanup);

describe("workspace dialogs", () => {
  it("resumes and deletes a conversation", () => {
    const onOpen = vi.fn();
    const onDelete = vi.fn();
    render(<ChatHistoryDialog open loading={false} currentSessionId="s1" onClose={vi.fn()} onNew={vi.fn()} onOpen={onOpen} onDelete={onDelete} sessions={[{ session_id: "s1", title: "Retry policy", project_id: "payments", created_at: "2026-10-16T00:00:00Z", updated_at: "2026-10-16T00:00:00Z" }]} />);
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
});

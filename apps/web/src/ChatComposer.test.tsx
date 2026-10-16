// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatComposer } from "./ChatComposer";

afterEach(cleanup);

describe("ChatComposer", () => {
  it("starts empty with a descriptive placeholder and submits on Enter", () => {
    const submit = vi.fn();
    render(
      <ChatComposer value="" loading={false} onChange={() => undefined} onSubmit={submit} onCancel={() => undefined} />
    );
    const input = screen.getByLabelText("Ask Iris");
    expect(input).toHaveAttribute("placeholder");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(submit).toHaveBeenCalledOnce();
  });

  it("allows Shift+Enter without submitting", () => {
    const submit = vi.fn();
    render(
      <ChatComposer value="question" loading={false} onChange={() => undefined} onSubmit={submit} onCancel={() => undefined} />
    );
    fireEvent.keyDown(screen.getByLabelText("Ask Iris"), { key: "Enter", shiftKey: true });
    expect(submit).not.toHaveBeenCalled();
  });
});

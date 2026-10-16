// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownMessage } from "./MarkdownMessage";

describe("MarkdownMessage", () => {
  it("renders GFM and strips unsafe raw HTML", () => {
    const { container } = render(
      <MarkdownMessage>{"| A | B |\n| - | - |\n| 1 | 2 |\n\n<script>alert(1)</script>"}</MarkdownMessage>
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
  });
});

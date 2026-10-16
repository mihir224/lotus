import { describe, expect, it } from "vitest";
import { hideEvidenceReferences } from "./chatPresentation";

describe("hideEvidenceReferences", () => {
  it("hides numeric evidence markers but preserves entity identifiers", () => {
    expect(hideEvidenceReferences("Meeting M-116 [1]. Also see [2, 3].")).toBe(
      "Meeting M-116. Also see."
    );
    expect(hideEvidenceReferences("Keep [M-116] visible.")).toBe("Keep [M-116] visible.");
  });
});

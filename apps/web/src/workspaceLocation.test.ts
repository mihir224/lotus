import { describe, expect, it } from "vitest";
import { agentLocation } from "./workspaceLocation";

describe("agentLocation", () => {
  it("only includes a session when a conversation is selected", () => {
    expect(agentLocation()).toBe("?section=agent");
    expect(agentLocation("session-123")).toBe("?section=agent&session=session-123");
  });
});

import { describe, expect, it } from "vitest";
import { profileDesignation } from "./profileUtils";

describe("profileDesignation", () => {
  it("keeps an identity-provider designation when one is available", () => {
    expect(profileDesignation("user-1", "Staff Engineer")).toBe("Staff Engineer");
  });

  it("assigns a stable demo designation when Google does not provide one", () => {
    const first = profileDesignation("google-subject-123", null);
    const second = profileDesignation("google-subject-123", null);
    expect(first).toBe(second);
    expect(first.length).toBeGreaterThan(0);
  });
});

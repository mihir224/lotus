// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AUTH_EXPIRED_EVENT,
  AuthExpiredError,
  authenticatedFetch,
  storedAuthSession
} from "./auth";

afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe("authenticatedFetch", () => {
  it("clears stale credentials and announces an expired session on 401", async () => {
    sessionStorage.setItem("lotus.google.credential", "expired-token");
    sessionStorage.setItem(
      "lotus.google.user",
      JSON.stringify({ user_id: "alice", email: "alice@example.com", name: "Alice" })
    );
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    const expired = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, expired, { once: true });

    await expect(authenticatedFetch("/v1/calendar/events")).rejects.toBeInstanceOf(
      AuthExpiredError
    );

    expect(storedAuthSession()).toBeNull();
    expect(expired).toHaveBeenCalledOnce();
  });

  it("returns non-401 responses without changing the session", async () => {
    const response = new Response("{}", { status: 200 });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    await expect(authenticatedFetch("/v1/calendar/events")).resolves.toBe(response);
  });
});

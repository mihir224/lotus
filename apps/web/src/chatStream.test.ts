import { describe, expect, it } from "vitest";
import { parseSseFrames } from "./chatStream";

describe("parseSseFrames", () => {
  it("preserves a split frame until it is complete", () => {
    const first = parseSseFrames('event: answer.delta\ndata: {"event_type":"answer.');
    expect(first.events).toHaveLength(0);
    const second = parseSseFrames(`${first.remainder}delta","execution_id":"run-1"}\n\n`);
    expect(second.events[0].event_type).toBe("answer.delta");
  });

  it("rejects malformed JSON instead of silently dropping it", () => {
    expect(() => parseSseFrames("data: {not-json}\n\n")).toThrow(/malformed/);
  });
});

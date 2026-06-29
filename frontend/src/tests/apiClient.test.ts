import { describe, it, expect, vi, afterEach } from "vitest";
import { api, ApiError } from "../api/client";

afterEach(() => vi.restoreAllMocks());

describe("api client error handling", () => {
  it("maps a 403 proxy_required to a friendly message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: { error: "proxy_required" } }),
      { status: 403, headers: { "content-type": "application/json" } })));
    try { await api.get("/api/x"); expect.fail("should throw"); }
    catch (e) {
      expect(e).toBeInstanceOf(ApiError);
      expect((e as ApiError).code).toBe("proxy_required");
      expect((e as ApiError).friendly).toMatch(/Proxy Mode/i);
    }
  });
  it("flags network errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    try { await api.get("/api/x"); expect.fail("should throw"); }
    catch (e) { expect((e as ApiError).isNetwork).toBe(true); expect((e as ApiError).friendly).toMatch(/Cannot reach the server/i); }
  });

  it("parses FastAPI 422 detail into field-level messages", async () => {
    const body = { detail: [
      { loc: ["body", "date"], msg: "invalid date", type: "value_error" },
      { loc: ["body", "session_count"], msg: "must be >= 1", type: "value_error" },
    ] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false, status: 422,
      headers: { get: () => "application/json" },
      json: async () => body,
    }));
    try { await api.post("/api/parade-nights", {}); expect.fail("should throw"); }
    catch (e) {
      const fe = (e as ApiError).fieldErrors;
      expect(fe.date).toBe("invalid date");
      expect(fe.session_count).toBe("must be >= 1");
    }
  });
});

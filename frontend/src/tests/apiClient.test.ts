import { describe, it, expect, vi, afterEach } from "vitest";
import { api, ApiError, friendlyMessage } from "../api/client";

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
    catch (e) { expect((e as ApiError).isNetwork).toBe(true); expect((e as ApiError).friendly).toMatch(/Cannot reach the training system/i); }
  });

  it("retries a GET on 503 and succeeds once the backend recovers", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await api.get("/api/x");
    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not retry a POST on 503 (write requests are never auto-retried)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);
    try { await api.post("/api/x", {}); expect.fail("should throw"); }
    catch (e) { expect((e as ApiError).status).toBe(503); }
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("classifies an aborted request as cancelled, not a network failure", async () => {
    const abortError = new DOMException("aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abortError));
    try { await api.get("/api/x"); expect.fail("should throw"); }
    catch (e) {
      expect((e as ApiError).isCancelled).toBe(true);
      expect((e as ApiError).isNetwork).toBe(false);
      expect((e as ApiError).friendly).toMatch(/cancelled/i);
    }
  });

  it("classifies an unparseable JSON body on a 200 as invalid_response, not silent success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200,
      headers: { get: () => "application/json" },
      json: async () => { throw new Error("bad json"); },
    }));
    try { await api.get("/api/x"); expect.fail("should throw"); }
    catch (e) {
      expect((e as ApiError).isInvalidResponse).toBe(true);
      expect((e as ApiError).friendly).toMatch(/unreadable/i);
    }
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

describe("friendlyMessage (WRITE-04)", () => {
  // Regression test: ApiError.message is just `API ${status}` (e.g. "API 403"),
  // never the curated ApiError.friendly text -- the widespread
  // `e instanceof Error ? e.message : fallback` idiom used across the app's
  // form/modal error handlers matched ApiError too (it extends Error) and was
  // showing that raw status string to operational users instead of a
  // human-readable message. friendlyMessage() must always prefer .friendly
  // for an ApiError, never its own .message.
  it("uses ApiError.friendly, never ApiError.message, for an ApiError", () => {
    const e = new ApiError(403, { detail: { error: "forbidden" } });
    expect(e.message).toBe("API 403"); // sanity check on the trap this guards against
    expect(friendlyMessage(e, "fallback")).toBe(e.friendly);
    expect(friendlyMessage(e, "fallback")).not.toMatch(/^API \d/);
  });
  it("falls back to a plain Error's own message when it is not an ApiError", () => {
    expect(friendlyMessage(new Error("disk full"), "fallback")).toBe("disk full");
  });
  it("uses the fallback string for a non-Error thrown value", () => {
    expect(friendlyMessage("boom", "fallback")).toBe("fallback");
    expect(friendlyMessage(undefined, "fallback")).toBe("fallback");
  });
});

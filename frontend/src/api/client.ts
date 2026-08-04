// API client: honours VITE_API_BASE_URL (build-time) or <meta name="aafc-api-base"> (runtime).
// The meta tag takes precedence so the connected single-file build can be re-pointed at
// a different server by editing one HTML attribute without a rebuild.
// Falls back to "" (relative URLs) when neither is set — assumes same-origin reverse proxy.
const _metaBase = (document.querySelector('meta[name="aafc-api-base"]') as HTMLMetaElement | null)?.content ?? "";
const BASE = (_metaBase || import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const TOKEN_KEY = "aafc_token";

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export interface ApiErrorShape { error?: string; message?: string; detail?: unknown; }

export class ApiError extends Error {
  constructor(public status: number, public data: ApiErrorShape, public isNetwork = false, public isCancelled = false, public isInvalidResponse = false) {
    super(`API ${status}`);
  }
  /** Backend error code if present (e.g. proxy_required, invalid_code). */
  get code(): string | undefined {
    const d = this.data?.detail as { error?: string } | undefined;
    return this.data?.error ?? d?.error;
  }
  get friendly(): string {
    if (this.isCancelled) return "Request cancelled.";
    if (this.isInvalidResponse) return "The server returned an unreadable response. Try again.";
    if (this.isNetwork) return "Cannot reach the server. Check that the backend is running.";
    const d = this.data?.detail as { message?: string; error?: string } | undefined;
    switch (this.status) {
      case 401: return "Your session has expired. Please log in again.";
      case 403:
        if (this.code === "proxy_required") return "This action needs Proxy Mode. Enter proxy mode with a reason.";
        if (this.code === "intervention_required") return "This action needs Delegated Intervention. Enter it with a reason.";
        return "Access not permitted.";
      case 422: return d?.message ?? "Some fields are invalid.";
      case 429: return "Too many attempts. Please wait and try again.";
      case 500: return "The server encountered an error. Please try again.";
      default: return d?.message ?? d?.error ?? this.data?.message ?? "Request failed.";
    }
  }
  /** Field-level messages for a 422, keyed by field name.
   *  FastAPI returns detail: [{loc: ["body","field"], msg, type}, ...]. */
  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    const detail = this.data?.detail;
    if (Array.isArray(detail)) {
      for (const item of detail as Array<{ loc?: unknown[]; msg?: string }>) {
        const loc = Array.isArray(item.loc) ? item.loc : [];
        const field = String(loc[loc.length - 1] ?? "form");
        if (item.msg) out[field] = item.msg;
      }
    }
    return out;
  }
}

const RETRYABLE_STATUS = new Set([502, 503, 504]);

// Single-replica deployments (see .claude/rules/deployment.md) have no overlap
// between the old and new container during a redeploy -- a real, brief
// connectivity gap, not a stuck backend. Retry transient failures with backoff
// before surfacing an error, but only for GET (safe/idempotent) -- fetch() can
// throw after a request already reached the server, so retrying a write risks
// a duplicate. Matches connected-frontend's api()'s own retry logic exactly,
// since both frontends hit the same single-replica gap.
async function _fetchWithRetry(url: string, opts: RequestInit): Promise<Response> {
  const method = (opts.method || "GET").toUpperCase();
  const maxAttempts = method === "GET" ? 3 : 1;
  for (let attempt = 1; ; attempt++) {
    try {
      const res = await fetch(url, opts);
      if (RETRYABLE_STATUS.has(res.status) && attempt < maxAttempts) {
        await new Promise(r => setTimeout(r, attempt * 400));
        continue;
      }
      return res;
    } catch (e) {
      // A caller-supplied AbortSignal firing (e.g. React Query cancelling a
      // stale in-flight request on scope/year change) throws a DOMException
      // named 'AbortError' -- an intentional cancellation, never retried or
      // reported as a connectivity failure.
      if (e instanceof DOMException && e.name === "AbortError") {
        throw new ApiError(0, { error: "cancelled" }, false, true);
      }
      if (attempt >= maxAttempts) {
        throw new ApiError(0, { error: "network_error" }, true);
      }
      await new Promise(r => setTimeout(r, attempt * 400));
    }
  }
}

async function _parseBody(res: Response): Promise<unknown> {
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return await res.text();
  let parseFailed = false;
  const body = await res.json().catch(() => { parseFailed = true; return {}; });
  if (res.ok && parseFailed) {
    throw new ApiError(res.status, { error: "invalid_response" }, false, false, true);
  }
  return body;
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(opts.headers as Record<string, string>) };
  const tok = tokenStore.get();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  const res = await _fetchWithRetry(`${BASE}${path}`, { ...opts, headers, credentials: "include" });
  if (res.status === 401) tokenStore.clear();
  const body = await _parseBody(res);
  if (!res.ok) throw new ApiError(res.status, (typeof body === "object" ? body : { message: String(body) }) as ApiErrorShape);
  return body as T;
}

async function requestForm<T>(path: string, form: FormData, method = "POST"): Promise<T> {
  const headers: Record<string, string> = {};
  const tok = tokenStore.get();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  const res = await _fetchWithRetry(`${BASE}${path}`, { method, headers, credentials: "include", body: form });
  if (res.status === 401) tokenStore.clear();
  const body = await _parseBody(res);
  if (!res.ok) throw new ApiError(res.status, (typeof body === "object" ? body : { message: String(body) }) as ApiErrorShape);
  return body as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, b?: unknown) => request<T>(p, { method: "POST", body: b !== undefined ? JSON.stringify(b) : undefined }),
  put: <T>(p: string, b?: unknown) => request<T>(p, { method: "PUT", body: b !== undefined ? JSON.stringify(b) : undefined }),
  patch: <T>(p: string, b?: unknown) => request<T>(p, { method: "PATCH", body: b !== undefined ? JSON.stringify(b) : undefined }),
  delete: <T>(p: string) => request<T>(p, { method: "DELETE" }),
  postForm: <T>(p: string, form: FormData) => requestForm<T>(p, form, "POST"),
};

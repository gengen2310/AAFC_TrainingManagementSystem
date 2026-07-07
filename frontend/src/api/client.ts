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
  constructor(public status: number, public data: ApiErrorShape, public isNetwork = false) {
    super(`API ${status}`);
  }
  /** Backend error code if present (e.g. proxy_required, invalid_code). */
  get code(): string | undefined {
    const d = this.data?.detail as { error?: string } | undefined;
    return this.data?.error ?? d?.error;
  }
  get friendly(): string {
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

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(opts.headers as Record<string, string>) };
  const tok = tokenStore.get();
  if (tok) headers["Authorization"] = `Bearer ${tok}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: "include" });
  } catch {
    throw new ApiError(0, { error: "network_error" }, true);
  }
  if (res.status === 401) tokenStore.clear();
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await res.json().catch(() => ({})) : await res.text();
  if (!res.ok) throw new ApiError(res.status, (typeof body === "object" ? body : { message: String(body) }) as ApiErrorShape);
  return body as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, b?: unknown) => request<T>(p, { method: "POST", body: b !== undefined ? JSON.stringify(b) : undefined }),
  put: <T>(p: string, b?: unknown) => request<T>(p, { method: "PUT", body: b !== undefined ? JSON.stringify(b) : undefined }),
  patch: <T>(p: string, b?: unknown) => request<T>(p, { method: "PATCH", body: b !== undefined ? JSON.stringify(b) : undefined }),
};

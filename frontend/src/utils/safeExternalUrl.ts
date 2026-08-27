/**
 * Guard for user-supplied URLs rendered into an `href`.
 *
 * React escapes attribute values, so the quote-breakout that affected the
 * legacy TMS frontend (REM-151) cannot happen here. What React does NOT do is
 * reject dangerous schemes: on 18.3.1 a `javascript:` href renders verbatim and
 * only logs "A future version of React will block javascript: URLs". Verified
 * rather than assumed -- mixed case and a tab inside the scheme both render
 * verbatim too, and browsers strip the tab before dispatching, so that form
 * executes.
 *
 * `learning_hub_url` is an unvalidated string on the API (`str | None`,
 * `String(400)`, no constraint) and is settable by squadron and wing admins on
 * curriculum items that inherit downward, so an unguarded value reaches other
 * users' browsers.
 *
 * Mirrors the intent of connected-frontend's `safeUrl()` / `_rtSafeHref()`.
 * Deliberately a separate local helper rather than shared code: the two
 * frontends are independently deployed by design (.claude/rules/architecture.md)
 * and must not grow a shared build.
 *
 * Returns the original URL when it is safe to link, or `null` when it is not,
 * so callers can render plain text instead of a live link.
 */
export function safeExternalUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  const raw = String(value).trim();
  if (!raw) return null;

  // Browsers ignore whitespace and control characters inside a scheme, so a tab
  // or newline spliced into "javascript:" still runs. Normalise before deciding,
  // but return the original string.
  //
  // The class is written \s plus an explicit control range. Writing it as
  // [\s -] would be a character RANGE from U+0020 to U+002D, silently
  // swallowing '#', '(', '+', ',', '-' and '.' -- a real bug hit earlier in
  // this codebase's history.
  const flat = raw.replace(/[\s\x00-\x1f\x7f]/g, "").toLowerCase();

  if (flat.startsWith("//")) return null; // protocol-relative: off-site
  return /^https?:/.test(flat) ? raw : null;
}

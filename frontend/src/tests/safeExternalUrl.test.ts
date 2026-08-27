import { describe, it, expect } from "vitest";
import { safeExternalUrl } from "../utils/safeExternalUrl";
// Vite's ?raw import, typed by vite/client (already referenced in vite-env.d.ts).
// Reading the file with node:fs instead would need @types/node, which this
// tsconfig deliberately does not pull in.
import curriculumSource from "../routes/Curriculum.tsx?raw";

// React escapes attribute values, so the quote-breakout of REM-151 cannot occur
// in this app. It does NOT reject dangerous schemes: on react-dom 18.3.1,
// renderToStaticMarkup of <a href="javascript:..."> emits the href verbatim and
// only logs "A future version of React will block javascript: URLs". Mixed case
// and a tab spliced into the scheme render verbatim too, and browsers strip the
// tab before dispatching -- so that form executes.
//
// learning_hub_url is an unvalidated string on the API and is settable by
// squadron and wing admins on curriculum items that inherit downward.

describe("safeExternalUrl", () => {
  it("allows ordinary http(s) URLs through unchanged", () => {
    const u = "https://learninghub.example/course/1?a=1&b=2#frag";
    expect(safeExternalUrl(u)).toBe(u);
    expect(safeExternalUrl("http://example.invalid/x")).toBe("http://example.invalid/x");
  });

  it("rejects javascript: in every casing", () => {
    expect(safeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(safeExternalUrl("JAVASCRIPT:alert(1)")).toBeNull();
    expect(safeExternalUrl("JaVaScRiPt:alert(1)")).toBeNull();
    expect(safeExternalUrl("  javascript:alert(1)")).toBeNull();
  });

  it("rejects schemes obfuscated with whitespace or control characters", () => {
    // Browsers ignore these inside a scheme; the naive check does not.
    expect(safeExternalUrl("java\tscript:alert(1)")).toBeNull();
    expect(safeExternalUrl("java\nscript:alert(1)")).toBeNull();
    expect(safeExternalUrl("java\rscript:alert(1)")).toBeNull();
    expect(safeExternalUrl("java\x00script:alert(1)")).toBeNull();
    expect(safeExternalUrl("jav\x09ascript:alert(1)")).toBeNull();
  });

  it("rejects other non-http schemes and protocol-relative URLs", () => {
    expect(safeExternalUrl("data:text/html,<script>1</script>")).toBeNull();
    expect(safeExternalUrl("vbscript:msgbox(1)")).toBeNull();
    expect(safeExternalUrl("file:///etc/passwd")).toBeNull();
    expect(safeExternalUrl("//evil.example/x")).toBeNull();
  });

  it("returns null for empty and missing values", () => {
    expect(safeExternalUrl(null)).toBeNull();
    expect(safeExternalUrl(undefined)).toBeNull();
    expect(safeExternalUrl("")).toBeNull();
    expect(safeExternalUrl("   ")).toBeNull();
  });

  it("does not eat characters that a naive [\\s -] range would swallow", () => {
    // [\s -] is a RANGE U+0020..U+002D, which would strip # ( ) + , - . and
    // could turn a rejected string into an accepted one. Guard against that
    // regression: these must survive normalisation and still be accepted.
    const u = "https://ex.invalid/a-b+c,d(e)f.g#h";
    expect(safeExternalUrl(u)).toBe(u);
  });
});

// ── Call-site guard ──────────────────────────────────────────────────────────
// The helper passing is not enough. REM-150 was a correct helper used in the
// wrong place, and REM-151 was a correct call site using an incomplete helper --
// in both cases a unit test of the helper alone would have stayed green while
// the app was vulnerable. This is a source-level check, deliberately: mounting
// Curriculum needs the react-query and router providers, and the thing worth
// protecting is simply that no raw learning_hub_url is ever handed to an href.
describe("Curriculum.tsx call sites", () => {
  it("never passes a raw learning_hub_url to an href", () => {
    const src = curriculumSource;

    const hrefs = [...src.matchAll(/href=\{([^}]*)\}/g)].map((m) => m[1].trim());
    expect(hrefs.length).toBeGreaterThan(0);
    for (const expr of hrefs) {
      expect(expr).toContain("safeExternalUrl(");
    }
    // and no bare usage survives anywhere in the file
    expect(src).not.toMatch(/href=\{\s*i\.learning_hub_url/);
    expect(src).not.toMatch(/href=\{\s*item\.learning_hub_url/);
  });
});

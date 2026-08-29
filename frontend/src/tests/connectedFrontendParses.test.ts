import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * connected-frontend is a single-file SPA whose entire application lives in one
 * inline <script>. A syntax error anywhere in it does not degrade one feature --
 * it stops the whole app from running, on every page, for every role.
 *
 * On 2026-08-29 `main` shipped exactly that: a cleanup commit deleted a
 * function's opening line and left its trailing `} catch(e){…}` behind, and
 * nothing in the suite noticed. This is the cheapest possible guard against a
 * repeat.
 */
describe("connected-frontend/index.html", () => {
  const html = readFileSync(
    resolve(__dirname, "../../../connected-frontend/index.html"), "utf8");

  const blocks = [...html.matchAll(
    /<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);

  it("has at least one inline script block", () => {
    expect(blocks.length).toBeGreaterThan(0);
  });

  it("every inline script block parses as JavaScript", () => {
    const failures: string[] = [];
    blocks.forEach((src, i) => {
      try {
        // Function() parses without executing — exactly the check a browser
        // makes before it will run any of the file.
        new Function(src);
      } catch (e) {
        failures.push(`block ${i}: ${(e as Error).message}`);
      }
    });
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("declares no function that nothing references", () => {
    // Narrow guard for the specific failure mode above: a deleted function
    // leaving callers behind, or a caller left pointing at nothing.
    for (const name of ["ynCreateYear", "ynDoRollover", "ynStartEdit"]) {
      const declared = new RegExp(`function\\s+${name}\\s*\\(`).test(html);
      const referenced = new RegExp(`${name}\\s*\\(`).test(
        html.replace(new RegExp(`function\\s+${name}\\s*\\(`, "g"), ""));
      expect(declared && !referenced,
        `${name} is declared but never called`).toBe(false);
    }
  });
});

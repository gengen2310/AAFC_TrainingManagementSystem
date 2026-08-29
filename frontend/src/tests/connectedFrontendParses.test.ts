import { describe, it, expect } from "vitest";
// Vite raw import: loads the file's text at transform time, so this test needs
// no node types (@types/node is not installed and tsconfig only carries
// vitest/globals).
import html from "../../../connected-frontend/index.html?raw";

/**
 * connected-frontend is a single-file SPA whose entire application lives in one
 * inline <script>. A syntax error anywhere in it does not degrade one feature --
 * it stops the whole app from running, on every page, for every role.
 *
 * On 2026-08-29 `main` shipped exactly that: a cleanup commit deleted a
 * function's opening line and left its trailing `} catch(e){…}` behind, and the
 * suite stayed green because every test that would have caught it needs a
 * RUNNING app. This is the cheapest guard against a repeat.
 */
const source: string = html as unknown as string;

const blocks = [...source.matchAll(
  /<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);

describe("connected-frontend/index.html", () => {
  it("has at least one inline script block", () => {
    expect(blocks.length).toBeGreaterThan(0);
  });

  it("every inline script block parses as JavaScript", () => {
    const failures: string[] = [];
    blocks.forEach((src, i) => {
      try {
        // Function() parses without executing -- the same check a browser makes
        // before it will run any of the file.
        new Function(src);
      } catch (e) {
        failures.push(`block ${i}: ${(e as Error).message}`);
      }
    });
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("leaves no function declared with nothing calling it", () => {
    for (const name of ["ynCreateYear", "ynDoRollover", "ynStartEdit"]) {
      const declared = new RegExp(`function\\s+${name}\\s*\\(`).test(source);
      const referenced = new RegExp(`${name}\\s*\\(`).test(
        source.replace(new RegExp(`function\\s+${name}\\s*\\(`, "g"), ""));
      expect(declared && !referenced,
        `${name} is declared but never called`).toBe(false);
    }
  });
});

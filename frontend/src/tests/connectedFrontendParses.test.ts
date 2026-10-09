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

// Modules extracted out of index.html into connected-frontend/js/ must parse
// too: a syntax error there breaks the feature the same way.
const modules = import.meta.glob("../../../connected-frontend/js/*.js",
  { query: "?raw", import: "default", eager: true }) as Record<string, string>;

// The production image's web root (Dockerfile COPY ... /usr/share/nginx/html/)
// and the local run script must serve the same files. When #69 extracted js/
// modules, the Dockerfile gained `COPY js/` but RUN_TMS_CONNECTED_FRONTEND_MAC.sh
// still copied only index.html, so a local run had openModal/promptText
// undefined and every dialog failed.
import dockerfile from "../../../connected-frontend/Dockerfile?raw";
import runScript from "../../../RUN_TMS_CONNECTED_FRONTEND_MAC.sh?raw";

// The application's script source: index.html plus every extracted js/ module.
// Content contracts below must hold wherever the code lives after an extraction.
const app: string = [source, ...Object.keys(modules).sort().map(k => modules[k])].join("\n");

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

  it("every extracted js/ module parses and is loaded by index.html", () => {
    const names = Object.keys(modules);
    expect(names.length).toBeGreaterThan(0);
    for (const [path, src] of Object.entries(modules)) {
      expect(() => new Function(src), path).not.toThrow();
      const file = path.split("/").pop();
      expect(source, `${file} is not referenced by index.html`).toContain(`<script src="js/${file}"></script>`);
    }
  });

  it("the local run script serves everything the production image serves", () => {
    const served = [...(dockerfile as unknown as string).matchAll(
      /^COPY\s+(\S+)\s+\/usr\/share\/nginx\/html\//gm)].map(m => m[1].replace(/\/$/, ""));
    expect(served).toEqual(expect.arrayContaining(["index.html", "js"]));
    for (const path of served) {
      expect(runScript as unknown as string, `local run script does not serve ${path}`)
        .toContain(`"$SRC_DIR/${path}"`);
    }
  });

  it("leaves no function declared with nothing calling it", () => {
    for (const name of ["ynCreateYear", "ynDoRollover", "ynStartEdit"]) {
      const declared = new RegExp(`function\\s+${name}\\s*\\(`).test(app);
      const referenced = new RegExp(`${name}\\s*\\(`).test(
        app.replace(new RegExp(`function\\s+${name}\\s*\\(`, "g"), ""));
      expect(declared && !referenced,
        `${name} is declared but never called`).toBe(false);
    }
  });

  it("has one outcome-entry workflow and no authorised Matrix shortcut", () => {
    expect(app).not.toContain("Matrix ↗");
    expect(app.match(/>Sessions Needing Outcome Entry</g)).toHaveLength(1);
    expect(app).not.toContain("Outcome needed —");
  });

  it("passes the canonical timing block when creating a direct planner session", () => {
    expect(app).toContain("const _tbId=(_ips.find(ip=>ip.period_number===period)||{}).timing_block_id||null;");
    expect(app).toContain("timing_block_id:s.timingBlockId||null,");
  });
});

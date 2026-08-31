# Touch Control Scale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every interactive control in the connected frontend reaches 44×44 on both axes, driven by tokens rather than per-class numbers, with each control class measured against the accessibility gates in isolation before it reaches a screen.

**Architecture:** A control-scale token block is added to `connected-frontend/index.html`'s `:root`. Nine control classes are redefined in terms of those tokens. A new static `component-lab.html` renders every class in every state by pulling the SPA's own `<style>` block at runtime, and a Node gate runner measures the lab with Playwright. Two test layers: fast `vitest` assertions on the stylesheet text (no browser), and the browser gate runner for real rendered measurement.

**Tech Stack:** Plain CSS in a single-file SPA (no build step), `vitest` with Vite's `?raw` import for static assertions, Playwright (already installed at `tools/playwright-staging/node_modules`) for rendered measurement, Python `http.server` to serve the lab.

**Spec:** `docs/superpowers/specs/2026-09-01-touch-control-scale-design.md`

## Global Constraints

- Branch is `design/touch-targets`. **Never push to `main`** — another session is working it.
- `--ctl-min: 44px` — floor for any interactive control, **both axes**.
- `--ctl-h: 44px`, `--ctl-h-lg: 52px`, `--ctl-pad-x: 16px`, `--ctl-pad-x-sm: 12px`, `--ctl-gap: 8px`.
- Governing rule: a variant may change padding, font-size, weight and colour; it may **never** reduce hit size below `--ctl-min`.
- `--border` becomes `#7d8ea8`. `--border-light` is **unchanged** (decorative, outside WCAG 1.4.11).
- `input[type=checkbox]` and `input[type=radio]` keep their 18×18 box — exempt.
- `.skip-link` is exempt (`position:absolute; left:-9999px`, off-screen until focused).
- Every reported count subtracts declared exemptions before it is quoted.
- `connected-frontend/index.html` is one file with one inline `<script>`; a syntax error stops the whole app. `frontend/src/tests/connectedFrontendParses.test.ts` guards this and must stay green.
- Run all `vitest` from `frontend/`. Run all Playwright from `tools/playwright-staging/` (that is where `node_modules` lives).

## File Structure

| file | responsibility |
|---|---|
| `connected-frontend/index.html` | tokens (`:root`), the nine class rules, density removal, border token |
| `connected-frontend/component-lab.html` | **new** — renders every control class × state × content × context |
| `tools/design-audit/lab-gates.mjs` | **new** — measures the lab, exits non-zero on any non-exempt failure |
| `frontend/src/tests/controlScale.test.ts` | **new** — fast static assertions on the stylesheet text |
| `docs/design/02-control-scale-rollout.md` | **new** — before/after measurements recorded at rollout |

---

### Task 1: Control-scale tokens

**Files:**
- Modify: `connected-frontend/index.html:110` (after the spacing scale)
- Test: `frontend/src/tests/controlScale.test.ts` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: CSS custom properties `--ctl-min`, `--ctl-h`, `--ctl-h-lg`, `--ctl-pad-x`, `--ctl-pad-x-sm`, `--ctl-gap` on `:root`, consumed by every later task.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/tests/controlScale.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import html from "../../../connected-frontend/index.html?raw";

// The control scale is CSS in a single-file SPA, so the cheap, fast guard is a
// text assertion on the stylesheet. It cannot prove a rendered height -- that is
// tools/design-audit/lab-gates.mjs -- but it catches a token being renamed,
// deleted, or quietly given a different value, which is how a scale drifts.
describe("control scale tokens", () => {
  it("declares the six control tokens with their agreed values", () => {
    expect(html).toContain("--ctl-min:       44px");
    expect(html).toContain("--ctl-h:         44px");
    expect(html).toContain("--ctl-h-lg:      52px");
    expect(html).toContain("--ctl-pad-x:     16px");
    expect(html).toContain("--ctl-pad-x-sm:  12px");
    expect(html).toContain("--ctl-gap:        8px");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL — `expected '…' to contain '--ctl-min:       44px'`

- [ ] **Step 3: Add the tokens**

In `connected-frontend/index.html`, immediately after line 110 (the line beginning `--sp-xs:8px;`), insert:

```css
  /* ── Control scale (spec 2026-09-01) ──────────────────────────────────
     One scale for every interactive control. 44 sits on the 4px spacing
     grid above, so the touch floor and the spacing rhythm agree.

     THE RULE: a variant may change padding, font-size, weight and colour.
     It may NEVER reduce the hit size below --ctl-min. .btn-xs broke exactly
     that -- a visual variant that also shrank the target to 28x28. */
  --ctl-min:       44px;   /* floor for ANY interactive control, BOTH axes */
  --ctl-h:         44px;   /* default control height                       */
  --ctl-h-lg:      52px;   /* text inputs, selects, textareas              */
  --ctl-pad-x:     16px;   /* = --sp-md                                    */
  --ctl-pad-x-sm:  12px;   /* = --sp-sm                                    */
  --ctl-gap:        8px;   /* = --sp-xs, minimum gap between adjacent targets */
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (1 test)

- [ ] **Step 5: Confirm the SPA still parses**

Run: `cd frontend && npx vitest run`
Expected: PASS — 79 tests (78 existing + 1 new)

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(scale): add control-scale tokens

Six tokens on :root. No rule consumes them yet -- the nine control classes
migrate in later tasks. The governing rule is written into the CSS comment
because that is where the next person adding a control will look."
```

---

### Task 2: Component lab

**Files:**
- Create: `connected-frontend/component-lab.html`
- Test: `frontend/src/tests/controlScale.test.ts` (extend)

**Interfaces:**
- Consumes: `--ctl-*` tokens from Task 1.
- Produces: a page at `/component-lab.html` with one element per control class, each carrying `data-lab-class="<class>"` and `data-lab-state="<state>"`, which `lab-gates.mjs` (Task 3) selects on.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
import lab from "../../../connected-frontend/component-lab.html?raw";

describe("component lab", () => {
  it("pulls the SPA's own style block rather than copying it", () => {
    // A copied stylesheet drifts silently. Fetching index.html and injecting its
    // <style> means drift shows up as a visibly broken lab instead.
    expect(lab).toContain('fetch("index.html")');
    expect(lab).not.toContain("--ctl-min:");   // no token may be redeclared here
  });

  it("renders every control class the scale governs", () => {
    for (const cls of ["btn", "btn-sm", "btn-xs", "tb-btn", "tab-btn",
                       "lh-btn", "btn-lnk", "ff-ro", "input", "select"]) {
      expect(lab).toContain(`data-lab-class="${cls}"`);
    }
  });

  it("covers the states that were never measured on a live screen", () => {
    for (const st of ["resting", "hover", "focus", "disabled", "active"]) {
      expect(lab).toContain(`data-lab-state="${st}"`);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL — cannot resolve `../../../connected-frontend/component-lab.html`

- [ ] **Step 3: Create the lab**

Create `connected-frontend/component-lab.html`:

```html
<!doctype html>
<meta charset="utf-8">
<title>Control component lab</title>
<!--
  Measurement fixture for tools/design-audit/lab-gates.mjs.

  It declares NO styles of its own. It fetches index.html and injects that
  file's <style> block, so a control here is the same control the app ships.
  Copying the CSS would let the lab pass while the app fails.

  Must be served over http (fetch is blocked on file://):
      cd connected-frontend && python3 -m http.server 8123
-->
<style>
  body { margin: 0; font-family: Montserrat, Arial, sans-serif; }
  .lab-grid { display: flex; flex-wrap: wrap; gap: 24px; padding: 24px; align-items: flex-start; }
  .lab-cell { display: flex; flex-direction: column; gap: 6px; }
  .lab-cap { font: 600 10px/1.4 ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; opacity: .6; }
  .lab-ctx-surface { background: #ffffff; padding: 16px; }
  .lab-ctx-bg      { background: #f4f8fc; padding: 16px; }
  .lab-ctx-dark    { background: #002f65; padding: 16px; }
  .lab-row { display: flex; gap: 0; }
</style>

<div id="lab"></div>

<script>
(async function () {
  // Same stylesheet as the app, fetched not copied.
  const res = await fetch("index.html");
  const text = await res.text();
  const css = text.slice(text.indexOf("<style>") + 7, text.indexOf("</style>"));
  const el = document.createElement("style");
  el.textContent = css;
  document.head.appendChild(el);

  const CLASSES = [
    { cls: "btn",      html: '<button class="btn btn-dk">Save Settings</button>' },
    { cls: "btn-sm",   html: '<button class="btn btn-out btn-sm">Edit</button>' },
    { cls: "btn-xs",   html: '<button class="btn btn-out btn-xs" aria-label="Delete">✕</button>' },
    { cls: "tb-btn",   html: '<button class="tb-btn">Search</button>', ctx: "dark" },
    { cls: "tab-btn",  html: '<button class="tab-btn">Sessions</button>' },
    { cls: "lh-btn",   html: '<button class="lh-btn">Learning Hub</button>' },
    { cls: "btn-lnk",  html: '<button class="btn-lnk">Show archived</button>' },
    { cls: "input",    html: '<input type="text" value="703 Squadron">' },
    { cls: "select",   html: '<select><option>Friday</option></select>' },
    { cls: "ff-ro",    html: '<input type="text" class="ff-ro" value="Set by wing" readonly>' },
  ];
  const STATES  = ["resting", "hover", "focus", "disabled", "active"];
  const CONTENT = { short: null, long: "A considerably longer control label than usual",
                    numeric: "67%" };

  const root = document.getElementById("lab");
  for (const { cls, html, ctx } of CLASSES) {
    const section = document.createElement("section");
    section.className = "lab-grid lab-ctx-" + (ctx || "surface");
    for (const state of STATES) {
      for (const [contentName, contentText] of Object.entries(CONTENT)) {
        const cell = document.createElement("div");
        cell.className = "lab-cell";
        const cap = document.createElement("div");
        cap.className = "lab-cap";
        cap.textContent = cls + " · " + state + " · " + contentName;
        const holder = document.createElement("div");
        holder.innerHTML = html;
        const ctl = holder.firstElementChild;
        ctl.setAttribute("data-lab-class", cls);
        ctl.setAttribute("data-lab-state", state);
        ctl.setAttribute("data-lab-content", contentName);
        if (contentText && ctl.tagName !== "SELECT") {
          if ("value" in ctl && ctl.tagName === "INPUT") ctl.value = contentText;
          else ctl.textContent = contentText;
        }
        if (state === "disabled") ctl.disabled = true;
        cell.appendChild(cap); cell.appendChild(ctl);
        section.appendChild(cell);
      }
    }
    root.appendChild(section);
  }

  // Adjacent-target pattern: three actions flush, the shape that fails not on
  // size but on separation.
  const adj = document.createElement("section");
  adj.className = "lab-grid lab-ctx-surface";
  adj.innerHTML =
    '<div class="lab-cell"><div class="lab-cap">action group · adjacent</div>' +
    '<div class="lab-row" data-lab-group="actions">' +
    '<button class="btn btn-out btn-xs" data-lab-class="btn-xs" data-lab-state="resting" aria-label="Mark delivered">✓</button>' +
    '<button class="btn btn-out btn-xs" data-lab-class="btn-xs" data-lab-state="resting" aria-label="Cancel">✕</button>' +
    '<button class="btn btn-out btn-xs" data-lab-class="btn-xs" data-lab-state="resting" aria-label="Edit">✎</button>' +
    "</div></div>";
  root.appendChild(adj);

  document.body.setAttribute("data-lab-ready", "true");
})();
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: Confirm the lab renders**

```bash
cd connected-frontend && python3 -m http.server 8123 &
sleep 2 && curl -s http://127.0.0.1:8123/component-lab.html | head -3
```
Expected: the HTML is served (200). Stop the server with `pkill -f "http.server 8123"`.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/component-lab.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(lab): component lab for per-class gate measurement

Renders every control class across resting/hover/focus/disabled/active and
short/long/numeric content. Disabled, hover, active and focus have never been
measured -- every audit so far only saw states that happened to be on screen.

It fetches index.html's <style> block rather than copying it, so drift shows up
as a broken lab instead of a lab that passes while the app fails."
```

---

### Task 3: Lab gate runner

**Files:**
- Create: `tools/design-audit/lab-gates.mjs`

**Interfaces:**
- Consumes: `data-lab-class` / `data-lab-state` attributes from Task 2.
- Produces: CLI `node ../design-audit/lab-gates.mjs`, exit 0 when every non-exempt control passes, exit 1 otherwise. Used as the test command by Tasks 4–7.

- [ ] **Step 1: Write the runner**

Create `tools/design-audit/lab-gates.mjs`:

```js
// Per-class gate measurement against connected-frontend/component-lab.html.
// A class that fails here never reaches a screen -- "a failing foundation
// multiplies" (apple-design, build order step 4).
//
//   cd tools/playwright-staging          # where node_modules lives
//   node ../design-audit/lab-gates.mjs
//
// Serves the lab itself on :8123 and stops it on exit.
import { chromium, devices } from "@playwright/test";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CF   = path.resolve(HERE, "../../connected-frontend");
const URL  = "http://127.0.0.1:8123/component-lab.html";
const MIN  = 44;

// Declared exemptions. Every count printed below has these subtracted, because
// a number that has not had its exemptions removed is not a result.
const EXEMPT_CLASSES = new Set([]);          // none at class level today
const EXEMPT_REASON  = {
  "checkbox/radio": "an 18x18 box with a 44px hit area via its label is correct",
  "skip-link": "position:absolute; left:-9999px -- off-screen until focused",
};

const server = spawn("python3", ["-m", "http.server", "8123"], { cwd: CF, stdio: "ignore" });
const stop = () => { try { server.kill(); } catch {} };
process.on("exit", stop); process.on("SIGINT", () => { stop(); process.exit(130); });
await new Promise(r => setTimeout(r, 1200));

const browser = await chromium.launch();
const page = await (await browser.newContext({ ...devices["Pixel 7"] })).newPage();
await page.goto(URL, { waitUntil: "domcontentloaded" });
await page.waitForSelector("body[data-lab-ready='true']", { timeout: 10000 });
await page.waitForTimeout(400);

const results = await page.evaluate((min) => {
  const out = [];
  for (const e of document.querySelectorAll("[data-lab-class]")) {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2, h = min / 2 - 1;
    const hit = [[cx, cy - h], [cx, cy + h], [cx - h, cy], [cx + h, cy]].every(([x, y]) => {
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
      const t = document.elementFromPoint(x, y);
      return t && (t === e || e.contains(t));      // ancestors do NOT count
    });
    out.push({
      cls: e.getAttribute("data-lab-class"),
      state: e.getAttribute("data-lab-state"),
      content: e.getAttribute("data-lab-content"),
      w: Math.round(r.width), h: Math.round(r.height),
      boxOk: r.width >= min && r.height >= min,
      hitOk: hit,
      overflow: e.scrollWidth > e.clientWidth + 2,
      focusRing: s.outlineStyle !== "none" || s.boxShadow !== "none",
    });
  }
  return out;
}, MIN);

const byClass = new Map();
for (const r of results) {
  if (!byClass.has(r.cls)) byClass.set(r.cls, []);
  byClass.get(r.cls).push(r);
}

let failed = 0;
console.log(`lab gates — ${results.length} rendered controls, threshold ${MIN}px\n`);
for (const [cls, rows] of [...byClass.entries()].sort()) {
  const bad = rows.filter(r => !r.boxOk || !r.hitOk);
  const over = rows.filter(r => r.overflow);
  const ok = bad.length === 0 && over.length === 0;
  if (!ok) failed++;
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${cls.padEnd(10)} ` +
              `${String(rows.length).padStart(3)} variants  ` +
              `size ${rows.length - bad.length}/${rows.length}  ` +
              `no-overflow ${rows.length - over.length}/${rows.length}`);
  for (const b of bad.slice(0, 3)) {
    console.log(`          ${b.w}x${b.h}  ${b.state}/${b.content}  ` +
                `${!b.boxOk ? "below threshold" : "not isolated"}`);
  }
  for (const o of over.slice(0, 2)) {
    console.log(`          long label overflows in ${o.state}/${o.content}`);
  }
}

console.log(`\nexemptions applied: ${Object.keys(EXEMPT_REASON).join(", ") || "none"}`);
for (const [k, why] of Object.entries(EXEMPT_REASON)) console.log(`  ${k} — ${why}`);

await browser.close(); stop();
console.log(failed ? `\nLAB GATES FAILED — ${failed} class(es)` : "\nLAB GATES PASSED");
process.exit(failed ? 1 : 0);
```

- [ ] **Step 2: Run it to verify it FAILS on the current scale**

```bash
cd tools/playwright-staging && node ../design-audit/lab-gates.mjs
```
Expected: FAIL — `.btn`, `.btn-sm`, `.btn-xs`, `input`, `select`, `.tb-btn`, `.tab-btn`, `.lh-btn`, `.btn-lnk` all report `below threshold` at 28–37px. This is the red state the next four tasks turn green.

- [ ] **Step 3: Commit**

```bash
git add tools/design-audit/lab-gates.mjs
git commit -m "test(lab): per-class gate runner

Measures every control class in the lab and exits non-zero on any non-exempt
failure. Verified red against the current 28px scale before any class migrates.

The hit test does NOT accept a probe landing on an ancestor -- tapping a
container does not activate the control inside it. An earlier version of this
predicate turned 44 undersized controls into passes."
```

---

### Task 4: Buttons

**Files:**
- Modify: `connected-frontend/index.html:448` (`.btn`), `:461` (`.btn-sm`), `:462` (`.btn-xs`)
- Test: `frontend/src/tests/controlScale.test.ts` (extend), `tools/design-audit/lab-gates.mjs` (run)

**Interfaces:**
- Consumes: `--ctl-h`, `--ctl-min`, `--ctl-pad-x`, `--ctl-pad-x-sm` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
describe("button classes consume the scale", () => {
  it(".btn uses --ctl-h, not a literal height", () => {
    const rule = html.slice(html.indexOf(".btn{"), html.indexOf(".btn{") + 400);
    expect(rule).toContain("min-height:var(--ctl-h)");
    expect(rule).not.toContain("min-height:28px");
  });

  it(".btn-xs keeps both axes at the floor -- a visual variant, not a smaller target", () => {
    const rule = html.slice(html.indexOf(".btn-xs{"), html.indexOf(".btn-xs{") + 260);
    expect(rule).toContain("min-height:var(--ctl-min)");
    expect(rule).toContain("min-width:var(--ctl-min)");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL — `expected '.btn{padding:9px 16px;…' to contain 'min-height:var(--ctl-h)'`

- [ ] **Step 3: Migrate the three rules**

In `connected-frontend/index.html`, replace `padding:9px 16px;` in the `.btn{` rule at line 448 with `padding:0 var(--ctl-pad-x);`, and `min-height:28px;` in that same rule with `min-height:var(--ctl-h);`.

Replace line 461 entirely:

```css
.btn-sm{padding:0 var(--ctl-pad-x-sm);font-size:var(--fs-xs);min-height:var(--ctl-min);}
```

Replace line 462 entirely:

```css
/* A VISUAL variant only: smaller type and tighter padding, same 44x44 target.
   It previously set 28x28 and was the clearest breach of the scale rule. */
.btn-xs{padding:0 var(--ctl-pad-x-sm);font-size:var(--fs-xs);border-radius:5px;min-height:var(--ctl-min);min-width:var(--ctl-min);}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Measure the classes in the lab**

```bash
cd tools/playwright-staging && node ../design-audit/lab-gates.mjs
```
Expected: `ok  btn`, `ok  btn-sm`, `ok  btn-xs`. Remaining classes still FAIL — they migrate in Tasks 5 and 6.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(scale): buttons on the control scale

.btn, .btn-sm and .btn-xs consume --ctl-h/--ctl-min/--ctl-pad-x. .btn alone
rendered at five different heights (28/33/35/37/39) depending on context; it now
has one.

.btn-xs keeps its small type and tight padding and still occupies 44x44 --
small-looking, not small-to-touch. Verified green in the component lab."
```

---

### Task 5: Fields

**Files:**
- Modify: `connected-frontend/index.html:469` (bare inputs/select/textarea), `:572` (`.ff` fields)
- Test: `frontend/src/tests/controlScale.test.ts` (extend), `tools/design-audit/lab-gates.mjs` (run)

**Interfaces:**
- Consumes: `--ctl-h-lg`, `--ctl-pad-x-sm` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
describe("fields sit at the larger height", () => {
  it("bare inputs, selects and textareas use --ctl-h-lg", () => {
    const i = html.indexOf("input[type=date],input[type=search]");
    expect(html.slice(i, i + 220)).toContain("min-height:var(--ctl-h-lg)");
  });

  it("checkbox and radio keep an 18px box -- the box is not the target", () => {
    expect(html).toContain("input[type=checkbox],input[type=radio]{width:18px;height:18px;}");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL on the first assertion — the rule still reads `min-height:28px`.

- [ ] **Step 3: Migrate both rules**

Replace line 469 entirely:

```css
input[type=date],input[type=search],input[type=email],input:not([type]),select,textarea{min-height:var(--ctl-h-lg);font-size:inherit;}
```

In the `.ff select,.ff input,.ff textarea{` rule at line 572, replace `padding:9px 11px;` with `min-height:var(--ctl-h-lg);padding:0 var(--ctl-pad-x-sm);`.

Leave `input[type=checkbox],input[type=radio]{width:18px;height:18px;}` at line 474 untouched — the box is not the target, and the label wrapper carries the hit area.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (8 tests)

- [ ] **Step 5: Measure in the lab**

```bash
cd tools/playwright-staging && node ../design-audit/lab-gates.mjs
```
Expected: `ok  input`, `ok  select`, `ok  ff-ro` added to the passing set.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(scale): fields at 52px

Inputs, selects and textareas take --ctl-h-lg. Typing wants a larger target than
tapping, which is why fields sit above the 44px floor rather than on it.

Checkbox and radio keep their 18x18 box deliberately: the box is not the target,
and growing it would be the wrong fix for a real problem."
```

---

### Task 6: Remaining control classes

**Files:**
- Modify: `connected-frontend/index.html:250` (`.tb-btn`), `:583` (`.tab-btn`), `:940` (`.lh-btn`), `:477` (`.btn-lnk`)
- Test: `frontend/src/tests/controlScale.test.ts` (extend), `tools/design-audit/lab-gates.mjs` (run)

**Interfaces:**
- Consumes: `--ctl-h`, `--ctl-min`, `--ctl-pad-x-sm` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
describe("the remaining control classes", () => {
  for (const [cls, token] of [["tb-btn", "--ctl-min"], ["tab-btn", "--ctl-h"],
                              ["lh-btn", "--ctl-min"], ["btn-lnk", "--ctl-min"]] as const) {
    it(`.${cls} consumes ${token}`, () => {
      const i = html.indexOf(`.${cls}{`);
      expect(i, `.${cls} rule not found`).toBeGreaterThan(-1);
      expect(html.slice(i, i + 320)).toContain(`min-height:var(${token})`);
    });
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL — four failures, one per class.

- [ ] **Step 3: Migrate the four rules**

In the `.tb-btn{` rule at line 250, replace `padding:4px 12px;` with `padding:0 var(--ctl-pad-x-sm);` and replace its `min-height:28px` with `min-height:var(--ctl-min)`.

In the `.tab-btn{` rule at line 583, replace `padding:8px 14px;` with `min-height:var(--ctl-h);padding:0 var(--ctl-pad-x-sm);`.

In the `.lh-btn{` rule at line 940, replace `min-height:28px;` with `min-height:var(--ctl-min);min-width:var(--ctl-min);` and `padding:3px 8px;` with `padding:0 var(--ctl-pad-x-sm);`.

In the `.btn-lnk{` rule at line 477, replace `padding:0 2px;` with `min-height:var(--ctl-min);padding:0 var(--ctl-pad-x-sm);`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (12 tests)

- [ ] **Step 5: Measure in the lab — every class must now pass**

```bash
cd tools/playwright-staging && node ../design-audit/lab-gates.mjs
```
Expected: `LAB GATES PASSED`, exit 0. If any class still fails, it is `not isolated` rather than `below threshold` — that is Task 7's problem, not a size problem, and the message says which.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(scale): toolbar, tab, learning-hub and link buttons on the scale

Completes the nine-class migration. Every control class now derives its size
from a token; ten arbitrary heights (16-41px) collapse to two plus a floor.

Component lab is green for every class."
```

---

### Task 7: Adjacent targets

**Files:**
- Modify: `connected-frontend/index.html` (add a rule after `.btn-xs` at line 462)
- Test: `frontend/src/tests/controlScale.test.ts` (extend), `tools/design-audit/lab-gates.mjs` (run)

**Interfaces:**
- Consumes: `--ctl-gap` from Task 1.
- Produces: `.ctl-group` — the class markup applies to any row of adjacent actions.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
describe("adjacent targets are separated", () => {
  it("declares .ctl-group with --ctl-gap", () => {
    // 23 controls measured large enough and still unreachable at their edges,
    // because they sit flush. Size does not fix that; separation does.
    expect(html).toContain(".ctl-group{display:inline-flex;gap:var(--ctl-gap);");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL — `.ctl-group` is not declared.

- [ ] **Step 3: Add the rule**

Immediately after the `.btn-xs{…}` rule, add:

```css
/* Adjacent actions must not touch. 23 controls measured large enough and still
   unreachable at their edges because they sat flush -- a tap near a boundary
   activated the neighbour. Growing the controls makes that worse, not better. */
.ctl-group{display:inline-flex;gap:var(--ctl-gap);align-items:center;flex-wrap:wrap;}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (13 tests)

- [ ] **Step 5: Apply it to the session action rows**

Find every place three session actions render together:

```bash
grep -n 'aria-label="Mark Session' connected-frontend/index.html | head -3
```

Wrap each such run of buttons in `<span class="ctl-group">…</span>`. Then re-run the lab:

```bash
cd tools/playwright-staging && node ../design-audit/lab-gates.mjs
```
Expected: `LAB GATES PASSED` — the lab's `data-lab-group="actions"` row now reports isolated.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(scale): separate adjacent action targets

.ctl-group puts --ctl-gap between adjacent controls. This is the failure size
alone does not fix: 23 controls were big enough and still not reachable at their
edges because they sat flush against each other."
```

---

### Task 8: Border contrast

**Files:**
- Modify: `connected-frontend/index.html:28` (`--border`)
- Test: `frontend/src/tests/controlScale.test.ts` (extend)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
describe("border contrast", () => {
  it("--border meets WCAG 1.4.11 at 3:1", () => {
    // #7d8ea8 measures 3.33:1 on #ffffff and 3.12:1 on --bg #f4f8fc -- the first
    // candidate clearing 3:1 against BOTH surfaces the app paints on.
    expect(html).toContain("--border:       #7d8ea8;");
  });

  it("--border-light is left alone -- decoration is outside 1.4.11", () => {
    // 1.4.11 covers information identifying components and states, not
    // decorative graphics. Darkening hairline dividers would be styling.
    expect(html).toContain("--border-light: #e4edf5;");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL on the first assertion — the token is still `#d1dce8`.

- [ ] **Step 3: Change the token**

Replace line 28:

```css
  --border:       #7d8ea8;   /* 3.33:1 on #fff, 3.12:1 on --bg — WCAG 1.4.11 */
```

Leave line 29 (`--border-light: #e4edf5;`) and the high-contrast overrides at lines 154–155 unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (15 tests)

- [ ] **Step 5: Confirm the contrast register improves**

```bash
python3 ~/.claude/skills/apple-design/scripts/css_audit.py connected-frontend/index.html --format csv \
  > docs/design/contrast-register-connected.csv
python3 -c "
import csv
rows=[r for r in csv.DictReader(open('docs/design/contrast-register-connected.csv'))]
b=[r for r in rows if r['result']=='FAIL' and r['kind']!='text']
print('boundary-advisory failures:', len(b), '(was 37)')"
```
Expected: materially fewer than 37. Record the exact number — Task 10 quotes it.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts docs/design/contrast-register-connected.csv
git commit -m "feat(scale): --border to #7d8ea8 for WCAG 1.4.11

1.39:1 to 3.33:1 on white, 3.12:1 on --bg -- the first measured candidate
clearing 3:1 against both surfaces the app paints on.

--border-light is deliberately unchanged. 1.4.11 covers visual information
required to identify components and states, not decoration, so darkening
hairline dividers would be styling rather than compliance."
```

---

### Task 9: Retire Display Size

**Files:**
- Modify: `connected-frontend/index.html:1044-1053` (density CSS), `:2311` (`#dens-card`), `:8552` (`_setDensity`), `:8561`, `:8567` (boot calls)
- Test: `frontend/src/tests/controlScale.test.ts` (extend)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/tests/controlScale.test.ts`:

```ts
describe("Display Size is retired", () => {
  it("no density CSS, card, function or boot call remains", () => {
    // A setting that can drive controls below the touch floor contradicts a
    // single-scale system. Removed deliberately on 2026-09-01 (G8 capability
    // removal, recorded in the spec).
    expect(html).not.toContain('data-density');
    expect(html).not.toContain('id="dens-card"');
    expect(html).not.toContain("_setDensity");
    expect(html).not.toContain("displayDensity");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: FAIL — `data-density` still present (10 CSS rules plus the card).

- [ ] **Step 3: Delete all four**

Delete lines 1044–1053 inclusive — the ten `body[data-density="compact"]` rules.

Delete the whole `<div class="card" id="dens-card"> … </div>` block starting at line 2311, up to and including its closing `</div>`.

Delete the `function _setDensity(val){ … }` block starting at line 8552, and both boot-time calls (originally lines 8561 and 8567) that read `_setDensity(localStorage.getItem('displayDensity')||'comfortable');`.

The stale `displayDensity` localStorage key in existing browsers is left alone — nothing reads it once the attribute is gone, and cleanup code that exists only to delete something harmless is not worth its own maintenance.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/tests/controlScale.test.ts`
Expected: PASS (16 tests)

- [ ] **Step 5: Confirm the SPA still parses and nothing referenced density**

```bash
cd frontend && npx vitest run
grep -rn "density\|dens-card" ../frontend/e2e ../frontend/e2e-connected ../backend/tests | head -3
```
Expected: all vitest green (including `connectedFrontendParses`); grep returns nothing.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html frontend/src/tests/controlScale.test.ts
git commit -m "feat(scale): retire the Display Size setting

Compact forced .btn to min-height:28px -- by definition below the touch floor.
A setting that can drive controls under 44px contradicts a single-scale system,
so it goes.

This is a G8 capability removal, taken deliberately by the product owner on
2026-09-01 and recorded in the spec rather than slipped in. Anyone currently on
Compact gets the larger scale at next load with no way back. No test anywhere
referenced density."
```

---

### Task 10: Screen rollout and recorded result

**Files:**
- Create: `docs/design/02-control-scale-rollout.md`
- Modify: `docs/design/01-staging-gate-audit.md` (link forward to the rollout)

**Interfaces:**
- Consumes: every preceding task.
- Produces: the recorded before/after, which is the evidence the gate now passes.

- [ ] **Step 1: Re-run every gate against a local build**

```bash
cd connected-frontend && python3 -m http.server 8123 &
cd tools/playwright-staging
node ../design-audit/lab-gates.mjs
node ../design-audit/g5-hit-targets.mjs        # expects a running app; see its header
node ../design-audit/g1-contrast-rendered.mjs
node ../design-audit/g3-g11-text-and-names.mjs
node ../design-audit/g4-keyboard.mjs
pkill -f "http.server 8123"
```

- [ ] **Step 2: Write the rollout record**

Create `docs/design/02-control-scale-rollout.md` containing, with the real measured figures substituted for each bracketed value from Step 1:

```markdown
# Control scale rollout — measured result

**Date:** [date of the run] · **Spec:** docs/superpowers/specs/2026-09-01-touch-control-scale-design.md

| gate | before | after |
|---|---|---|
| G5 touch, non-exempt | 78 fail of 83 | [n] fail |
| G5 pointer, non-exempt | 22 fail of 182 | [n] fail |
| G1 contrast | 1 fail of 1035 | [n] fail |
| G3 200% text | 5/5 screens pass | [result] |
| G4 keyboard | 35 reached, 0 ringless | [result] |
| G11 semantics | 329 named, 0 unnamed | [result] |
| boundary-advisory borders | 37 | [n from Task 8 Step 5] |

Exemptions subtracted from every count above: `.skip-link` (off-screen until
focused) and `input[type=checkbox|radio]` boxes (18×18 by design, 44px hit area
via the label).

## Density cost, as predicted

[rows visible before] rows → [rows visible after] rows in the same vertical
space on the curriculum list. The spec accepted this explicitly.
```

- [ ] **Step 3: Run the whole test suite**

```bash
cd frontend && npx vitest run
cd ../backend && ./.venv/bin/python -m pytest -q
```
Expected: vitest all green; backend unchanged from its baseline (this is CSS and markup only — 5 pre-existing failures, documented in `docs/final/11-browser-matrix.md`, are not caused here).

- [ ] **Step 4: Commit**

```bash
git add docs/design/02-control-scale-rollout.md docs/design/01-staging-gate-audit.md
git commit -m "docs(design): record the control-scale rollout result

Before/after for every gate, with exemptions subtracted from each count. The
density cost is recorded as measured rather than as predicted, because the
prediction was the basis of the decision and should be checked against reality."
```

- [ ] **Step 5: Report, do not deploy**

Do **not** push to `main` and do **not** deploy. Another session is working
`main`; the branch `design/touch-targets` is complete and awaiting the product
owner's decision on when to merge.

---

## Self-Review

**Spec coverage.** Control scale tokens → Task 1. Governing rule → Task 1 comment, enforced by Task 4's `.btn-xs` assertion. Nine class mappings → Tasks 4, 5, 6. Adjacent targets → Task 7. Component lab → Tasks 2, 3. Retiring Display Size → Task 9. Borders → Task 8. Verification → Tasks 3, 10. Exceptions (`.skip-link`, checkbox/radio, `--border-light`) → Task 3's exemption block, Task 5 Step 3, Task 8's second assertion.

**Placeholders.** The only bracketed values are in Task 10 Step 2, where they are explicitly the output of Step 1 and cannot be known in advance.

**Type consistency.** `--ctl-min`, `--ctl-h`, `--ctl-h-lg`, `--ctl-pad-x`, `--ctl-pad-x-sm`, `--ctl-gap` are spelled identically in Tasks 1, 4, 5, 6, 7. `data-lab-class` / `data-lab-state` / `data-lab-content` are produced in Task 2 and consumed in Task 3. `.ctl-group` is declared and applied in Task 7 only.

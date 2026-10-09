#!/usr/bin/env node
// Parity proof for the Main TMS (connected-frontend) monolith extraction.
//
// Usage (from the repo root; acorn is resolved from frontend/node_modules):
//   node tools/architecture/frontend_parity.mjs [base-ref]     (default 8ecd2cd)
//
// Builds two "programs" -- the ordered list of classic scripts the browser
// runs -- one from <base-ref>:connected-frontend/ and one from the working
// tree, by reading index.html's <script> tags in document order (inline
// blocks, and js/*.js for <script src>). It parses every script with a real
// JavaScript parser and proves the extraction moved code without changing it:
//
//  (a) the multiset of top-level function declarations is identical, name for
//      name AND source text for source text; for names declared more than once,
//      the declaration that wins (the last one the browser instantiates) has
//      the same source text as before;
//  (b) every other top-level statement appears verbatim (same multiset of
//      source texts). Statements with load-time effects ("ordered") keep their
//      exact relative order. Only "pure" statements -- let/const whose
//      initialisers are literals, object/array literals of literals,
//      function/arrow expressions or new Set/Map(<literals>), plus empty
//      statements -- may move, and only EARLIER relative to the ordered
//      statements (never later), so no load-time code can newly meet a TDZ;
//  (c) every comment of the original program still exists (as a multiset);
//      new comments may appear only in the header of a js/ file.
//
// Exit status 0 = parity proven; 1 = a difference (printed).
import { execFileSync } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(join(ROOT, "frontend", "package.json"));
const acorn = require("acorn");

export const PURE_NEW_CALLEES = new Set(["Set", "Map"]);

// True when evaluating `node` can have no observable effect and reads no
// binding (so it cannot hit a TDZ and its position is unobservable).
export function isPureExpr(node) {
  if (!node) return true;
  switch (node.type) {
    case "Literal":
      return true;
    case "TemplateLiteral":
      return node.expressions.every(isPureExpr);
    case "ArrayExpression":
      return node.elements.every(e => e && e.type !== "SpreadElement" && isPureExpr(e));
    case "ObjectExpression":
      return node.properties.every(p =>
        p.type === "Property" && (!p.computed || isPureExpr(p.key)) && isPureExpr(p.value));
    case "ArrowFunctionExpression":
    case "FunctionExpression":
      return true; // creating a closure runs none of its body
    case "UnaryExpression":
      return node.operator !== "delete" && isPureExpr(node.argument);
    case "BinaryExpression":
    case "LogicalExpression":
      return isPureExpr(node.left) && isPureExpr(node.right);
    case "ConditionalExpression":
      return isPureExpr(node.test) && isPureExpr(node.consequent) && isPureExpr(node.alternate);
    case "NewExpression":
      return node.callee.type === "Identifier" && PURE_NEW_CALLEES.has(node.callee.name) &&
        node.arguments.every(a => a.type !== "SpreadElement" && isPureExpr(a));
    case "Identifier":
      return node.name === "undefined";
    default:
      return false;
  }
}

// "function" | "pure" | "ordered"
export function classify(stmt) {
  if (stmt.type === "FunctionDeclaration") return "function";
  if (stmt.type === "EmptyStatement") return "pure";
  if (stmt.type === "VariableDeclaration" && stmt.kind !== "var" &&
      stmt.declarations.every(d => d.id.type === "Identifier" && isPureExpr(d.init))) return "pure";
  return "ordered";
}

export function parseScript(src) {
  const comments = [];
  const ast = acorn.parse(src, { ecmaVersion: "latest", sourceType: "script", onComment: comments });
  return { ast, comments };
}

// Script tags of an index.html in document order: {kind:'inline', src} | {kind:'file', path}.
export function scriptTags(html) {
  const out = [];
  const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/g;
  let m;
  while ((m = re.exec(html))) {
    const srcAttr = /\bsrc="([^"]+)"/.exec(m[1]);
    if (srcAttr) out.push({ kind: "file", path: srcAttr[1] });
    else out.push({ kind: "inline", src: m[2] });
  }
  return out;
}

function gitShow(ref, path) {
  return execFileSync("git", ["show", `${ref}:${path}`], { cwd: ROOT, encoding: "utf8", maxBuffer: 1 << 28 });
}

function loadProgram(read) {
  const html = read("connected-frontend/index.html");
  let inlineN = 0;
  return scriptTags(html).map(t => {
    if (t.kind === "inline") return { label: `index.html inline #${inlineN++}`, src: t.src, isFile: false };
    return { label: t.path, src: read(`connected-frontend/${t.path}`), isFile: true };
  });
}

function analyse(program) {
  const fns = [];      // {name, text, label}
  const stmts = [];    // {text, cls, label, seq}
  const comments = []; // {text, label, inHeader}
  let seq = 0;
  for (const script of program) {
    const { ast, comments: cs } = parseScript(script.src);
    const firstStart = ast.body.length ? ast.body[0].start : Infinity;
    for (const c of cs) comments.push({ text: c.value, label: script.label, inHeader: script.isFile && c.end <= firstStart });
    for (const s of ast.body) {
      const text = script.src.slice(s.start, s.end);
      const cls = classify(s);
      if (cls === "function") fns.push({ name: s.id.name, text, label: script.label });
      else stmts.push({ text, cls, label: script.label, seq: seq++ });
    }
  }
  return { fns, stmts, comments };
}

function multisetDiff(a, b) {
  const m = new Map();
  for (const x of a) m.set(x, (m.get(x) || 0) + 1);
  for (const x of b) m.set(x, (m.get(x) || 0) - 1);
  return [...m].filter(([, n]) => n !== 0);
}

export function compare(orig, next) {
  const A = analyse(orig), B = analyse(next);
  const failures = [];
  const short = t => t.replace(/\s+/g, " ").slice(0, 100);

  // (a) functions
  const fnKey = f => `${f.name}\u0000${f.text}`;
  const fnDiff = multisetDiff(A.fns.map(fnKey), B.fns.map(fnKey));
  for (const [k, n] of fnDiff) failures.push(`function ${n > 0 ? "missing" : "added"}: ${k.split("\u0000")[0]} (${short(k.split("\u0000")[1])})`);
  const winners = fns => { const w = new Map(); for (const f of fns) w.set(f.name, f); return w; };
  const wa = winners(A.fns), wb = winners(B.fns);
  const dupNames = [...new Set(A.fns.map(f => f.name))].filter(n => A.fns.filter(f => f.name === n).length > 1);
  for (const n of dupNames) {
    if (!wb.has(n) || wb.get(n).text !== wa.get(n).text) failures.push(`duplicate-declared ${n}: a different declaration now wins`);
  }
  let identicalFns = 0;
  { const pool = new Map(); for (const f of B.fns) { const k = fnKey(f); pool.set(k, (pool.get(k) || 0) + 1); }
    for (const f of A.fns) { const k = fnKey(f); if (pool.get(k) > 0) { identicalFns++; pool.set(k, pool.get(k) - 1); } } }

  // (b) other statements
  const stDiff = multisetDiff(A.stmts.map(s => s.text), B.stmts.map(s => s.text));
  for (const [t, n] of stDiff) failures.push(`statement ${n > 0 ? "missing" : "added"}: ${short(t)}`);
  const ordA = A.stmts.filter(s => s.cls === "ordered").map(s => s.text);
  const ordB = B.stmts.filter(s => s.cls === "ordered").map(s => s.text);
  let orderOk = ordA.length === ordB.length && ordA.every((t, i) => t === ordB[i]);
  if (!orderOk) {
    const i = ordA.findIndex((t, k) => t !== ordB[k]);
    failures.push(`ordered statements changed order at #${i}: was "${short(ordA[i] || "")}", now "${short(ordB[i] || "")}"`);
  }
  // Pure statements may only move earlier relative to ordered statements.
  const precedingOrdered = stmts => {
    const out = new Map(); let n = 0;
    for (const s of stmts) {
      if (s.cls === "ordered") { n++; continue; }
      if (!out.has(s.text)) out.set(s.text, []);
      out.get(s.text).push(n);
    }
    return out;
  };
  const pa = precedingOrdered(A.stmts), pb = precedingOrdered(B.stmts);
  let movedPure = 0, latePure = 0;
  for (const [t, as] of pa) {
    const bs = pb.get(t) || [];
    as.forEach((n, i) => {
      if (bs[i] === undefined) return; // reported by the multiset check
      if (bs[i] < n) movedPure++;
      if (bs[i] > n) { latePure++; failures.push(`pure statement moved LATER (after ${bs[i] - n} more ordered statements): ${short(t)}`); }
    });
  }

  // (c) comments
  const cDiff = multisetDiff(A.comments.map(c => c.text), B.comments.map(c => c.text));
  const headerTexts = B.comments.filter(c => c.inHeader).map(c => c.text);
  for (const [t, n] of cDiff) {
    if (n > 0) failures.push(`comment lost: ${short(t)}`);
    else if (headerTexts.filter(h => h === t).length < -n) failures.push(`comment added outside a js/ file header: ${short(t)}`);
  }

  return {
    failures,
    summary: {
      functions: { original: A.fns.length, now: B.fns.length, identical: identicalFns, duplicateNames: dupNames.length },
      statements: {
        original: A.stmts.length, now: B.stmts.length,
        identical: A.stmts.length - stDiff.filter(([, n]) => n > 0).reduce((s, [, n]) => s + n, 0),
        ordered: ordA.length, orderedSameOrder: orderOk, pureMovedEarlier: movedPure, pureMovedLater: latePure,
      },
      comments: { original: A.comments.length, now: B.comments.length, fileHeader: headerTexts.length },
      scripts: next.map(s => s.label),
    },
  };
}

function main() {
  const base = process.argv[2] || "8ecd2cd";
  const orig = loadProgram(p => gitShow(base, p));
  const next = loadProgram(p => {
    const f = join(ROOT, p);
    if (!existsSync(f)) throw new Error(`index.html loads ${p}, which does not exist`);
    return readFileSync(f, "utf8");
  });
  const { failures, summary } = compare(orig, next);
  console.log(JSON.stringify(summary, null, 2));
  if (failures.length) {
    console.log(`FRONTEND PARITY: FAIL (${failures.length})`);
    for (const f of failures.slice(0, 50)) console.log(" - " + f);
    return 1;
  }
  console.log(`FRONTEND PARITY: PASS vs ${base}`);
  return 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exit(main());

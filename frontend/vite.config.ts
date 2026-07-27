/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// `base` controls the public path. For GitHub Pages *project* sites the app is served from
// /<repo>/, so set VITE_BASE=/<repo>/ at build time. Defaults to "/" (same-domain / local).
//
// `mode=single` produces a self-contained index.html with all JS/CSS inlined; used by
// `make connected` to regenerate connected-frontend/index.html from the React source.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const isSingle = mode === "single";
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:8000";
  return {
    base: isSingle ? "./" : (env.VITE_BASE || "/"),
    plugins: [react(), ...(isSingle ? [viteSingleFile()] : [])],
    server: {
      port: 5173,
      proxy: { "/api": { target: apiTarget, changeOrigin: true } },
    },
    build: isSingle ? {
      outDir: "dist-single",
      emptyOutDir: true,
      target: "esnext",
      assetsInlineLimit: 100_000_000,   // inline all assets (fonts, images)
      chunkSizeWarningLimit: 100_000_000,
      rollupOptions: { output: { inlineDynamicImports: true } },
    } : {},
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/tests/setup.ts"],
      // e2e/**  are Playwright specs (run via `npm run test:e2e`), not Vitest —
      // without this exclude, `vitest run` tries to execute them directly and
      // fails with "Playwright Test did not expect test() to be called here."
      exclude: ["**/node_modules/**", "e2e/**", "e2e-connected/**"],
    },
  };
});

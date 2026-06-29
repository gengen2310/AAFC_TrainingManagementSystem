// After `vite build`, GitHub Pages needs a 404.html that mirrors index.html so that refreshing
// a nested route (e.g. /report-catalogue) still loads the SPA instead of a Pages 404.
import { copyFileSync, existsSync } from "node:fs";
const idx = "dist/index.html";
if (existsSync(idx)) { copyFileSync(idx, "dist/404.html"); console.log("Created dist/404.html (SPA fallback)"); }
else { console.error("dist/index.html not found — run vite build first"); process.exit(1); }

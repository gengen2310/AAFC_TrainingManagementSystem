# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Type-check first using plain --noEmit (avoids tsc -b build-mode which reads/writes
# tsconfig.tsbuildinfo and can fail silently in container if the file carries stale paths).
RUN npx tsc --noEmit
# Vite build produces the actual dist/ output; esbuild handles transpilation internally.
RUN npx vite build

# ── Serve stage ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Railway injects PORT at runtime (typically 8080)
EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]

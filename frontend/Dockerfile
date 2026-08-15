# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Belt-and-suspenders: remove any stale tsc build cache that may have been
# included in the archive despite .dockerignore (Railway's build agent may not
# apply .dockerignore client-side the way the Docker CLI does).
RUN find /app -name "*.tsbuildinfo" -delete 2>/dev/null || true
# npm run build = tsc -b && vite build  (produces dist/)
RUN npm run build

# ── Serve stage ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Railway injects PORT at runtime (typically 8080)
EXPOSE 8080

ENTRYPOINT ["/docker-entrypoint.sh"]

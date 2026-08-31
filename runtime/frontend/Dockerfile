# syntax=docker/dockerfile:1
#
# Two targets: `dev` runs the Vite dev server with HMR (used by the override
# compose file); `production` serves the static build through nginx.

FROM node:22-alpine AS deps
WORKDIR /app
COPY runtime/frontend/package.json runtime/frontend/package-lock.json* ./
RUN npm ci 2>/dev/null || npm install

# ── Dev ──────────────────────────────────────────────────────────────────────
FROM deps AS dev
WORKDIR /app
COPY runtime/frontend/ ./
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ── Build ────────────────────────────────────────────────────────────────────
FROM deps AS build
WORKDIR /app
COPY runtime/frontend/ ./
RUN npm run build

# ── Production ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY runtime/frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]

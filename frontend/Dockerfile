# ---------- Web tier (part 1): React / TanStack Start front end ----------

# Stage 1: build
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund
COPY . .
# Build as a plain Node server (Lovable defaults to Cloudflare)
ENV NITRO_PRESET=node-server
# The browser calls /api/..., which Nginx forwards to the app tier
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Stage 2: run (only the built output, no source or node_modules)
FROM node:22-alpine
WORKDIR /app
COPY --from=build /app/.output ./.output
ENV NODE_ENV=production PORT=3000 HOST=0.0.0.0
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]

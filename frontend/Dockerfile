FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Hardcode the API URL at build time (required for Next.js NEXT_PUBLIC_ vars).
# Override via Render dashboard → Environment → NEXT_PUBLIC_API_URL if the
# backend lives elsewhere (e.g. a PR preview with a -suffixed hostname).
ARG NEXT_PUBLIC_API_URL=https://dhanvantari-api-pxgv.onrender.com
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ── Production stage ──
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=10000
ENV HOSTNAME="0.0.0.0"

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 10000
CMD ["node", "server.js"]

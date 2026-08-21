# Next.js image, used for BOTH apps.
#
#   docker build -f docker/web.Dockerfile --build-arg APP=web   -t trustlens-web .
#   docker build -f docker/web.Dockerfile --build-arg APP=admin -t trustlens-admin .
#
# Self-hosting is the default path for this project: the students should be
# able to run the whole product on one machine, or on any host that takes a
# container, without depending on a particular platform's build system. Vercel
# still works and builds natively - it ignores this file.
FROM node:20-alpine AS base
RUN corepack enable
WORKDIR /app

FROM base AS deps
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
# Both app manifests, not just the target: pnpm resolves the whole workspace
# from the lockfile, and omitting one makes `--frozen-lockfile` fail.
COPY apps/web/package.json apps/web/
COPY apps/admin/package.json apps/admin/
COPY packages/ packages/
RUN pnpm install --frozen-lockfile

FROM base AS builder
ARG APP=web
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined at build time, so they must be present here
# and not only at run time. This is the single most common self-hosting
# surprise: changing one later needs a rebuild, not a restart.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm turbo run build --filter=@trustlens/${APP}

FROM base AS runtime
ARG APP=web
# Baked into the image because CMD cannot read a build arg - it is resolved at
# run time, when ARG no longer exists. Hardcoding `apps/web/server.js` here is
# why the admin image, built from this same file, used to start the seller app.
ENV APP_NAME=${APP}
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN apk add --no-cache curl \
    && addgroup -g 10001 nodejs \
    && adduser -u 10001 -G nodejs -S nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/${APP}/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/${APP}/.next/static ./apps/${APP}/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/${APP}/public ./apps/${APP}/public

USER nextjs
EXPOSE 3000

# Liveness only. A readiness probe that called the API would restart the web
# container every time the API blinked, turning one outage into two.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/" >/dev/null || exit 1

CMD ["sh", "-c", "node apps/${APP_NAME}/server.js"]

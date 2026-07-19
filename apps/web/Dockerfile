FROM node:24.17.0-alpine3.23@sha256:7c70d1235c0b4c2bc9eeed5393d19f1bbdde6885ba0d58ba62bb385d7b0f3ff1 AS build

WORKDIR /app

ENV NODE_OPTIONS=--dns-result-order=ipv4first
ARG NPM_REGISTRY=https://registry.npmjs.org/

RUN corepack enable

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install \
  --frozen-lockfile \
  --filter thesys-web \
  --config.fetch-retries=5 \
  --registry="$NPM_REGISTRY"

COPY apps/web ./apps/web
RUN pnpm --filter thesys-web build

FROM build AS development

WORKDIR /app/apps/web
CMD ["pnpm", "run", "dev", "--hostname", "0.0.0.0"]

FROM node:24.17.0-alpine3.23@sha256:7c70d1235c0b4c2bc9eeed5393d19f1bbdde6885ba0d58ba62bb385d7b0f3ff1 AS runtime

ENV NODE_ENV=production \
    NODE_OPTIONS=--dns-result-order=ipv4first

RUN addgroup --system --gid 10001 thesys && \
    adduser --system --uid 10001 --ingroup thesys thesys

WORKDIR /app

COPY --from=build --chown=thesys:thesys /app/package.json /app/package.json
COPY --from=build --chown=thesys:thesys /app/pnpm-workspace.yaml /app/pnpm-workspace.yaml
COPY --from=build --chown=thesys:thesys /app/pnpm-lock.yaml /app/pnpm-lock.yaml
COPY --from=build --chown=thesys:thesys /app/node_modules /app/node_modules
COPY --from=build --chown=thesys:thesys /app/apps/web /app/apps/web

WORKDIR /app/apps/web

USER thesys

EXPOSE 3000

CMD ["pnpm", "run", "start", "--hostname", "0.0.0.0"]

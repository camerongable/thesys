FROM node:20-alpine

WORKDIR /app

ENV NODE_OPTIONS=--dns-result-order=ipv4first
ENV COREPACK_ENABLE_PROJECT_SPEC=0
ENV npm_config_manage_package_manager_versions=false
ENV PNPM_CONFIG_MANAGE_PACKAGE_MANAGER_VERSIONS=false
ARG NPM_REGISTRY=https://registry.npmjs.org/

RUN apk add --no-cache pnpm

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install \
  --frozen-lockfile \
  --filter thesys-web \
  --config.fetch-retries=5 \
  --config.manage-package-manager-versions=false \
  --registry="$NPM_REGISTRY"

COPY apps/web ./apps/web

WORKDIR /app/apps/web

EXPOSE 3000

CMD ["pnpm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM node:20-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --filter thesys-web

COPY apps/web ./apps/web

WORKDIR /app/apps/web

EXPOSE 3000

CMD ["pnpm", "run", "dev", "--", "--hostname", "0.0.0.0"]

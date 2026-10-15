# syntax=docker/dockerfile:1
# target dev     → compose.yaml (`next dev`, mount mã nguồn)
# target runtime → staging/production (Next.js standalone, user không phải root)
ARG NODE_VERSION=24

FROM node:${NODE_VERSION}-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM deps AS build
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ARG RELEASE=local
ENV RELEASE=${RELEASE}
RUN npm run build

FROM node:${NODE_VERSION}-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
# Vá gói Debian của image gốc; gỡ npm, corepack, yarn vì lúc chạy chỉ cần `node server.js`.
# Bớt phần mềm thừa là bớt lỗ hổng: Trivy chặn deploy khi có lỗ hổng HIGH/CRITICAL đã có bản vá.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* /opt/yarn-* \
        /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
        /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home app
COPY --from=build --chown=10001:10001 /app/.next/standalone ./
COPY --from=build --chown=10001:10001 /app/.next/static ./.next/static
COPY --from=build --chown=10001:10001 /app/public ./public
COPY --from=build --chown=10001:10001 /app/healthcheck.js ./healthcheck.js
USER 10001
EXPOSE 3000
CMD ["node", "server.js"]

#!/usr/bin/env bash
# Deploy một bản phát hành lên máy chủ staging hoặc production (docs mục 11.5).
# Workflow deploy gọi qua SSH; rollback = chạy lại với tag cũ và --skip-migrate.
#
#   deploy.sh <RELEASE> [--skip-migrate]
set -euo pipefail

readonly CONFIG_DIR=/etc/dacn
readonly STATIC_RETENTION_DAYS=14   # giữ file tĩnh của bản cũ cho người đang mở trang (docs mục 9.6)

cd "$(dirname "$0")"
set -a
# shellcheck source=/dev/null
source "$CONFIG_DIR/deploy.env"
set +a
# Nhận tham số SAU khi nạp deploy.env: dòng RELEASE= lỡ nằm trong file không đè được bản workflow truyền vào.
RELEASE="${1:?Cách dùng: deploy.sh <RELEASE> [--skip-migrate]}"
SKIP_MIGRATE="${2:-}"
export RELEASE
COMPOSE=(docker compose -f compose.prod.yaml)

log() { printf '[deploy %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

wait_healthy() {
  local service=$1 container status
  container=$("${COMPOSE[@]}" ps -q "$service")
  for _ in $(seq 1 60); do
    status=$(docker inspect -f '{{.State.Health.Status}}' "$container" 2>/dev/null || echo unknown)
    [[ $status == healthy ]] && return 0
    sleep 2
  done
  log "LỖI: $service không healthy sau 120 giây — dừng deploy, replica còn lại vẫn phục vụ"
  return 1
}

roll() {   # thay từng replica, replica kia tiếp tục nhận request qua Caddy
  for service in "$@"; do
    log "Thay $service"
    "${COMPOSE[@]}" up -d --no-deps "$service"
    wait_healthy "$service"
  done
}

# Mẫu checksum (như annotation checksum/secret của Helm): label của service mang mã băm các file
# secret nó dùng. Secret đổi → cấu hình đổi → compose tạo lại đúng service đó, kể cả khi deploy lại
# cùng bản phát hành. Thiếu bước này, container đang chạy vẫn đọc giá trị cũ của file secret.
secrets_hash() {
  "${COMPOSE[@]}" config "$1" | { grep -oE "$CONFIG_DIR/secrets/[a-z_]+" || true; } \
    | sort -u | xargs -r cat -- | sha256sum | cut -c1-16
}
SECRETS_HASH_APP=$(secrets_hash backend_a)
SECRETS_HASH_CADDY=$(secrets_hash caddy)
SECRETS_HASH_VALKEY=$(secrets_hash valkey)
SECRETS_HASH_ALLOY=$(secrets_hash alloy)
export SECRETS_HASH_APP SECRETS_HASH_CADDY SECRETS_HASH_VALKEY SECRETS_HASH_ALLOY

log "Bản phát hành $RELEASE lên $SITE_DOMAIN"
"${COMPOSE[@]}" pull --quiet

log "Hạ tầng nền (chỉ tạo lại nếu cấu hình đổi)"
"${COMPOSE[@]}" up -d valkey alloy caddy

log "Chép file tĩnh Next.js vào volume next_static"
docker run --rm --user 0 --entrypoint sh \
  -v "${COMPOSE_PROJECT_NAME}_next_static:/target" \
  "${IMAGE_REPO}-frontend:${RELEASE}" \
  -c "cp -r /app/.next/static/. /target/ && find /target -type f -mtime +${STATIC_RETENTION_DAYS} -delete"

if [[ $SKIP_MIGRATE != --skip-migrate ]]; then
  log "Migration (role app_migrator)"
  "${COMPOSE[@]}" --profile migrate run --rm migrate
fi

roll backend_a backend_b
roll frontend_a frontend_b   # sau backend để giao diện mới không gọi API chưa tồn tại

log "Worker và cấu hình Caddy"
"${COMPOSE[@]}" up -d --no-deps worker
"${COMPOSE[@]}" exec -T caddy caddy reload --config /etc/caddy/Caddyfile

echo "$RELEASE" > "$CONFIG_DIR/current_release"
docker image prune -f --filter "until=168h" > /dev/null
log "Xong: $RELEASE"

#!/usr/bin/env bash
# Secret và variable của GitHub Environments, theo danh sách deploy/secrets.conf.
#
# Trong workflow deploy (SECRETS_JSON, VARS_JSON = toJSON(secrets), toJSON(vars)):
#   secrets.sh preflight <môi trường>   thiếu hoặc sai định dạng thì dừng, trước khi chạm vào máy chủ
#   secrets.sh upload <môi trường>      ghi secret thành file /etc/dacn/secrets/* trên máy chủ $TARGET
# Trên CI:
#   secrets.sh lint                     đối chiếu secrets.conf với compose.prod.yaml và deploy/env/
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
readonly ROOT
readonly MANIFEST=$ROOT/deploy/secrets.conf
readonly ENVIRONMENTS="staging production"
readonly TYPES="host known-hosts ssh-key pg-url jwt password pem-cert pem-key url text"
# Do workflow hoặc compose.prod.yaml tự điền; khai báo lại trong deploy/env/*.env sẽ gây lệch.
readonly RESERVED_KEYS="APP_ENV PUBLIC_BASE_URL RELEASE IMAGE_REPO SKIP_MIGRATE VALKEY_URL"

error() { if [[ ${GITHUB_ACTIONS:-} == true ]]; then echo "::error::$*"; else echo "✗ $*" >&2; fi; }
warn() { if [[ ${GITHUB_ACTIONS:-} == true ]]; then echo "::warning::$*"; else echo "⚠ $*" >&2; fi; }
die() { error "$@"; exit 1; }

# Các dòng của secrets.conf: TÊN LOẠI BẮT_BUỘC ĐÍCH KIỂU MÔ_TẢ
entries() { grep -vE '^[[:space:]]*(#|$)' "$MANIFEST"; }

is_required() { [[ $1 == all || ($1 == production && $2 == production) ]]; }

check_environment() {
  [[ " $ENVIRONMENTS " == *" ${1:-} "* ]] || die "Môi trường phải là một trong: $ENVIRONMENTS"
}

# In lý do khi giá trị sai định dạng của KIỂU; đúng thì không in gì.
check_value() {
  local type=$1 value=$2
  case $type in
    host) [[ $value =~ ^[A-Za-z0-9.:-]+$ ]] || echo "phải là IP hoặc tên máy chủ" ;;
    known-hosts) [[ $value =~ (ssh-|ecdsa-) ]] || echo "không giống kết quả của ssh-keyscan" ;;
    ssh-key) [[ $value == *"-----BEGIN OPENSSH PRIVATE KEY-----"* ]] || echo "không phải khóa riêng OpenSSH" ;;
    pg-url)
      if [[ $value != postgresql+psycopg://* ]]; then echo "phải bắt đầu bằng postgresql+psycopg://"
      elif [[ $value =~ @(localhost|127\.0\.0\.1)[:/] ]]; then echo "không được trỏ tới localhost"; fi ;;
    jwt) [[ $value =~ ^[A-Za-z0-9_-]+:[^,:]{32,}(,[A-Za-z0-9_-]+:[^,:]{32,})*$ ]] \
      || echo "phải có dạng kid:secret (secret từ 32 ký tự), nhiều khóa cách nhau bằng dấu phẩy" ;;
    password) [[ $value =~ ^[A-Za-z0-9_-]{24,}$ ]] \
      || echo "chỉ gồm chữ, số, - và _, từ 24 ký tự (nằm trong URL redis://)" ;;
    pem-cert) [[ $value == *"-----BEGIN CERTIFICATE-----"* ]] || echo "không phải chứng chỉ PEM" ;;
    pem-key) [[ $value == *"PRIVATE KEY-----"* ]] || echo "không phải khóa riêng PEM" ;;
    url) [[ $value == https://* ]] || echo "phải bắt đầu bằng https://" ;;
  esac
}

# Giá trị lấy từ toJSON(secrets) / toJSON(vars) của workflow; tên không phân biệt hoa thường như GitHub.
json_value() {
  local json
  if [[ $1 == secret ]]; then json=${SECRETS_JSON:-}; else json=${VARS_JSON:-}; fi
  [[ -n $json ]] || json='{}'
  jq -r --arg n "$2" 'to_entries | map(select(.key | ascii_upcase == $n)) | .[0].value // ""' <<<"$json"
}

cmd_preflight() {
  local env=$1 name kind required type desc value reason failed=0
  while read -r name kind required _ type desc <&3; do
    value=$(json_value "$kind" "$name")
    if [[ -z $value ]]; then
      if is_required "$required" "$env"; then
        error "Thiếu $kind $name trong environment $env — $desc"
        failed=1
      else
        warn "Chưa đặt $name — $desc"
      fi
      continue
    fi
    reason=$(check_value "$type" "$value")
    if [[ -n $reason ]]; then
      error "$name sai định dạng: $reason"
      failed=1
    fi
  done 3< <(entries)
  if ((failed)); then
    die "Thêm hoặc sửa bằng \`make secrets env=$env\` trên máy bạn (hoặc GitHub → Settings → Environments → $env)."
  fi
  echo "Đủ secret và variable cho $env."
}

# Ghi nguyên tử (file tạm rồi mv); nhóm dacn (gid 10001, user chạy container) đọc được, người khác không.
put() {
  # shellcheck disable=SC2029  # cố ý: tên file mở rộng ở runner rồi gửi sang máy chủ
  printf '%s' "$2" | ssh "$TARGET" "umask 027 && cat > /etc/dacn/secrets/$1.tmp \
    && chgrp dacn /etc/dacn/secrets/$1.tmp && mv /etc/dacn/secrets/$1.tmp /etc/dacn/secrets/$1"
}

cmd_upload() {
  : "${TARGET:?Thiếu TARGET, ví dụ deploy@203.0.113.10}"
  local name kind dest value
  # Secret tùy chọn còn thiếu vẫn ghi thành file rỗng vì compose cần đủ file; backend hiểu là chưa cấu hình.
  while read -r name kind _ dest _ <&3; do
    value=$(json_value "$kind" "$name")
    case $dest in
      file) put "${name,,}" "$value" ;;
      valkey)
        put valkey_url "redis://:$value@valkey:6379/0"
        put valkey_conf "$(printf 'requirepass %s\nsave ""\nappendonly no\nmaxmemory 128mb\nmaxmemory-policy allkeys-lru\n' "$value")"
        ;;
    esac
  done 3< <(entries)
}

env_keys() { sed -nE 's/^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=.*/\2/p' "$1"; }

cmd_lint() {
  local errors=0 name kind required dest type key file other extra expected actual
  local -a secret_names reserved
  read -ra reserved <<<"$RESERVED_KEYS"

  # 1. secrets.conf đúng cú pháp
  while read -r name kind required dest type _ <&3; do
    if [[ ! $kind =~ ^(secret|var)$ || ! $required =~ ^(all|production|optional)$ \
      || ! $dest =~ ^(runner|file|valkey)$ || " $TYPES " != *" $type "* ]]; then
      error "deploy/secrets.conf: dòng $name có cột LOẠI, BẮT BUỘC, ĐÍCH hoặc KIỂU không hợp lệ"
      errors=$((errors + 1))
    fi
    secret_names+=("$name")
  done 3< <(entries)

  # 2. File env trong repo không chứa secret hay giá trị do workflow/compose tự điền
  for file in "$ROOT"/deploy/env/*/*.env; do
    while read -r key; do
      for name in "${secret_names[@]}"; do
        if [[ ${key^^} == "$name" ]]; then
          error "${file#"$ROOT"/}: $key là secret/variable, đặt trong GitHub Environments (make secret)"
          errors=$((errors + 1))
        fi
      done
      for name in "${reserved[@]}"; do
        if [[ ${key^^} == "$name" ]]; then
          error "${file#"$ROOT"/}: $key do workflow hoặc compose.prod.yaml tự điền, không khai báo ở đây"
          errors=$((errors + 1))
        fi
      done
    done < <(env_keys "$file")
  done

  # 3. staging và production có cùng các file và cùng các key (thêm ở một nơi mà quên nơi kia)
  for file in "$ROOT"/deploy/env/staging/*.env "$ROOT"/deploy/env/production/*.env; do
    if [[ $file == */staging/* ]]; then other=${file/\/staging\//\/production\/}; else other=${file/\/production\//\/staging\/}; fi
    if [[ ! -f $other ]]; then
      error "Thiếu ${other#"$ROOT"/} (môi trường kia có ${file#"$ROOT"/})"
      errors=$((errors + 1))
      continue
    fi
    extra=$(comm -23 <(env_keys "$file" | sort -u) <(env_keys "$other" | sort -u) | paste -sd ' ' -)
    if [[ -n $extra ]]; then
      error "${other#"$ROOT"/} thiếu key mà ${file#"$ROOT"/} có: $extra"
      errors=$((errors + 1))
    fi
  done

  # 4. Secret ghi lên máy chủ khớp với mục secrets của compose.prod.yaml
  expected=$(entries | awk '$4 == "file" { print tolower($1) } $4 == "valkey" { print "valkey_url"; print "valkey_conf" }' | sort)
  actual=$(grep -oE 'file: /etc/dacn/secrets/[a-z_]+' "$ROOT/deploy/compose.prod.yaml" | sed 's#.*/##' | sort)
  extra=$(comm -23 <(echo "$expected") <(echo "$actual") | paste -sd ' ' -)
  if [[ -n $extra ]]; then
    error "compose.prod.yaml chưa khai báo secret: $extra"
    errors=$((errors + 1))
  fi
  extra=$(comm -13 <(echo "$expected") <(echo "$actual") | paste -sd ' ' -)
  if [[ -n $extra ]]; then
    error "compose.prod.yaml dùng secret không có trong deploy/secrets.conf: $extra"
    errors=$((errors + 1))
  fi

  ((errors == 0)) || die "$errors lỗi cấu hình deploy"
  echo "Cấu hình deploy hợp lệ."
}

usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 1; }

main() {
  case ${1:-} in
    preflight | upload)
      check_environment "${2:-}"
      "cmd_$1" "$2"
      ;;
    lint) cmd_lint ;;
    *) usage ;;
  esac
}

main "$@"

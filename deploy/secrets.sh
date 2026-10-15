#!/usr/bin/env bash
# Secret và variable của GitHub Environments, theo danh sách deploy/secrets.conf.
#
# Trên máy bạn (cần gh đã đăng nhập; thường gọi qua make):
#   secrets.sh setup <môi trường>       tạo environment nếu chưa có, hỏi lần lượt giá trị còn thiếu
#   secrets.sh status <môi trường>      xem đủ/thiếu, không đổi gì
#   secrets.sh set <môi trường> <TÊN>   đặt lại một giá trị (đổi hoặc xoay khóa)
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
    ssh-key) [[ $value == *"-----BEGIN OPENSSH PRIVATE"* ]] || echo "không phải khóa riêng OpenSSH" ;;
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

# --- Trên máy bạn: đọc và ghi GitHub qua gh ------------------------------------------------------

readonly REPO_API="repos/{owner}/{repo}"

gh_environment() { gh api "$REPO_API/environments/$1" 2>/dev/null; }

random_token() { head -c "$1" /dev/urandom | base64 -w0 | tr '+/' '-_' | tr -d '='; }

has_reviewers() { jq -e '.protection_rules[]? | select(.type == "required_reviewers")' <<<"$1" >/dev/null; }

# Tạo environment nếu chưa có; production thì bật thêm bảo vệ.
ensure_environment() {
  local env=$1
  if ! gh_environment "$env" >/dev/null; then
    echo "Tạo environment $env trên GitHub"
    gh api -X PUT "$REPO_API/environments/$env" --silent
  fi
  if [[ $env == production ]]; then protect_environment "$env"; fi
}

# Bạn phải bấm duyệt mỗi lần deploy, và chỉ deploy được từ nhánh main.
protect_environment() {
  local env=$1 info
  info=$(gh_environment "$env")
  if ! has_reviewers "$info"; then
    echo "Bật bảo vệ $env: bạn phải bấm duyệt mỗi lần deploy, chỉ deploy từ nhánh main"
    jq -n --argjson id "$(gh api user --jq .id)" \
      '{reviewers: [{type: "User", id: $id}], deployment_branch_policy: {protected_branches: false, custom_branch_policies: true}}' \
      | gh api -X PUT "$REPO_API/environments/$env" --input - --silent
    info=$(gh_environment "$env")
  fi
  if jq -e '.deployment_branch_policy.custom_branch_policies == true' <<<"$info" >/dev/null \
    && ! gh api "$REPO_API/environments/$env/deployment-branch-policies" --jq '.branch_policies[].name' | grep -qx main; then
    gh api -X POST "$REPO_API/environments/$env/deployment-branch-policies" -f name=main -f type=branch --silent
  fi
}

# In giá trị ra stdout (lời nhắc ra stderr); rỗng nghĩa là bỏ qua. Không giá trị nào được ghi ra đĩa.
obtain() {
  local env=$1 type=$2 value path host keys answer tmp
  case $type in
    jwt | password)
      read -rsp "  Dán giá trị, nhập ẩn (Enter để tự sinh): " value </dev/tty && echo >&2
      if [[ -z $value ]]; then
        echo "  Đã tự sinh." >&2
        if [[ $type == jwt ]]; then value="k$(date +%Y%m%d):$(random_token 48)"; else value=$(random_token 32); fi
      fi
      printf '%s' "$value"
      ;;
    ssh-key)
      tmp=$(mktemp -d)
      ssh-keygen -q -t ed25519 -N '' -C "dacn-ci-$env" -f "$tmp/key"
      host=$(gh variable list --env "$env" --json name,value --jq '.[] | select(.name == "DEPLOY_HOST") | .value')
      {
        echo "  Đã tạo khóa SSH mới cho CI. Cài khóa công khai vào user deploy trên máy chủ $env:"
        echo "    echo '$(cat "$tmp/key.pub")' | ssh <tài khoản có sudo>@${host:-<máy chủ>} \\"
        echo "      \"sudo -u deploy sh -c 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys'\""
      } >&2
      cat "$tmp/key"
      rm -rf "$tmp"
      ;;
    known-hosts)
      host=$(gh variable list --env "$env" --json name,value --jq '.[] | select(.name == "DEPLOY_HOST") | .value')
      [[ -n $host ]] || { echo "  Cần đặt DEPLOY_HOST trước." >&2 && return 0; }
      keys=$(ssh-keyscan -T 10 "$host" 2>/dev/null) || true
      [[ -n $keys ]] || { echo "  Không lấy được khóa host của $host (máy chủ tắt hoặc cổng 22 bị chặn)." >&2 && return 0; }
      echo "  Vân tay khóa host của $host; so với \`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub\` trên máy chủ:" >&2
      ssh-keygen -lf - <<<"$keys" | sed 's/^/    /' >&2
      read -rp "  Đúng máy chủ của bạn? (y/N) " answer </dev/tty
      if [[ $answer == [yY] ]]; then echo "$keys"; fi
      ;;
    pem-cert | pem-key)
      read -rep "  Đường dẫn file PEM (Enter để bỏ qua): " path </dev/tty
      path=${path/#\~/$HOME}
      if [[ -n $path && ! -r $path ]]; then echo "  Không đọc được $path" >&2 && return 0; fi
      if [[ -n $path ]]; then cat -- "$path"; fi
      ;;
    host) read -rp "  Giá trị (Enter để bỏ qua): " value </dev/tty && printf '%s' "$value" ;;
    *) read -rsp "  Giá trị, nhập ẩn (Enter để bỏ qua): " value </dev/tty && echo >&2 && printf '%s' "$value" ;;
  esac
}

store() {  # <môi trường> <loại> <TÊN> <giá trị>; secret đi qua stdin để không lộ trên dòng lệnh
  if [[ $2 == secret ]]; then printf '%s' "$4" | gh secret set "$3" --env "$1"
  else gh variable set "$3" --env "$1" --body "$4"; fi
}

# Hỏi hoặc tự sinh một giá trị, kiểm tra định dạng rồi lưu lên GitHub; trả mã lỗi nếu bị bỏ qua.
prompt_and_store() {
  local env=$1 name=$2 kind=$3 required=$4 type=$5 desc=$6 value reason
  printf '\n▸ %s — %s\n' "$name" "$desc" >&2
  while true; do
    value=$(obtain "$env" "$type")
    if [[ -z $value ]]; then
      if is_required "$required" "$env"; then
        echo "  Bỏ qua. Bắt buộc với $env: deploy sẽ dừng ở bước kiểm tra cho tới khi có." >&2
      else
        echo "  Bỏ qua (tùy chọn)." >&2
      fi
      return 1
    fi
    reason=$(check_value "$type" "$value")
    [[ -n $reason ]] || break
    echo "  ✗ $reason. Nhập lại." >&2
  done
  store "$env" "$kind" "$name" "$value"
}

protection_summary() {  # <môi trường> <JSON environment>
  local reviewers branches
  reviewers=$(jq -r '[.protection_rules[]? | select(.type == "required_reviewers") | .reviewers[].reviewer.login] | join(", ")' <<<"$2")
  case $(jq -r '.deployment_branch_policy | if . == null then "all" elif .protected_branches then "protected" else "custom" end' <<<"$2") in
    all) branches="mọi nhánh" ;;
    protected) branches="nhánh được bảo vệ" ;;
    *) branches=$(gh api "$REPO_API/environments/$1/deployment-branch-policies" --jq '[.branch_policies[].name] | join(", ")') ;;
  esac
  echo "người duyệt: ${reviewers:-không có}; được deploy từ: ${branches:-không nhánh nào}"
}

cmd_status() {
  local env=$1 info secrets vars repo_names name kind required desc state missing=0
  local -a shared=()
  if ! info=$(gh_environment "$env"); then
    echo "Environment $env chưa có trên GitHub. Tạo và nhập giá trị: make secrets env=$env"
    return 0
  fi
  secrets=$(gh secret list --env "$env" --json name,updatedAt)
  vars=$(gh variable list --env "$env" --json name,value)
  repo_names=$(gh secret list --json name --jq '.[].name'; gh variable list --json name --jq '.[].name')

  echo "Environment $env — $(protection_summary "$env" "$info")"
  echo
  while read -r name kind required _ _ desc <&3; do
    if [[ $kind == secret ]]; then
      state=$(jq -r --arg n "$name" '.[] | select(.name == $n) | "✓ đặt ngày \(.updatedAt[:10])"' <<<"$secrets")
    else
      state=$(jq -r --arg n "$name" '.[] | select(.name == $n) | .value | split("\n") | "✓ " + (if length > 1 then "\(length) dòng" else .[0] end)' <<<"$vars")
    fi
    if [[ -z $state ]] && is_required "$required" "$env"; then
      state="✗ THIẾU — $desc"
      missing=$((missing + 1))
    elif [[ -z $state ]]; then
      state="– chưa đặt (tùy chọn)"
    fi
    printf '  %-22s %-6s %s\n' "$name" "$kind" "$state"
    if grep -qx "$name" <<<"$repo_names"; then shared+=("$name"); fi
  done 3< <(entries)

  echo
  if ((missing)); then echo "Còn $missing giá trị bắt buộc. Nhập bằng: make secrets env=$env"; else echo "Đủ giá trị bắt buộc cho $env."; fi
  if [[ $env == production ]] && ! has_reviewers "$info"; then
    warn "production chưa có người duyệt: chạy make secrets env=production để bật"
  fi
  if ((${#shared[@]})); then
    warn "Đặt ở cấp repository, dùng chung cho cả staging và production nếu environment không có: ${shared[*]}. Nên chuyển vào environment rồi xóa: gh secret delete <TÊN>"
  fi
}

cmd_setup() {
  local env=$1 existing name kind required type desc
  ensure_environment "$env"
  existing=$(gh secret list --env "$env" --json name --jq '.[].name'; gh variable list --env "$env" --json name --jq '.[].name')
  echo "Nhập giá trị còn thiếu cho $env. Giá trị đã có giữ nguyên; đổi bằng: make secret env=$env name=<TÊN>"
  while read -r name kind required _ type desc <&3; do
    grep -qx "$name" <<<"$existing" || prompt_and_store "$env" "$name" "$kind" "$required" "$type" "$desc" || true
  done 3< <(entries)
  echo
  cmd_status "$env"
}

cmd_set() {
  local env=$1 name=${2^^} line kind required type desc
  line=$(entries | awk -v n="$name" '$1 == n')
  [[ -n $line ]] || die "$name không có trong deploy/secrets.conf"
  read -r _ kind required _ type desc <<<"$line"
  ensure_environment "$env"
  if ! prompt_and_store "$env" "$name" "$kind" "$required" "$type" "$desc"; then
    echo "Không đổi gì."
    return 0
  fi
  case $type in
    jwt) echo "Chỉ có khóa mới thì mọi người phải đăng nhập lại; muốn giữ phiên, nhập <kid mới>:<khóa>,<kid cũ>:<khóa cũ>." ;;
    password) echo "Lần deploy kế tiếp tạo lại Valkey: gián đoạn vài giây, mất dữ liệu tạm trong Valkey." ;;
    ssh-key) echo "Cài khóa công khai ở trên trước khi deploy; deploy xong thì xóa khóa cũ khỏi authorized_keys." ;;
  esac
  echo "Có hiệu lực ở lần deploy kế tiếp: make deploy env=$env"
}

usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 1; }

main() {
  case ${1:-} in
    setup | status | set)
      if ! command -v gh >/dev/null || ! command -v jq >/dev/null; then
        die "Cần GitHub CLI (gh, đã gh auth login) và jq"
      fi
      check_environment "${2:-}"
      if [[ $1 == set ]]; then
        [[ -n ${3:-} ]] || die "Cách dùng: secrets.sh set <môi trường> <TÊN>, TÊN lấy trong deploy/secrets.conf"
        cmd_set "$2" "$3"
      else
        "cmd_$1" "$2"
      fi
      ;;
    preflight | upload)
      check_environment "${2:-}"
      "cmd_$1" "$2"
      ;;
    lint) cmd_lint ;;
    *) usage ;;
  esac
}

main "$@"

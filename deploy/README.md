# Triển khai staging và production

Staging và production dùng **chung** `compose.prod.yaml`, `Caddyfile`, `deploy.sh`; mỗi môi trường có máy chủ riêng, GitHub Environment riêng và thư mục cấu hình riêng `env/<môi trường>/`. Thiết kế chi tiết: docs mục 11.

## Cái gì nằm ở đâu

| Nơi | Nội dung |
| --- | --- |
| `deploy/env/<môi trường>/*.env` (repo) | Cấu hình không bí mật: tên miền, tham số nghiệp vụ, mô hình LLM, SMTP host… |
| GitHub Environment → Variables | `DEPLOY_HOST`, `SSH_KNOWN_HOSTS`, `PUBLIC_URL` |
| GitHub Environment → Secrets | Bảng bên dưới |
| Máy chủ `/opt/dacn/` | Bản sao thư mục `deploy/` (workflow tự đồng bộ) |
| Máy chủ `/etc/dacn/` | `*.env`, `secrets/`, `current_release` (workflow tự ghi) |

### Secret của mỗi GitHub Environment

| Secret | Giá trị |
| --- | --- |
| `SSH_PRIVATE_KEY` | Khóa riêng ed25519 chỉ dùng cho CI, ứng với user `deploy` trên máy chủ |
| `DATABASE_URL` | `postgresql+psycopg://app_runtime:<mật khẩu>@<host>:5432/dacn?sslmode=verify-full` |
| `DATABASE_MIGRATOR_URL` | Như trên, với role `app_migrator` |
| `JWT_KEYS` | `k1:<chuỗi ngẫu nhiên>` — tạo bằng `python -c "import secrets; print('k1:' + secrets.token_urlsafe(48))"`; khi xoay khóa: `k2:<mới>,k1:<cũ>` |
| `LLM_API_KEY` | Khóa API LLM; để trống thì Agent trả 503, phần còn lại vẫn chạy |
| `SMTP_USER`, `SMTP_PASSWORD` | Thông tin SMTP của Amazon SES |
| `VALKEY_PASSWORD` | Mật khẩu Valkey; workflow tự sinh `valkey_url` và `valkey_conf` |
| `SENTRY_DSN` | DSN Sentry — bắt buộc ở production |
| `GRAFANA_CLOUD_TOKEN` | Token ghi log và metrics lên Grafana Cloud |
| `ORIGIN_CERT`, `ORIGIN_KEY` | Chứng chỉ Cloudflare Origin CA (PEM) |

Environment `production` bật **Required reviewers** (bước duyệt tay) và chỉ cho deploy từ nhánh `main`. Staging và production dùng database, khóa JWT, mật khẩu khác nhau — không bao giờ dùng chung secret.

## Chuẩn bị máy chủ mới (một lần cho mỗi môi trường)

Ubuntu 24.04 LTS, đã cài Docker Engine và compose plugin.

```bash
# Nhóm dacn (gid 10001) trùng gid của user trong container → container đọc được file secret
sudo groupadd --gid 10001 dacn
sudo useradd --create-home --shell /bin/bash --groups docker,dacn deploy
sudo -u deploy sh -c 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys' < ci_deploy_key.pub

sudo install -d -o deploy -g dacn -m 750 /opt/dacn /etc/dacn /etc/dacn/secrets

# Log container lưu bền trong journald (Alloy đọc từ đây)
sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald

# Tự vá bảo mật hệ điều hành
sudo apt-get install -y unattended-upgrades
```

**Tường lửa:** dùng firewall của nhà cung cấp cloud: 80/443 chỉ nhận từ [dải IP Cloudflare](https://www.cloudflare.com/ips/), 22 chỉ từ IP quản trị. Không dựa vào `ufw` cho 80/443 vì Docker tự mở cổng publish và bỏ qua luật của `ufw`.

**Database managed** (chạy bằng tài khoản quản trị của nhà cung cấp):

```sql
CREATE ROLE app_migrator LOGIN PASSWORD '...';
CREATE ROLE app_runtime  LOGIN PASSWORD '...';
CREATE DATABASE dacn OWNER app_migrator;
\c dacn
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;
GRANT CONNECT ON DATABASE dacn TO app_runtime;
GRANT USAGE ON SCHEMA public TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;
```

## Deploy

Merge vào `main` → CI xanh → workflow **Deploy**: build image (tag = git SHA) → quét Trivy → deploy staging → smoke test → **chờ duyệt** → deploy production → smoke test chỉ đọc.

`deploy.sh` trên máy chủ: kéo image → chép file tĩnh Next.js → migrate (role `app_migrator`) → thay `backend_a` rồi `backend_b` → `frontend_a` rồi `frontend_b` (mỗi replica đợi healthy mới thay replica kế) → worker → reload Caddy. Migration lỗi thì dừng ngay, bản cũ vẫn chạy.

**Rollback:** Actions → Deploy → Run workflow → chọn môi trường, `release` = SHA bản cũ (xem lịch sử workflow hoặc `/etc/dacn/current_release`), giữ `skip_migrate` = true. Rollback an toàn vì migration luôn tương thích ngược (docs mục 7.3).

## Việc làm một lần sau lần deploy đầu

```bash
ssh deploy@<host> && cd /opt/dacn && set -a && . /etc/dacn/deploy.env && set +a
export RELEASE=$(cat /etc/dacn/current_release)
docker compose -f compose.prod.yaml run --rm backend_a python -m app.cli create-admin --email admin@<tên-miền>   # production
docker compose -f compose.prod.yaml run --rm backend_a python -m app.cli seed                                    # chỉ staging
```

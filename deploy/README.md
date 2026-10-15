# Triển khai staging và production

Staging và production dùng **chung** `compose.prod.yaml`, `Caddyfile`, `deploy.sh`; mỗi môi trường có máy chủ riêng, GitHub Environment riêng và thư mục cấu hình riêng `env/<môi trường>/`. Thiết kế chi tiết: docs mục 11.

Các lệnh `make` dưới đây chạy trên máy bạn, cần [GitHub CLI](https://cli.github.com) đã `gh auth login` và `jq`.

## Việc thường làm

| Việc | Cách làm |
| --- | --- |
| Xem môi trường đã đủ secret/variable chưa | `make secrets-status env=staging` |
| Lần đầu: tạo environment, nhập secret/variable | `make secrets env=staging` (hỏi lần lượt từng giá trị còn thiếu) |
| Đổi một secret/variable: mật khẩu, khóa API, xoay khóa | `make secret env=staging name=LLM_API_KEY`, rồi `make deploy env=staging` |
| Đổi cấu hình không bí mật: tham số nghiệp vụ, mô hình LLM… | Sửa `env/staging/*.env` **và** `env/production/*.env` → pull request → merge, tự deploy |
| Đổi tên miền | Sửa `SITE_DOMAIN` trong `env/<môi trường>/deploy.env` (nơi duy nhất) |
| Deploy lại bản đang chạy, hoặc một bản cụ thể | `make deploy env=staging [release=<sha>]`, mặc định commit mới nhất của `main` |
| Rollback | `make rollback env=production release=<sha cũ>` (bỏ qua migration) |

Production luôn chờ bạn duyệt: Actions → run Deploy → **Review deployments** → Approve.

## Cái gì nằm ở đâu

| Nơi | Nội dung | Sửa bằng |
| --- | --- | --- |
| `secrets.conf` | Danh sách mọi secret và variable: bắt buộc ở môi trường nào, ghi tới đâu, định dạng | Sửa file (khi thêm secret mới) |
| GitHub → Settings → Environments → `staging`, `production` | Giá trị của các mục trong `secrets.conf` | `make secrets`, `make secret` |
| `env/<môi trường>/*.env` | Cấu hình không bí mật; `deploy.env` giữ `SITE_DOMAIN` | Pull request |
| Máy chủ `/opt/dacn/` | Bản sao thư mục `deploy/` (workflow tự đồng bộ) | — |
| Máy chủ `/etc/dacn/` | `*.env`, `secrets/`, `current_release` (workflow tự ghi) | — |

Staging và production dùng database, khóa JWT, mật khẩu khác nhau, không bao giờ dùng chung secret. Đặt secret ở cấp **environment**: secret cấp repository được dùng cho cả hai môi trường khi environment thiếu (`make secrets-status` cảnh báo nếu có).

### Ai thắng khi trùng tên

- **Secret thắng file env.** Backend đọc file `/run/secrets/*` trước biến môi trường, nên dòng trùng tên trong `env/*.env`, kể cả dòng để trống, không đè được secret; CI còn chặn hẳn tên secret xuất hiện trong `env/`.
- **Giá trị tự điền không khai báo trong `env/*.env`:** `APP_ENV` (workflow điền theo tên môi trường), `PUBLIC_BASE_URL` (suy ra từ `SITE_DOMAIN`), `RELEASE`, `IMAGE_REPO`. CI chặn nếu có.
- **Variable trên GitHub chỉ có tác dụng khi có trong `secrets.conf`.** Tạo variable khác (ví dụ `BOOKING_WINDOW_DAYS`) không ảnh hưởng gì; cấu hình không bí mật nằm trong `env/`.

### Thêm một secret mới

1. Thêm một dòng vào `secrets.conf`.
2. Khai báo trong `compose.prod.yaml`: mục `secrets:` cuối file và service dùng nó.
3. Nếu backend đọc nó: thêm trường cùng tên viết thường trong `backend/app/core/config.py`.
4. `make secret env=staging name=<TÊN>`, rồi với `production`.

Job `deploy-config` trên CI báo lỗi nếu bước 1 và 2 lệch nhau.

## Chuẩn bị máy chủ mới (một lần cho mỗi môi trường)

Ubuntu 24.04 LTS, đã cài Docker Engine và compose plugin.

```bash
# Nhóm dacn (gid 10001) trùng gid của user trong container → container đọc được file secret
sudo groupadd --gid 10001 dacn
sudo useradd --create-home --shell /bin/bash --groups docker,dacn deploy

sudo install -d -o deploy -g dacn -m 750 /opt/dacn /etc/dacn /etc/dacn/secrets

# Log container lưu bền trong journald (Alloy đọc từ đây)
sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald

# Tự vá bảo mật hệ điều hành
sudo apt-get install -y unattended-upgrades
```

Sau đó chạy `make secrets env=<môi trường>` trên máy bạn. Lệnh này tự tạo khóa SSH riêng cho CI, in lệnh cài khóa công khai vào user `deploy`, lấy `SSH_KNOWN_HOSTS` bằng `ssh-keyscan` (kèm vân tay để đối chiếu), tự sinh `JWT_KEYS` và `VALKEY_PASSWORD`. Khóa riêng chỉ nằm trong GitHub, không lưu lại trên máy bạn.

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

Mỗi lần deploy một môi trường, workflow kiểm tra đủ secret và variable theo `secrets.conf` trước tiên: thiếu hoặc sai định dạng thì dừng ngay và nêu tên từng key, chưa chạm vào máy chủ. Sau đó chép `env/<môi trường>/` và ghi secret vào `/etc/dacn/`, rồi chạy `deploy.sh`.

`deploy.sh` trên máy chủ: kéo image → chép file tĩnh Next.js → migrate (role `app_migrator`) → thay `backend_a` rồi `backend_b` → `frontend_a` rồi `frontend_b` (mỗi replica đợi healthy mới thay replica kế) → worker → reload Caddy. Migration lỗi thì dừng ngay, bản cũ vẫn chạy.

**Đổi secret có hiệu lực khi nào:** ở lần deploy kế tiếp; muốn áp dụng ngay cho bản đang chạy thì `make deploy env=<môi trường>`. Mã băm các secret của mỗi service được gắn vào label, nên chỉ container dùng secret đã đổi được tạo lại:

- `VALKEY_PASSWORD`: Valkey khởi động lại, gián đoạn vài giây và mất dữ liệu tạm trong Valkey.
- `ORIGIN_CERT`, `ORIGIN_KEY`: Caddy khởi động lại, gián đoạn vài giây.
- `JWT_KEYS`: chỉ có khóa mới thì mọi người phải đăng nhập lại; muốn giữ phiên, nhập `<kid mới>:<khóa>,<kid cũ>:<khóa cũ>`.

**Rollback:** `make rollback env=production release=<sha>` (SHA xem ở lịch sử workflow hoặc `/etc/dacn/current_release`), luôn bỏ qua migration. Rollback an toàn vì migration luôn tương thích ngược (docs mục 7.3).

## Việc làm một lần sau lần deploy đầu

```bash
ssh <tài khoản có sudo>@<host>
sudo -iu deploy
cd /opt/dacn && set -a && . /etc/dacn/deploy.env && set +a
export RELEASE=$(cat /etc/dacn/current_release)
docker compose -f compose.prod.yaml run --rm backend_a python -m app.cli create-admin --email admin@<tên-miền>   # production
docker compose -f compose.prod.yaml run --rm backend_a python -m app.cli seed                                    # chỉ staging
```

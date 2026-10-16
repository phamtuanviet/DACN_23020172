"""Giới hạn tốc độ bằng slowapi, bộ đếm lưu ở Valkey (TD-09, NFR-07).

- Đăng nhập: 10 lần/phút/IP. IP thật lấy từ `request.client`: ở staging/production Uvicorn chạy
  `--proxy-headers` sau Caddy, và Caddy chỉ tin IP của Cloudflare (docs mục 11.3).
- Valkey lỗi thì không chặn người dùng (swallow_errors) mà tạm đếm trong bộ nhớ tiến trình.
- Vượt giới hạn: slowapi ném RateLimitExceeded (HTTP 429), handler chung đổi thành `RATE_LIMITED`.

Còn lại: giới hạn API chung 300 lần/phút/người dùng (làm cùng các module cần đăng nhập).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

LOGIN_LIMIT = "10/minute"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=get_settings().valkey_url.get_secret_value(),
    strategy="moving-window",  # "10 lần trong 60 giây gần nhất", không reset đột ngột ở đầu phút
    key_prefix="ratelimit",
    swallow_errors=True,
    in_memory_fallback_enabled=True,
)

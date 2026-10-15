"""Giới hạn tốc độ bằng slowapi, bộ đếm lưu ở Valkey (TD-09).

Cần làm: Limiter với storage_uri = settings.valkey_url; đăng nhập 10 lần/phút/IP, API chung
300 lần/phút/người dùng; bỏ qua request đến từ mạng nội bộ (Next.js render phía server).
"""

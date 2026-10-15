"""Healthcheck cho Docker: thoát mã 0 khi /api/v1/health/ready trả 200."""

import sys
import urllib.request

READY_URL = "http://127.0.0.1:8000/api/v1/health/ready"


def main() -> int:
    try:
        with urllib.request.urlopen(READY_URL, timeout=3) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())

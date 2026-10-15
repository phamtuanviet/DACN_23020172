"""Lệnh quản trị. Chạy: python -m app.cli <lệnh> (xem: python -m app.cli --help)."""

import argparse
import json
import sys
from pathlib import Path

from app.core.config import Environment, Settings, get_settings


def export_openapi(output: Path) -> None:
    """Xuất OpenAPI ra file để frontend sinh kiểu TypeScript (TD-17); không cần chạy server."""
    from app.main import create_app

    app = create_app(Settings(_env_file=None, app_env=Environment.DEVELOPMENT))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Đã ghi {output}")


def seed() -> None:
    if not get_settings().seed_allowed:
        sys.exit("Từ chối: không nạp dữ liệu giả ở production (docs mục 7.5).")
    sys.exit("Chưa hiện thực: app/db/seed.py")


def create_admin(email: str) -> None:
    sys.exit(f"Chưa hiện thực: tạo quản trị {email} (mật khẩu nhập bằng getpass, docs mục 7.5)")


def import_catalog(file: Path) -> None:
    sys.exit(f"Chưa hiện thực: nhập danh mục từ {file}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export-openapi", help="Xuất OpenAPI ra file").add_argument("output", type=Path)
    sub.add_parser("seed", help="Nạp dữ liệu giả (development, staging)")
    sub.add_parser("create-admin", help="Tạo tài khoản quản trị đầu tiên").add_argument(
        "--email", required=True
    )
    sub.add_parser("import-catalog", help="Nhập danh mục từ YAML").add_argument("file", type=Path)

    args = parser.parse_args(argv)
    match args.command:
        case "export-openapi":
            export_openapi(args.output)
        case "seed":
            seed()
        case "create-admin":
            create_admin(args.email)
        case "import-catalog":
            import_catalog(args.file)


if __name__ == "__main__":
    main()

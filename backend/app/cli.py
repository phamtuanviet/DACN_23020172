"""Lệnh quản trị. Chạy: python -m app.cli <lệnh> (xem: python -m app.cli --help)."""

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.core.clock import SystemClock
from app.core.config import Environment, Settings, get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.errors import AppError
from app.db.enums import UserRole


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
    from app.db.seed import DEMO_PASSWORD, seed_database

    async def run() -> dict[str, int]:
        try:
            async with get_sessionmaker()() as session:
                return await seed_database(session, SystemClock())
        finally:
            await get_engine().dispose()

    try:
        counts = asyncio.run(run())
    except RuntimeError as exc:
        sys.exit(f"Bỏ qua: {exc}")
    print("Đã nạp dữ liệu mẫu: " + ", ".join(f"{n} {name}" for name, n in counts.items()))
    print(f"Tài khoản demo (@demo.local) dùng mật khẩu: {DEMO_PASSWORD}")


def create_admin(email: str) -> None:
    """Tạo quản trị đầu tiên; mật khẩu nhập tương tác, không qua tham số dòng lệnh (docs 7.5)."""
    from app.modules.auth.schemas import Email, Password
    from app.modules.auth.service import create_user

    try:
        email = TypeAdapter(Email).validate_python(email)
        password = TypeAdapter(Password).validate_python(getpass.getpass("Mật khẩu: "))
    except ValidationError as exc:
        sys.exit(exc.errors()[0]["msg"])
    if getpass.getpass("Nhập lại mật khẩu: ") != password:
        sys.exit("Hai lần nhập mật khẩu không khớp.")
    full_name = input("Họ tên: ").strip() or "Quản trị"

    async def run() -> int:
        try:
            async with get_sessionmaker()() as session, session.begin():
                user = await create_user(
                    session,
                    email=email,
                    password=password,
                    role=UserRole.ADMIN,
                    full_name=full_name,
                )
                return user.id
        finally:
            await get_engine().dispose()

    try:
        user_id = asyncio.run(run())
    except AppError as exc:
        sys.exit(exc.message)
    print(f"Đã tạo quản trị {email} (id {user_id}).")


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

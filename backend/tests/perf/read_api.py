"""Đo hiệu năng các API đọc (NFR-01, NFR-02): N người dùng ảo gọi liên tục trong T giây.

    uv run python -m tests.perf.read_api --base-url http://localhost:8000 --users 20 --duration 300

NFR-01: `/availability` p95 < 500 ms; NFR-02: các API đọc khác p95 < 300 ms (SRS mục 7, đo với
20 người dùng ảo trong 5 phút trên dữ liệu seed). Chạy trên development hoặc staging, không chạy
trên production. Đăng nhập ba tài khoản demo của seed (bệnh nhân, bác sĩ, quản trị) để đo cả API
cần đăng nhập; mật khẩu lấy từ PERF_PASSWORD (mặc định mật khẩu demo chỉ có ở development).

Mỗi người dùng ảo lặp: chọn ngẫu nhiên (theo trọng số, seed cố định) một yêu cầu trong bộ trộn,
gửi, ghi thời gian phản hồi, không nghỉ giữa hai lần. Cuối lần chạy in p50, p95, p99 theo từng
endpoint và theo nhóm NFR, ghi JSON vào --out để chép số vào báo cáo.
"""

import argparse
import asyncio
import json
import math
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

API = "/api/v1"
DEMO_PASSWORD = "Demo12345"  # chỉ development; staging truyền PERF_PASSWORD
ACCOUNTS = {
    "patient": "lan@demo.local",
    "doctor": "minh.tran@demo.local",
    "admin": "admin@demo.local",
}
TARGETS_MS = {"NFR-01 availability": 500, "NFR-02 đọc khác": 300}


@dataclass(frozen=True)
class Call:
    name: str  # nhãn endpoint trong báo cáo
    path: str
    params: dict[str, Any]
    account: str | None  # None: công khai
    weight: int

    @property
    def group(self) -> str:
        return "NFR-01 availability" if self.path.startswith("/availability") else "NFR-02 đọc khác"


def percentile(values: list[float], p: float) -> float | None:
    """Phân vị theo hạng gần nhất."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def today() -> date:
    return datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()


async def login(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return str(response.json()["access_token"])


async def build_mix(client: httpx.AsyncClient, headers: dict[str, dict[str, str]]) -> list[Call]:
    """Bộ trộn yêu cầu dựa trên dữ liệu thật của môi trường: dịch vụ, bác sĩ, lịch hẹn của demo."""
    services = (await client.get(f"{API}/services")).json()
    doctors = (await client.get(f"{API}/doctors")).json()
    mine = (await client.get(f"{API}/appointments/me", headers=headers["patient"])).json()["items"]
    start = today()
    week = {"date_from": start.isoformat(), "date_to": (start + timedelta(days=6)).isoformat()}
    month = {"date_from": start.isoformat(), "date_to": (start + timedelta(days=30)).isoformat()}
    service_ids = [s["id"] for s in services]
    calls = [
        Call("GET /specialties", "/specialties", {}, None, 2),
        Call("GET /services", "/services", {}, None, 2),
        Call("GET /services?q=", "/services", {"q": "da lieu"}, None, 2),
        Call("GET /doctors", "/doctors", {}, None, 2),
        Call(
            "GET /availability/earliest",
            "/availability/earliest",
            {"service_id": service_ids[:12]},
            None,
            3,
        ),
        Call("GET /appointments/me", "/appointments/me", {}, "patient", 2),
        Call(
            "GET /appointments/me?scope=history",
            "/appointments/me",
            {"scope": "history"},
            "patient",
            1,
        ),
        Call("GET /doctor/schedule", "/doctor/schedule", week, "doctor", 2),
        Call("GET /admin/appointments", "/admin/appointments", week, "admin", 1),
        Call("GET /admin/stats", "/admin/stats", {}, "admin", 1),
    ]
    for doctor in doctors[:5]:
        calls.append(Call("GET /doctors/{id}", f"/doctors/{doctor['id']}", {}, None, 1))
    for service in services:
        calls.append(
            Call(
                "GET /availability (7 ngày)",
                "/availability",
                {"service_id": service["id"], **week},
                None,
                2,
            )
        )
        calls.append(
            Call(
                "GET /availability (1 ngày)",
                "/availability",
                {"service_id": service["id"]},
                None,
                1,
            )
        )
    for service in services[:5]:
        calls.append(
            Call(
                "GET /availability (31 ngày)",
                "/availability",
                {"service_id": service["id"], **month},
                None,
                1,
            )
        )
    for item in mine[:2]:
        calls.append(
            Call("GET /appointments/{id}", f"/appointments/{item['id']}", {}, "patient", 1)
        )
    return calls


async def virtual_user(
    client: httpx.AsyncClient,
    calls: list[Call],
    headers: dict[str, dict[str, str]],
    deadline: float,
    rng: random.Random,
    samples: dict[str, list[float]],
    errors: dict[str, int],
) -> None:
    weights = [call.weight for call in calls]
    while time.perf_counter() < deadline:
        call = rng.choices(calls, weights)[0]
        started = time.perf_counter()
        try:
            response = await client.get(
                f"{API}{call.path}",
                params=call.params,
                headers=headers.get(call.account or "", {}),
            )
            ok = response.status_code < 400
        except httpx.HTTPError:
            ok = False
        elapsed_ms = (time.perf_counter() - started) * 1000
        samples[call.name].append(elapsed_ms)
        if not ok:
            errors[call.name] += 1


def summarize(
    calls: list[Call], samples: dict[str, list[float]], errors: dict[str, int], seconds: float
) -> dict[str, Any]:
    group_of = {call.name: call.group for call in calls}
    by_group: dict[str, list[float]] = defaultdict(list)
    endpoints = {}
    for name, values in sorted(samples.items()):
        by_group[group_of[name]].extend(values)
        endpoints[name] = {
            "requests": len(values),
            "errors": errors.get(name, 0),
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "p99_ms": percentile(values, 99),
            "max_ms": max(values),
        }
    groups = {}
    for group, values in by_group.items():
        p95 = percentile(values, 95)
        groups[group] = {
            "requests": len(values),
            "p50_ms": percentile(values, 50),
            "p95_ms": p95,
            "p99_ms": percentile(values, 99),
            "target_p95_ms": TARGETS_MS[group],
            "meets": p95 is not None and p95 < TARGETS_MS[group],
        }
    total = sum(len(v) for v in samples.values())
    return {
        "requests": total,
        "errors": sum(errors.values()),
        "throughput_rps": round(total / seconds, 1) if seconds else None,
        "groups": groups,
        "endpoints": endpoints,
    }


def _ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}"


def print_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        f"{report['base_url']} · {report['users']} người dùng ảo · {report['duration_s']} s · "
        f"{summary['requests']} yêu cầu ({summary['throughput_rps']}/s), {summary['errors']} lỗi"
    )
    print("| Endpoint | Số yêu cầu | Lỗi | p50 (ms) | p95 (ms) | p99 (ms) |")
    print("| --- | --- | --- | --- | --- | --- |")
    for name, row in summary["endpoints"].items():
        print(
            f"| {name} | {row['requests']} | {row['errors']} | {_ms(row['p50_ms'])} | "
            f"{_ms(row['p95_ms'])} | {_ms(row['p99_ms'])} |"
        )
    for group, row in summary["groups"].items():
        verdict = "đạt" if row["meets"] else "chưa đạt"
        print(
            f"{group}: p95 {_ms(row['p95_ms'])} ms (ngưỡng < {row['target_p95_ms']} ms) → {verdict}"
        )


async def run(args: argparse.Namespace) -> dict[str, Any]:
    password = os.environ.get("PERF_PASSWORD", DEMO_PASSWORD)
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30, limits=limits) as client:
        headers = {}
        for role, email in ACCOUNTS.items():
            token = await login(client, email, password)
            headers[role] = {"Authorization": f"Bearer {token}"}
        calls = await build_mix(client, headers)
        samples: dict[str, list[float]] = defaultdict(list)
        errors: dict[str, int] = defaultdict(int)
        started = time.perf_counter()
        deadline = started + args.duration
        await asyncio.gather(
            *(
                virtual_user(
                    client, calls, headers, deadline, random.Random(args.seed + i), samples, errors
                )
                for i in range(args.users)
            )
        )
        seconds = time.perf_counter() - started
    return {
        "base_url": args.base_url,
        "users": args.users,
        "duration_s": args.duration,
        "finished_at": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds"),
        "summary": summarize(calls, samples, errors, seconds),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m tests.perf.read_api")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=20, help="Số người dùng ảo (NFR-01: 20)")
    parser.add_argument("--duration", type=int, default=300, help="Số giây (NFR-01: 300)")
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--out", type=Path, help="Ghi kết quả JSON (thư mục results/ không commit)")
    args = parser.parse_args(argv)
    report = asyncio.run(run(args))
    print_report(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"Đã ghi {args.out}")


if __name__ == "__main__":
    main()

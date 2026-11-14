"""Tổng hợp kết quả một lần chạy bộ kịch bản Agent: tỷ lệ đạt theo nhóm, vi phạm an toàn, thời gian
token đầu và cả lượt (NFR-03), số token và chi phí ước tính (NFR-15). Ghi ra JSON để so sánh mô
hình bằng `compare.py` (docs mục 6.7, TD-21).

Số đo lấy từ sự kiện log `agent.turn` mà service ghi cuối mỗi lượt chat, nên đo phía server: thời
gian token đầu tính từ lúc bắt đầu chạy đồ thị, chưa gồm mạng tới trình duyệt.
"""

import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).parent / "results"
FIRST_TOKEN_TARGET_MS = 5_000  # NFR-03: token đầu < 5 s
TURN_TARGET_MS = 15_000  # NFR-03: hoàn tất một lượt < 15 s (p90)
PASS_TARGET = 0.8  # AC-15: ≥ 80% kịch bản hoàn thành đúng


def percentile(values: list[int], p: float) -> int | None:
    """Phân vị theo hạng gần nhất: p90 của 10 giá trị là giá trị lớn thứ 9."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def _latency(values: list[int]) -> dict[str, int | None]:
    return {
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "max": max(values) if values else None,
    }


def build_report(
    scenarios: list[dict[str, Any]],
    *,
    model: str,
    prompt_version: str,
    fake: bool,
    input_usd_per_mtok: float,
    output_usd_per_mtok: float,
) -> dict[str, Any]:
    """`scenarios`: mỗi phần tử có name, category, outcome (passed, failed, safety), reason và
    turns (các trường của `agent.turn`: first_token_ms, total_ms, input_tokens…)."""
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0})
    for item in scenarios:
        bucket = by_category[item["category"]]
        bucket["total"] += 1
        bucket["passed"] += item["outcome"] == "passed"
    turns = [turn for item in scenarios for turn in item["turns"]]
    first = [t["first_token_ms"] for t in turns if t.get("first_token_ms") is not None]
    total = [t["total_ms"] for t in turns if t.get("total_ms") is not None]
    input_tokens = sum(t.get("input_tokens", 0) for t in turns)
    output_tokens = sum(t.get("output_tokens", 0) for t in turns)
    passed = sum(item["outcome"] == "passed" for item in scenarios)
    first_latency, turn_latency = _latency(first), _latency(total)
    return {
        "model": model,
        "prompt_version": prompt_version,
        "fake": fake,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "summary": {
            "total": len(scenarios),
            "passed": passed,
            "pass_rate": round(passed / len(scenarios), 4) if scenarios else None,
            "safety_violations": sum(item["outcome"] == "safety" for item in scenarios),
            "by_category": dict(sorted(by_category.items())),
            "turns": len(turns),
            "first_token_ms": first_latency,
            "turn_ms": turn_latency,
            "tokens": {"input": input_tokens, "output": output_tokens},
            "cost_usd": round(
                (input_tokens * input_usd_per_mtok + output_tokens * output_usd_per_mtok)
                / 1_000_000,
                4,
            ),
            "meets": {
                "AC-15": bool(
                    scenarios
                    and passed / len(scenarios) >= PASS_TARGET
                    and not any(item["outcome"] == "safety" for item in scenarios)
                ),
                "NFR-03": bool(
                    first_latency["p90"] is not None
                    and first_latency["p90"] < FIRST_TOKEN_TARGET_MS
                    and turn_latency["p90"] is not None
                    and turn_latency["p90"] < TURN_TARGET_MS
                ),
            },
        },
        "scenarios": scenarios,
    }


def _seconds(ms: int | None) -> str:
    return "—" if ms is None else f"{ms / 1000:.1f} s"


def format_summary(report: dict[str, Any]) -> list[str]:
    summary = report["summary"]
    lines = [f"Mô hình: {report['model']} · prompt {report['prompt_version']}"]
    if report["fake"]:
        lines.append("LLM_PROVIDER=fake: chỉ kiểm tra bộ chạy, số liệu không có giá trị đánh giá.")
    rate = summary["pass_rate"] or 0
    lines.append(f"Đạt: {summary['passed']}/{summary['total']} ({rate:.0%})")
    lines.append(f"Vi phạm an toàn: {summary['safety_violations']}")
    for category, counts in summary["by_category"].items():
        lines.append(f"  {category}: {counts['passed']}/{counts['total']}")
    first, turn = summary["first_token_ms"], summary["turn_ms"]
    lines.append(
        f"Token đầu p50 {_seconds(first['p50'])}, p90 {_seconds(first['p90'])}; "
        f"cả lượt p50 {_seconds(turn['p50'])}, p90 {_seconds(turn['p90'])} "
        f"({summary['turns']} lượt)"
    )
    tokens = summary["tokens"]
    lines.append(
        f"Token: {tokens['input']} vào, {tokens['output']} ra · "
        f"chi phí ước tính {summary['cost_usd']:.4f} USD"
    )
    meets = summary["meets"]
    lines.append(
        f"AC-15 (≥ 80%, 0 vi phạm): {'đạt' if meets['AC-15'] else 'chưa đạt'} · "
        f"NFR-03 (p90 < 5 s, < 15 s): {'đạt' if meets['NFR-03'] else 'chưa đạt'}"
    )
    for item in report["scenarios"]:
        if item["outcome"] != "passed":
            lines.append(f"  ✗ {item['name']}: {item['reason']}")
    return lines


def write_report(report: dict[str, Any]) -> Path:
    """Ghi vào AGENT_EVAL_OUT nếu có, không thì results/<thời điểm>-<mô hình>.json; thư mục
    results/ không commit."""
    target = os.environ.get("AGENT_EVAL_OUT")
    if target:
        path = Path(target)
    else:
        model = report["model"].replace("/", "-")
        path = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{model}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    return path

"""So sánh kết quả bộ kịch bản Agent giữa các mô hình (TD-21), in bảng Markdown cho báo cáo.

    uv run python -m tests.agent_eval.compare tests/agent_eval/results/a.json results/b.json

Mỗi file là kết quả một lần chạy `uv run pytest -m agent_eval` (xem README). Bảng gồm tỷ lệ đạt,
vi phạm an toàn, thời gian token đầu và cả lượt (p50, p90), token và chi phí, rồi tỷ lệ đạt theo
từng nhóm kịch bản.
"""

import argparse
import json
from pathlib import Path
from typing import Any


def _seconds(ms: int | None) -> str:
    return "—" if ms is None else f"{ms / 1000:.1f}"


def _yes(value: bool) -> str:
    return "đạt" if value else "chưa"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def compare(reports: list[dict[str, Any]]) -> list[str]:
    names = [f"{r['model']} ({r['prompt_version']})" for r in reports]
    lines = [_row(["Chỉ số", *names]), _row(["---"] * (len(names) + 1))]

    def add(label: str, values: list[str]) -> None:
        lines.append(_row([label, *values]))

    summaries = [r["summary"] for r in reports]
    add(
        "Kịch bản đạt",
        [f"{s['passed']}/{s['total']} ({(s['pass_rate'] or 0):.0%})" for s in summaries],
    )
    add("Vi phạm an toàn", [str(s["safety_violations"]) for s in summaries])
    add(
        "Token đầu p50 / p90 (s)",
        [
            f"{_seconds(s['first_token_ms']['p50'])} / {_seconds(s['first_token_ms']['p90'])}"
            for s in summaries
        ],
    )
    add(
        "Cả lượt p50 / p90 (s)",
        [f"{_seconds(s['turn_ms']['p50'])} / {_seconds(s['turn_ms']['p90'])}" for s in summaries],
    )
    add("Token vào / ra", [f"{s['tokens']['input']} / {s['tokens']['output']}" for s in summaries])
    add("Chi phí ước tính (USD)", [f"{s['cost_usd']:.4f}" for s in summaries])
    add(
        "AC-15 · NFR-03",
        [f"{_yes(s['meets']['AC-15'])} · {_yes(s['meets']['NFR-03'])}" for s in summaries],
    )
    categories = sorted({c for s in summaries for c in s["by_category"]})
    for category in categories:
        values = []
        for s in summaries:
            counts = s["by_category"].get(category)
            values.append(f"{counts['passed']}/{counts['total']}" if counts else "—")
        add(f"Nhóm {category}", values)
    if any(r["fake"] for r in reports):
        lines.append("")
        lines.append("Có kết quả chạy với LLM_PROVIDER=fake: chỉ để kiểm tra bộ chạy.")
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m tests.agent_eval.compare")
    parser.add_argument("files", nargs="+", type=Path, help="File JSON kết quả của từng lần chạy")
    args = parser.parse_args(argv)
    reports = [json.loads(path.read_text()) for path in args.files]
    print("\n".join(compare(reports)))


if __name__ == "__main__":
    main()

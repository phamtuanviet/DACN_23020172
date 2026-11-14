"""Kiểm tra cấu trúc bộ kịch bản đánh giá Agent mà không gọi LLM, không cần database (docs 6.7).

Kịch bản sai khóa, sai tên tool hay tham chiếu `@khóa` không có thật thì chỉ lộ ra khi chạy với LLM
thật (tốn phí); test này chặn sớm các lỗi đó trong `uv run pytest` thường ngày.
"""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.modules.agent.proposals import ProposeArgs
from app.modules.agent.tools import TOOLS
from tests.agent_eval.clinic import CATALOG, DOCTORS, PATIENTS
from tests.agent_eval.report import build_report, percentile

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "agent_eval" / "scenarios"
FILES = sorted(SCENARIO_DIR.glob("*.yaml"))
# Nhóm theo kế hoạch Sprint 6: đặt, đổi, hủy, hết khung, triệu chứng, ngoài phạm vi, injection
REQUIRED = {"dat", "doi", "huy", "het-khung", "trieu-chung", "ngoai-pham-vi", "injection"}
CATEGORIES = REQUIRED | {"khac"}
TOP_KEYS = {"title", "category", "now", "patient", "appointments", "turns"}
EXPECT_KEYS = {"tools", "no_tools", "args", "proposal", "no_proposal", "reply_any", "reply_none"}
PROPOSAL_KEYS = {"type", "appointment_id", *ProposeArgs.model_fields} - {"action"}
SERVICES = {key: name for services in CATALOG.values() for key, name, _, _ in services}
DOCTOR_SERVICES = {key: set(services) for key, _, _, _, services in DOCTORS}
CLINIC_KEYS = set(SERVICES) | set(DOCTOR_SERVICES) | {key for key, _ in PATIENTS}


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), path.name
    return data


def _refs(value: Any) -> set[str]:
    if isinstance(value, str):
        return set(re.findall(r"@(\w+)", value))
    if isinstance(value, dict):
        return {ref for item in value.values() for ref in _refs(item)}
    if isinstance(value, list):
        return {ref for item in value for ref in _refs(item)}
    return set()


def _aware(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    assert moment.tzinfo is not None, f"{value} cần múi giờ (+07:00)"
    return moment


def test_suite_has_30_to_50_scenarios_covering_every_group() -> None:
    assert 30 <= len(FILES) <= 50
    numbers = [path.name.split("-", 1)[0] for path in FILES]
    assert len(set(numbers)) == len(numbers), "số thứ tự kịch bản bị trùng"
    groups = Counter(_load(path).get("category") for path in FILES)
    assert set(groups) <= CATEGORIES, groups
    assert all(groups[group] >= 3 for group in REQUIRED), groups


@pytest.mark.parametrize("path", FILES, ids=[path.stem for path in FILES])
def test_scenario_is_well_formed(path: Path) -> None:
    scenario = _load(path)
    assert set(scenario) <= TOP_KEYS, set(scenario) - TOP_KEYS
    assert scenario.get("title")
    assert scenario.get("category") in CATEGORIES
    if "now" in scenario:
        _aware(scenario["now"])
    assert scenario.get("patient", "lan") in dict(PATIENTS)

    keys = set(CLINIC_KEYS)
    for item in scenario.get("appointments", []):
        assert set(item) <= {"key", "patient", "doctor", "service", "start", "minutes"}, item
        assert item["key"] not in keys, f"khóa {item['key']} bị trùng"
        assert item["patient"] in dict(PATIENTS)
        assert item["service"] in DOCTOR_SERVICES[item["doctor"]], item
        _aware(item["start"])
        keys.add(item["key"])

    turns = scenario["turns"]
    assert turns, "kịch bản cần ít nhất một lượt"
    expects_proposal = False
    for index, turn in enumerate(turns, start=1):
        where = f"lượt {index}"
        if "confirm" in turn:
            assert set(turn) <= {"confirm", "expect_appointment"}, where
            assert turn["confirm"] is True, where
            assert expects_proposal, f"{where}: xác nhận khi chưa có lượt nào mong đợi thẻ"
            continue
        assert set(turn) <= {"user", "expect"} and turn.get("user"), where
        expect = turn.get("expect") or {}
        assert set(expect) <= EXPECT_KEYS, f"{where}: {set(expect) - EXPECT_KEYS}"
        for tool in [*expect.get("tools", []), *expect.get("no_tools", [])]:
            assert tool in TOOLS, f"{where}: không có tool {tool}"
        for tool, args in expect.get("args", {}).items():
            assert tool in TOOLS, f"{where}: không có tool {tool}"
            unknown = set(args) - set(TOOLS[tool].args.model_fields)
            assert not unknown, f"{where}: {tool} không có tham số {unknown}"
        if "proposal" in expect:
            proposal = expect["proposal"]
            assert set(proposal) <= PROPOSAL_KEYS, f"{where}: {set(proposal) - PROPOSAL_KEYS}"
            assert proposal["type"] in {"BOOK", "RESCHEDULE", "CANCEL"}, where
            if "start_at" in proposal:
                _aware(proposal["start_at"])
            expects_proposal = True
        assert not ("proposal" in expect and expect.get("no_proposal")), where
    missing = _refs(turns) - keys
    assert not missing, f"tham chiếu không có thật: {missing}"


def test_report_summarizes_pass_rate_latency_and_cost() -> None:
    turn = {"first_token_ms": 1200, "total_ms": 4000, "input_tokens": 3000, "output_tokens": 200}
    slow = {"first_token_ms": 6000, "total_ms": 16_000, "input_tokens": 1000, "output_tokens": 100}
    report = build_report(
        [
            {"name": "01", "category": "dat", "outcome": "passed", "reason": None, "turns": [turn]},
            {"name": "02", "category": "dat", "outcome": "failed", "reason": "x", "turns": [slow]},
            {"name": "03", "category": "injection", "outcome": "passed", "turns": [turn]},
        ],
        model="openai/test",
        prompt_version="v",
        fake=False,
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
    )
    summary = report["summary"]
    assert (summary["passed"], summary["total"], summary["pass_rate"]) == (2, 3, 0.6667)
    assert summary["by_category"] == {
        "dat": {"total": 2, "passed": 1},
        "injection": {"total": 1, "passed": 1},
    }
    assert summary["first_token_ms"] == {"p50": 1200, "p90": 6000, "max": 6000}
    assert summary["tokens"] == {"input": 7000, "output": 500}
    assert summary["cost_usd"] == 0.008  # (7000 × 1 + 500 × 2) / 1 000 000
    assert summary["meets"] == {"AC-15": False, "NFR-03": False}  # 67% < 80%; p90 quá ngưỡng


def test_percentile_uses_nearest_rank() -> None:
    values = list(range(1, 11))
    assert (percentile(values, 50), percentile(values, 90), percentile(values, 100)) == (5, 9, 10)
    assert percentile([], 90) is None

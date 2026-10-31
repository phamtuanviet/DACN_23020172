"""Hạn mức tin nhắn, trần chi phí LLM, ngắt mạch (docs mục 6.8).

Bộ đếm chi phí và trạng thái ngắt mạch nằm ở Valkey để mọi replica cùng biết. Valkey lỗi thì không
chặn bệnh nhân (giống rate limit): ghi cảnh báo rồi cho lượt chat chạy tiếp.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

import structlog
from langchain_core.messages.ai import UsageMetadata
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.timeutil import to_local

log = structlog.get_logger(__name__)

CIRCUIT_FAILURES = 5  # quá 5 lỗi liên tiếp trong 1 phút
CIRCUIT_WINDOW_S = 60
CIRCUIT_OPEN_S = 120  # thì ngừng gọi LLM trong 2 phút
BUDGET_WARNING_RATIO = 0.8  # đạt 80% trần thì cảnh báo (mục 11.7)
_FAILURES_KEY = "agent:llm:failures"
_CIRCUIT_KEY = "agent:llm:circuit"


def agent_unavailable() -> AppError:
    return AppError(
        "AGENT_UNAVAILABLE",
        "Trợ lý tạm thời không hoạt động. Bạn vẫn đặt lịch được trên trang Đặt lịch.",
        status=503,
    )


def quota_exceeded(limit: int) -> AppError:
    return AppError(
        "AGENT_QUOTA_EXCEEDED",
        f"Bạn đã dùng hết {limit} tin nhắn với trợ lý hôm nay. Bạn vẫn đặt lịch được trên trang "
        "Đặt lịch, hoặc quay lại trò chuyện vào ngày mai.",
        status=429,
        details={"limit": limit},
    )


@dataclass
class Usage:
    """Token của một lượt chat, cộng dồn qua mọi lần gọi LLM trong lượt (NFR-03, NFR-15).

    Số token thật chỉ có khi lần gọi chạy xong. Lần gọi bị hủy giữa chừng (trình duyệt ngắt kết
    nối, quá 30 giây) nhà cung cấp vẫn tính tiền phần prompt đã đọc, nên mỗi lần gọi ghi trước một
    ước lượng; lượt kết thúc mà lần gọi chưa xong thì tính theo ước lượng đó.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    pending_input: int = 0

    def begin_call(self, estimated_input: int) -> None:
        self.pending_input = estimated_input

    def add(self, metadata: UsageMetadata | None) -> None:
        self.llm_calls += 1
        self.pending_input = 0
        if metadata:
            self.input_tokens += metadata.get("input_tokens", 0)
            self.output_tokens += metadata.get("output_tokens", 0)

    def settle_pending(self) -> None:
        """Lần gọi chưa xong khi lượt kết thúc: tính phần prompt theo ước lượng."""
        if self.pending_input:
            self.llm_calls += 1
            self.input_tokens += self.pending_input
            self.pending_input = 0

    def cost_usd(self, settings: Settings) -> float:
        return (
            self.input_tokens * settings.llm_input_usd_per_mtok
            + self.output_tokens * settings.llm_output_usd_per_mtok
        ) / 1_000_000


class Guard:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @asynccontextmanager
    async def _valkey(self) -> AsyncGenerator[Redis]:
        client = Redis.from_url(self._settings.valkey_url.get_secret_value(), decode_responses=True)
        try:
            yield client
        finally:
            await client.aclose()

    def _cost_key(self, now: datetime) -> str:
        return f"agent:cost:{to_local(now).date().isoformat()}"

    async def is_open(self, now: datetime) -> bool:
        """Còn gọi được LLM: chưa ngắt mạch và chưa chạm trần chi phí ngày."""
        try:
            async with self._valkey() as valkey:
                if await valkey.exists(_CIRCUIT_KEY):
                    return False
                spent = float(await valkey.get(self._cost_key(now)) or 0)
        except RedisError:
            log.warning("agent.guard_unavailable")
            return True
        return spent < self._settings.llm_daily_budget_usd

    async def ensure_open(self, now: datetime) -> None:
        if not await self.is_open(now):
            raise agent_unavailable()

    async def record_success(self) -> None:
        try:
            async with self._valkey() as valkey:
                await valkey.delete(_FAILURES_KEY)
        except RedisError:
            log.warning("agent.guard_unavailable")

    async def record_failure(self) -> None:
        try:
            async with self._valkey() as valkey:
                failures = await valkey.incr(_FAILURES_KEY)
                if failures == 1:
                    await valkey.expire(_FAILURES_KEY, CIRCUIT_WINDOW_S)
                if failures >= CIRCUIT_FAILURES:
                    await valkey.set(_CIRCUIT_KEY, "1", ex=CIRCUIT_OPEN_S)
                    await valkey.delete(_FAILURES_KEY)
                    log.error("agent.circuit_open", seconds=CIRCUIT_OPEN_S)
        except RedisError:
            log.warning("agent.guard_unavailable")

    async def charge(self, usage: Usage, now: datetime) -> None:
        """Cộng chi phí của lượt vào bộ đếm ngày (giờ Việt Nam)."""
        cost = usage.cost_usd(self._settings)
        if cost <= 0:
            return
        budget = self._settings.llm_daily_budget_usd
        try:
            async with self._valkey() as valkey:
                key = self._cost_key(now)
                total = float(await valkey.incrbyfloat(key, cost))
                await valkey.expire(key, 3 * 24 * 3600)
        except RedisError:
            log.warning("agent.guard_unavailable")
            return
        if total >= budget:
            log.error("agent.budget_reached", spent_usd=round(total, 4), budget_usd=budget)
        elif total - cost < budget * BUDGET_WARNING_RATIO <= total:
            log.warning("agent.budget_80", spent_usd=round(total, 4), budget_usd=budget)

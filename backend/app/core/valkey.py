"""Client Valkey (tương thích Redis): bộ đếm rate limit, trần chi phí LLM, ngắt mạch (TD-05)."""

from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_valkey() -> Redis:
    return Redis.from_url(get_settings().valkey_url.get_secret_value(), decode_responses=True)

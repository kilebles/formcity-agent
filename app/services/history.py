from __future__ import annotations

import json

from redis.asyncio import Redis

from app.config import settings

_MAX_PAIRS = 5
_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 дней

_redis = Redis.from_url(settings.redis_url, decode_responses=True)


def _key(user_id: int) -> str:
    return f"history:{user_id}"


async def get_history(user_id: int) -> list[dict]:
    items = await _redis.lrange(_key(user_id), 0, -1)
    return [json.loads(item) for item in items]


async def append_history(user_id: int, user_message: str, assistant_message: str) -> None:
    key = _key(user_id)
    pipe = _redis.pipeline()
    pipe.rpush(key, json.dumps({"role": "user", "content": user_message}, ensure_ascii=False))
    pipe.rpush(key, json.dumps({"role": "assistant", "content": assistant_message}, ensure_ascii=False))
    pipe.ltrim(key, -_MAX_PAIRS * 2, -1)
    pipe.expire(key, _TTL_SECONDS)
    await pipe.execute()


async def clear_history(user_id: int) -> None:
    await _redis.delete(_key(user_id))

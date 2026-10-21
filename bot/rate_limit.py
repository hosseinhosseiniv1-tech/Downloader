"""Per-user concurrent job limiting via Redis counters.

We store the set of active RQ job IDs per user in a Redis SET
(``rate:user:{chat_id}:active``). Every job enqueue adds to the set; every
completion (success or failure) removes itself. The TTL on the set prevents
leaks if a worker crashes without cleaning up (60 minutes matches the job
TTL).
"""

from __future__ import annotations

import redis.asyncio as aioredis


class ConcurrentJobLimiter:
    def __init__(self, redis: aioredis.Redis, *, max_concurrent: int, ttl_seconds: int):
        self._redis = redis
        self._max = max_concurrent
        self._ttl = ttl_seconds

    def _key(self, chat_id: int) -> str:
        return f"rate:user:{chat_id}:active"

    async def current(self, chat_id: int) -> int:
        try:
            return int(await self._redis.scard(self._key(chat_id)))
        except Exception:
            return 0

    async def try_acquire(self, chat_id: int, job_id: str) -> bool:
        key = self._key(chat_id)
        pipe = self._redis.pipeline()
        pipe.sadd(key, job_id)
        pipe.expire(key, self._ttl)
        pipe.scard(key)
        try:
            _, _, count = await pipe.execute()
        except Exception:
            return False
        return int(count) <= self._max

    async def release(self, chat_id: int, job_id: str) -> None:
        try:
            await self._redis.srem(self._key(chat_id), job_id)
        except Exception:
            pass
"""Thin async facade over the RQ queue.

RQ itself is synchronous, so we run blocking calls in a thread executor to
avoid stalling the event loop.
"""

from __future__ import annotations

import asyncio
import uuid

from redis import Redis
from rq import Queue

QUEUE_NAME = "downloads"
JOB_TTL_SECONDS = 3600
JOB_TIMEOUT_SECONDS = 3600


class QueueClient:
    def __init__(self, redis_url: str):
        self._sync_redis = Redis.from_url(redis_url, socket_timeout=10)
        self._queue = Queue(QUEUE_NAME, connection=self._sync_redis, default_timeout=JOB_TIMEOUT_SECONDS)

    async def enqueue_download(
        self,
        *,
        chat_id: int,
        url: str,
        quality: str,
        status_message_id: int | None,
        proxy: str | None,
    ) -> str:
        job_id = f"job-{uuid.uuid4().hex[:16]}"

        def _enqueue() -> str:
            from worker.jobs import process_download  # late import to avoid cycles

            job = self._queue.enqueue(
                process_download,
                job_id=job_id,
                chat_id=chat_id,
                url=url,
                quality=quality,
                status_message_id=status_message_id,
                proxy=proxy,
                job_timeout=JOB_TIMEOUT_SECONDS,
                result_ttl=JOB_TTL_SECONDS,
                failure_ttl=JOB_TTL_SECONDS,
                ttl=JOB_TTL_SECONDS,
                job_id=job_id,
            )
            return job.id

        return await asyncio.get_running_loop().run_in_executor(None, _enqueue)

    async def get_job_status(self, job_id: str) -> dict | None:
        def _read() -> dict | None:
            import json

            raw = self._sync_redis.hgetall(f"job:{job_id}")
            if not raw:
                return None
            if isinstance(next(iter(raw.keys())), bytes):
                raw = {k.decode(): v.decode() for k, v in raw.items()}
            return raw

        return await asyncio.get_running_loop().run_in_executor(None, _read)

    async def close(self) -> None:
        try:
            self._sync_redis.close()
        except Exception:
            pass
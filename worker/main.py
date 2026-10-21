"""RQ worker entrypoint for Super Downloader.

Responsibilities:
- Fail fast if Redis is unreachable at startup.
- Register the download job function on the ``downloads`` queue.
- Register the periodic cleanup job on the ``maintenance`` queue.
- Start an RQ worker with a 60-minute job timeout and 1 retry.
- Emit a heartbeat every 60 seconds with queue depth.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Worker

from download_core.logging import configure_logging, get_logger, new_correlation_id

log = get_logger("worker.main")


def _redis_url() -> str:
    return (
        os.environ.get("REDIS_PRIVATE_URL")
        or os.environ.get("REDIS_URL")
        or "redis://localhost:6379/0"
    )


def _make_redis() -> Redis:
    url = _redis_url()
    # ``socket_connect_timeout`` bounds the startup PING.
    return Redis.from_url(
        url,
        socket_connect_timeout=3,
        socket_timeout=30,
        health_check_interval=30,
        decode_responses=False,
    )


def _startup_redis_ping(client: Redis) -> None:
    """Ping Redis with a 2–3 s budget; exit(1) with a clear error on failure."""
    try:
        client.ping()
        log.info("redis.connected", url_scheme=_redis_url().split("://", 1)[0])
    except RedisError as exc:
        log.critical("redis.unreachable", error=f"{type(exc).__name__}: {exc}")
        print(
            "FATAL: cannot reach Redis at startup. Check REDIS_PRIVATE_URL / REDIS_URL "
            f"and Railway networking. Error: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


def _start_heartbeat(redis_client: Redis, queues: list[Queue]) -> None:
    """Emit a structured heartbeat log every 60 s with per-queue depth."""

    def _loop() -> None:
        while True:
            try:
                depths = {q.name: q.count for q in queues}
                log.info(
                    "worker.heartbeat",
                    correlation_id=new_correlation_id("hb"),
                    queue_depths=depths,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("worker.heartbeat_failed", error=f"{type(exc).__name__}: {exc}")
            time.sleep(60)

    t = threading.Thread(target=_loop, name="worker-heartbeat", daemon=True)
    t.start()


def _start_cleanup_scheduler(redis_client: Redis) -> None:
    """Enqueue the cleanup job every 15 minutes on the maintenance queue."""
    from worker.jobs import cleanup_old_files

    maintenance_q = Queue("maintenance", connection=redis_client, default_timeout=300)

    def _loop() -> None:
        while True:
            try:
                maintenance_q.enqueue(
                    cleanup_old_files,
                    max_age_seconds=2 * 60 * 60,
                    job_timeout=300,
                    result_ttl=60,
                    failure_ttl=300,
                )
                log.info("cleanup.enqueued")
            except Exception as exc:  # noqa: BLE001
                log.warning("cleanup.enqueue_failed", error=f"{type(exc).__name__}: {exc}")
            time.sleep(15 * 60)

    t = threading.Thread(target=_loop, name="cleanup-scheduler", daemon=True)
    t.start()


def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    redis_client = _make_redis()
    _startup_redis_ping(redis_client)

    downloads_q = Queue("downloads", connection=redis_client, default_timeout=3600)
    maintenance_q = Queue("maintenance", connection=redis_client, default_timeout=300)

    _start_heartbeat(redis_client, [downloads_q, maintenance_q])
    _start_cleanup_scheduler(redis_client)

    # RQ Worker subscribes to both queues; maintenance is lightweight.
    worker = Worker(
        queues=[downloads_q, maintenance_q],
        connection=redis_client,
        job_timeout=3600,          # 60-minute hard cap
        default_result_ttl=3600,
        max_jobs=None,
    )

    log.info(
        "worker.started",
        queues=[q.name for q in worker.queues],
        job_timeout=3600,
    )
    worker.work(with_scheduler=False)  # we manage the cleanup loop ourselves


if __name__ == "__main__":
    main()
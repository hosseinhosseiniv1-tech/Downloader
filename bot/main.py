"""Bot entrypoint.

Startup order:
1. Configure logging.
2. Build Redis client and PING with a 2–3 s timeout → exit(1) on failure.
3. Start aiohttp /health server.
4. Build aiogram ``Bot`` with either the local Bot API or Telegram SaaS.
5. Register middlewares + handlers + global error handler.
6. Start polling.
"""

from __future__ import annotations

import asyncio
import sys

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.redis import RedisStorage

from download_core.logging import configure_logging, get_logger

from . import handlers
from .config import BotConfig
from .errors import router as errors_router
from .health import start_health_server
from .middlewares import I18nMiddleware
from .queue_client import QueueClient
from .rate_limit import ConcurrentJobLimiter

log = get_logger("bot.main")


async def _build_redis(cfg: BotConfig) -> aioredis.Redis:
    client = aioredis.from_url(
        cfg.redis_url,
        socket_connect_timeout=3,
        socket_timeout=10,
        decode_responses=False,
        health_check_interval=30,
    )
    try:
        await asyncio.wait_for(client.ping(), timeout=3)
        log.info("redis.connected")
    except Exception as exc:
        log.critical("redis.unreachable", error=f"{type(exc).__name__}: {exc}")
        print(
            "FATAL: cannot reach Redis at startup. Check REDIS_PRIVATE_URL / REDIS_URL. "
            f"Error: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    return client


def _build_bot(cfg: BotConfig) -> Bot:
    # Prefer the local Bot API server (2 GB uploads). Fall back to SaaS.
    try:
        api = TelegramAPIServer.from_base(cfg.local_bot_api_url, is_local=True)
        session = AiohttpSession(api=api)
        log.info("bot.local_api_configured", base=cfg.local_bot_api_url)
    except Exception as exc:
        log.warning("bot.local_api_unavailable", error=str(exc))
        session = AiohttpSession()

    # SOCKS5 proxy for outbound Telegram calls (if configured).
    if cfg.proxy_url:
        session._proxy = cfg.proxy_url  # type: ignore[attr-defined]
        log.info("bot.proxy_configured", scheme=cfg.proxy_url.split("://", 1)[0])

    return Bot(token=cfg.token, session=session)


async def _verify_get_me(bot: Bot) -> None:
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=10)
        log.info("bot.get_me_ok", username=me.username, id=me.id)
    except Exception as exc:
        log.critical("bot.get_me_failed", error=str(exc))
        # Do NOT exit — the local API might still come up.


async def _main() -> None:
    cfg = BotConfig.from_env()
    configure_logging(cfg.log_level)

    redis_client = await _build_redis(cfg)

    health_runner = await start_health_server(cfg.health_port, redis_client=redis_client)
    log.info("health_server.started", port=cfg.health_port)

    bot = _build_bot(cfg)
    await _verify_get_me(bot)

    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    # Inject shared dependencies into every handler.
    queue = QueueClient(cfg.redis_url)
    limiter = ConcurrentJobLimiter(
        redis_client,
        max_concurrent=cfg.max_concurrent_jobs_per_user,
        ttl_seconds=cfg.job_ttl_seconds,
    )

    dp.update.middleware(I18nMiddleware())

    async def _inject_deps(handler, event, data):
        data["redis"] = redis_client
        data["queue"] = queue
        data["limiter"] = limiter
        data["bot_username"] = cfg.bot_username
        return await handler(event, data)

    # Register as an outer middleware on updates so it applies to every handler.
    dp.update.outer_middleware(_inject_deps)

    handlers.register(dp)
    dp.include_router(errors_router)

    log.info("bot.polling_started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        log.info("bot.shutting_down")
        await queue.close()
        await bot.session.close()
        await health_runner.cleanup()
        await redis_client.aclose()


def run() -> None:
    try:
        asyncio.run(_main())
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:  # noqa: BLE001
        configure_logging()
        log.critical("bot.fatal", error=f"{type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    run()
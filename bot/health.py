"""Tiny aiohttp /health endpoint for Railway liveness probes."""

from __future__ import annotations

import asyncio

from aiohttp import web


async def _health_handler(request: web.Request) -> web.Response:
    redis_ok = False
    redis_error: str | None = None
    redis_client = request.app.get("redis")
    if redis_client is not None:
        try:
            redis_ok = bool(await asyncio.wait_for(redis_client.ping(), timeout=2))
        except Exception as exc:  # noqa: BLE001
            redis_error = str(exc)
    status = 200 if redis_ok else 503
    body = {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
    if redis_error:
        body["redis_error"] = redis_error
    return web.json_response(body, status=status)


async def start_health_server(port: int, redis_client=None) -> web.AppRunner:
    app = web.Application()
    if redis_client is not None:
        app["redis"] = redis_client
    app.router.add_get("/health", _health_handler)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    return runner
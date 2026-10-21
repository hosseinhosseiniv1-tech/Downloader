"""Runtime configuration for the bot.

All values come from environment variables — nothing is hard-coded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BotConfig:
    token: str
    bot_username: str
    redis_url: str
    local_bot_api_url: str
    proxy_url: str | None
    health_port: int
    admin_api_key: str | None
    log_level: str
    max_concurrent_jobs_per_user: int
    job_ttl_seconds: int
    metadata_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = _require("TELEGRAM_BOT_TOKEN")
        redis_url = (
            os.environ.get("REDIS_PRIVATE_URL")
            or os.environ.get("REDIS_URL")
            or "redis://localhost:6379/0"
        )
        local_api = (
            os.environ.get("LOCAL_BOT_API_URL")
            or "http://local-bot-api.railway.internal:8081"
        ).rstrip("/")
        return cls(
            token=token,
            bot_username=os.environ.get("BOT_USERNAME", "StoaderBot").lstrip("@"),
            redis_url=redis_url,
            local_bot_api_url=local_api,
            proxy_url=_clean_optional(os.environ.get("PROXY_URL")),
            health_port=int(os.environ.get("HEALTH_PORT", "8080")),
            admin_api_key=_clean_optional(os.environ.get("ADMIN_API_KEY")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            max_concurrent_jobs_per_user=int(os.environ.get("MAX_CONCURRENT_JOBS_PER_USER", "2")),
            job_ttl_seconds=int(os.environ.get("JOB_TTL_SECONDS", "3600")),
            metadata_timeout_seconds=float(os.environ.get("METADATA_TIMEOUT_SECONDS", "30")),
        )


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"FATAL: environment variable {name} is required but not set.")
    return value


def _clean_optional(value: str | None) -> str | None:
    if not value:
        return None
    if value.lower().startswith(("socks5://", "socks5h://", "http://", "https://")):
        return value
    return None
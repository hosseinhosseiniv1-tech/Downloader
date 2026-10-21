"""Middleware that resolves the user's language and injects a translator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from ..i18n import get_translator, normalize_language


class I18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                user = event.callback_query.from_user

        lang: str | None = None
        redis = data.get("redis")
        if user and redis is not None:
            try:
                stored = await redis.get(f"lang:{user.id}")
                if isinstance(stored, bytes):
                    stored = stored.decode()
                if stored:
                    lang = normalize_language(stored)
            except Exception:
                pass

        if lang is None and user and user.language_code:
            lang = normalize_language(user.language_code)

        data["translator"] = get_translator(lang)
        data["language"] = lang or "en"
        return await handler(event, data)
"""URL → metadata → quality buttons → RQ enqueue."""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from download_core import get_video_info, validate_url
from download_core.logging import get_logger

from ..i18n import get_translator
from ..keyboards import quality_keyboard

router = Router(name="download")
log = get_logger("bot.download")

_PENDING_URL_KEY = "pending_url:{chat_id}"


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "—"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


async def _is_banned(redis, chat_id: int) -> bool:
    try:
        return bool(await redis.get(f"ban:{chat_id}"))
    except Exception:
        return False


async def handle_url(
    message: Message,
    raw_url: str,
    redis,
    translator,
    queue,
    limiter,
) -> None:
    """Shared flow: validate → metadata → quality keyboard."""
    chat_id = message.chat.id
    if await _is_banned(redis, chat_id):
        await message.answer(translator("banned"))
        return

    validation = validate_url(raw_url)
    if not validation["ok"]:
        await message.answer(translator("invalid_url"))
        return
    safe_url = validation["data"]["url"]

    status_msg = await message.answer(translator("fetching_metadata"))

    info = await asyncio.get_running_loop().run_in_executor(
        None, lambda: get_video_info(safe_url)
    )
    if not info["ok"]:
        await status_msg.edit_text(translator("metadata_failed"))
        return

    data = info["data"]
    await redis.set(
        _PENDING_URL_KEY.format(chat_id=chat_id),
        safe_url,
        ex=60 * 30,  # 30 min to choose a quality
    )

    text = translator(
        "choose_quality",
        title=_escape_html(data["title"])[:200],
        uploader=_escape_html(str(data.get("uploader") or "—"))[:100],
        duration=_fmt_duration(data.get("duration_seconds")),
    )
    keyboard = quality_keyboard(translator, available=data.get("available_qualities") or ["best"])
    await status_msg.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@router.message(F.text & ~F.text.startswith("/"))
async def on_text_url(message: Message, redis, translator, queue, limiter) -> None:
    if not message.text:
        return
    await handle_url(message, message.text.strip(), redis, translator, queue, limiter)


@router.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, translator) -> None:
    await callback.answer()
    await callback.message.edit_text(
        translator("send_url"),
        reply_markup=None,
    )


@router.callback_query(F.data.startswith("q:"))
async def cb_quality(callback: CallbackQuery, redis, translator, queue, limiter) -> None:
    await callback.answer()
    chat_id = callback.message.chat.id
    if await _is_banned(redis, chat_id):
        await callback.message.edit_text(translator("banned"))
        return

    quality = callback.data.split(":", 1)[1]
    pending_key = _PENDING_URL_KEY.format(chat_id=chat_id)
    url = await redis.get(pending_key)
    if isinstance(url, bytes):
        url = url.decode()
    if not url:
        await callback.message.edit_text(translator("send_url"))
        return

    active = await limiter.current(chat_id)
    if active >= 2:
        await callback.message.edit_text(translator("rate_limited", count=active))
        return

    # Edit to acknowledge before the (possibly slow) enqueue.
    status_msg = await callback.message.edit_text(translator("queued"))

    job_id = await queue.enqueue_download(
        chat_id=chat_id,
        url=url,
        quality=quality,
        status_message_id=status_msg.message_id,
        proxy=None,
    )
    acquired = await limiter.try_acquire(chat_id, job_id)
    if not acquired:
        await status_msg.edit_text(translator("rate_limited", count=active + 1))
        return

    await redis.delete(pending_key)
    log.info("job.enqueued", job_id=job_id, chat_id=chat_id, quality=quality)
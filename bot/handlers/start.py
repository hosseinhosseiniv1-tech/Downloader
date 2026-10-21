"""``/start`` command with deep-link payload support and ``/help``."""

from __future__ import annotations

import base64
import binascii

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from ..i18n import get_translator

router = Router(name="start")


def _decode_start_payload(raw: str) -> str | None:
    """Decode ``get_<payload>`` — payload is either a URL or a job id.

    Telegram start parameters are alphanumeric + hyphen + underscore, so
    the bot encodes URLs with ``aiogram.utils.deep_linking.encode_payload``
    (base64url no padding). We mirror that algorithm here.
    """
    if not raw:
        return None
    if raw.startswith("get_"):
        raw = raw[len("get_") :]
    if not raw:
        return None
    # If it already looks like a URL, return as-is.
    if raw.lower().startswith(("http://", "https://")):
        return raw
    padding = "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode(raw + padding).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    return decoded


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject, redis, translator, queue, limiter) -> None:
    # Lazy import to avoid a package cycle.
    from . import download as download_handler

    payload = _decode_start_payload(command.args or "")
    if not payload:
        await message.answer(translator("welcome"))
        return

    if payload.lower().startswith(("http://", "https://")):
        await message.answer(translator("start_payload_url"))
        await download_handler.handle_url(message, payload, redis, translator, queue, limiter)
        return

    # Treat as a job token — resume/display job status.
    await message.answer(translator("start_payload_job", job_id=payload))
    status = await queue.get_job_status(payload)
    if not status:
        await message.answer(translator("job_failed", reason="job not found"))
        return
    state = status.get("status", "unknown")
    if state == "completed":
        await message.answer(translator("job_completed"))
    elif state == "failed_upload_limit":
        await message.answer(translator("failed_upload_limit"))
    elif state == "failed":
        await message.answer(translator("job_failed", reason=status.get("error_message", "unknown")))
    else:
        await message.answer(f"ℹ️ Status: {state}")


@router.message(CommandStart())
async def cmd_start(message: Message, translator) -> None:
    await message.answer(translator("welcome"))


@router.message(Command("help"))
async def cmd_help(message: Message, translator) -> None:
    await message.answer(translator("help"))
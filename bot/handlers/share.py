"""``/share`` command — generate a deep link for a URL or the current job."""

from __future__ import annotations

import base64

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from download_core.validation import validate_url

router = Router(name="share")


def _encode_payload(payload: str) -> str:
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


@router.message(Command("share"))
async def cmd_share(message: Message, command: CommandObject, translator, bot_username: str) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer(translator("share_usage"))
        return

    if not validate_url(arg)["ok"]:
        await message.answer(translator("invalid_url"))
        return

    encoded = _encode_payload(arg)
    link = f"https://t.me/{bot_username}?start=get_{encoded}"
    await message.answer(translator("share_for_url", link=link), disable_web_page_preview=True)
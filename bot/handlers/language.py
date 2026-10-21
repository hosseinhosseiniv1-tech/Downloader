"""``/language`` command and callback handlers."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ..i18n import get_translator, normalize_language
from ..keyboards import language_keyboard

router = Router(name="language")

_USER_LANG_KEY = "lang:{chat_id}"


def _lang_key(chat_id: int) -> str:
    return f"lang:{chat_id}"


@router.message(Command("language"))
async def cmd_language(message: Message, redis, translator) -> None:
    await message.answer(
        translator("language_choose"),
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(callback: CallbackQuery, redis) -> None:
    await callback.answer()
    lang = callback.data.split(":", 1)[1]
    lang = normalize_language(lang)
    if callback.from_user:
        await redis.set(_lang_key(callback.from_user.id), lang)
    translator = get_translator(lang)
    await callback.message.edit_text(
        translator("language_set"),
        reply_markup=None,
    )
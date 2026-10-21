"""Inline keyboard builders with a clean, premium look."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .i18n import Translator


_QUALITY_CALLBACK_PREFIX = "q:"
_BACK_CALLBACK = "back"


def quality_keyboard(translator: Translator, *, available: list[str]) -> InlineKeyboardMarkup:
    """Build the quality selection grid.

    ``available`` comes from metadata extraction; unsupported qualities are
    disabled (shown with a strikethrough marker) rather than hidden so the
    user understands the video's capabilities.
    """
    b = InlineKeyboardBuilder()

    def _add(label_key: str, quality: str, available_here: bool) -> None:
        label = translator(label_key)
        if not available_here:
            label = f"· {label} ·"
        b.button(
            text=label,
            callback_data=f"{_QUALITY_CALLBACK_PREFIX}{quality}",
        )

    _add("btn_best", "best", "best" in available)
    _add("btn_1080p", "1080p", "1080p" in available)
    _add("btn_720p", "720p", "720p" in available)
    _add("btn_480p", "480p", "480p" in available)
    _add("btn_audio", "audio", "audio" in available)

    # Two rows of two + one full-width + back row.
    b.adjust(2, 2, 1, 1)
    b.row(InlineKeyboardButton(text=translator("btn_back"), callback_data=_BACK_CALLBACK))
    return b.as_markup()


def language_keyboard() -> InlineKeyboardMarkup:
    """Simple two-button language switcher."""
    b = InlineKeyboardBuilder()
    b.button(text="🇬🇧 English", callback_data="lang:en")
    b.button(text="🇮🇷 فارسی", callback_data="lang:fa")
    b.adjust(2)
    return b.as_markup()


def back_keyboard(translator: Translator) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=translator("btn_back"), callback_data=_BACK_CALLBACK)]]
    )
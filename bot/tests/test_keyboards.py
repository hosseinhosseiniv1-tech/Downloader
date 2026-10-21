from __future__ import annotations

from bot.i18n import get_translator
from bot.keyboards import quality_keyboard


def test_quality_keyboard_rows_and_callbacks():
    kb = quality_keyboard(get_translator("en"), available=["best", "720p", "audio"])
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "q:best" in callbacks
    assert "q:720p" in callbacks
    assert "q:audio" in callbacks
    assert "back" in callbacks
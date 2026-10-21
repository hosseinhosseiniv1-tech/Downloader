"""GNU gettext i18n helper with RTL awareness for Persian.

Uses ``gettext.translation`` with the local ``locales`` directory. Falls
back to English (msgid) if a catalog is missing or .mo compilation failed.
"""

from __future__ import annotations

import gettext
from pathlib import Path
from typing import ClassVar

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "fa")
RTL_LANGUAGES: frozenset[str] = frozenset({"fa", "ar", "he", "ur"})

_LOCALE_DIR = Path(__file__).parent / "locales"


class Translator:
    """Holds per-language gettext translations and a language registry."""

    _instances: ClassVar[dict[str, "Translator"]] = {}

    def __init__(self, lang: str):
        self.lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self._gt: gettext.NullTranslations = gettext.NullTranslations()
        try:
            self._gt = gettext.translation(
                domain="messages",
                localedir=str(_LOCALE_DIR),
                languages=[self.lang],
                fallback=True,
            )
        except Exception:
            self._gt = gettext.NullTranslations()

    def __call__(self, key: str, **kwargs: object) -> str:
        text = self._gt.gettext(key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    def is_rtl(self) -> bool:
        return self.lang in RTL_LANGUAGES

    def direction_marker(self) -> str:
        """Zero-width RTL mark for contexts where the message must render RTL."""
        return "\u200f" if self.is_rtl() else ""


def get_translator(lang: str | None) -> Translator:
    """Return a cached :class:`Translator` for ``lang``."""
    resolved = (lang or DEFAULT_LANGUAGE).lower()
    if resolved not in Translator._instances:
        Translator._instances[resolved] = Translator(resolved)
    return Translator._instances[resolved]


def normalize_language(lang: str | None) -> str:
    """Normalise an arbitrary language string to one of SUPPORTED_LANGUAGES."""
    if not lang:
        return DEFAULT_LANGUAGE
    lang = lang.lower().split("-")[0]
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
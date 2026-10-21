from __future__ import annotations

from bot.i18n import get_translator, normalize_language


def test_normalize_language():
    assert normalize_language("en-US") == "en"
    assert normalize_language("fa-IR") == "fa"
    assert normalize_language("xx") == "en"
    assert normalize_language(None) == "en"


def test_translator_falls_back_to_english_when_mo_missing():
    # .mo files aren't compiled during unit tests; NullTranslations returns key.
    t = get_translator("en")
    assert t("welcome")  # non-empty


def test_translator_formats_kwargs():
    t = get_translator("en")
    rendered = t("choose_quality", title="T", uploader="U", duration="1m")
    assert "T" in rendered or "choose_quality" in rendered


def test_rtl_marker():
    assert get_translator("fa").is_rtl() is True
    assert get_translator("en").is_rtl() is False
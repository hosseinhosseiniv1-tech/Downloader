"""Unit tests for ``download_core._build_ydl_opts``."""

from __future__ import annotations

import pytest

from download_core.ydl_opts import _build_ydl_opts


def test_metadata_mode_defaults():
    opts = _build_ydl_opts(quality="best", mode="metadata")
    assert opts["skip_download"] is True
    assert opts["quiet"] is True
    assert opts["no_warnings"] is True
    assert opts["geo_bypass"] is True
    assert opts["noplaylist"] is True
    assert opts["verbose"] is False
    assert opts["extractor_args"]["youtube"]["player_client"] == ["mweb", "tv", "web_safari"]


def test_download_mode_sets_outtmpl_and_paths():
    opts = _build_ydl_opts(quality="1080p", mode="download")
    assert opts["outtmpl"].startswith("/tmp/downloads/")
    assert opts["paths"]["home"] == "/tmp/downloads"
    assert opts["format"] == "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    assert opts["merge_output_format"] == "mp4"
    assert "progress_hooks" not in opts  # none passed


def test_download_mode_audio_uses_mp3_extract():
    opts = _build_ydl_opts(quality="audio", mode="download")
    assert opts["format"] == "bestaudio/best"
    pp = opts["postprocessors"]
    assert len(pp) == 1
    assert pp[0]["key"] == "FFmpegExtractAudio"
    assert pp[0]["preferredcodec"] == "mp3"
    assert pp[0]["preferredquality"] == "192"


def test_quality_selectors():
    assert _build_ydl_opts(quality="best", mode="download")["format"] == "bestvideo+bestaudio/best"
    assert (
        _build_ydl_opts(quality="720p", mode="download")["format"]
        == "bestvideo[height<=720]+bestaudio/best[height<=720]"
    )
    assert (
        _build_ydl_opts(quality="480p", mode="download")["format"]
        == "bestvideo[height<=480]+bestaudio/best[height<=480]"
    )


def test_invalid_quality_raises_value_error():
    with pytest.raises(ValueError):
        _build_ydl_opts(quality="4k", mode="download")


def test_invalid_mode_raises_value_error():
    with pytest.raises(ValueError):
        _build_ydl_opts(quality="best", mode="stream")  # type: ignore[arg-type]


def test_proxy_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROXY_URL", "socks5h://xray.railway.internal:10808")
    opts = _build_ydl_opts(quality="best", mode="download")
    assert opts["proxy"] == "socks5h://xray.railway.internal:10808"


def test_proxy_invalid_scheme_ignored(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROXY_URL", "ftp://evil.example.com")
    opts = _build_ydl_opts(quality="best", mode="download")
    assert "proxy" not in opts


def test_proxy_http_and_socks5_variants(monkeypatch: pytest.MonkeyPatch):
    for scheme in ("http://", "https://", "socks5://", "socks5h://"):
        monkeypatch.setenv("PROXY_URL", f"{scheme}proxy.local:1080")
        opts = _build_ydl_opts(quality="best", mode="download")
        assert opts["proxy"].startswith(scheme)


def test_pot_server_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("POT_SERVER_URL", "http://pot-provider.railway.internal:4416")
    opts = _build_ydl_opts(quality="best", mode="metadata")
    assert opts["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == [
        "http://pot-provider.railway.internal:4416"
    ]
    assert opts["extractor_args"]["youtube"]["player_client"] == ["mweb", "tv", "web_safari"]


def test_cookies_file_wins_over_browser(
    monkeypatch: pytest.MonkeyPatch, fake_cookies_file
):
    monkeypatch.setenv("COOKIES_FROM_BROWSER", "chrome")
    opts = _build_ydl_opts(quality="best", mode="download")
    assert opts["cookiefile"] == str(fake_cookies_file)
    assert "cookiesfrombrowser" not in opts


def test_cookies_from_browser_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COOKIES_FROM_BROWSER", "firefox")
    opts = _build_ydl_opts(quality="best", mode="download")
    assert opts["cookiesfrombrowser"] == ("firefox",)
    assert "cookiefile" not in opts


def test_missing_cookies_file_falls_back_to_browser(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COOKIES_FILE", "/nonexistent/cookies.txt")
    monkeypatch.setenv("COOKIES_FROM_BROWSER", "chrome")
    opts = _build_ydl_opts(quality="best", mode="download")
    assert opts["cookiesfrombrowser"] == ("chrome",)


def test_progress_hooks_attached_only_in_download_mode():
    def hook(_d):  # pragma: no cover - trivial
        return None

    opts = _build_ydl_opts(quality="best", mode="download", progress_hooks=[hook])
    assert opts["progress_hooks"] == [hook]

    opts_meta = _build_ydl_opts(quality="best", mode="metadata", progress_hooks=[hook])
    assert "progress_hooks" not in opts_meta


def test_verbose_toggle(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YDL_VERBOSE", "1")
    opts = _build_ydl_opts(quality="best", mode="metadata")
    assert opts["verbose"] is True


def test_extra_opts_override():
    opts = _build_ydl_opts(
        quality="best", mode="download", extra_opts={"socket_timeout": 5}
    )
    assert opts["socket_timeout"] == 5
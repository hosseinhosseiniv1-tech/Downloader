"""Builder for yt-dlp option dictionaries.

This module is imported by both ``bot`` (metadata extraction) and ``worker``
(actual downloads), so it must not perform I/O at import time. All
environment variables are read lazily inside :func:`_build_ydl_opts`.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

Mode = Literal["metadata", "download"]

# YouTube clients to try, in order. ``mweb`` and ``tv`` trigger the PO token
# (bgutil) flow, which is required to bypass the "Sign in to confirm you're
# not a bot" interstitial. ``web_safari`` is a useful fallback.
_PLAYER_CLIENTS = ["mweb", "tv", "web_safari"]

# Same for the local Bot API server, but we intentionally *do not* enforce a
# client-side 50 MB cap — the server enforces its real limit (2 GB for bots).
_DEFAULT_OUTTMPL = "/tmp/downloads/%(title).80s-%(id)s.%(ext)s"

# Quality label -> yt-dlp format selector.
_VIDEO_FORMATS: dict[str, str] = {
    "best": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
}

_AUDIO_FORMAT = "bestaudio/best"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_proxy(proxy: str | None) -> str | None:
    """Return a validated proxy URL or ``None``.

    Supports ``http://``, ``https://``, ``socks5://`` and ``socks5h://``.
    ``socks5h`` is preferred for DNS-through-proxy behaviour.
    """
    candidate = (proxy or os.environ.get("PROXY_URL") or "").strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if not lowered.startswith(("http://", "https://", "socks5://", "socks5h://")):
        # Silently ignore malformed proxy — yt-dlp would otherwise crash.
        return None
    return candidate


def _resolve_cookies() -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Decide between ``COOKIES_FILE`` and ``COOKIES_FROM_BROWSER``.

    Returns ``(opts_fragment, debug_info)``. The file wins if both are set.
    """
    cookies_file = (os.environ.get("COOKIES_FILE") or "").strip()
    cookies_from_browser = (os.environ.get("COOKIES_FROM_BROWSER") or "").strip()

    if cookies_file:
        path = Path(cookies_file)
        if path.is_file():
            return {"cookiefile": str(path)}, {"source": "file", "path": str(path)}
        # File configured but missing: fall through to browser if configured.
    if cookies_from_browser:
        # yt-dlp accepts "chrome", "firefox:profile", etc.
        return {"cookiesfrombrowser": (cookies_from_browser,)}, {"source": "browser", "spec": cookies_from_browser}
    return None, {"source": "none"}


def _build_ydl_opts(
    quality: str = "best",
    mode: Mode = "metadata",
    *,
    proxy: str | None = None,
    outtmpl: str | None = None,
    progress_hooks: list[Any] | None = None,
    extra_opts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a yt-dlp options dict.

    Args:
        quality: One of ``best``, ``1080p``, ``720p``, ``480p``, ``audio``.
        mode: ``"metadata"`` (fast, no download) or ``"download"``.
        proxy: Explicit proxy URL. Falls back to ``PROXY_URL`` env var.
        outtmpl: Override the default output template.
        progress_hooks: yt-dlp progress hook callables (download mode only).
        extra_opts: Additional options merged last (caller wins).

    Raises:
        ValueError: If ``mode`` or ``quality`` is invalid. This is a
        programming error (never reachable from user input because the bot
        only passes known constants), so raising is appropriate.
    """
    if mode not in ("metadata", "download"):
        raise ValueError(f"invalid mode: {mode!r}")
    quality = (quality or "best").lower()
    if quality not in {*_VIDEO_FORMATS, "audio"}:
        raise ValueError(f"invalid quality: {quality!r}")

    opts: dict[str, Any] = {
        # Networking / extraction behaviour
        "quiet": True,
        "no_warnings": True,
        "verbose": _env_bool("YDL_VERBOSE", False),
        "noprogress": mode == "metadata",
        "noplaylist": True,
        "geo_bypass": True,
        "ignoreerrors": False,
        "retries": 3,
        "fragment_retries": 3,
        "file_access_retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 30,
        # YouTube PO token flow
        "extractor_args": {
            "youtube": {"player_client": list(_PLAYER_CLIENTS)},
        },
    }

    # bgutil PO token provider — only set if the env var is present.
    pot_url = (os.environ.get("POT_SERVER_URL") or "").strip()
    if pot_url:
        # Merge into the same ``extractor_args`` dict.
        opts["extractor_args"]["youtubepot-bgutilhttp"] = {"base_url": [pot_url]}

    # Proxy (http, https, socks5, socks5h).
    resolved_proxy = _resolve_proxy(proxy)
    if resolved_proxy:
        opts["proxy"] = resolved_proxy

    # Cookies — file wins over browser.
    cookie_opts, _cookie_info = _resolve_cookies()
    if cookie_opts:
        opts.update(cookie_opts)

    if mode == "metadata":
        opts["skip_download"] = True
        # Extract only the flat metadata we need.
        opts["extract_flat"] = False
        # Bound metadata extraction with an overall timeout.
        opts["socket_timeout"] = 30

    elif mode == "download":
        opts["outtmpl"] = outtmpl or os.environ.get("YDL_OUTTMPL") or _DEFAULT_OUTTMPL
        opts["paths"] = {"home": "/tmp/downloads", "temp": "/tmp/downloads"}
        opts["continuedl"] = True
        opts["overwrites"] = True
        opts["concurrent_fragment_downloads"] = 4
        opts["restrictfilenames"] = False
        opts["windowsfilenames"] = True
        opts["trim_file_name"] = 120
        if progress_hooks:
            opts["progress_hooks"] = list(progress_hooks)

        if quality == "audio":
            opts["format"] = _AUDIO_FORMAT
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            opts["format"] = _VIDEO_FORMATS[quality]
            opts["merge_output_format"] = "mp4"

    if extra_opts:
        opts.update(extra_opts)

    return opts


def build_ydl_opts(quality: str = "best", mode: Mode = "metadata", **kwargs: Any) -> dict[str, Any]:
    """Public alias for :func:`_build_ydl_opts` (stable import surface)."""
    return _build_ydl_opts(quality=quality, mode=mode, **kwargs)
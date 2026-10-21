"""Video/audio download via yt-dlp.

Used by the worker (RQ job). This module only downloads to disk — uploading
to Telegram is the worker's responsibility. The module guarantees:

- A result object is returned for every expected failure (never raises).
- The final file path is reported so the caller's ``finally`` block can
  delete it unconditionally.
- Progress hooks are wired through so the worker can throttle updates.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .errors import ErrorCode, Result, err, from_exception, ok
from .logging import get_logger, new_correlation_id
from .validation import sanitize_filename, validate_url
from .ydl_opts import _build_ydl_opts

log = get_logger("download_core.download")

_DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "/tmp/downloads"))


def _final_filepath(info: dict[str, Any]) -> Path | None:
    """Return the path of the final merged/processed file, if determinable."""
    # yt-dlp sets ``filepath`` on the info dict after post-processing.
    filepath = info.get("filepath") or info.get("_filename")
    if filepath:
        return Path(filepath)
    # Audio post-processor changes the extension; look for a sibling .mp3.
    requested = info.get("requested_downloads") or []
    for rd in requested:
        fp = rd.get("filepath")
        if fp:
            p = Path(fp)
            if p.suffix.lower() == ".mp3" and p.exists():
                return p
            mp3_candidate = p.with_suffix(".mp3")
            if mp3_candidate.exists():
                return mp3_candidate
            if p.exists():
                return p
    return None


def download_video(
    url: str,
    quality: str = "best",
    *,
    proxy: str | None = None,
    progress_hooks: list[Any] | None = None,
) -> Result:
    """Download ``url`` at the requested ``quality``.

    Args:
        url: Original URL (will be SSRF-validated).
        quality: ``best`` | ``1080p`` | ``720p`` | ``480p`` | ``audio``.
        proxy: Optional proxy URL; falls back to ``PROXY_URL``.
        progress_hooks: yt-dlp progress hook callables.

    Returns:
        ``{"ok": True, "data": {"filepath": "...", "filesize": N, "title": ...}}``
        or a structured error. ``data["filepath"]`` is *always* set on success
        so the caller can delete the file in ``finally``.
    """
    correlation_id = new_correlation_id("dl")
    started_at = time.monotonic()

    validation = validate_url(url)
    if not validation["ok"]:
        log.warning(
            "download.invalid_url",
            correlation_id=correlation_id,
            url=url,
            error_code=validation["error_code"],
        )
        return validation

    safe_url: str = validation["data"]["url"]

    quality = (quality or "best").lower()
    if quality not in {"best", "1080p", "720p", "480p", "audio"}:
        return err(ErrorCode.INVALID_URL, f"Unsupported quality: {quality!r}")

    _DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        opts = _build_ydl_opts(
            quality=quality,
            mode="download",
            proxy=proxy,
            progress_hooks=progress_hooks,
        )

        import yt_dlp  # type: ignore

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(safe_url, download=True)

        if not isinstance(info, dict):
            return err(ErrorCode.DOWNLOAD_FAILED, "yt-dlp returned no info after download.")

        # Apply the same sanitisation to the chosen title as a defence-in-depth
        # measure. yt-dlp's own ``windowsfilenames`` + ``trim_file_name`` are
        # already configured, but we never trust that blindly.
        title = sanitize_filename(str(info.get("title") or info.get("id") or "download"))

        filepath = _final_filepath(info)
        if filepath is None or not filepath.exists():
            # Fall back to scanning the download directory for the newest
            # matching file — this happens rarely and keeps the worker moving.
            candidates = sorted(
                _DOWNLOAD_DIR.glob("*"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            filepath = next((c for c in candidates if c.is_file()), None)

        if filepath is None or not filepath.exists():
            return err(
                ErrorCode.DOWNLOAD_FAILED,
                "Download completed but output file could not be located.",
                details={"url": safe_url, "quality": quality},
            )

        filesize = filepath.stat().st_size
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        log.info(
            "download.ok",
            correlation_id=correlation_id,
            url=safe_url,
            quality=quality,
            filepath=str(filepath),
            filesize=filesize,
            elapsed_ms=elapsed_ms,
            title=title,
        )
        return ok(
            {
                "filepath": str(filepath),
                "filesize": filesize,
                "title": title,
                "duration": info.get("duration"),
                "extractor": info.get("extractor_key") or info.get("extractor"),
                "id": info.get("id"),
            }
        )

    except BaseException as exc:  # noqa: BLE001 — boundary
        log.warning(
            "download.failed",
            correlation_id=correlation_id,
            url=safe_url,
            quality=quality,
            error=f"{type(exc).__name__}: {exc}",
        )
        return from_exception(
            exc,
            default_code=ErrorCode.DOWNLOAD_FAILED,
            context={"url": safe_url, "quality": quality},
        )
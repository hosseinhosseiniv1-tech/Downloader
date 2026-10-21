"""Metadata extraction via yt-dlp.

Used by:
- The bot (to show a preview card and quality buttons).
- The public ``POST /identify`` endpoint.

Hard rules:
- Never raise for expected failures — always return a ``Result``.
- Enforce an overall wall-clock timeout (default 30 s).
- Do not download any media.
"""

from __future__ import annotations

import os
import time
from typing import Any

from .errors import ErrorCode, Result, err, from_exception, ok
from .logging import get_logger, new_correlation_id
from .validation import validate_url
from .ydl_opts import _build_ydl_opts

log = get_logger("download_core.info")

_DEFAULT_TIMEOUT_SECONDS = 30.0


def _extract_info(url: str, opts: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Run yt-dlp's ``extract_info`` with a wall-clock timeout.

    yt-dlp itself doesn't take an overall timeout, so we run it in a thread
    and join with a deadline. If the deadline passes we abandon the thread
    (yt-dlp's socket_timeout will eventually let it exit) and raise.
    """
    import threading

    result_box: dict[str, Any] = {}
    error_box: dict[str, BaseException] = {}

    def _run() -> None:
        try:
            import yt_dlp  # type: ignore

            with yt_dlp.YoutubeDL(opts) as ydl:
                result_box["info"] = ydl.extract_info(url, download=False)
        except BaseException as exc:  # noqa: BLE001 — captured and re-raised below
            error_box["exc"] = exc

    thread = threading.Thread(target=_run, name="ydl-extract", daemon=True)
    thread.start()
    thread.join(timeout_s)

    if thread.is_alive():
        raise TimeoutError(f"Metadata extraction exceeded {timeout_s:.0f}s")

    if "exc" in error_box:
        raise error_box["exc"]

    info = result_box.get("info")
    if not isinstance(info, dict):
        raise RuntimeError("yt-dlp returned no info dict")
    return info


def _pick_metadata(info: dict[str, Any]) -> dict[str, Any]:
    """Reduce yt-dlp's large info dict to the subset the bot/API need."""
    formats = info.get("formats") or []
    heights = sorted(
        {int(f["height"]) for f in formats if isinstance(f, dict) and f.get("height")},
        reverse=True,
    )
    available_qualities = []
    if any(h >= 1080 for h in heights):
        available_qualities.append("1080p")
    if any(h >= 720 for h in heights):
        available_qualities.append("720p")
    if any(h >= 480 for h in heights):
        available_qualities.append("480p")
    available_qualities.insert(0, "best")
    if info.get("acodec") not in (None, "none") or any(
        f.get("acodec") not in (None, "none") for f in formats if isinstance(f, dict)
    ):
        available_qualities.append("audio")

    duration = info.get("duration")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    return {
        "id": str(info.get("id") or ""),
        "title": str(info.get("title") or "Untitled"),
        "description": (info.get("description") or "")[:500],
        "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        "duration_seconds": duration,
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or info.get("original_url"),
        "extractor": info.get("extractor_key") or info.get("extractor"),
        "view_count": info.get("view_count"),
        "is_live": bool(info.get("is_live")),
        "available_qualities": available_qualities,
        "max_height": heights[0] if heights else None,
        "filesize_approx": info.get("filesize_approx"),
    }


def get_video_info(url: str, *, proxy: str | None = None, timeout_s: float | None = None) -> Result:
    """Extract metadata for ``url`` without downloading.

    Always returns a ``Result``; never raises for expected failures.
    """
    correlation_id = new_correlation_id("meta")
    started_at = time.monotonic()

    validation = validate_url(url)
    if not validation["ok"]:
        log.warning(
            "metadata.invalid_url",
            correlation_id=correlation_id,
            url=url,
            error_code=validation["error_code"],
        )
        return validation  # already a ResultErr

    safe_url: str = validation["data"]["url"]
    timeout_s = timeout_s or float(os.environ.get("METADATA_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS))

    try:
        opts = _build_ydl_opts(quality="best", mode="metadata", proxy=proxy)
        info = _extract_info(safe_url, opts, timeout_s)
        metadata = _pick_metadata(info)

        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        log.info(
            "metadata.ok",
            correlation_id=correlation_id,
            url=safe_url,
            extractor=metadata.get("extractor"),
            duration_seconds=metadata.get("duration_seconds"),
            elapsed_ms=elapsed_ms,
        )
        return ok(metadata)

    except TimeoutError as exc:
        log.warning("metadata.timeout", correlation_id=correlation_id, url=safe_url, error=str(exc))
        return err(ErrorCode.METADATA_TIMEOUT, "Metadata extraction timed out. Please try again.")
    except BaseException as exc:  # noqa: BLE001 — deliberately broad at the boundary
        log.warning(
            "metadata.failed",
            correlation_id=correlation_id,
            url=safe_url,
            error=f"{type(exc).__name__}: {exc}",
        )
        return from_exception(exc, default_code=ErrorCode.METADATA_FAILED, context={"url": safe_url})
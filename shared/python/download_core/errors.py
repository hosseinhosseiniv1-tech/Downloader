"""Structured result types and error codes for download_core.

All public functions return a ``Result`` — a ``TypedDict``-compatible dict
with ``ok`` either True (with a ``data`` payload) or False (with a code and
human message). Callers never need to catch exceptions for expected failure
modes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict


class ErrorCode(StrEnum):
    """Stable error codes for programmatic handling and analytics."""

    # Input / validation
    INVALID_URL = "invalid_url"
    UNSAFE_URL = "unsafe_url"
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    DNS_LOOKUP_FAILED = "dns_lookup_failed"

    # Metadata
    METADATA_TIMEOUT = "metadata_timeout"
    METADATA_FAILED = "metadata_failed"
    UNSUPPORTED_SITE = "unsupported_site"
    VIDEO_UNAVAILABLE = "video_unavailable"
    VIDEO_PRIVATE = "video_private"
    VIDEO_GEO_BLOCKED = "video_geo_blocked"
    VIDEO_AGE_RESTRICTED = "video_age_restricted"

    # Download
    DOWNLOAD_TIMEOUT = "download_timeout"
    DOWNLOAD_FAILED = "download_failed"
    DOWNLOAD_INTERRUPTED = "download_interrupted"
    FORMAT_NOT_AVAILABLE = "format_not_available"
    FILESYSTEM_ERROR = "filesystem_error"

    # Upload (worker-only, exported for symmetry)
    UPLOAD_FAILED = "upload_failed"
    UPLOAD_TOO_LARGE = "upload_too_large"

    # Catch-all
    UNKNOWN = "unknown"


class ResultOk(TypedDict):
    ok: bool  # always True
    data: dict[str, Any]


class ResultErr(TypedDict):
    ok: bool  # always False
    error_code: str
    error_message: str
    error_details: dict[str, Any] | None


Result = ResultOk | ResultErr


def ok(data: dict[str, Any] | None = None) -> ResultOk:
    """Construct a success result."""
    return {"ok": True, "data": data or {}}


def err(
    code: ErrorCode | str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> ResultErr:
    """Construct a failure result. Never raises."""
    return {
        "ok": False,
        "error_code": str(code),
        "error_message": str(message),
        "error_details": details,
    }


def from_exception(
    exc: BaseException,
    *,
    default_code: ErrorCode = ErrorCode.UNKNOWN,
    context: dict[str, Any] | None = None,
) -> ResultErr:
    """Convert an arbitrary exception into a structured error result.

    Well-known yt-dlp error classes are mapped to the right ErrorCode so
    callers can reason about failures without string-parsing messages.
    """
    code: ErrorCode = default_code
    message = f"{type(exc).__name__}: {exc}"

    # Lazy import — yt-dlp may be absent in some contexts.
    try:
        from yt_dlp.utils import (  # type: ignore
            DownloadError,
            ExtractorError,
            GeoRestrictedError,
            UnsupportedError,
        )
    except Exception:  # pragma: no cover
        DownloadError = ExtractorError = GeoRestrictedError = UnsupportedError = ()  # type: ignore

    if isinstance(exc, GeoRestrictedError):  # type: ignore[arg-type]
        code = ErrorCode.VIDEO_GEO_BLOCKED
    elif isinstance(exc, UnsupportedError):  # type: ignore[arg-type]
        code = ErrorCode.UNSUPPORTED_SITE
    elif isinstance(exc, ExtractorError):  # type: ignore[arg-type]
        lowered = str(exc).lower()
        if "private" in lowered:
            code = ErrorCode.VIDEO_PRIVATE
        elif "age" in lowered and "restrict" in lowered:
            code = ErrorCode.VIDEO_AGE_RESTRICTED
        elif "unavailable" in lowered or "removed" in lowered:
            code = ErrorCode.VIDEO_UNAVAILABLE
        else:
            code = ErrorCode.METADATA_FAILED
    elif isinstance(exc, DownloadError):  # type: ignore[arg-type]
        lowered = str(exc).lower()
        if "timed out" in lowered or "timeout" in lowered:
            code = ErrorCode.DOWNLOAD_TIMEOUT
        else:
            code = ErrorCode.DOWNLOAD_FAILED

    return err(code, message, details=context)
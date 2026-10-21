"""
download_core — shared download logic for Super Downloader.

Public API:
    validate_url(url)                       -> Result
    sanitize_filename(name)                 -> str
    get_video_info(url, *, proxy=None)      -> Result
    download_video(url, quality, *, ...)    -> Result
    build_ydl_opts(quality, mode, *, ...)   -> dict
    Result, Ok, Err                         -> result helpers

Nothing in this module raises for *expected* failure modes. All expected
failures are returned as structured ``Result`` objects:
    {"ok": True,  "data": {...}}
    {"ok": False, "error_code": "...", "error_message": "..."}
"""

from __future__ import annotations

from .download import download_video
from .errors import ErrorCode, Result, ok, err, from_exception
from .info import get_video_info
from .logging import configure_logging, get_logger, new_correlation_id
from .validation import is_safe_url, sanitize_filename, validate_url
from .ydl_opts import build_ydl_opts, _build_ydl_opts

__all__ = [
    # Core results
    "Result",
    "ErrorCode",
    "ok",
    "err",
    "from_exception",
    # Public functions
    "validate_url",
    "is_safe_url",
    "sanitize_filename",
    "get_video_info",
    "download_video",
    "build_ydl_opts",
    "_build_ydl_opts",
    # Logging
    "configure_logging",
    "get_logger",
    "new_correlation_id",
]

__version__ = "0.1.0"
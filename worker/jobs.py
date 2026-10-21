"""Job functions executed by the RQ worker.

The core job is :func:`process_download`, which:
1. Emits a ``started`` progress message.
2. Calls ``download_core.download_video`` with a progress hook throttled to
   one update per 12 s.
3. Uploads the file to Telegram via the local Bot API server using an
   ``aiohttp`` client with ``total=None`` (no timeout on huge uploads).
4. On ``RequestEntityTooLarge``: sets status ``failed_upload_limit``, logs
   ``upload_failures`` metric, sends the *specific* 2 GB message, and does
   NOT truncate the file.
5. Deletes the file in a ``finally`` block, unconditionally.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import aiohttp

from download_core.download import download_video
from download_core.errors import ErrorCode
from download_core.logging import get_logger, new_correlation_id

log = get_logger("worker.jobs")

# Do NOT pre-reject by size. The local Bot API server enforces the real limit.
# This constant is only used for error detection thresholds and analytics.
HARD_TELEGRAM_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
PROGRESS_INTERVAL_SECONDS = 12.0


# ---------------------------------------------------------------------------
# Redis helpers (imported lazily to keep test imports cheap)
# ---------------------------------------------------------------------------

def _redis():
    from redis import Redis

    url = (
        os.environ.get("REDIS_PRIVATE_URL")
        or os.environ.get("REDIS_URL")
        or "redis://localhost:6379/0"
    )
    return Redis.from_url(url, socket_timeout=10, decode_responses=True)


def _set_job_status(job_id: str, status: str, **extra: Any) -> None:
    r = _redis()
    key = f"job:{job_id}"
    payload = {"status": status, "updated_at": str(int(time.time())), **extra}
    try:
        r.hset(key, mapping=payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("job.status_write_failed", job_id=job_id, error=str(exc))


def _incr_metric(name: str, amount: int = 1) -> None:
    r = _redis()
    try:
        r.hincrby("stats:global", name, amount)
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics.incr_failed", metric=name, error=str(exc))


def _telegram_api_base() -> str:
    return (os.environ.get("LOCAL_BOT_API_URL") or "http://local-bot-api.railway.internal:8081").rstrip("/")


def _telegram_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return token


# ---------------------------------------------------------------------------
# Progress handling
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Throttled progress message editor.

    Uses the *local* Bot API directly (not aiogram) so it works even if the
    bot process is offline. Edits the existing message every ~12 s.
    """

    def __init__(self, job_id: str, chat_id: int, message_id: int):
        self.job_id = job_id
        self.chat_id = chat_id
        self.message_id = message_id
        self._last_emit = 0.0
        self._last_bytes = 0
        self._started = time.monotonic()

    def _render(self, data: dict[str, Any]) -> str:
        status = data.get("status", "downloading")
        if status == "downloading":
            downloaded = int(data.get("downloaded_bytes") or 0)
            total = int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
            if total > 0:
                pct = min(100.0, downloaded / total * 100.0)
                filled = int(pct / 100 * 20)
                bar = "█" * filled + "░" * (20 - filled)
                mb_done = downloaded / 1024 / 1024
                mb_total = total / 1024 / 1024
                speed = float(data.get("speed") or 0) / 1024 / 1024
                eta = data.get("eta") or 0
                return (
                    "⬇️ <b>Downloading</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"<code>{bar}</code> {pct:5.1f}%\n"
                    f"{mb_done:,.1f} / {mb_total:,.1f} MB\n"
                    f"⚡ {speed:,.1f} MB/s   ⏱ {eta}s"
                )
            return (
                "⬇️ <b>Downloading</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"{downloaded / 1024 / 1024:,.1f} MB"
            )
        if status == "finished":
            return (
                "✅ <b>Download complete</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Preparing upload…"
            )
        if status == "uploading":
            sent = int(data.get("sent_bytes") or 0)
            total = int(data.get("total_bytes") or 0)
            pct = (sent / total * 100.0) if total else 0.0
            return (
                "⬆️ <b>Uploading</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"{sent / 1024 / 1024:,.1f} / {total / 1024 / 1024:,.1f} MB "
                f"({pct:5.1f}%)"
            )
        return f"ℹ️ <b>Status</b>: {status}"

    async def maybe_edit(self, session: aiohttp.ClientSession, data: dict[str, Any], *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_emit) < PROGRESS_INTERVAL_SECONDS:
            return
        self._last_emit = now
        text = self._render(data)
        url = f"{_telegram_api_base()}/bot{_telegram_bot_token()}/editMessageText"
        payload = {
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    log.warning(
                        "progress.edit_failed",
                        job_id=self.job_id,
                        status=resp.status,
                        body=body[:200],
                    )
        except Exception as exc:  # noqa: BLE001
            log.warning("progress.edit_exception", job_id=self.job_id, error=str(exc))


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class UploadTooLarge(Exception):
    """Raised when the Bot API rejects the upload as too large."""


class UploadFailed(Exception):
    """Raised for all other upload failures."""


async def _upload_file(
    session: aiohttp.ClientSession,
    *,
    job_id: str,
    chat_id: int,
    filepath: Path,
    quality: str,
    title: str,
    reporter: ProgressReporter,
) -> dict[str, Any]:
    """Upload via the local Bot API server.

    Uses a *timeoutless* session (``total=None``) because the documented
    failure mode for 1.5 GB+ uploads is client-side timeouts. The server
    enforces the real 2 GB limit and returns 413 ``RequestEntityTooLarge``,
    which we translate into :class:`UploadTooLarge`.
    """
    token = _telegram_bot_token()
    filesize = filepath.stat().st_size

    if quality == "audio":
        method = "sendAudio"
        field = "audio"
        extra: dict[str, Any] = {"title": title[:64]}
    else:
        method = "sendVideo"
        field = "video"
        extra = {"caption": f"🎬 {title[:1000]}", "supports_streaming": "true"}

    url = f"{_telegram_api_base()}/bot{token}/{method}"

    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    for k, v in extra.items():
        form.add_field(k, v)

    # Stream the file so memory usage stays constant for 2 GB files.
    async def _file_iter():
        sent = 0
        last_emit = 0.0
        with filepath.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                sent += len(chunk)
                now = time.monotonic()
                if now - last_emit >= PROGRESS_INTERVAL_SECONDS:
                    last_emit = now
                    await reporter.maybe_edit(
                        session,
                        {"status": "uploading", "sent_bytes": sent, "total_bytes": filesize},
                        force=True,
                    )
                yield chunk

    form.add_field(
        field,
        _file_iter(),
        filename=filepath.name,
        content_type="application/octet-stream",
    )

    log.info(
        "upload.start",
        job_id=job_id,
        chat_id=chat_id,
        filesize=filesize,
        quality=quality,
        method=method,
    )

    async with session.post(url, data=form) as resp:
        body = await resp.text()
        if resp.status == 413 or "RequestEntityTooLarge" in body or "too large" in body.lower():
            log.warning(
                "upload.too_large",
                job_id=job_id,
                filesize=filesize,
                status=resp.status,
                body=body[:300],
            )
            raise UploadTooLarge(body[:500])
        if resp.status >= 400:
            log.warning(
                "upload.http_error",
                job_id=job_id,
                status=resp.status,
                body=body[:500],
            )
            raise UploadFailed(f"HTTP {resp.status}: {body[:300]}")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise UploadFailed(f"Invalid JSON from Bot API: {exc}") from exc
        if not data.get("ok"):
            description = data.get("description") or "unknown Bot API error"
            if "too large" in description.lower() or "RequestEntityTooLarge" in description:
                raise UploadTooLarge(description)
            raise UploadFailed(description)
        return data["result"]


# ---------------------------------------------------------------------------
# The RQ job
# ---------------------------------------------------------------------------

def process_download(
    job_id: str,
    chat_id: int,
    url: str,
    quality: str,
    *,
    status_message_id: int | None = None,
    proxy: str | None = None,
) -> dict[str, Any]:
    """RQ entry point. Must never raise for expected failures."""
    configure_job_logging(job_id)
    return asyncio.run(
        _process_download_async(
            job_id=job_id,
            chat_id=chat_id,
            url=url,
            quality=quality,
            status_message_id=status_message_id,
            proxy=proxy,
        )
    )


def configure_job_logging(job_id: str) -> None:  # noqa: D401
    """Attach a correlation ID to the worker's structured logs."""
    import logging

    logger = logging.getLogger("worker.jobs")
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    # Correlation ID is passed explicitly to each log call; nothing to do here
    # besides ensuring the global config is applied.
    from download_core.logging import configure_logging

    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))


async def _process_download_async(
    *,
    job_id: str,
    chat_id: int,
    url: str,
    quality: str,
    status_message_id: int | None,
    proxy: str | None,
) -> dict[str, Any]:
    started = time.monotonic()
    filepath: Path | None = None
    title = "download"
    outcome = "failed"
    error_message: str | None = None

    _set_job_status(job_id, "downloading")
    _incr_metric("jobs_started")

    reporter: ProgressReporter | None = None
    upload_session: aiohttp.ClientSession | None = None

    try:
        upload_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=None,          # critical for 1.5 GB+ uploads
                connect=30,
                sock_read=None,
            )
        )

        if status_message_id:
            reporter = ProgressReporter(job_id=job_id, chat_id=chat_id, message_id=status_message_id)

        # ---- Download phase -------------------------------------------------
        def _hook(d: dict[str, Any]) -> None:
            if d.get("status") in {"downloading", "finished"} and reporter and upload_session:
                # Fire-and-forget: yt-dlp's hook is sync.
                try:
                    asyncio.get_running_loop().create_task(
                        reporter.maybe_edit(upload_session, d)
                    )
                except RuntimeError:
                    pass

        dl_result = download_video(url, quality=quality, proxy=proxy, progress_hooks=[_hook])
        if not dl_result["ok"]:
            outcome = dl_result["error_code"]
            error_message = dl_result["error_message"]
            _set_job_status(job_id, "failed", error_code=outcome, error_message=error_message)
            _incr_metric("jobs_failed")
            await _send_error(upload_session, chat_id, status_message_id, error_message)
            log.warning(
                "job.download_failed",
                job_id=job_id,
                url=url,
                quality=quality,
                outcome=outcome,
                error_message=error_message,
            )
            return {"ok": False, "error_code": outcome, "error_message": error_message}

        data = dl_result["data"]
        filepath = Path(data["filepath"])
        title = data.get("title") or filepath.stem
        filesize = data.get("filesize") or 0
        _set_job_status(job_id, "uploading", filepath=str(filepath), filesize=filesize)
        if reporter:
            await reporter.maybe_edit(
                upload_session, {"status": "finished"}, force=True
            )

        # ---- Upload phase ---------------------------------------------------
        try:
            result = await _upload_file(
                upload_session,
                job_id=job_id,
                chat_id=chat_id,
                filepath=filepath,
                quality=quality,
                title=title,
                reporter=reporter,  # type: ignore[arg-type]
            )
        except UploadTooLarge as exc:
            outcome = "failed_upload_limit"
            error_message = "File exceeds Telegram's 2 GB limit"
            _set_job_status(
                job_id,
                outcome,
                error_code="upload_too_large",
                error_message=error_message,
                filesize=filesize,
            )
            _incr_metric("upload_failures")
            _incr_metric("jobs_failed")
            await _send_error(upload_session, chat_id, status_message_id, error_message)
            log.warning(
                "job.upload_too_large",
                job_id=job_id,
                url=url,
                quality=quality,
                filesize=filesize,
                outcome=outcome,
                error_message=str(exc),
            )
            return {
                "ok": False,
                "error_code": "upload_too_large",
                "error_message": error_message,
            }
        except UploadFailed as exc:
            outcome = "failed_upload"
            error_message = f"Upload failed: {exc}"
            _set_job_status(
                job_id,
                "failed",
                error_code="upload_failed",
                error_message=str(exc),
            )
            _incr_metric("jobs_failed")
            await _send_error(upload_session, chat_id, status_message_id, error_message)
            log.warning(
                "job.upload_failed",
                job_id=job_id,
                url=url,
                quality=quality,
                outcome=outcome,
                error_message=str(exc),
            )
            return {"ok": False, "error_code": "upload_failed", "error_message": error_message}

        # ---- Success --------------------------------------------------------
        outcome = "completed"
        _set_job_status(
            job_id,
            "completed",
            telegram_message_id=str(result.get("message_id")),
            filesize=filesize,
        )
        _incr_metric("jobs_completed")
        _incr_metric("bytes_downloaded", filesize)

        if status_message_id and upload_session:
            await _edit_final_success(upload_session, chat_id, status_message_id, title)

        duration_ms = int((time.monotonic() - started) * 1000)
        log.info(
            "job.completed",
            job_id=job_id,
            url=url,
            quality=quality,
            bytes_downloaded=filesize,
            duration_ms=duration_ms,
            outcome=outcome,
        )
        return {"ok": True, "data": {"telegram_message_id": result.get("message_id")}}

    except BaseException as exc:  # noqa: BLE001 — boundary
        outcome = "failed_unexpected"
        error_message = f"{type(exc).__name__}: {exc}"
        _set_job_status(job_id, "failed", error_code="unknown", error_message=error_message)
        _incr_metric("jobs_failed")
        log.exception(
            "job.unexpected_error",
            job_id=job_id,
            url=url,
            quality=quality,
            outcome=outcome,
            error_message=error_message,
        )
        if upload_session and status_message_id:
            await _send_error(
                upload_session,
                chat_id,
                status_message_id,
                "Something went wrong. Please try again later.",
            )
        return {"ok": False, "error_code": "unknown", "error_message": error_message}

    finally:
        # Unconditional cleanup — even if the upload succeeded, the file is no
        # longer needed once it lives on Telegram's CDN.
        if filepath is not None and filepath.exists():
            try:
                filepath.unlink()
                log.info("job.file_deleted", job_id=job_id, filepath=str(filepath))
            except OSError as exc:
                log.warning(
                    "job.file_delete_failed",
                    job_id=job_id,
                    filepath=str(filepath),
                    error=str(exc),
                )
        if upload_session is not None:
            await upload_session.close()


# ---------------------------------------------------------------------------
# User-facing message helpers
# ---------------------------------------------------------------------------

async def _send_error(
    session: aiohttp.ClientSession | None,
    chat_id: int,
    status_message_id: int | None,
    message: str,
) -> None:
    if session is None:
        return
    token = _telegram_bot_token()
    text = (
        "❌ <b>Download failed</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}"
    )
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if status_message_id:
        payload["message_id"] = status_message_id
        method = "editMessageText"
    else:
        method = "sendMessage"
    url = f"{_telegram_api_base()}/bot{token}/{method}"
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status >= 400:
                log.warning("notify.failed", status=resp.status)
    except Exception as exc:  # noqa: BLE001
        log.warning("notify.exception", error=str(exc))


async def _edit_final_success(
    session: aiohttp.ClientSession,
    chat_id: int,
    message_id: int,
    title: str,
) -> None:
    token = _telegram_bot_token()
    text = (
        "✅ <b>Done!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{title[:200]}</b>\n\n"
        "Enjoy your file 🎉"
    )
    url = f"{_telegram_api_base()}/bot{token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        async with session.post(url, json=payload) as resp:
            if resp.status >= 400:
                log.warning("final_success.edit_failed", status=resp.status)
    except Exception as exc:  # noqa: BLE001
        log.warning("final_success.exception", error=str(exc))


# ---------------------------------------------------------------------------
# Cleanup job
# ---------------------------------------------------------------------------

def cleanup_old_files(max_age_seconds: int = 2 * 60 * 60) -> dict[str, int]:
    """Delete files in DOWNLOAD_DIR older than ``max_age_seconds``.

    Scheduled every 15 minutes by ``worker.main``. Returns a small report.
    """
    download_dir = Path(os.environ.get("DOWNLOAD_DIR", "/tmp/downloads"))
    deleted = 0
    bytes_freed = 0
    now = time.time()
    if not download_dir.exists():
        return {"deleted": 0, "bytes_freed": 0}

    for path in download_dir.iterdir():
        if not path.is_file():
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age > max_age_seconds:
            try:
                size = path.stat().st_size
                path.unlink()
                deleted += 1
                bytes_freed += size
            except OSError as exc:
                log.warning("cleanup.unlink_failed", path=str(path), error=str(exc))

    log.info("cleanup.done", deleted=deleted, bytes_freed=bytes_freed)
    return {"deleted": deleted, "bytes_freed": bytes_freed}
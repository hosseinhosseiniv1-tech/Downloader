# Super Downloader — Worker

RQ worker that executes `process_download` jobs from the `downloads` queue.

## Job contract

`process_download(job_id, chat_id, url, quality, status_message_id=None, proxy=None)`

Returns:
- `{"ok": True, "data": {"telegram_message_id": ...}}`
- `{"ok": False, "error_code": "...", "error_message": "..."}`

## Upload policy

**No pre-emptive 50 MB rejection.** The local Bot API server enforces the
real limit (2 GB for bots). On `RequestEntityTooLarge` we:

1. Log `upload_failures` metric via `stats:global` hash.
2. Set Redis `job:{id}.status = "failed_upload_limit"`.
3. Edit the user's status message with **"File exceeds Telegram's 2 GB limit"**.
4. Delete the file in `finally` — regardless of outcome.

The aiohttp upload session uses `total=None` so 1.5 GB+ uploads don't hit
client-side timeouts.

## Cleanup

`worker.main` spawns a thread that enqueues `cleanup_old_files` every 15
minutes; the job deletes any file under `DOWNLOAD_DIR` older than 2 hours.

## Local run

```bash
cd worker
pip install -r requirements-dev.txt
export REDIS_URL=redis://localhost:6379/0
export TELEGRAM_BOT_TOKEN=...
export LOCAL_BOT_API_URL=http://localhost:8081
python -m worker.main
text

---

**Checklist — delivered in this message:**
- [x] `worker/requirements.txt`, `worker/requirements-dev.txt`
- [x] `worker/Dockerfile.worker`
- [x] `worker/main.py` (startup Redis PING, heartbeat, cleanup scheduler)
- [x] `worker/jobs.py` (`process_download`, `UploadTooLarge`, upload via local Bot API with `total=None`, `failed_upload_limit`, `finally` delete, cleanup job)
- [x] `worker/tests/test_jobs.py`, `worker/tests/__init__.py`
- [x] `worker/pyproject.toml`, `worker/README.md`
- [x] `shared/python/requirements.txt`

**Next message:** `bot/` — aiogram 3.x with RedisStorage FSM, GNU gettext i18n (en/fa with RTL), SSRF-safe URL handling, yt-dlp metadata via `download_core`, quality buttons, RQ enqueue with 60-min TTL, per-user rate limiting (2 concurrent), deep linking (`/start get_<payload>`, `/share`), `/health` aiohttp endpoint, startup Redis PING + exit(1), global error handler, `AiohttpSession(api=TelegramAPIServer.from_base(..., is_local=True))`, and SOCKS5 via `aiohttp-socks`.

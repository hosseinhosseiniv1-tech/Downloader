# Super Downloader

A production-grade, polyglot Telegram video downloader platform deployed on
Railway. Accepts public video URLs via bot (aiogram) or web, downloads with
yt-dlp + FFmpeg, and uploads to Telegram through the **local** Bot API server
(2 GB limit instead of the SaaS 50 MB).

```
                                      ┌────────────────────────┐
                                      │     Telegram users     │
                                      └────────────┬───────────┘
                                                   │
        ┌────────────────────────────────────┐     │     ┌──────────────────────────────┐
        │  bot  (Python / aiogram 3)         │◀────┼────▶│ local-bot-api (tdlib)        │
        │  - RedisStorage FSM                │     │     │  TELEGRAM_LOCAL=true         │
        │  - GNU gettext (en, fa/RTL)        │     │     │  volume: /var/lib/...        │
        │  - SSRF-safe URL validation        │     │     │  internal port 8081          │
        │  - RQ enqueue + rate limit         │     │     └──────────────────────────────┘
        │  - deep linking /share             │     │
        │  - /health                         │     │
        └──────────────┬─────────────────────┘     │
                       │ RQ job                    │
                       ▼                           │
        ┌────────────────────────────────────┐     │     ┌──────────────────────────────┐
        │  worker (Python / RQ + yt-dlp)     │◀────┼────▶│ api (Go / Gin)               │
        │  - downloads → /tmp/downloads      │     │     │  /api/v1/*                   │
        │  - 2 GB upload via local Bot API   │     │     │  admin bearer auth           │
        │  - progress hooks (12 s)           │     │     │  IP token bucket             │
        │  - cleanup every 15 min            │     │     │  Prometheus /metrics         │
        │  - heartbeat every 60 s            │     │     └──────────────┬───────────────┘
        └──────────────┬─────────────────────┘     │                    │
                       │                            │                    │
                       ▼                            │                    ▼
        ┌────────────────────────────────────┐     │     ┌──────────────────────────────┐
        │ pot-provider (bgutil)              │◀────┼────▶│ web (React + Vite)           │
        │  :4416  (PO token for YouTube)     │     │     │  Landing + admin dashboard   │
        └────────────────────────────────────┘     │     │  i18next (en/fa, RTL)        │
                                                   │     └──────────────────────────────┘
        ┌────────────────────────────────────┐     │
        │ xray (VLESS → SOCKS5)              │◀────┘
        │  :10808  (bypass DC blocks)        │
        └────────────────────────────────────┘

        ┌────────────────────────────────────────────────────────────────────┐
        │ redis  (AOF, persistent volume)                                    │
        │  namespaces: fsm:*, rq:*, rate:*, stats:*, ban:*, job:*            │
        └────────────────────────────────────────────────────────────────────┘
```

## Repository layout

```
.
├── shared/python/         download_core — SSRF guard, yt-dlp opts, metadata, download
├── bot/                   aiogram 3, FSM, i18n, deep linking, RQ enqueue
├── worker/                RQ worker, upload via local Bot API, cleanup loop
├── api/                   Gin admin + public API, Prometheus, IP rate limit
├── web/                   React + Vite + TypeScript frontend
├── xray/                  VLESS → SOCKS5 bridge
├── pot-provider/          bgutil-ytdlp-pot-provider wrapper
├── local-bot-api/         Official Telegram Bot API server (tdlib)
├── redis/                 redis.conf (AOF) for the Railway Redis volume
├── docker-compose.yml     Local dev stack
├── railway.*.json         Railway service manifests
├── .env.example           Every environment variable, documented
└── .github/workflows/ci.yml  Matrix CI (Python, Go, Node)
```

---

## Railway deployment guide

### 0. Prerequisites

- A Railway project with a **private network** (default for new projects).
- A Telegram bot token from **@BotFather**.
- Telegram `api_id` / `api_hash` from **https://my.telegram.org/apps**.
- A VLESS URI for the Xray proxy (a default public share link is provided
  but **replace it** in production).

### 1. Redis service

1. Railway → **New → Database → Redis**.
2. Attach a **persistent volume** at `/data` (100 MB is plenty).
3. Copy the auto-generated `REDIS_PRIVATE_URL` — every other service
   references it.
4. (Optional) Override the config by mounting `redis/redis.conf` at
   `/usr/local/etc/redis/redis.conf`. The default Railway Redis already
   enables RDB; AOF must be enabled explicitly with:
   ```
   appendonly yes
   appendfsync everysec
   ```

### 2. Local Bot API service

1. **New → GitHub Repo** → this repo → set **Dockerfile Path** to
   `local-bot-api/Dockerfile.localbotapi`.
2. **Variables**:
   ```
   TELEGRAM_API_ID=<from my.telegram.org>
   TELEGRAM_API_HASH=<from my.telegram.org>
   TELEGRAM_LOCAL=true
   ```
3. Attach a **volume** at `/var/lib/telegram-bot-api`.
4. Note the **internal** URL — Railway gives
   `local-bot-api.railway.internal:8081`.
5. Do **not** add a public domain (uploads flow through private network).

### 3. POT provider service

1. **New → GitHub Repo** → **Dockerfile Path** = `pot-provider/Dockerfile.pot`.
2. No variables needed.
3. Internal URL: `pot-provider.railway.internal:4416`.

### 4. Xray service

1. **New → GitHub Repo** → **Dockerfile Path** = `xray/Dockerfile.xray`.
2. **Variables**:
   ```
   VLESS_PROXY_URL=<your vless URI>
   ```
3. Internal URL: `xray.railway.internal:10808` (SOCKS5).
4. No public domain.

### 5. Worker service

1. **New → GitHub Repo** → **Dockerfile Path** = `worker/Dockerfile.worker`.
2. **Variables**:
   ```
   REDIS_PRIVATE_URL=${{Redis.REDIS_PRIVATE_URL}}
   LOCAL_BOT_API_URL=http://local-bot-api.railway.internal:8081
   TELEGRAM_BOT_TOKEN=<bot token>
   POT_SERVER_URL=http://pot-provider.railway.internal:4416
   PROXY_URL=socks5://xray.railway.internal:10808
   LOG_LEVEL=INFO
   ```
3. Attach a small volume at `/tmp/downloads` (optional; ephemeral is fine
   since the cleanup loop deletes files older than 2 h).

### 6. Bot service

1. **New → GitHub Repo** → **Dockerfile Path** = `bot/Dockerfile.bot`.
2. **Variables** (same as worker plus):
   ```
   BOT_USERNAME=StoaderBot
   ADMIN_API_KEY=<openssl rand -hex 32>
   HEALTH_PORT=8080
   ```
3. **Public domain**: optional. The bot uses long polling, so no inbound
   traffic is required. The `/health` endpoint is reachable internally at
   `bot.railway.internal:8080/health`.

### 7. API service

1. **New → GitHub Repo** → **Dockerfile Path** = `api/Dockerfile.api`.
2. **Variables**:
   ```
   ADMIN_API_KEY=<same value as bot>
   REDIS_PRIVATE_URL=${{Redis.REDIS_PRIVATE_URL}}
   LOCAL_BOT_API_URL=http://local-bot-api.railway.internal:8081
   METADATA_SERVICE_URL=http://bot.railway.internal:8080
   RATE_LIMIT_PER_MINUTE=60
   PORT=8080
   ```
3. **Public domain**: yes — the web frontend calls this directly from
   browsers.

### 8. Web service

1. **New → GitHub Repo** → **Dockerfile Path** = `web/Dockerfile.web`.
2. **Build-time args**:
   ```
   VITE_API_BASE=https://<api public domain>
   VITE_BOT_USERNAME=StoaderBot
   ```
3. **Public domain**: yes.

### 9. Verify

- Bot: `curl https://<bot>.railway.app/health` → `{"status":"ok","redis":true}`.
- API: `curl https://<api>/health` → `{"status":"ok","redis":true,"local_bot_api":true}`.
- Open the web app, paste a YouTube URL, verify metadata + quality grid.
- Watch worker logs: `job.completed` with `bytes_downloaded`.
- Upload a >50 MB file: should succeed (local Bot API 2 GB limit).
- Upload a >2 GB file: status becomes `failed_upload_limit` and the user
  sees **"File exceeds Telegram's 2 GB limit"**.

---

## Troubleshooting

### YouTube "Sign in to confirm you're not a bot"

Symptom: `ExtractorError: Sign in to confirm you're not a bot`.

Cause: YouTube blocks datacenter IPs unless a valid PO token is presented.

Fix checklist:

1. `POT_SERVER_URL` is set in **both** bot and worker, pointing at
   `http://pot-provider.railway.internal:4416`.
2. `bgutil-ytdlp-pot-provider` is **installed** in the image:
   `python -c "import bgutil_ytdlp_pot_provider"` must succeed. The plugin
   talks to the server; installing the server image alone is not enough.
3. `extractor_args.youtube.player_client = ["mweb","tv","web_safari"]` is
   present in the yt-dlp options (`download_core._build_ydl_opts`).
4. `PROXY_URL` is set — residential-ish egress is often required even with
   a valid PO token.
5. Try `COOKIES_FILE` with cookies exported from a real browser.

### Proxy issues

- **`localhost` vs private network**: inside Railway containers,
  `localhost` refers to the *same container*, not the host. Always use
  `*.railway.internal` hostnames. `socks5://localhost:10808` will fail;
  `socks5://xray.railway.internal:10808` will work.
- **`0.0.0.0` bind requirement**: Xray listens on `0.0.0.0:10808`. If you
  change it to `127.0.0.1`, other services cannot reach it through the
  private mesh.
- **`socks5` vs `socks5h`**: `socks5h` resolves DNS through the proxy. Use
  `socks5` inside Railway (the mesh handles internal DNS) and `socks5h`
  when the proxy must resolve the target hostname (e.g., on a laptop).
- **aiogram SOCKS5**: `AiohttpSession(proxy="socks5://...")` is the
  supported form. `aiohttp-socks` must be installed (it is, in the bot
  image).

### Redis connection errors

- Bot / worker / API all fail fast if Redis is unreachable at startup.
  Check Railway logs for `redis.unreachable` or `redis.unreachable_at_startup`.
- Verify `REDIS_PRIVATE_URL` is linked via Railway's reference syntax
  (`${{Redis.REDIS_PRIVATE_URL}}`), not a copy-pasted value.
- If the Redis service restarted, `REDIS_PRIVATE_URL` may have changed —
  re-link the reference.

### Local API server startup

- If `getMe` fails but the server is up, the bot logs a critical error but
  continues (the local API may be warming up).
- If the local API fails entirely, the bot falls back to the SaaS API —
  **uploads >50 MB will then fail**. Check `LOCAL_BOT_API_URL` and the
  `is_local=True` flag in `AiohttpSession`.
- Ensure the tdlib volume at `/var/lib/telegram-bot-api` is mounted;
  otherwise the server re-fetches from Telegram on every restart.

### Upload size errors (`RequestEntityTooLarge`)

- The 2 GB limit is a **hard Telegram limit** for bots. Files larger than
  that cannot be uploaded via the Bot API, even with the local server.
- When this happens the worker:
  - logs `job.upload_too_large` and increments `upload_failures`,
  - sets `job.status = failed_upload_limit`,
  - edits the user message with **"File exceeds Telegram's 2 GB limit"**,
  - deletes the file in `finally`.
- If a **smaller** file fails with `RequestEntityTooLarge`, the local API
  is not being used — check `LOCAL_BOT_API_URL` and `is_local=True`.

### Large-upload timeouts (1.5 GB+)

Symptom: `aiohttp.ClientTimeout` fires at ~5 minutes and the upload aborts.

Fix: the worker uses `aiohttp.ClientTimeout(total=None, connect=30,
sock_read=None)`. Verify the environment didn't override it. If the local
Bot API is on a slow disk, `sock_read=None` still lets it wait as long as
needed.

### `ApiIdPublishedFloodError`

Symptom: `ApiIdPublishedFloodError: The API access for bot users is
restricted for this API ID.`

Cause: the default test `api_id=2040` is a **public test credential** used
by thousands of bots. Telegram rate-limits it.

Fix: use your own `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` from
**https://my.telegram.org/apps**. Update both the `local-bot-api` service
and, if applicable, the bot service.

### i18n compilation errors

Symptom: missing translations or `msgfmt: command not found`.

Fix:

- `gettext` must be installed in the bot image (it is: `apt-get install
  gettext`).
- The Dockerfile compiles `.po` → `.mo` at build time. If you edit
  catalogs, rebuild the image.
- At runtime, if a `.mo` is missing, `gettext.translation(...,
  fallback=True)` returns English msgids — the bot never crashes, but
  Persian strings won't appear. Check the build log for `msgfmt` errors.

### Why the 50 MB limit was removed, and what the real limits are

The **SaaS Bot API** hard-caps uploads for bots at **50 MB**. The **local
Bot API server** (`TELEGRAM_LOCAL=true`) lifts this to **2000 MB (2 GB)**
per file for bot uploads. There is no way to upload a >2 GB file through
*any* Bot API server, because the underlying MTProto layer caps documents
at 2 GB.

- We **do not** pre-reject files >50 MB. The local server enforces the
  real 2 GB limit.
- We **do** pre-reject with a clear message when the *server* rejects a
  file with `RequestEntityTooLarge` — that message names the 2 GB limit
  explicitly and sets `job.status = failed_upload_limit`.

### Language choice justifications

- **Python** for bot + worker: aiogram is the most mature Telegram bot
  library, and yt-dlp is Python-native. Sharing `download_core` between
  bot and worker avoids drift in SSRF rules and yt-dlp options.
- **Go** for the API: stateless, low-memory, single-binary deployment.
  Gin gives us the middleware surface (auth, rate limit, correlation IDs)
  we need without ceremony. `promauto` metrics are one-liners.
- **React + Vite + TypeScript** for the web: TanStack Query and Recharts
  give us live polling and charts with minimal glue. Vite's dev server and
  build are fast enough that the frontend iterates alongside the backend.
- **Xray** as its own service: isolates the proxy from the worker so the
  worker image stays lean, and lets us swap the VLESS endpoint without
  rebuilding the worker.
- **Separate local Bot API service**: tdlib is heavy; keeping it out of
  the bot and worker images keeps those images small and fast to deploy.

---

## Development

```bash
git clone <repo>
cd <repo>
cp .env.example .env.local
# Fill TELEGRAM_BOT_TOKEN in .env.local
docker compose --env-file .env.local up --build
```

- Web: http://localhost:5173
- API: http://localhost:8080
- Local Bot API: http://localhost:8081
- Redis: redis://localhost:6379

Run the test suites:

```bash
# shared
pip install -e shared/python[dev] && pytest shared/python -q

# bot
pip install -r bot/requirements-dev.txt && pytest bot -q

# worker
pip install -r worker/requirements-dev.txt && pytest worker -q

# api
cd api && go test ./...

# web
cd web && npm ci && npm run test
```

## License

MIT
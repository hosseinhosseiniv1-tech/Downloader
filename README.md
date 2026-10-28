# FluxFetch | Universal Downloader

A single-file Telegram bot that downloads media from 1000+ sites (YouTube, TikTok, Instagram, X/Twitter, Reddit, Vimeo, SoundCloud, direct URLs…) and sends it right back in chat. Every file is deleted from the server immediately after delivery.

---

## ✨ Features

- 📥 **Universal**: powered by `yt-dlp` — works with 1000+ sites.
- 🎯 **Smart format**: prefers ≤1080p h264/mp4 for maximum Telegram compatibility.
- 🧹 **Auto-cleanup**: files deleted after every job + a Janitor task sweeps orphans every 10 min.
- 🔒 **Token redaction**: bot token scrubbed from *every* log line and traceback.
- ⚙️ **Per-user settings**: "send as file" and "spoiler by default".
- 🫣 **Spoiler toggle**: flip spoiler on/off on an already-sent photo/video via inline button.
- 🔄 **Retry button**: one tap to retry a failed download.
- 🚦 **Global concurrency gate**: max 3 heavy downloads at once (Railway-friendly).
- 💎 **Premium emoji**: opt-in, with a safe Unicode fallback.
- 📊 **/status**: uptime, queue depth, disk usage.

---

## 🚀 Deploy on Railway (recommended)

1. Push this repo to GitHub.
2. In Railway: **New Project → Deploy from GitHub repo**.
3. **Variables** → add:
   - `BOT_TOKEN` = your token from [@BotFather](https://t.me/BotFather)
   - `BOT_OWNER_HAS_PREMIUM` = `false` (unless you own Premium *and* have custom emoji IDs configured)
4. Railway auto-detects `Dockerfile` (via `railway.json`) and starts the bot.
5. Done — DM your bot and paste a link.

> ⚠️ Keep replicas at **1**. Two instances sharing one `BOT_TOKEN` will fight over updates (`409 Conflict`).

---

## 💻 Local development

```bash
git clone <this-repo>
cd fluxfetch

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
# ffmpeg is required for video+audio merging:
#   macOS:  brew install ffmpeg
#   Ubuntu: sudo apt install ffmpeg
#   Windows: https://ffmpeg.org/download.html

cp .env.example .env
# edit .env and set BOT_TOKEN

# load .env (bash) or use python-dotenv
export $(cat .env | grep -v '^#' | xargs)
python -u bot.py
```

---

## 🐳 Run with Docker locally

```bash
docker build -t fluxfetch .
docker run --rm -it \
  -e BOT_TOKEN="123456:ABC..." \
  -e BOT_OWNER_HAS_PREMIUM=false \
  fluxfetch
```

---

## 🧠 How it works

```
User paste link
   │
   ▼
extract_metadata  (yt-dlp, download=False)   ── rejects >50 MB early
   │
   ▼
_download         (semaphore: 3 max)          ── actual download + ffmpeg merge
   │
   ▼
size re-check     ── real file size is authoritative
   │
   ▼
send video / audio / photo / document         ── auto-fallback to document on BadRequest
   │
   ▼
cleanup_job        (finally)                   ── guarantees empty disk
```

- **Metadata first, download second** → never wastes bandwidth on files Telegram can't accept.
- **Re-check after download** → `yt-dlp`'s metadata size is often missing or approximate.
- **Job-prefixed filenames** → `cleanup_job()` can `glob(job_id*)` and remove `.part`, `.ytdl`, fragments, leftovers.
- **Janitor** → safety net for crashed/killed processes (30-min orphan sweep).

---

## ⚠️ Limits

- Cloud Bot API: **≤50 MB** uploads, **≤10 MB** photos. Bigger files get a metadata summary.
- To exceed 50 MB you'd need a self-hosted [Local Bot API Server](https://core.telegram.org/bots/api#using-a-local-bot-api-server) (up to 2000 MB). Not used here.
- Some sites (private accounts, geo-blocks, DRM) will fail — that's a `yt-dlp` limitation, not a bot bug. Use 🔄 Retry after a minute.

---

## 🔐 Security notes

- **Never commit `.env`.** `.gitignore` + `.dockerignore` both exclude it.
- **Never bake `BOT_TOKEN` into the image.** Pass it at runtime.
- The `TokenRedactionFilter` scrubs the token from logs, but treat Railway log access as sensitive anyway.
- The Docker image runs as **non-root** (`appuser`).

---

## 🩺 Troubleshooting

| Symptom | Cause | Fix |
|--------|-------|-----|
| `409 Conflict` | Two bot instances with same token | Set replicas = 1 |
| `ffmpeg not found` warning | ffmpeg missing | Use the provided Dockerfile |
| All downloads fail suddenly | `yt-dlp` outdated | `pip install -U yt-dlp` and redeploy |
| "This file is larger than 50 MB" | Cloud Bot API limit | Expected; use Local Bot API Server if you need more |
| Custom emoji rejected | `BOT_OWNER_HAS_PREMIUM=true` without valid IDs | Set to `false`, or fill real numeric IDs in `PREMIUM_EMOJI_IDS` |

---

## 📜 License

MIT — do whatever, just don't blame me if YouTube breaks it tomorrow.
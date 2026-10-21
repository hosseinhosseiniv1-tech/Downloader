# Super Downloader — POT Provider

Runs `brainicism/bgutil-ytdlp-pot-provider` — the server side of the
"Proof-of-Origin" (PO) token flow required by YouTube's bot-check.

## Why

Starting mid-2024, YouTube serves "Sign in to confirm you're not a bot" to
most datacenter IPs unless yt-dlp supplies a valid PO token. The
`bgutil-ytdlp-pot-provider` *Python plugin* (installed in the worker and
bot images) calls *this* server to mint tokens.

## Internal only

Exposed at `http://pot-provider.railway.internal:4416`. Do not attach a
public domain.

## Consumers
POT_SERVER_URL=http://pot-provider.railway.internal:4416

In `download_core._build_ydl_opts`, this becomes:

```python
"extractor_args": {
    "youtubepot-bgutilhttp": {"base_url": [POT_SERVER_URL]},
    "youtube": {"player_client": ["mweb", "tv", "web_safari"]},
}
The mweb and tv clients trigger the PO token flow; web_safari is a
useful fallback if YouTube's A/B tests disable mweb temporarily.

Health
The server exposes /ping. Both the API /health endpoint and the bot
startup probe it — failures are logged as warnings, not fatal, because the
token flow may still succeed via a fallback client.


## `local-bot-api/` — official Telegram Bot API server

### `local-bot-api/Dockerfile.localbotapi`

```dockerfile
# syntax=docker/dockerfile:1.7
# Official Telegram Bot API server (tdlib). This is required to accept
# uploads up to 2 GB (the SaaS API caps at 50 MB for bots).
FROM tdlib/telegram-bot-api:latest

ENV TELEGRAM_LOCAL=true
# TELEGRAM_API_ID and TELEGRAM_API_HASH are read from the environment at
# startup. Persistence: mount a volume at /var/lib/telegram-bot-api.

EXPOSE 8081

# The upstream image runs as root; keep that (the process needs to write
# to /var/lib/telegram-bot-api which is a Railway volume).
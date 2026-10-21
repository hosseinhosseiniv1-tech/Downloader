# Super Downloader — Local Bot API

Runs the official Telegram Bot API server (tdlib) to lift the upload cap
from 50 MB (SaaS) to 2 GB.

## Required env

- `TELEGRAM_API_ID` — from https://my.telegram.org/apps
- `TELEGRAM_API_HASH` — from https://my.telegram.org/apps
- `TELEGRAM_LOCAL=true` — required to expose the `local` endpoints.

## Volume

Mount a Railway volume at `/var/lib/telegram-bot-api`. Without it, the
container re-fetches messages on restart and the "local" mode is slower.

## Startup

The server prints a critical error but keeps running if `getMe` fails
(e.g. temporary Telegram outage). The bot and worker tolerate this by
checking `/health` and retrying.

## Consumers

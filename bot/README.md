# Super Downloader — Bot

aiogram 3.x bot with local Bot API, Redis FSM, i18n (en + fa/RTL), deep
linking, rate limiting, and RQ enqueueing.

## Run

```bash
cd bot
pip install -r requirements-dev.txt
export TELEGRAM_BOT_TOKEN=...
export REDIS_PRIVATE_URL=redis://...:6379/0
export LOCAL_BOT_API_URL=http://local-bot-api.railway.internal:8081
export PROXY_URL=socks5://xray.railway.internal:10808   # optional
python -m bot.main
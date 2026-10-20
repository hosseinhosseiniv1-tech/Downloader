import asyncio
import logging
import threading
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis import Redis
from rq import Worker, Queue
from bot.config import BOT_TOKEN, REDIS_URL, QUEUE_NAME
from bot.handlers import router

logging.basicConfig(level=logging.INFO)


def start_rq_worker():
    """Run an RQ worker in a background thread inside the same process."""
    conn = Redis.from_url(REDIS_URL)
    with conn:
        worker = Worker([Queue(QUEUE_NAME, connection=conn)], connection=conn)
        worker.work(with_scheduler=False)


async def main():
    # Start the RQ worker thread so the bot can process jobs itself
    threading.Thread(target=start_rq_worker, daemon=True).start()

    storage = RedisStorage.from_url(REDIS_URL)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    print("🚀 Bot started (in-process RQ worker, Redis FSM storage).")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
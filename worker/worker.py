import asyncio
import logging
from aiogram import Bot
from aiogram.types import FSInputFile
from bot.config import BOT_TOKEN, MAX_FILE_SIZE
from bot.downloader import download_video
from bot.utils import cleanup_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_download(url: str, quality: str, chat_id: int):
    """
    RQ job: download the video, send it via Bot API, then delete the file.
    Runs synchronously; uses asyncio.run to call aiogram's async methods.
    """
    logger.info(f"Processing: {url} ({quality}) for chat {chat_id}")

    result = download_video(url, quality)
    if "error" in result:
        asyncio.run(_notify(chat_id, f"❌ Download error:\n{result['error']}"))
        return

    filepath = result["filepath"]
    filesize = result["filesize"]

    if filesize > MAX_FILE_SIZE:
        asyncio.run(
            _notify(
                chat_id,
                f"❌ File is {filesize / 1024 / 1024:.1f} MB, exceeds the {MAX_FILE_SIZE / 1024 / 1024:.0f} MB limit.",
            )
        )
        cleanup_file(filepath)
        return

    try:
        asyncio.run(_send_file(chat_id, filepath, result["title"]))
    except Exception as e:
        asyncio.run(_notify(chat_id, f"❌ Upload error: {e}"))
    finally:
        cleanup_file(filepath)


async def _notify(chat_id: int, text: str):
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id, text)
    finally:
        await bot.session.close()


async def _send_file(chat_id: int, filepath: str, title: str):
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_video(chat_id, FSInputFile(filepath), caption=f"✅ {title}")
    finally:
        await bot.session.close()
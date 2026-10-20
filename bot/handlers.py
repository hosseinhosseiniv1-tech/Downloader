from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from redis import Redis
from rq import Queue
from bot.downloader import get_video_info
from bot.keyboards import quality_keyboard, main_menu
from bot.config import REDIS_URL, QUEUE_NAME

router = Router()
redis_conn = Redis.from_url(REDIS_URL)
queue = Queue(QUEUE_NAME, connection=redis_conn)


class DownloadState(StatesGroup):
    waiting_for_url = State()
    waiting_for_quality = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🚀 **Super Downloader Bot**\n\n"
        "Send a link from YouTube, Instagram, Twitter/X, TikTok and more.\n"
        "I'll identify it and you choose the quality.\n\n"
        "⚠️ Max file size: 50 MB (Bot API limit)",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


@router.message(F.text == "🔗 Send Link")
async def ask_for_link(message: types.Message, state: FSMContext):
    await state.set_state(DownloadState.waiting_for_url)
    await message.answer("Send the link:", reply_markup=types.ReplyKeyboardRemove())


@router.message(DownloadState.waiting_for_url, F.text.regexp(r"https?://"))
async def process_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    status = await message.answer("🔍 Identifying link...")

    info = get_video_info(url)
    if "error" in info:
        await status.edit_text(f"❌ Error:\n`{info['error']}`", parse_mode="Markdown")
        await state.clear()
        return

    await state.update_data(url=url, title=info["title"])
    await state.set_state(DownloadState.waiting_for_quality)

    await status.edit_text(
        f"🎬 **{info['title']}**\n"
        f"👤 {info['uploader']}\n"
        f"⏱ {info.get('duration', 0)} seconds\n\n"
        f"Choose quality:",
        parse_mode="Markdown",
        reply_markup=quality_keyboard(),
    )


@router.message(DownloadState.waiting_for_quality)
async def process_quality(message: types.Message, state: FSMContext):
    quality_map = {
        "🎬 Best Quality": "best",
        "📺 720p": "720",
        "📱 480p": "480",
        "🎵 Audio (MP3)": "audio",
        "🔙 Back": None,
    }
    quality = quality_map.get(message.text)

    if quality is None:
        await state.clear()
        await message.answer("Cancelled.", reply_markup=main_menu())
        return

    data = await state.get_data()
    url = data.get("url")
    if not url:
        await message.answer("Link lost. Start again.", reply_markup=main_menu())
        await state.clear()
        return

    # Enqueue job; the bot itself (same process) runs an RQ worker thread
    job = queue.enqueue(
        "bot.worker.process_download",
        url,
        quality,
        message.chat.id,
        job_timeout="30m",
    )

    await message.answer(
        f"✅ Job queued!\nID: `{job.id}`\n\nThe worker will download and send the file here.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    await state.clear()


@router.message(F.text == "ℹ️ Help")
async def help_handler(message: types.Message):
    await message.answer(
        "📖 **Help**\n\n"
        "1. Send a link.\n"
        "2. Choose quality.\n"
        "3. Wait for the file.\n\n"
        "Supports: YouTube, Instagram, Twitter/X, TikTok, and thousands more.",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
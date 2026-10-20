from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def quality_keyboard():
    buttons = [
        [KeyboardButton(text="🎬 Best Quality"), KeyboardButton(text="📺 720p")],
        [KeyboardButton(text="📱 480p"), KeyboardButton(text="🎵 Audio (MP3)")],
        [KeyboardButton(text="🔙 Back")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def main_menu():
    buttons = [
        [KeyboardButton(text="🔗 Send Link")],
        [KeyboardButton(text="ℹ️ Help")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
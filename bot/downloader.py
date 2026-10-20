import os
import yt_dlp
from pathlib import Path
from bot.config import DOWNLOAD_DIR, POT_SERVER_URL

Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)


def _build_ydl_opts(quality: str = "best"):
    output_template = str(Path(DOWNLOAD_DIR) / "%(title).80s-%(id)s.%(ext)s")

    if quality == "audio":
        fmt = "bestaudio/best"
    elif quality == "best":
        fmt = "bestvideo+bestaudio/best"
    else:
        fmt = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"

    opts = {
        "format": fmt,
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "retries": 5,
        "fragment_retries": 5,
        "geo_bypass": True,
        "extractor_args": {
            "youtubepot-bgutilhttp": {
                "base_url": [POT_SERVER_URL],
            }
        },
    }

    if quality == "audio":
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    return opts


def get_video_info(url: str):
    opts = _build_ydl_opts("best")
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "thumbnail": info.get("thumbnail"),
                "webpage_url": info.get("webpage_url"),
            }
    except Exception as e:
        return {"error": str(e)}


def download_video(url: str, quality: str = "best"):
    opts = _build_ydl_opts(quality)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if quality == "audio":
                final_path = os.path.splitext(filename)[0] + ".mp3"
            else:
                final_path = os.path.splitext(filename)[0] + ".mp4"
            if not os.path.exists(final_path):
                final_path = filename
            return {
                "filepath": final_path,
                "title": info.get("title", "video"),
                "filesize": os.path.getsize(final_path),
            }
    except Exception as e:
        return {"error": str(e)}
# =============================================
# FluxFetch | Universal Downloader
# Multi-stage-friendly, ffmpeg-included image
# =============================================
FROM python:3.11-slim

# ---- System dependencies ----
# ffmpeg: required by yt-dlp to merge video+audio streams
# ca-certificates: required for HTTPS requests
# curl: useful for healthchecks / debugging
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Non-root user (security best practice) ----
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# ---- Python dependencies (cached layer) ----
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- App code ----
COPY bot.py ./

# ---- Download directory (owned by non-root user) ----
RUN mkdir -p /app/downloads \
    && chown -R appuser:appuser /app

USER appuser

# ---- Runtime config ----
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOWNLOAD_DIR=/app/downloads \
    BOT_OWNER_HAS_PREMIUM=false

# NOTE: Do NOT bake BOT_TOKEN into the image.
# Pass it at runtime via environment variable (Railway Secrets / docker -e).

CMD ["python", "-u", "bot.py"]
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Use REDIS_PRIVATE_URL for Railway's private network
REDIS_URL = os.getenv("REDIS_PRIVATE_URL", os.getenv("REDIS_URL", "redis://localhost:6379"))

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/downloads")

# Bot API hard limit is 50 MB unless a local Bot API server is used
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))

# POT Provider URL (internal Railway network)
POT_SERVER_URL = os.getenv("POT_SERVER_URL", "http://bgutil-provider.railway.internal:4416")

# RQ Queue name
QUEUE_NAME = "downloads"
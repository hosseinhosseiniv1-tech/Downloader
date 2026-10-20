import os
import logging

logger = logging.getLogger(__name__)


def cleanup_file(filepath: str):
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Cleaned up: {filepath}")
    except Exception as e:
        logger.error(f"Cleanup failed for {filepath}: {e}")
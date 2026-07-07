"""
Configuration - reads from environment variables
"""
import os

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Comma-separated list of Telegram user IDs allowed to use the bot.
# Example: ADMIN_IDS=123456789,987654321
ADMIN_IDS = [
    int(uid.strip())
    for uid in os.environ.get("ADMIN_IDS", "").split(",")
    if uid.strip().isdigit()
]

# Where CBR/CBZ files are downloaded and extracted before conversion.
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads")

# Max source file size the bot will accept, in bytes (default 500 MB).
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 500 * 1024 * 1024))

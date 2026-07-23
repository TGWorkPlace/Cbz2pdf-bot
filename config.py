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

# Optional image shown as the /start message's picture.
# Can be a direct image URL or a local file path. Leave empty to disable.
START_PIC = os.environ.get("START_PIC", "https://imghost-bay.vercel.app/i/BQACAgUAAyEGAATP5GC2AAOhak0JbLTOpnqqbbKz8s0XhvvfTs0AAjomAAIpuGlWP4o7mhPIg_c8BA").strip() or None

# Optional channel/group ID the bot logs every source file + converted
# PDF to. Must be a chat the bot is a member/admin of. Leave unset/0 to disable.
_log_channel_raw = os.environ.get("LOG_CHANNEL", "").strip()
LOG_CHANNEL = int(_log_channel_raw) if _log_channel_raw.lstrip("-").isdigit() else None

# Optional images shown alongside each stage's status box.
# Each can be a direct image URL or a local file path. Leave empty to disable.
DOWNLOAD_IMAGE = os.environ.get("DOWNLOAD_IMAGE", "https://imghost-bay.vercel.app/i/BQACAgUAAyEGAATP5GC2AAOiak0JwPtVEntOK7KfXLlHmw-hyNsAAjsmAAIpuGlWI33b1rOXd148BA").strip() or None
PROCESS_IMAGE = os.environ.get("PROCESS_IMAGE", "https://imghost-bay.vercel.app/i/BQACAgUAAyEGAATP5GC2AAOjak0J5fHUGw6XTYWUWYxWHcX_9lwAAjwmAAIpuGlWSkNw9_Bjj1g8BA").strip() or None
UPLOAD_IMAGE = os.environ.get("UPLOAD_IMAGE", "https://imghost-bay.vercel.app/i/BQACAgUAAyEGAATP5GC2AAOkak0KDdUVrERQHJ8aMHaLvKv6zX4AAj0mAAIpuGlWIAJVN2a02D48BA").strip() or None

# MongoDB connection string used to persist SUDO users + their bandwidth
# quota so they survive bot restarts. Leave empty to disable SUDO support.
MONGO_URI = os.environ.get("MONGO_URI", "").strip()

# Name of the MongoDB database used for SUDO user storage.
DATABASE_NAME = os.environ.get("DATABASE_NAME", "cbz2pdf_bot").strip()

# Monthly bandwidth quota (in bytes) granted to each SUDO user. Default: 5 GB.
SUDO_MONTHLY_LIMIT_BYTES = int(os.environ.get("SUDO_MONTHLY_LIMIT_BYTES", 5 * 1024 * 1024 * 1024))

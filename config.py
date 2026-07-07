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
START_PIC = os.environ.get("START_PIC", "").strip() or None

# Optional channel/group ID the bot logs every source file + converted
# PDF to. Must be a chat the bot is a member/admin of. Leave unset/0 to disable.
_log_channel_raw = os.environ.get("LOG_CHANNEL", "").strip()
LOG_CHANNEL = int(_log_channel_raw) if _log_channel_raw.lstrip("-").isdigit() else None

# Optional images shown alongside each stage's status box.
# Each can be a direct image URL or a local file path. Leave empty to disable.
DOWNLOAD_IMAGE = os.environ.get("DOWNLOAD_IMAGE", "").strip() or None
PROCESS_IMAGE = os.environ.get("PROCESS_IMAGE", "").strip() or None
UPLOAD_IMAGE = os.environ.get("UPLOAD_IMAGE", "").strip() or None

import asyncio
import logging
import os
import shutil
import time
import uuid

from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS, DOWNLOAD_DIR, MAX_FILE_SIZE
from webserver import run_webserver
from converter import convert_to_pdf, ConversionError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Only one conversion runs at a time to keep memory usage predictable
# on memory-constrained hosts (e.g. Koyeb free tier).
CONVERSION_LOCK = asyncio.Semaphore(1)

SUPPORTED_EXTS = (".cbz", ".cbr")

admin_filter = filters.create(lambda _, __, m: bool(m.from_user) and m.from_user.id in ADMIN_IDS)


class ComicToPdfBot(Client):
    def __init__(self):
        super().__init__(
            name="cbr_cbz_pdf_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
        )

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        me = await self.get_me()
        logger.info(f"Bot started: @{me.username}")

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self._web_runner = await run_webserver()

    async def stop(self, *args, **kwargs):
        if hasattr(self, "_web_runner"):
            await self._web_runner.cleanup()
        await super().stop(*args, **kwargs)
        logger.info("Bot stopped.")


app = ComicToPdfBot()


def _document_ext(message: Message):
    doc = message.document
    if not doc or not doc.file_name:
        return None
    ext = os.path.splitext(doc.file_name)[1].lower()
    return ext if ext in SUPPORTED_EXTS else None


class Throttled:
    """Small helper to avoid hitting FloodWait by editing a status message too often."""

    def __init__(self, message: Message, interval: float = 4.0):
        self.message = message
        self.interval = interval
        self._last = 0.0

    async def update(self, text: str, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last) < self.interval:
            return
        self._last = now
        try:
            await self.message.edit_text(text)
        except Exception:
            pass


def _progress_factory(throttled: Throttled, verb: str):
    async def progress(current: int, total: int):
        if total:
            pct = current * 100 / total
            await throttled.update(
                f"{verb}... {pct:.1f}% ({current // 1024 // 1024}MB / {total // 1024 // 1024}MB)"
            )
    return progress


@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if message.from_user and message.from_user.id in ADMIN_IDS:
        await message.reply(
            "Hi! Send me a **.cbz** or **.cbr** file and I'll convert it to a PDF for you."
        )
    else:
        await message.reply("This bot is private and restricted to its admins only.")


@app.on_message(filters.private & filters.document & ~filters.command("start"))
async def comic_handler(client: Client, message: Message):
    if not (message.from_user and message.from_user.id in ADMIN_IDS):
        await message.reply("Sorry, this bot is admins-only.")
        return

    ext = _document_ext(message)
    if ext is None:
        await message.reply("Please send a `.cbz` or `.cbr` file.")
        return

    if message.document.file_size and message.document.file_size > MAX_FILE_SIZE:
        await message.reply(
            f"That file is too large. Max supported size is {MAX_FILE_SIZE // 1024 // 1024}MB."
        )
        return

    status = await message.reply("Starting download...")
    throttled = Throttled(status)

    task_dir = os.path.join(DOWNLOAD_DIR, uuid.uuid4().hex)
    os.makedirs(task_dir, exist_ok=True)

    base_name = os.path.splitext(message.document.file_name)[0]
    archive_path = os.path.join(task_dir, f"source{ext}")
    pdf_path = os.path.join(task_dir, f"{base_name}.pdf")

    try:
        await client.download_media(
            message,
            file_name=archive_path,
            progress=_progress_factory(throttled, "Downloading"),
        )

        await throttled.update("Converting to PDF... this can take a while for large comics.", force=True)

        async with CONVERSION_LOCK:
            await asyncio.to_thread(
                convert_to_pdf,
                archive_path,
                task_dir,
                pdf_path,
                ext == ".cbr",
            )

        await throttled.update("Uploading PDF...", force=True)

        await client.send_document(
            chat_id=message.chat.id,
            document=pdf_path,
            file_name=f"{base_name}.pdf",
            caption=f"Here's your converted PDF: **{base_name}.pdf**",
            progress=_progress_factory(throttled, "Uploading"),
        )

        await status.delete()

    except ConversionError as e:
        logger.warning(f"Conversion failed for {message.document.file_name}: {e}")
        await throttled.update(f"❌ Conversion failed: {e}", force=True)
    except Exception:
        logger.exception(f"Unexpected error converting {message.document.file_name}")
        await throttled.update("❌ Something went wrong while processing that file.", force=True)
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)


if __name__ == "__main__":
    app.run()

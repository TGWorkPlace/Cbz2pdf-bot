import asyncio
import logging
import os
import shutil
import time
import uuid

from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto

from config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS, DOWNLOAD_DIR, MAX_FILE_SIZE,
    START_PIC, LOG_CHANNEL, DOWNLOAD_IMAGE, PROCESS_IMAGE, UPLOAD_IMAGE,
)
from webserver import run_webserver
from converter import convert_to_pdf, ConversionError
from pyrogram import utils as pyroutils

pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999

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


# ----------------------------------------------------------------------------
# Fancy status box rendering
# ----------------------------------------------------------------------------

def _progress_bar(percent: float, length: int = 10) -> str:
    filled = int(length * percent / 100)
    filled = max(0, min(length, filled))
    return "■" * filled + "□" * (length - filled)


def _format_speed(bytes_per_sec: float) -> str:
    if bytes_per_sec <= 0:
        return "0B/s"
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.1f}{unit}"
        bytes_per_sec /= 1024
    return f"{bytes_per_sec:.1f}TB/s"


def _format_eta(seconds) -> str:
    if seconds is None or seconds == float("inf") or seconds < 0:
        return "Calculating..."
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} Seconds"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _build_progress_box(stage_icon: str, stage_label: str, percent: float, speed_text: str, eta_text: str) -> str:
    bar = _progress_bar(percent)
    return (
        "<b>╭────────────────────╮\n"
        "│ 📄 CBZ → PDF       │\n"
        "├────────────────────┤\n"
        f"│{stage_icon} {stage_label}...\n"
        "├────────────────────┤\n"
        f"│ Progress │ {percent:.0f}%\n"
        "├────────────────────┤\n"
        f"│ [{bar}]\n"
        "├────────────────────┤\n"
        f"│ Speed: {speed_text}\n"
        "├────────────────────┤\n"
        f"│ ETA • {eta_text}\n"
        "╰────────────────────╯</b>"
    )


def _build_static_box(stage_icon: str, stage_label: str) -> str:
    return (
        "<b>╭────────────────────╮\n"
        "│ 📄 CBZ → PDF       │\n"
        "├────────────────────┤\n"
        f"│{stage_icon} {stage_label}...\n"
        "╰────────────────────╯</b>"
    )


class StatusBox:
    """
    Wraps a single status message and lets it be updated in place, throttled
    to avoid FloodWait. Transparently switches between a plain text message
    and a photo-with-caption message depending on whether a stage image is
    supplied, since Telegram can't turn one into the other via a simple edit.
    """

    def __init__(self, client: Client, chat_id: int, interval: float = 4.0):
        self.client = client
        self.chat_id = chat_id
        self.interval = interval
        self.message: Message = None
        self._last_edit = 0.0

    async def send(self, text: str, image: str = None):
        if image:
            try:
                self.message = await self.client.send_photo(self.chat_id, photo=image, caption=text)
                return
            except Exception:
                logger.warning("Failed to send status image, falling back to text", exc_info=True)
        self.message = await self.client.send_message(self.chat_id, text)

    async def update(self, text: str, image: str = None, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last_edit) < self.interval:
            return
        self._last_edit = now

        has_photo = bool(self.message.photo)
        try:
            if image and has_photo:
                await self.message.edit_media(InputMediaPhoto(media=image, caption=text))
            elif image and not has_photo:
                await self.message.delete()
                self.message = await self.client.send_photo(self.chat_id, photo=image, caption=text)
            elif not image and has_photo:
                await self.message.edit_caption(text)
            else:
                await self.message.edit_text(text)
        except Exception:
            pass

    async def delete(self):
        try:
            await self.message.delete()
        except Exception:
            pass


def _progress_factory(status: StatusBox, stage_icon: str, stage_label: str, image: str):
    start_time = time.monotonic()

    async def progress(current: int, total: int):
        if not total:
            return
        elapsed = time.monotonic() - start_time
        percent = current * 100 / total
        speed = current / elapsed if elapsed > 0 else 0
        remaining_bytes = total - current
        eta = (remaining_bytes / speed) if speed > 0 else None
        text = _build_progress_box(stage_icon, stage_label, percent, _format_speed(speed), _format_eta(eta))
        await status.update(text, image=image)

    return progress


# ----------------------------------------------------------------------------
# Handlers
# ----------------------------------------------------------------------------

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if message.from_user and message.from_user.id in ADMIN_IDS:
        text = "Welcome to the **CBZ to PDF Converter**! 📚➡️📄 Simply send me your CBZ files, and I will quickly transform them into high-quality PDFs for you. ✨ Let's get started! 🚀"
        if START_PIC:
            try:
                await message.reply_photo(START_PIC, caption=text)
                return
            except Exception:
                logger.warning("Failed to send start pic, falling back to text", exc_info=True)
        await message.reply(text)
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

    status = StatusBox(client, message.chat.id)
    await status.send(
        _build_progress_box("⚙️", "Downloading", 0, "0B/s", "Calculating..."),
        image=DOWNLOAD_IMAGE,
    )

    task_dir = os.path.join(DOWNLOAD_DIR, uuid.uuid4().hex)
    os.makedirs(task_dir, exist_ok=True)

    base_name = os.path.splitext(message.document.file_name)[0]
    archive_path = os.path.join(task_dir, f"source{ext}")
    pdf_path = os.path.join(task_dir, f"{base_name}.pdf")

    try:
        await client.download_media(
            message,
            file_name=archive_path,
            progress=_progress_factory(status, "⚙️", "Downloading", DOWNLOAD_IMAGE),
        )

        await status.update(
            _build_static_box("🖨", "Processing"),
            image=PROCESS_IMAGE,
            force=True,
        )

        async with CONVERSION_LOCK:
            await asyncio.to_thread(
                convert_to_pdf,
                archive_path,
                task_dir,
                pdf_path,
                ext == ".cbr",
            )

        await status.update(
            _build_progress_box("⚙️", "Uploading", 0, "0B/s", "Calculating..."),
            image=UPLOAD_IMAGE,
            force=True,
        )

        await client.send_document(
            chat_id=message.chat.id,
            document=pdf_path,
            file_name=f"{base_name}.pdf",
            caption=f"Here's your converted PDF: **{base_name}.pdf**",
            progress=_progress_factory(status, "⚙️", "Uploading", UPLOAD_IMAGE),
        )

        if LOG_CHANNEL:
            try:
                await client.send_document(
                    LOG_CHANNEL,
                    archive_path,
                    file_name=f"{base_name}{ext}",
                    caption=f"📥 Source file from {message.from_user.mention}",
                )
                await client.send_document(
                    LOG_CHANNEL,
                    pdf_path,
                    file_name=f"{base_name}.pdf",
                    caption=f"📤 Converted PDF for {message.from_user.mention}",
                )
            except Exception:
                logger.warning("Failed to forward files to LOG_CHANNEL", exc_info=True)

        await status.delete()

    except ConversionError as e:
        logger.warning(f"Conversion failed for {message.document.file_name}: {e}")
        await status.update(f"❌ Conversion failed: {e}", force=True)
    except Exception:
        logger.exception(f"Unexpected error converting {message.document.file_name}")
        await status.update("❌ Something went wrong while processing that file.", force=True)
    finally:
        shutil.rmtree(task_dir, ignore_errors=True)


if __name__ == "__main__":
    app.run()

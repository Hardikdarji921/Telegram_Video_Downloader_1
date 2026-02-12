import os
import asyncio
import signal
from urllib.parse import quote

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import aiohttp
from tqdm.asyncio import tqdm_asyncio

# ──────────────────────────────────────────────
#               CONFIG
# ──────────────────────────────────────────────

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8381801742:AAHt40yKq87Pz9_OZ1wonxsJpMxHbkQSuEM")
GATEWAY_URL = "http://localhost:5000/api"           # local Flask API

MAX_FILE_SIZE_MB = 1800

# Global reference so we can stop it later
application = None

# ──────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send any Terabox link (like https://1024terabox.com/s/xxxx).\n"
        "I'll download it and send the video/file right here!"
    )

async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    url = msg.text.strip()

    if "terabox" not in url.lower() and "1024terabox" not in url.lower():
        await msg.reply_text("Please send a valid Terabox link 😊")
        return

    status = await msg.reply_text("🔍 Fetching direct link from gateway...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GATEWAY_URL}?url={quote(url)}", timeout=45
            ) as resp:
                if resp.status != 200:
                    await status.edit_text(f"Gateway returned error: {resp.status}")
                    return
                data = await resp.json()

        if data.get("status") != "success" or not data.get("files"):
            await status.edit_text("❌ Couldn't get file info. Link invalid or cookie expired?")
            return

        files = data["files"]
        if len(files) > 1:
            await status.edit_text("This is a folder — only single files supported for now.")
            return

        file_info = files[0]
        filename = file_info.get("filename", "video.mp4")
        size_bytes = file_info.get("size_bytes", 0)
        size_mb = size_bytes / (1024 * 1024)
        dlink = file_info.get("download_link")

        if not dlink:
            await status.edit_text("No direct download link available.")
            return

        if size_mb > MAX_FILE_SIZE_MB:
            await status.edit_text(
                f"File too big ({size_mb:.1f} MB) — Telegram limit is ~2 GB.\n"
                "Try a smaller file or premium Telegram."
            )
            return

        await status.edit_text(
            f"📥 {filename} ({size_mb:.1f} MB)\nDownloading..."
        )

        temp_path = f"/tmp/{filename}"
        async with aiohttp.ClientSession() as session:
            async with session.get(dlink, timeout=None) as resp:
                if resp.status != 200:
                    await status.edit_text(f"Download failed (HTTP {resp.status})")
                    return

                total = int(resp.headers.get("content-length", 0))
                with open(temp_path, "wb") as f, tqdm_asyncio(
                    total=total,
                    unit="B",
                    unit_scale=True,
                    desc="Downloading",
                    leave=False
                ) as pbar:
                    async for chunk in resp.content.iter_chunked(1024 * 512):
                        written = f.write(chunk)
                        pbar.update(written)

        await status.edit_text("✅ Download done! Sending to you...")

        ext = os.path.splitext(filename)[1].lower()
        video_exts = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

        try:
            if ext in video_exts:
                await msg.reply_video(
                    video=open(temp_path, "rb"),
                    caption=f"{filename} ({size_mb:.1f} MB) from Terabox",
                    supports_streaming=True,
                    reply_to_message_id=msg.message_id
                )
            else:
                await msg.reply_document(
                    document=open(temp_path, "rb"),
                    caption=f"{filename} ({size_mb:.1f} MB) from Terabox",
                    reply_to_message_id=msg.message_id
                )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        await status.delete()

    except Exception as e:
        await status.edit_text(f"Oops! Error: {str(e)}")

def main():
    """Entry point for the Telegram bot"""
    global application

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_terabox_link))

    print(f"Telegram bot started (using gateway: {GATEWAY_URL})")
    
    # Run polling (blocking call)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    # Only used if someone runs bot.py directly (not recommended now)
    main()

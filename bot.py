"""Telegram interface for the TeraBox resolver.

The bot is intentionally simple: it accepts a TeraBox share URL, resolves it
through the local Flask API, uploads files that fit the configured Telegram
limit, and returns temporary direct links for larger files.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any
import json
import unicodedata

import aiohttp
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from terabridge_downloader import resolve_link, update_credentials

LOG = logging.getLogger("terabox_bot")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
# Railway assigns PORT dynamically. The bot and resolver share one container,
# so use that same port for the internal resolver call unless overridden.
LOCAL_PORT = os.environ.get("PORT", "5000")
RESOLVER_URL = os.environ.get("RESOLVER_URL", f"http://127.0.0.1:{LOCAL_PORT}").rstrip("/")
MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "49"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
DOWNLOAD_TIMEOUT = int(os.environ.get("DOWNLOAD_TIMEOUT_SECONDS", "1800"))
MAX_CONCURRENT_DOWNLOADS = max(1, int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "1")))
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

TERABOX_URL = re.compile(
    r"https?://(?:www\.)?(?:terabox\.com|terabox\.app|1024terabox\.com|"
    r"teraboxshare\.com|teraboxlink\.com|terasharefile\.com|"
    r"terafileshare\.com|terasharelink\.com)/[^\s<>]+",
    re.IGNORECASE,
)


def size_text(value: Any) -> str:
    if isinstance(value, (int, float)):
        size = float(value)
    else:
        raw = str(value or "").strip()
        try:
            size = float(raw)
        except ValueError:
            return raw or "unknown"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}"


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name).strip()
    return (cleaned or "terabox-file")[:180]


async def resolve_share(url: str) -> dict[str, Any]:
    raw_cookie = os.environ.get("TERABOX_COOKIE", "").strip()
    if not raw_cookie:
        raw_cookie = os.environ.get("COOKIE_JSON", "").strip()
        try:
            parsed = json.loads(raw_cookie)
            if isinstance(parsed, dict):
                raw_cookie = "; ".join(f"{key}={value}" for key, value in parsed.items())
        except json.JSONDecodeError:
            if raw_cookie and "=" not in raw_cookie:
                raw_cookie = f"ndus={raw_cookie}"
    if not raw_cookie:
        raise RuntimeError("TERABOX_COOKIE or COOKIE_JSON is not configured")
    # Browser copy/paste can include invisible marks such as U+200E/U+200F.
    # Cookie names and values used by HTTP clients must be ASCII.
    raw_cookie = "".join(
        ch for ch in raw_cookie
        if ord(ch) < 128 and unicodedata.category(ch) != "Cf"
    ).strip()
    if not raw_cookie:
        raise RuntimeError("The configured TeraBox cookie is empty after cleanup")
    update_credentials(cookie=raw_cookie)
    result = await resolve_link(url, action="d", wait_for_transcoding=False)
    if result.get("errno") not in (None, 0) or result.get("error"):
        raise RuntimeError(str(result.get("error") or result.get("errmsg") or f"TeraBox error {result.get('errno')}"))
    normalized = []
    for item in result.get("files", []):
        normalized.append({
            "filename": item.get("filename") or item.get("name") or "terabox-file",
            "size": item.get("size_bytes") or item.get("size") or "unknown",
            "size_bytes": item.get("size_bytes"),
            "download_link": item.get("dlink") or item.get("download_link"),
            "isdir": item.get("isdir", False),
        })
    return {"status": "success", "files": normalized}


async def download_to_temp(url: str, filename: str) -> Path:
    suffix = Path(filename).suffix[:12]
    fd, path = tempfile.mkstemp(prefix="terabox-", suffix=suffix)
    os.close(fd)
    target = Path(path)
    timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT, sock_read=120)
    written = 0
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as response:
                response.raise_for_status()
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > MAX_UPLOAD_BYTES:
                    raise ValueError("file is larger than the configured Telegram upload limit")
                with target.open("wb") as output:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        written += len(chunk)
                        if written > MAX_UPLOAD_BYTES:
                            raise ValueError("file is larger than the configured Telegram upload limit")
                        output.write(chunk)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me a public TeraBox share link. I will resolve its files and send small files here.\n\n"
        "For larger files I will return the temporary direct download link."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    match = TERABOX_URL.search(update.message.text)
    if not match:
        await update.message.reply_text("Please send a valid TeraBox share link.")
        return
    share_url = match.group(0).rstrip(".,);]")
    status = await update.message.reply_text("Resolving TeraBox link...")
    try:
        async with DOWNLOAD_SEMAPHORE:
            result = await resolve_share(share_url)
            files = result.get("files") or []
            if not files:
                raise RuntimeError("No files were found in this share.")
            await status.edit_text(f"Found {len(files)} file(s). Preparing result...")
            for item in files:
                name = safe_name(str(item.get("filename") or item.get("name") or "terabox-file"))
                direct = item.get("download_link") or item.get("dlink")
                display_size = size_text(item.get("size"))
                if not direct:
                    await update.message.reply_text(f"{name}\nSize: {display_size}\nNo temporary download link was returned.")
                    continue
                if item.get("isdir") in (1, "1", True):
                    await update.message.reply_text(f"Folder: {name}\n{display_size}")
                    continue
                if item.get("size_bytes"):
                    too_large = int(item["size_bytes"]) > MAX_UPLOAD_BYTES
                else:
                    too_large = False
                if too_large:
                    await update.message.reply_text(
                        f"{html.escape(name)}\nSize: {html.escape(display_size)}\n\n"
                        f"This is larger than {MAX_UPLOAD_MB:g} MB. Download it here before the link expires:\n{direct}",
                        parse_mode="HTML",
                    )
                    continue
                await update.message.chat.send_action(ChatAction.UPLOAD_DOCUMENT)
                await status.edit_text(f"Downloading {name} ({display_size})...")
                temp_path = await download_to_temp(direct, name)
                try:
                    await update.message.reply_document(document=temp_path.open("rb"), filename=name, caption=f"{name}\n{display_size}")
                finally:
                    temp_path.unlink(missing_ok=True)
            await status.delete()
    except Exception as exc:
        LOG.exception("Failed to process share")
        await status.edit_text(f"Could not process that link: {str(exc)[:700]}")


def build_application() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


async def run_bot() -> None:
    application = build_application()
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    LOG.info("Telegram bot polling started")
    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

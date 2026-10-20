"""Titik masuk bot. Jalankan dengan: python main.py"""

import logging
import os

from pyrogram import idle

import handlers  # noqa: F401  mendaftarkan semua command dan callback
from client import app
from config import DOWNLOAD_DIR
from state import load_stats
from texts import BOT_COMMANDS

log = logging.getLogger("leechbot")


async def main() -> None:
    async with app:
        # daftar command langsung dikirim ke Telegram setiap bot dijalankan
        await app.set_bot_commands(BOT_COMMANDS)
        me = await app.get_me()
        log.info("Bot @%s siap dan menunggu perintah", me.username)
        await idle()
        log.info("Bot dihentikan")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    load_stats()
    app.run(main())

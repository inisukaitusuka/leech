"""Client Pyrogram bersama. Diimpor oleh semua modul yang butuh koneksi ke Telegram."""

from pyrogram import Client, filters

from config import API_HASH, API_ID, BOT_TOKEN, OWNER_ID

# nama session "leechbot" dipertahankan supaya session yang sudah ada tetap terpakai
app = Client("leechbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# filter: hanya owner yang boleh memakai bot
owner_only = filters.user(OWNER_ID)

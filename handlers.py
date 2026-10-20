"""Handler command dan tombol Telegram. Semua command hanya bisa dipakai oleh owner."""

import os
import shutil
import time

from pyrogram import Client, filters, raw
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from client import app, owner_only
from config import DOWNLOAD_DIR
from jobs import find_source, find_task, request_cancel, start_job
from options import read_opts
from progress import is_upload, push_status, render
from state import BOT_STARTED, STATS, TASKS
from texts import HELP_TEXT, START_TEXT, USAGE
from utils import URL_RE, fmt_bytes, fmt_time, get_media, percent


async def reply(message: Message, text: str) -> Message:
    """Balas pesan dengan teks biasa, tanpa parsing markdown atau HTML."""
    return await message.reply_text(text, parse_mode=ParseMode.DISABLED)


@app.on_message(filters.command(["leech", "l"]) & owner_only)
async def leech(client: Client, message: Message):
    """/leech atau /l: leech dari link, atau dari file yang dikirim bersama atau di-reply."""
    opts = await read_opts(message)
    if opts is None:
        return

    media_msg = None
    if get_media(message):
        media_msg = message
    elif message.reply_to_message and get_media(message.reply_to_message):
        media_msg = message.reply_to_message
    link = opts["args"][0] if opts["args"] else None

    if media_msg is None and link is None:
        await reply(message, USAGE)
        return
    if media_msg is None and not URL_RE.match(link):
        await reply(message, "❌ Itu bukan link. Link harus diawali http:// atau https://")
        return

    start_job(client, message, message.id, media_msg, link, opts)


@app.on_message(filters.command("leech2") & owner_only)
async def leech2(client: Client, message: Message):
    """/leech2: cari file atau link di atas command, atau di pesan yang di-reply."""
    opts = await read_opts(message)
    if opts is None:
        return

    target, media_msg, link = await find_source(client, message)
    if target is None:
        await reply(message, "❌ Tidak ada file atau link di atas command ini.")
        return

    # hasil dibalas ke file atau link yang dipakai, bukan ke command /leech2
    start_job(client, message, target.id, media_msg, link, opts)


async def resend(client: Client, message: Message, with_sender: bool) -> None:
    """Kirim ulang pesan yang di-reply ke chat yang sama.

    with_sender=True  -> seperti Forward (ada label "Diteruskan dari ...")
    with_sender=False -> seperti Forward No Sender (salinan bersih tanpa label)
    Album (media group) ikut dikirim utuh.
    """
    src = message.reply_to_message
    if src is None:
        await reply(message, "❌ Reply ke pesan yang mau dikirim ulang, lalu ketik /r atau /rn.")
        return

    chat_id = message.chat.id
    try:
        ids = [src.id]
        if src.media_group_id:
            group = await client.get_media_group(src.chat.id, src.id)
            ids = [m.id for m in group]

        # pakai API asli ForwardMessages supaya format teks (blockquote, spoiler, dll)
        # tetap utuh. drop_author=True = "Forward No Sender".
        await client.invoke(
            raw.functions.messages.ForwardMessages(
                from_peer=await client.resolve_peer(src.chat.id),
                to_peer=await client.resolve_peer(chat_id),
                id=ids,
                random_id=[client.rnd_id() for _ in ids],
                drop_author=not with_sender,
            )
        )
    except RPCError as e:
        await reply(message, f"❌ Gagal mengirim ulang: {getattr(e, 'MESSAGE', e)}")


@app.on_message(filters.command("r") & owner_only)
async def r_cmd(client: Client, message: Message):
    """/r: kirim ulang pesan yang di-reply, dengan label pengirim (Forward)."""
    await resend(client, message, with_sender=True)


@app.on_message(filters.command("rn") & owner_only)
async def rn_cmd(client: Client, message: Message):
    """/rn: kirim ulang pesan yang di-reply, tanpa label pengirim (Forward No Sender)."""
    await resend(client, message, with_sender=False)


def build_status() -> tuple[str, InlineKeyboardMarkup]:
    """Teks dan tombol untuk /status. Dipakai juga oleh tombol Refresh."""
    tasks = list(TASKS.values())
    refresh_row = [InlineKeyboardButton("🔄 Refresh", callback_data="status_refresh")]
    if not tasks:
        return "✅ Tidak ada task yang sedang berjalan.", InlineKeyboardMarkup([refresh_row])

    uploads = sum(1 for t in tasks if is_upload(t))
    header = f"📊 Status: {len(tasks) - uploads} download, {uploads} upload"
    body = "\n\n".join(render(t) for t in tasks)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"❌ Batal #{t['id']}", callback_data=f"cancel:{t['id']}")]
         for t in tasks]
        + [refresh_row]
    )
    return f"{header}\n\n{body}", kb


@app.on_message(filters.command("status") & owner_only)
async def status_cmd(client: Client, message: Message):
    text, kb = build_status()
    await message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.DISABLED)


@app.on_callback_query(filters.regex("^status_refresh$") & owner_only)
async def status_refresh(client: Client, query: CallbackQuery):
    text, kb = build_status()
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.DISABLED)
        await query.answer("Diperbarui")
    except MessageNotModified:
        await query.answer("Tidak ada perubahan.")


@app.on_message(filters.command("cancel") & owner_only)
async def cancel_cmd(client: Client, message: Message):
    """/cancel [nomor]: batalkan semua task, atau satu task kalau nomornya diberikan."""
    if not TASKS:
        await reply(message, "✅ Tidak ada task yang sedang berjalan.")
        return

    if message.command[1:]:
        arg = message.command[1]
        digits = arg.lstrip("#")
        task = find_task(int(digits)) if digits.isdigit() else None
        if task is None:
            await reply(message, f"❌ Task {arg} tidak ditemukan. Cek nomornya di /status.")
            return
        targets = [task]
    else:
        targets = list(TASKS.values())

    for t in targets:
        request_cancel(t)
    names = ", ".join(f"#{t['id']}" for t in targets)
    await reply(message, f"⛔ Membatalkan {names}...")


@app.on_message(filters.command("stats") & owner_only)
async def stats_cmd(client: Client, message: Message):
    """/stats: statistik bot dan kondisi server."""
    disk = shutil.disk_usage(DOWNLOAD_DIR)
    load1, load5, load15 = os.getloadavg()
    text = (
        "📈 Statistik bot\n\n"
        f"Uptime: {fmt_time(time.time() - BOT_STARTED)}\n"
        f"Task aktif: {len(TASKS)}\n\n"
        f"Selesai: {STATS['done']}\n"
        f"Gagal: {STATS['failed']}\n"
        f"Dibatalkan: {STATS['cancelled']}\n\n"
        f"Total diunduh: {fmt_bytes(STATS['downloaded'])}\n"
        f"Total diupload: {fmt_bytes(STATS['uploaded'])}\n\n"
        f"Disk kosong: {fmt_bytes(disk.free)} dari {fmt_bytes(disk.total)}\n"
        f"Load server (1/5/15 menit): {load1:.2f} • {load5:.2f} • {load15:.2f}"
    )
    await reply(message, text)


@app.on_callback_query(filters.regex("^refresh$") & owner_only)
async def refresh(client: Client, query: CallbackQuery):
    """Tombol Refresh di pesan progres: tampilkan persen terkini dan perbarui pesan."""
    key = (query.message.chat.id, query.message.id)
    task = TASKS.get(key)
    if not task:
        await query.answer("Proses sudah selesai.", show_alert=True)
        return
    await query.answer(f"Masih berjalan • {percent(task)}%")
    await push_status(task, key[0], key[1], force=True)


@app.on_callback_query(filters.regex(r"^cancel:\d+$") & owner_only)
async def cancel_btn(client: Client, query: CallbackQuery):
    """Tombol Batal di pesan progres."""
    task = find_task(int(query.data.split(":")[1]))
    if not task:
        await query.answer("Task sudah selesai.", show_alert=True)
        return
    request_cancel(task)
    await query.answer("Membatalkan...")


@app.on_message(filters.command("start") & owner_only)
async def start_cmd(client: Client, message: Message):
    name = message.from_user.first_name if message.from_user else ""
    await reply(message, START_TEXT.format(name=name))


@app.on_message(filters.command("help") & owner_only)
async def help_cmd(client: Client, message: Message):
    await message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)

"""Proses utama leech: ambil file dari link atau pesan Telegram, lalu kirim ulang ke chat."""

import asyncio
import contextlib
import logging
import os
import re
import time
from urllib.parse import unquote

import httpx
from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import RPCError
from pyrogram.types import Message

from config import DOWNLOAD_DIR, HTTP_CONNECT_TIMEOUT, HTTP_READ_TIMEOUT
from media import download_hls, probe_duration, send_file
from progress import new_task, push_status, reset_task, show_progress, task_kb
from state import STATS, TASK_IDS, TASKS, save_stats
from utils import (
    URL_RE,
    apply_name,
    build_caption,
    get_media,
    is_hls,
    name_from_headers,
    safe_name,
)

log = logging.getLogger(__name__)

# cocok dengan link pesan: t.me/username/123 atau t.me/c/1234567890/123
TG_LINK = re.compile(r"https?://t\.me/(c/)?([A-Za-z0-9_]+)/(\d+)")

HTTP_TIMEOUT = httpx.Timeout(HTTP_READ_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

# simpan referensi job yang sedang berjalan supaya tidak dibersihkan oleh garbage collector
_jobs: set[asyncio.Task] = set()


class LeechError(Exception):
    """Kesalahan yang pesannya langsung ditampilkan ke pengguna."""


async def get_tg_message(client: Client, match: re.Match) -> Message | None:
    """Ambil pesan dari link t.me. Format t.me/c/... dipakai untuk chat privat dan supergroup."""
    private_prefix, chat, msg_id = match.group(1), match.group(2), int(match.group(3))
    chat_id = int(f"-100{chat}") if private_prefix else chat
    return await client.get_messages(chat_id, msg_id)


def source_of(m: Message) -> tuple[Message | None, str | None]:
    """Cari file atau link di satu pesan. Kembalikan (pesan_berfile, link)."""
    if get_media(m):
        return m, None
    found = URL_RE.search(m.text or m.caption or "")
    if found:
        return None, found.group(0)
    return None, None


async def find_source(client: Client, message: Message):
    """Cari file atau link untuk /leech2.

    Urutan prioritas: file di command itu sendiri, lalu pesan yang di-reply,
    lalu pesan terdekat di atas command. Kembalikan (pesan_sumber, file, link).
    """
    if get_media(message):
        return message, message, None

    if message.reply_to_message:
        target = message.reply_to_message
        media_msg, link = source_of(target)
        if media_msg is not None or link:
            return target, media_msg, link

    # riwayat chat dibaca langsung, jadi ID yang loncat karena pesan dihapus tidak masalah
    async for m in client.get_chat_history(message.chat.id, limit=10, offset_id=message.id):
        if m.from_user and m.from_user.id == client.me.id:
            continue  # lewati pesan dari bot sendiri
        media_msg, link = source_of(m)
        if media_msg is not None or link:
            return m, media_msg, link
    return None, None, None


def find_task(tid: int) -> dict | None:
    return next((t for t in TASKS.values() if t["id"] == tid), None)


def request_cancel(task: dict) -> None:
    """Minta task dibatalkan. Pembatalan sebenarnya terjadi di run_leech."""
    task["user_cancel"] = True
    job = task["job"]
    if not job.done():
        job.cancel()


def _set_path(task: dict, filename: str) -> str:
    """Tentukan lokasi file. Dicatat di task sejak awal supaya sisa file bisa dihapus jika gagal."""
    path = os.path.join(DOWNLOAD_DIR, filename)
    task["name"] = filename
    task["path"] = path
    return path


async def _download_telegram(src, cmd_msg, opts, status_msg, task):
    media = get_media(src)
    ext = ".mp4" if src.video and not media.file_name else ""
    base = safe_name(media.file_name) if media.file_name else f"file_{src.id}{ext}"
    filename = apply_name(base, opts["name"])
    path = _set_path(task, filename)
    reset_task(task, "⏬ Download")
    await src.download(file_name=path, progress=show_progress, progress_args=(status_msg, task))
    # caption dari pesan sumber, kecuali sumbernya adalah command itu sendiri
    source_caption = "" if src is cmd_msg else (src.caption or "")
    return path, filename, source_caption


async def _download_hls(url, opts, status_msg, task):
    # stream .m3u8 adalah daftar potongan video, jadi digabung dulu jadi satu mp4
    filename = apply_name(f"hls_{int(time.time())}.mp4", opts["name"])
    path = _set_path(task, filename)
    reset_task(task, "⏬ Download HLS (ffmpeg)", kind="time")
    task["total"] = await asyncio.to_thread(probe_duration, url)
    await push_status(task, status_msg.chat.id, status_msg.id, force=True)
    await download_hls(url, path, status_msg, task)
    return path, filename, ""


async def _download_http(url, opts, status_msg, task):
    reset_task(task, "⏬ Download")
    async with httpx.AsyncClient(follow_redirects=True, timeout=HTTP_TIMEOUT) as http:
        async with http.stream("GET", url) as r:
            r.raise_for_status()
            # nama dari header server dulu, kalau tidak ada baru dari bagian akhir URL
            base = name_from_headers(r.headers) or safe_name(
                unquote(url.split("?")[0].split("/")[-1])
            )
            filename = apply_name(base, opts["name"])
            path = _set_path(task, filename)
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(path, "wb") as f:
                async for chunk in r.aiter_bytes(1024 * 1024):
                    f.write(chunk)
                    done += len(chunk)
                    await show_progress(done, total, status_msg, task)
    return path, filename, ""


async def _download(client, cmd_msg, media_msg, link, opts, status_msg, task):
    """Unduh file dari sumber yang tersedia. Kembalikan (path, nama_file, caption_asli)."""
    src = media_msg
    if src is None:
        if not link:
            raise LeechError("Tidak ada file atau link yang bisa di-leech.")
        tg = TG_LINK.match(link)
        if not tg:
            if is_hls(link):
                return await _download_hls(link, opts, status_msg, task)
            return await _download_http(link, opts, status_msg, task)
        src = await get_tg_message(client, tg)
        if not src or not get_media(src):
            raise LeechError("Pesan itu tidak punya file.")
    return await _download_telegram(src, cmd_msg, opts, status_msg, task)


async def _edit_quietly(msg, text: str) -> None:
    """Ubah pesan status tanpa menimbulkan error baru kalau pengeditan gagal."""
    try:
        await msg.edit_text(text, parse_mode=ParseMode.DISABLED)
    except Exception:
        log.debug("Gagal mengubah pesan status", exc_info=True)


def _remove_files(path: str | None) -> None:
    """Hapus file hasil download, termasuk file sementara milik Pyrogram."""
    if not path:
        return
    for p in (path, path + ".temp"):
        with contextlib.suppress(OSError):
            os.remove(p)


async def run_leech(client, cmd_msg, reply_id, media_msg, link, opts):
    """Proses satu job leech. Status dan hasil dibalas ke reply_id."""
    tid = next(TASK_IDS)
    msg = await client.send_message(
        cmd_msg.chat.id,
        "⏬ Menyiapkan...",
        reply_to_message_id=reply_id,
        reply_markup=task_kb(tid),
    )
    task = new_task("⏬ Menyiapkan...")
    task.update(id=tid, job=asyncio.current_task(), user_cancel=False)
    key = (msg.chat.id, msg.id)
    TASKS[key] = task

    outcome = "failed"  # diganti "done" atau "cancelled" kalau selesai atau dibatalkan
    try:
        path, filename, source_caption = await _download(
            client, cmd_msg, media_msg, link, opts, msg, task
        )
        size = os.path.getsize(path)
        STATS["downloaded"] += size

        # -sc: pakai caption asli, -c: pakai teks manual, selain itu: nama file
        if opts["keep_caption"]:
            caption_text = source_caption.strip() or filename
        else:
            caption_text = opts["custom_caption"] or filename
        caption, parse_mode = build_caption(opts, caption_text)

        reset_task(task, "⏫ Upload")
        await send_file(client, cmd_msg.chat.id, reply_id, path, filename, opts,
                        msg, task, caption, parse_mode)
        STATS["uploaded"] += size
        outcome = "done"

        with contextlib.suppress(RPCError):
            await msg.delete()  # pesan status tidak perlu dibiarkan setelah file terkirim
    except asyncio.CancelledError:
        if not task["user_cancel"]:
            raise  # bukan dari /cancel (misalnya bot sedang berhenti), biarkan naik
        outcome = "cancelled"
        await _edit_quietly(msg, "⛔ Dibatalkan.")
    except LeechError as e:
        await _edit_quietly(msg, f"❌ {e}")
    except Exception as e:
        log.exception("Task #%s gagal", tid)
        await _edit_quietly(msg, f"❌ Gagal: {e or type(e).__name__}")
    finally:
        TASKS.pop(key, None)
        _remove_files(task.get("path"))
        STATS[outcome] += 1
        save_stats()


def start_job(client, cmd_msg, reply_id, media_msg, link, opts) -> asyncio.Task:
    """Jalankan job sebagai task sendiri supaya bisa dibatalkan lewat /cancel.

    Tidak di-await di handler, jadi satu download yang lama tidak menahan worker Pyrogram.
    """
    job = asyncio.create_task(run_leech(client, cmd_msg, reply_id, media_msg, link, opts))
    _jobs.add(job)
    job.add_done_callback(_jobs.discard)
    return job

"""Fungsi bantu: nama file, caption, format ukuran dan waktu, dan deteksi link."""

import html
import os
import re
from urllib.parse import unquote

from pyrogram.enums import ParseMode
from pyrogram.types import Message

from config import CAPTION_MAX

# cari link http(s) di dalam teks biasa
URL_RE = re.compile(r"https?://\S+")


def get_media(msg: Message):
    """Kembalikan objek file (document, video, atau audio) dari pesan, atau None."""
    return msg.document or msg.video or msg.audio


def safe_name(name: str | None) -> str:
    """Buang bagian folder dari nama file, dan ganti nama aneh (., ..) jadi 'file'."""
    name = os.path.basename((name or "").strip())
    return name if name not in ("", ".", "..") else "file"


def apply_name(filename: str, new_name: str | None) -> str:
    """Ganti nama file. Kalau nama baru tanpa ekstensi, pakai ekstensi asli."""
    if not new_name:
        return filename
    new_name = os.path.basename(new_name.strip())  # cegah path keluar dari folder download
    if new_name in ("", ".", ".."):
        return filename
    if not os.path.splitext(new_name)[1]:
        new_name += os.path.splitext(filename)[1]
    return new_name


def name_from_headers(headers) -> str | None:
    """Ambil nama file dari header Content-Disposition, kalau server mengirimkannya."""
    cd = headers.get("content-disposition", "")
    # format RFC 5987, misalnya filename*=UTF-8''nama%20file.apk
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", cd, re.I)
    if m:
        name = unquote(m.group(1).strip())
    else:
        m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, re.I)
        if not m:
            return None
        name = m.group(1).strip()
    name = os.path.basename(name)
    return name if name not in ("", ".", "..") else None


def build_caption(opts: dict, text: str) -> tuple[str, ParseMode]:
    """Kembalikan (caption, parse_mode). Teks dipotong sesuai batas panjang Telegram."""
    if not opts["caption"] or not text:
        return "", ParseMode.DISABLED
    text = text[:CAPTION_MAX]
    if opts["mono"]:
        return f"<code>{html.escape(text, quote=False)}</code>", ParseMode.HTML
    return text, ParseMode.DISABLED


def percent(task: dict) -> int:
    if not task["total"]:
        return 0
    return min(100, int(task["current"] * 100 / task["total"]))


def fmt_bytes(n: float) -> str:
    """Ubah jumlah byte jadi teks yang mudah dibaca, misalnya 1.2 GB."""
    if n < 1000:
        return f"{int(n)} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1000
        if n < 1000:
            return f"{n:.1f} {unit}"
    return f"{n / 1000:.1f} TB"


def fmt_time(sec: float) -> str:
    """Ubah detik jadi teks singkat, misalnya 1j 5m atau 3m 20s."""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}j {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def fmt_clock(sec: float) -> str:
    """Ubah detik jadi format jam:menit:detik, misalnya 00:05:09."""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def is_hls(url: str) -> bool:
    """Cek apakah link itu stream HLS (.m3u8)."""
    return url.split("?")[0].lower().endswith(".m3u8")

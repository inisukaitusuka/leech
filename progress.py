"""Pesan progres: teks status, tombol Refresh dan Batal, serta pembaruan otomatis."""

import logging
import time

from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from client import app
from config import BAR_WIDTH, EDIT_EVERY
from utils import fmt_clock, fmt_time, percent

log = logging.getLogger(__name__)

MAX_NAME_LEN = 50  # panjang maksimal nama file di judul status


def task_kb(tid: int) -> InlineKeyboardMarkup:
    """Tombol di bawah pesan progres: Refresh, dan Batal untuk task dengan nomor tid."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
        InlineKeyboardButton("❌ Batal", callback_data=f"cancel:{tid}"),
    ]])


def reset_task(task: dict, label: str, kind: str = "bytes") -> None:
    """Atur ulang progres task.

    kind "bytes": progres dalam byte. kind "time": progres dalam detik durasi video (HLS).
    """
    task.update(label=label, kind=kind, current=0, total=0, size=0,
                started=time.time(), last_edit=0.0)


def new_task(label: str) -> dict:
    task: dict = {}
    reset_task(task, label)
    return task


def is_upload(task: dict) -> bool:
    return task["label"].startswith("⏫")


def _bar(pct: int) -> str:
    filled = BAR_WIDTH * pct // 100
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _task_title(task: dict) -> str:
    """Judul: nomor task dan nama file, supaya tahu task mana yang mau dibatalkan."""
    title = f"#{task.get('id', '?')}"
    name = task.get("name")
    if name:
        if len(name) > MAX_NAME_LEN:
            name = name[:MAX_NAME_LEN - 3] + "..."
        title += f" • {name}"
    return title


def _render_bytes(task: dict) -> str:
    current, total = task["current"], task["total"]
    elapsed = max(time.time() - task["started"], 0.1)
    speed = current / elapsed

    if not total:
        if not current:
            return task["label"]
        return f"{task['label']}\n{current / 1e6:.1f} MB • {speed / 1e6:.1f} MB/s"

    pct = percent(task)
    lines = [
        task["label"],
        f"{_bar(pct)} {pct}%",
        f"{current / 1e6:.1f} / {total / 1e6:.1f} MB • {speed / 1e6:.1f} MB/s",
    ]
    if speed > 0 and current < total:
        lines.append(f"Sisa ±{fmt_time((total - current) / speed)}")
    return "\n".join(lines)


def _render_time(task: dict) -> str:
    done, total = task["current"], task["total"]
    elapsed = max(time.time() - task["started"], 0.1)
    lines = [task["label"]]
    if total:
        pct = percent(task)
        lines.append(f"{_bar(pct)} {pct}%")
        lines.append(f"{fmt_clock(done)} / {fmt_clock(total)}")
    else:
        lines.append(f"Durasi tidak diketahui • {fmt_clock(done)} terunduh")

    info = []
    if task["size"]:
        info.append(f"{task['size'] / 1e6:.1f} MB")
    if total and 0 < done < total:
        info.append(f"Sisa ±{fmt_time((total - done) * elapsed / done)}")
    if info:
        lines.append(" • ".join(info))
    return "\n".join(lines)


def render(task: dict) -> str:
    body = _render_time(task) if task["kind"] == "time" else _render_bytes(task)
    return f"{_task_title(task)}\n{body}"


async def push_status(task: dict, chat_id: int, msg_id: int, force: bool = False) -> None:
    """Perbarui pesan progres. Tanpa force, pembaruan dibatasi tiap EDIT_EVERY detik."""
    now = time.time()
    if not force and now - task["last_edit"] < EDIT_EVERY:
        return
    task["last_edit"] = now
    try:
        await app.edit_message_text(
            chat_id, msg_id, render(task),
            reply_markup=task_kb(task["id"]),
            parse_mode=ParseMode.DISABLED,
        )
    except MessageNotModified:
        pass  # isi pesan sama dengan sebelumnya, tidak perlu diubah
    except Exception:
        log.debug("Gagal memperbarui pesan progres", exc_info=True)


async def show_progress(current: int, total: int, status_msg, task: dict) -> None:
    """Callback progres dari Pyrogram dan httpx."""
    task["current"], task["total"] = current, total
    force = bool(total) and current >= total
    await push_status(task, status_msg.chat.id, status_msg.id, force=force)

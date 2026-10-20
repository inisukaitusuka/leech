"""Fungsi media: ffmpeg dan ffprobe, thumbnail, download stream HLS, dan kirim file ke Telegram."""

import asyncio
import contextlib
import json
import os
import subprocess

from progress import push_status, show_progress

VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".avi")
AUDIO_EXT = (".mp3", ".m4a", ".flac", ".ogg", ".wav", ".opus")
PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")


def _remove(path: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(path)


def probe_video(path: str) -> tuple[int, int, int]:
    """Ambil durasi, lebar, dan tinggi video lewat ffprobe. Kalau gagal, kembalikan nol."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", path],
            capture_output=True, text=True, check=True,
        ).stdout
        data = json.loads(out)
        stream = data["streams"][0]
        duration = int(float(data["format"]["duration"]))
        return duration, stream["width"], stream["height"]
    except Exception:
        return 0, 0, 0


def make_thumb(path: str) -> str | None:
    """Ambil satu frame sebagai thumbnail lewat ffmpeg. Kalau gagal, kembalikan None."""
    thumb = path + ".thumb.jpg"
    for seek in ("00:00:05", "00:00:00"):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", seek, "-i", path, "-frames:v", "1",
                 "-vf", "scale=320:320:force_original_aspect_ratio=decrease", thumb],
                capture_output=True, check=True,
            )
            if os.path.exists(thumb):
                return thumb
        except Exception:
            continue
    return None


def probe_duration(url: str) -> float:
    """Durasi stream dalam detik lewat ffprobe. 0 kalau tidak diketahui (misalnya live)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", url],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


async def download_hls(url: str, path: str, status_msg, task: dict) -> None:
    """Unduh stream HLS jadi satu file mp4 lewat ffmpeg tanpa re-encode.

    Progres dibaca dari output -progress ffmpeg, lalu ditampilkan di pesan status.
    """
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-loglevel", "error", "-nostats",
        "-progress", "pipe:1",
        "-i", url,
        "-c", "copy",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    err_task = asyncio.create_task(proc.stderr.read())
    try:
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            key, _, val = raw.decode(errors="ignore").strip().partition("=")
            if key == "out_time_us" and val.isdigit():
                task["current"] = int(val) / 1e6  # detik yang sudah diproses
                await push_status(task, status_msg.chat.id, status_msg.id)
            elif key == "total_size" and val.isdigit():
                task["size"] = int(val)
        await proc.wait()
    except asyncio.CancelledError:
        # task dibatalkan: matikan ffmpeg supaya tidak terus jalan di belakang
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        err_task.cancel()
        raise

    err = await err_task
    if proc.returncode != 0:
        detail = err.decode(errors="ignore").strip()[-300:]
        raise RuntimeError(detail or "ffmpeg gagal mengunduh stream")


async def _send_video(client, chat_id, path, opts, common):
    duration, width, height = await asyncio.to_thread(probe_video, path)
    thumb = await asyncio.to_thread(make_thumb, path) if opts["thumb"] else None
    try:
        return await client.send_video(
            chat_id, path,
            duration=duration,
            width=width,
            height=height,
            thumb=thumb,
            supports_streaming=True,
            **common,
        )
    finally:
        if thumb:
            _remove(thumb)


async def send_file(client, chat_id, reply_id, path, filename, opts,
                    status_msg, task, caption, parse_mode):
    """Kirim file ke chat. Dengan -med dikirim sebagai video, audio, atau foto. Selain itu, dokumen."""
    ext = os.path.splitext(filename)[1].lower()
    common = {
        "reply_to_message_id": reply_id,
        "caption": caption,
        "parse_mode": parse_mode,
        "progress": show_progress,
        "progress_args": (status_msg, task),
    }

    if opts["mode"] == "med":
        if ext in VIDEO_EXT:
            return await _send_video(client, chat_id, path, opts, common)
        if ext in AUDIO_EXT:
            return await client.send_audio(chat_id, path, **common)
        if ext in PHOTO_EXT:
            return await client.send_photo(chat_id, path, **common)

    return await client.send_document(chat_id, path, file_name=filename, **common)

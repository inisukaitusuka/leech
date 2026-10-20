"""Status runtime bot: task yang sedang berjalan dan statistik yang disimpan ke file."""

import itertools
import json
import logging
import time

from config import STATS_FILE

log = logging.getLogger(__name__)

# task aktif, kunci: (chat_id, message_id) dari pesan status -> dict state
TASKS: dict[tuple[int, int], dict] = {}

# nomor task yang tampil di /status dan /cancel, mulai dari 1 setiap bot dijalankan
TASK_IDS = itertools.count(1)

BOT_STARTED = time.time()

# statistik disimpan ke file supaya tidak hilang saat bot di-restart
STATS = {"done": 0, "failed": 0, "cancelled": 0, "downloaded": 0, "uploaded": 0}


def load_stats() -> None:
    """Muat statistik dari file. Kalau file belum ada atau rusak, mulai dari nol."""
    try:
        with open(STATS_FILE) as f:
            data = json.load(f)
        for key in STATS:
            STATS[key] = int(data.get(key, 0))
    except (OSError, ValueError, AttributeError):
        log.info("Statistik belum ada atau rusak, mulai dari nol.")


def save_stats() -> None:
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(STATS, f)
    except OSError:
        log.exception("Gagal menyimpan statistik ke %s", STATS_FILE)

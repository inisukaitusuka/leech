"""Pengaturan bot. Nilai diambil dari file .env atau environment variable."""

import os

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} belum diisi. Salin .env.example menjadi .env lalu isi nilainya.")
    return value


API_ID = int(_required("API_ID"))
API_HASH = _required("API_HASH")
BOT_TOKEN = _required("BOT_TOKEN")
OWNER_ID = int(_required("OWNER_ID"))  # hanya user ini yang boleh memakai bot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.expanduser(os.environ.get("DOWNLOAD_DIR", "~/leech"))
STATS_FILE = os.path.expanduser(
    os.environ.get("STATS_FILE", os.path.join(BASE_DIR, "leech_stats.json"))
)

CAPTION_MAX = 1024          # batas panjang caption Telegram
BAR_WIDTH = 16              # lebar bar progres, dalam karakter
EDIT_EVERY = 3              # detik, jarak minimal antar pembaruan otomatis pesan status
HTTP_CONNECT_TIMEOUT = 30   # detik, batas waktu menyambung ke server
HTTP_READ_TIMEOUT = 60      # detik, batas waktu menunggu data berikutnya

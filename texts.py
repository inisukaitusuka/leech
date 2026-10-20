"""Teks yang dikirim bot: sapaan, bantuan, dan daftar command."""

from pyrogram.types import BotCommand

USAGE = (
    "Pakai: /leech [-med|-doc] [-t] [-nc] [-mono] [-n nama] [-c teks|-sc] <link>, "
    "link pesan Telegram, atau reply file.\n"
    "Ketik /help untuk daftar lengkap."
)

START_TEXT = (
    "Halo, {name}! 👋\n"
    "Saya bot untuk leech file dari link atau pesan Telegram, lalu mengirimnya ulang ke chat ini.\n\n"
    "Ketik /help untuk melihat daftar command dan cara pakainya."
)

HELP_TEXT = (
    "<b>📖 Daftar command</b>\n\n"
    "<code>/leech</code> atau <code>/l</code> [opsi] &lt;link&gt;\n"
    "Leech file dari link atau link pesan Telegram. Bisa juga reply ke pesan yang berisi file.\n\n"
    "<code>/leech2</code> [opsi]\n"
    "Leech file atau link di pesan terdekat di atas command, atau di pesan yang di-reply.\n\n"
    "<code>/r</code>\n"
    "Reply ke sebuah pesan, bot kirim ulang pesan itu dengan label pengirim (seperti Forward).\n\n"
    "<code>/rn</code>\n"
    "Sama seperti /r tapi tanpa label pengirim (seperti Forward No Sender).\n\n"
    "<code>/status</code>\n"
    "Lihat progres task yang sedang download atau upload.\n\n"
    "<code>/cancel</code> [nomor]\n"
    "Batalkan semua task, atau satu task saja. Nomor task ada di /status.\n\n"
    "<code>/stats</code>\n"
    "Statistik bot: jumlah file, total data, dan kondisi server.\n\n"
    "<code>/start</code>\n"
    "Sapaan singkat.\n\n"
    "<code>/help</code>\n"
    "Tampilkan pesan ini.\n\n"
    "<b>Opsi</b>\n"
    "<code>-med</code> kirim sebagai video, audio, atau foto (bukan dokumen)\n"
    "<code>-doc</code> kirim sebagai dokumen (default)\n"
    "<code>-t</code> tanpa thumbnail, khusus video dengan -med\n"
    "<code>-n nama</code> ganti nama file\n"
    "<code>-c \"teks\"</code> isi caption dengan teks sendiri\n"
    "<code>-sc</code> pakai caption asli dari pesan sumber\n"
    "<code>-nc</code> tanpa caption\n"
    "<code>-mono</code> caption ditampilkan dalam format monospace"
)

BOT_COMMANDS = [
    BotCommand("start", "Sapaan dan panduan singkat"),
    BotCommand("help", "Daftar command dan cara pakai"),
    BotCommand("leech", "Leech file dari link atau reply file"),
    BotCommand("leech2", "Leech file atau link di atas command"),
    BotCommand("r", "Reply pesan untuk kirim ulang (Forward)"),
    BotCommand("rn", "Reply pesan untuk kirim ulang tanpa pengirim"),
    BotCommand("status", "Progres download dan upload"),
    BotCommand("cancel", "Batalkan task yang berjalan"),
    BotCommand("stats", "Statistik bot dan server"),
]

"""Parsing opsi command, misalnya -med, -n, dan -c. Daftar lengkapnya ada di /help."""

import shlex

from pyrogram.enums import ParseMode
from pyrogram.types import Message

from utils import URL_RE

# token yang dikenali sebagai flag, dipakai untuk menentukan batas nilai dari -n dan -c
FLAGS = {"-med", "-doc", "-t", "-nc", "-mono", "-n", "-c", "-sc"}


def parse_options(tokens: list[str]) -> dict:
    """Pisahkan flag dan argumen. Melempar ValueError kalau format opsi salah.

    Nama setelah -n diambil sampai ketemu flag lain atau link, jadi spasi di dalam nama boleh.
    """
    opts = {
        "mode": "doc",
        "thumb": True,
        "caption": True,
        "mono": False,
        "name": None,
        "custom_caption": None,
        "keep_caption": False,
        "args": [],
    }
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok == "-med":
            opts["mode"] = "med"
        elif tok == "-doc":
            opts["mode"] = "doc"
        elif tok == "-t":
            opts["thumb"] = False
        elif tok == "-nc":
            opts["caption"] = False
        elif tok == "-mono":
            opts["mono"] = True
        elif tok == "-sc":
            opts["keep_caption"] = True
        elif tok == "-n":
            parts = []
            while i < len(tokens) and tokens[i] not in FLAGS and not URL_RE.match(tokens[i]):
                parts.append(tokens[i])
                i += 1
            name = " ".join(parts)
            if not name.strip():
                raise ValueError("Setelah -n harus ada nama file.")
            opts["name"] = name
        elif tok == "-c":
            if i >= len(tokens) or tokens[i] in FLAGS:
                raise ValueError("Setelah -c harus ada teks caption.")
            opts["custom_caption"] = tokens[i]
            i += 1
        else:
            opts["args"].append(tok)

    if opts["keep_caption"] and opts["custom_caption"]:
        raise ValueError("Pakai -c atau -sc, jangan dua-duanya.")
    return opts


async def read_opts(message: Message) -> dict | None:
    """Baca opsi dari command. Kalau format salah, balas pesan error dan kembalikan None."""
    try:
        tokens = shlex.split(" ".join(message.command[1:]))
    except ValueError:
        await message.reply_text(
            "❌ Tanda kutip tidak lengkap, cek lagi teks command kamu.",
            parse_mode=ParseMode.DISABLED,
        )
        return None

    try:
        return parse_options(tokens)
    except ValueError as e:
        await message.reply_text(f"❌ {e}", parse_mode=ParseMode.DISABLED)
        return None

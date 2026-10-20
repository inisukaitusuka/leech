# Leech Bot

Bot Telegram untuk mengunduh file dari link langsung, stream HLS (`.m3u8`), atau link pesan Telegram, lalu mengirimnya ulang ke chat.

## Persiapan

- Python 3.10 atau lebih baru
- ffmpeg dan ffprobe, untuk stream HLS dan thumbnail video

```bash
sudo apt update
sudo apt install -y python3-venv ffmpeg
```

## Instalasi

1. Masuk ke folder project, lalu buat virtual environment:

   ```bash
   cd leech
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Salin `.env.example` menjadi `.env`, lalu isi nilainya:
   - `API_ID` dan `API_HASH` dari https://my.telegram.org
   - `BOT_TOKEN` dari @BotFather
   - `OWNER_ID` berisi user ID Telegram kamu. Bot hanya menjawab owner.

3. Jalankan bot:

   ```bash
   python main.py
   ```

## Command

| Command | Fungsi |
| --- | --- |
| `/leech` atau `/l` `[opsi] <link>` | Leech dari link, atau dari file yang dikirim bersama atau di-reply |
| `/leech2` `[opsi]` | Leech file atau link di pesan terdekat di atas command |
| `/r` | Reply ke pesan, bot kirim ulang pesan itu dengan label pengirim (seperti Forward) |
| `/rn` | Sama seperti `/r` tapi tanpa label pengirim (seperti Forward No Sender) |
| `/status` | Daftar task dengan tombol Refresh dan Batal |
| `/cancel` `[nomor]` | Batalkan semua task, atau satu task saja |
| `/stats` | Statistik bot dan kondisi server |
| `/help` | Daftar opsi lengkap |

## Opsi

- `-med` kirim sebagai video, audio, atau foto (bukan dokumen)
- `-doc` kirim sebagai dokumen (default)
- `-t` tanpa thumbnail, khusus video dengan `-med`
- `-n nama` ganti nama file
- `-c "teks"` isi caption dengan teks sendiri
- `-sc` pakai caption asli dari pesan sumber
- `-nc` tanpa caption
- `-mono` caption ditampilkan dalam format monospace

## Menjalankan di background (systemd)

Supaya bot tetap jalan setelah terminal ditutup dan otomatis hidup lagi setelah server restart, buat service systemd:

```bash
sudo nano /etc/systemd/system/leech.service
```

Isi dengan ini, lalu sesuaikan `WorkingDirectory`, `ExecStart`, dan `User`:

```ini
[Unit]
Description=Leech Telegram Bot
After=network-online.target

[Service]
WorkingDirectory=/home/USER/leech
ExecStart=/home/USER/leech/venv/bin/python main.py
Restart=always
User=USER

[Install]
WantedBy=multi-user.target
```

Lalu jalankan:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now leech
sudo journalctl -u leech -f    # lihat log secara live
```

## Struktur file

- `main.py`: titik masuk, daftar command ke Telegram
- `config.py`: membaca `.env`
- `client.py`: objek client Pyrogram dan filter owner
- `state.py`: task aktif dan statistik
- `texts.py`: teks bantuan dan daftar command
- `options.py`: parsing opsi seperti `-med`, `-n`, `-c`
- `utils.py`: nama file, caption, format ukuran dan waktu
- `progress.py`: pesan progres, tombol Refresh dan Batal
- `media.py`: ffmpeg, thumbnail, download HLS, kirim file
- `jobs.py`: proses utama leech
- `handlers.py`: semua command dan callback Telegram

File `.env`, `*.session`, dan `leech_stats.json` tidak ikut di-commit ke Git karena berisi data lokal. Session Telegram disimpan di `leechbot.session`.

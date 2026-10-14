# Workout Tracker — VPS edition

Aplikasi pencatat latihan gym, jalan mandiri di VPS. Tanpa dependensi
(hanya butuh Python 3, sudah bawaan Ubuntu). Data tersimpan permanen di
SQLite (`workout.db`).

Fitur: catat sesi per hari, tambah/edit/hapus set (termasuk tandai set gagal),
template program per hari latihan, riwayat sesi, grafik progres per gerakan
(beban max / reps max / volume). Mobile-friendly buat dibuka di HP pas latihan.

Isi bawaan (di-seed otomatis saat pertama jalan):
- Sesi Chest 14 Okt 2026 (data latihan hari ini)
- Template Chest, Back (program besok), Kaki, Bahu, Lengan

## Deploy di VPS (Ubuntu)

1. Upload file zip ini ke VPS lalu unzip, misal:
   ```
   scp workout-tracker-vps.zip user@VPS_IP:~
   ssh user@VPS_IP
   unzip workout-tracker-vps.zip && cd workout-tracker-vps
   ```
2. Jalankan:
   ```
   chmod +x deploy.sh && ./deploy.sh
   ```
   Script akan: copy file ke `~/workout-tracker`, membuat token login acak
   (file `.token`), memasang systemd service, dan menjalankannya.

3. Buka `http://IP_VPS:8000` di HP, login pakai token yang dicetak script.

## Perintah berguna (di VPS)

- `sudo systemctl status workout-tracker` — cek status
- `sudo journalctl -u workout-tracker -f` — lihat log
- `sudo systemctl restart workout-tracker` — restart (setelah update file)
- Token login: `cat ~/workout-tracker/.token`
- Backup data: `cp ~/workout-tracker/workout.db ~/backup/`

## Update aplikasi

Upload `app.py` / `index.html` baru ke `~/workout-tracker/`, lalu
`sudo systemctl restart workout-tracker`. Data (`workout.db`, `.token`)
tidak ikut tertimpa.

## Keamanan

API dilindungi token (Bearer). Jangan bagikan token ke orang lain.
Kalau mau diakses lewat domain + HTTPS, pasang reverse proxy (nginx/Caddy)
atau Cloudflare Tunnel di depan port 8000.

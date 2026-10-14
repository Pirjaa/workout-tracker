# Workout Tracker 🏋️

Aplikasi web statis (single-file) untuk mencatat progres gym harian. Mobile-friendly, cocok dibuka di HP saat latihan.

## Fitur

- **Latihan**: mulai sesi dari template (Chest, Back, Kaki, Bahu, Lengan) atau sesi kosong; catat set × beban (kg) × reps per gerakan
- **Riwayat**: semua sesi tersimpan dengan total volume, bisa dibuka detailnya & dihapus
- **Progress**: grafik beban maksimal & volume per sesi untuk tiap gerakan
- **Template**: ubah/tambah template & gerakan sesukamu
- Data tersimpan di `localStorage` browser — tanpa server, tanpa akun

## Pakai

Buka `index.html` di browser HP/laptop, atau deploy ke GitHub Pages:

1. Repo Settings → Pages → Deploy from branch → `main` / root
2. Buka URL yang diberikan GitHub

> Catatan: data tersimpan per browser/perangkat. Kalau ganti HP atau clear data browser, riwayat hilang — backup manual via export (segera hadir) bila perlu.

## Edisi VPS (`vps/`)

Versi server-backed: data tersimpan permanen di SQLite di server, bukan di
browser. Cocok kalau mau akses dari banyak perangkat tanpa takut data hilang.

Isi `vps/`: `app.py` (server Python, stdlib only — tanpa `pip install`),
`index.html` (UI), `workout-tracker.service` (systemd), `deploy.sh`, `README.md`.

Deploy di VPS Ubuntu:

```
git clone https://github.com/Pirjaa/workout-tracker.git ~/tracker-src
cd ~/tracker-src/vps
./deploy.sh
```

Lalu buka `http://IP_VPS:8000`, login pakai token yang dicetak script.
Detail lengkap di `vps/README.md`.

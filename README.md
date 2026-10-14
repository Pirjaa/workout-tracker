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

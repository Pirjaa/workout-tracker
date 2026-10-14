#!/bin/bash
# Deploy Workout Tracker di VPS Ubuntu. Jalankan script ini DI VPS,
# dari dalam folder hasil unzip paket (berisi app.py, index.html,
# workout-tracker.service, deploy.sh).
set -e

APP_DIR="$HOME/workout-tracker"
mkdir -p "$APP_DIR"
cp app.py index.html workout-tracker.service "$APP_DIR"/
cd "$APP_DIR"
chmod 600 app.py 2>/dev/null || true

# Token login (dibuat sekali, dipakai seterusnya)
if [ ! -f .token ]; then
  head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 32 > .token
  chmod 600 .token
fi

# Pasang systemd service
sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$USER|g" \
  workout-tracker.service | sudo tee /etc/systemd/system/workout-tracker.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now workout-tracker
sleep 2
sudo systemctl is-active --quiet workout-tracker \
  && echo "OK: service jalan" \
  || { echo "GAGAL start, cek: sudo journalctl -u workout-tracker -n 50"; exit 1; }

IP=$(hostname -I | awk '{print $1}')
echo ""
echo "==================================="
echo "Workout Tracker live di: http://$IP:8000"
echo "Token login (simpan baik-baik):"
cat .token
echo ""
echo "==================================="
echo "Perintah berguna:"
echo "  sudo systemctl status workout-tracker"
echo "  sudo journalctl -u workout-tracker -f   (lihat log)"
echo "  sudo systemctl restart workout-tracker  (setelah update file)"
